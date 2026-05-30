"""
UB Pattern Classifier.
Maps IR structural differences and source patterns to specific UB categories
with confidence scores, CWE identifiers, and compiler optimization reasoning.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional

from core.ir_analyzer import IRDiff, IRFunction
from models.schemas import UBBomb


# ── UB Category Registry ──────────────────────────────────────────────────────

UB_CATEGORIES = {
    "signed_integer_overflow": {
        "label": "Signed Integer Overflow",
        "icon": "⚠",
        "cwe": "CWE-190",
        "cwe_url": "https://cwe.mitre.org/data/definitions/190.html",
        "reasoning": (
            "LLVM InstCombine and SimplifyCFG assume signed integer arithmetic "
            "never overflows (undefined behavior per C/C++ standard §6.5). "
            "With nsw (no signed wrap) semantics, LLVM folds comparisons like "
            "'x+1 > x' to constant 'true', and eliminates overflow-guarding "
            "branches as provably dead."
        ),
    },
    "null_pointer_dereference": {
        "label": "Null Pointer Dereference Assumption",
        "icon": "💀",
        "cwe": "CWE-476",
        "cwe_url": "https://cwe.mitre.org/data/definitions/476.html",
        "reasoning": (
            "LLVM's GVN and InstCombine pass propagate non-null information "
            "through the IR. When a pointer is dereferenced at point A, LLVM "
            "records it as non-null. Any subsequent null check (point B > A) "
            "is then classified as always-false and the guarding branch is "
            "eliminated by SimplifyCFG as dead code."
        ),
    },
    "strict_aliasing_violation": {
        "label": "Strict Aliasing Violation",
        "icon": "🔀",
        "cwe": "CWE-843",
        "cwe_url": "https://cwe.mitre.org/data/definitions/843.html",
        "reasoning": (
            "LLVM's alias analysis (TBAA — Type-Based Alias Analysis) assumes "
            "that pointers of different types cannot alias the same memory "
            "(C99 §6.5 / C++17 [basic.lval]). At -O2, LLVM reorders or "
            "eliminates loads/stores between differently-typed accesses, "
            "producing stale cached values instead of reading actual memory."
        ),
    },
    "uninitialized_variable": {
        "label": "Uninitialized Variable Use",
        "icon": "❓",
        "cwe": "CWE-457",
        "cwe_url": "https://cwe.mitre.org/data/definitions/457.html",
        "reasoning": (
            "LLVM represents uninitialized values as 'undef' (or 'poison' in "
            "newer IR). Undef propagates freely through any operation: "
            "'undef + 1' is undef, 'icmp eq undef, 0' is undef. "
            "At -O2, passes like CorrelatedValuePropagation and InstSimplify "
            "may resolve these to constants that eliminate branches, producing "
            "deterministic but wrong behavior."
        ),
    },
    "shift_overflow": {
        "label": "Shift Amount Overflow",
        "icon": "↔",
        "cwe": "CWE-190",
        "cwe_url": "https://cwe.mitre.org/data/definitions/190.html",
        "reasoning": (
            "Shifting a signed integer by an amount ≥ its bit-width, or "
            "shifting a negative value, is undefined behavior (C11 §6.5.7). "
            "LLVM marks the result as 'poison' and propagates it through "
            "dependent operations. At -O2, poison propagation enables "
            "aggressive constant folding that may delete safety checks."
        ),
    },
    "out_of_bounds_access": {
        "label": "Out-of-Bounds Access Assumption",
        "icon": "🔓",
        "cwe": "CWE-125",
        "cwe_url": "https://cwe.mitre.org/data/definitions/125.html",
        "reasoning": (
            "GEP (GetElementPointer) instructions with inbounds keyword tell "
            "LLVM that the access is within allocated memory. At -O2, LLVM "
            "assumes inbounds and may eliminate bounds checks as always-passing."
        ),
    },
    "division_by_zero": {
        "label": "Division by Zero Assumption",
        "icon": "➗",
        "cwe": "CWE-369",
        "cwe_url": "https://cwe.mitre.org/data/definitions/369.html",
        "reasoning": (
            "Integer division and modulo by zero are undefined behavior. "
            "LLVM's InstCombine may remove zero-divisor guards when it can "
            "prove through value range analysis that the divisor is non-zero "
            "due to prior UB that makes zero impossible."
        ),
    },
    "lifetime_violation": {
        "label": "Object Lifetime Violation",
        "icon": "⏱",
        "cwe": "CWE-416",
        "cwe_url": "https://cwe.mitre.org/data/definitions/416.html",
        "reasoning": (
            "Accessing an object outside its lifetime (use-after-free, "
            "dangling references) is undefined. LLVM's MemorySSA and alias "
            "analysis may cache the value from the original live access "
            "and eliminate subsequent loads that would read the dead object."
        ),
    },
    "type_punning": {
        "label": "Type Punning (Strict Aliasing Subcase)",
        "icon": "🔄",
        "cwe": "CWE-843",
        "cwe_url": "https://cwe.mitre.org/data/definitions/843.html",
        "reasoning": (
            "*(float*)&int_val accesses integer storage through a float pointer, "
            "violating strict aliasing. At -O0 the CPU reads the raw bytes. "
            "At -O2 LLVM's TBAA considers the float* and int* accesses "
            "independent and may reorder them, caching the int read in a "
            "register while presenting a stale float value."
        ),
    },
    "invalid_pointer_arithmetic": {
        "label": "Invalid Pointer Arithmetic",
        "icon": "📐",
        "cwe": "CWE-119",
        "cwe_url": "https://cwe.mitre.org/data/definitions/119.html",
        "reasoning": (
            "Pointer arithmetic beyond allocated object boundaries is UB. "
            "LLVM's GVN and SROA may eliminate bounds guards when the "
            "'inbounds' GEP semantics allow it to assume the result is valid."
        ),
    },
}

SEVERITY_MAP = {
    "critical": 0.85,  # confidence threshold for critical
    "high": 0.65,
    "medium": 0.40,
    "low": 0.0,
}


def _severity_from_confidence(confidence: float) -> str:
    for sev, threshold in SEVERITY_MAP.items():
        if confidence >= threshold:
            return sev
    return "low"


def _make_bomb(
    idx: int,
    line: int,
    col: int,
    func_name: str,
    category: str,
    confidence: float,
    description: str,
    o0_behavior: str,
    o2_behavior: str,
    suggestion: str,
    ir_evidence: str = "",
    o0_ir_snippet: str = "",
    o2_ir_snippet: str = "",
    source_snippet: str = "",
    end_line: int = 0,
) -> UBBomb:
    cat_info = UB_CATEGORIES.get(category, UB_CATEGORIES["signed_integer_overflow"])
    severity = _severity_from_confidence(confidence)
    return UBBomb(
        id=idx,
        line=line,
        col=col,
        end_line=end_line or line,
        func_name=func_name,
        category=category,
        category_label=cat_info["label"],
        category_icon=cat_info["icon"],
        severity=severity,
        confidence=round(confidence, 3),
        description=description,
        o0_behavior=o0_behavior,
        o2_behavior=o2_behavior,
        suggestion=suggestion,
        ir_evidence=ir_evidence,
        compiler_reasoning=cat_info["reasoning"],
        o0_ir_snippet=o0_ir_snippet,
        o2_ir_snippet=o2_ir_snippet,
        source_snippet=source_snippet,
        cwe=cat_info["cwe"],
        cwe_url=cat_info["cwe_url"],
    )


# ── IR-Based Detectors ────────────────────────────────────────────────────────

def detect_from_ir_diff(
    diff: IRDiff,
    source: str,
    o0_ir: str,
    o2_ir: str,
    bomb_start_idx: int = 0,
) -> List[UBBomb]:
    """Produce UBBombs from a computed IR diff for one function."""
    bombs: List[UBBomb] = []
    idx = bomb_start_idx

    from core.ir_analyzer import get_function_ir_snippet
    o0_snip = get_function_ir_snippet(o0_ir, diff.func_name)
    o2_snip = get_function_ir_snippet(o2_ir, diff.func_name)

    # ── 1. Signed Overflow (nsw added + structural change) ────────────────────
    if diff.has_nsw_added:
        elim_branches = diff.cond_branches_o0 - diff.cond_branches_o2
        elim_icmps = diff.comparisons_o0 - diff.comparisons_o2

        if diff.constant_ret_o2:
            confidence = 0.97
            const_vals = ", ".join(set(diff.constant_ret_o2))
            description = (
                f"'{diff.func_name}': Comparison folded to constant [{const_vals}]. "
                f"Optimizer added nsw (no signed wrap) and reduced conditional logic to a constant return."
            )
            ir_ev = (
                f"O0: {diff.comparisons_o0} comparison(s), {diff.cond_branches_o0} conditional branch(es)\n"
                f"O2: {diff.comparisons_o2} comparison(s), {diff.cond_branches_o2} branch(es)\n"
                f"O2 constant return(s): {const_vals}"
            )
        elif elim_branches > 0:
            confidence = 0.92
            description = (
                f"'{diff.func_name}': {elim_branches} conditional branch(es) eliminated after nsw annotation. "
                f"Optimizer proved branches are dead by assuming signed arithmetic never overflows."
            )
            ir_ev = (
                f"O0: {diff.cond_branches_o0} cond-branch(es) → O2: {diff.cond_branches_o2}\n"
                f"nsw flag absent in O0, present in O2 (added by InstCombine)"
            )
        else:
            confidence = 0.78
            description = (
                f"'{diff.func_name}': nsw (no signed wrap) flag added at -O2. "
                f"Future optimization passes may exploit this UB assumption."
            )
            ir_ev = "nsw absent in O0 IR; present in O2 IR on arithmetic instruction(s)"

        line_no = _find_ub_line_in_source(source, diff.func_name, "signed_overflow")
        bombs.append(_make_bomb(
            idx=idx, line=line_no, col=0,
            func_name=diff.func_name,
            category="signed_integer_overflow",
            confidence=confidence,
            description=description,
            o0_behavior="Signed arithmetic wraps on overflow (two's complement hardware behavior at -O0)",
            o2_behavior=(
                "InstCombine marks arithmetic with nsw; SimplifyCFG and ConstantFolding "
                "eliminate overflow-guarding branches as provably dead."
            ),
            suggestion="Use unsigned arithmetic, __builtin_add_overflow(), or -fwrapv flag",
            ir_evidence=ir_ev,
            o0_ir_snippet=o0_snip, o2_ir_snippet=o2_snip,
        ))
        idx += 1

    # ── 2. Null Pointer Check Eliminated ─────────────────────────────────────
    if diff.null_checks_o0 > diff.null_checks_o2:
        eliminated_checks = diff.null_checks_o0 - diff.null_checks_o2
        elim_blocks = diff.o0_block_count - diff.o2_block_count
        confidence = min(0.97, 0.80 + 0.05 * eliminated_checks)
        description = (
            f"'{diff.func_name}': {eliminated_checks} null pointer check(s) eliminated. "
            f"Optimizer inferred pointer is non-null from earlier dereference — "
            f"guards that look protective at -O0 vanish at -O2."
        )
        line_no = _find_ub_line_in_source(source, diff.func_name, "null_deref")
        bombs.append(_make_bomb(
            idx=idx, line=line_no, col=0,
            func_name=diff.func_name,
            category="null_pointer_dereference",
            confidence=confidence,
            description=description,
            o0_behavior="Null check executes and protects the following code path",
            o2_behavior=(
                "GVN/MemorySSA records prior dereference → marks pointer non-null → "
                f"SimplifyCFG removes {eliminated_checks} null guard(s) as dead code. "
                f"{elim_blocks} basic block(s) eliminated."
            ),
            suggestion="Move null check BEFORE any dereference; validate inputs at function entry",
            ir_evidence=(
                f"O0: {diff.null_checks_o0} null icmp(s), {diff.o0_block_count} blocks\n"
                f"O2: {diff.null_checks_o2} null icmp(s), {diff.o2_block_count} blocks\n"
                f"Eliminated: {', '.join(diff.eliminated_blocks) or '(unnamed)'}"
            ),
            o0_ir_snippet=o0_snip, o2_ir_snippet=o2_snip,
        ))
        idx += 1

    # ── 3. Dead Code Elimination (generic block removal) ─────────────────────
    elim = diff.o0_block_count - diff.o2_block_count
    if elim >= 2 and diff.null_checks_o0 == diff.null_checks_o2 and not diff.has_nsw_added:
        confidence = 0.72
        description = (
            f"'{diff.func_name}': {elim} basic block(s) eliminated by optimizer. "
            f"Branches proven unreachable via UB assumptions."
        )
        line_no = _find_ub_line_in_source(source, diff.func_name, "generic")
        bombs.append(_make_bomb(
            idx=idx, line=line_no, col=0,
            func_name=diff.func_name,
            category="signed_integer_overflow",
            confidence=confidence,
            description=description,
            o0_behavior=f"Executes through {diff.o0_block_count} basic blocks of logic",
            o2_behavior=f"Optimizer reduces to {diff.o2_block_count} blocks; UB makes {elim} block(s) unreachable",
            suggestion="Audit conditional branches for UB-based assumptions; add -fsanitize=undefined",
            ir_evidence=(
                f"O0: {diff.o0_block_count} blocks → O2: {diff.o2_block_count} blocks\n"
                f"Removed: {', '.join(diff.eliminated_blocks[:5])}"
            ),
            o0_ir_snippet=o0_snip, o2_ir_snippet=o2_snip,
        ))
        idx += 1

    # ── 4. Uninitialized Values (undef exploitation) ──────────────────────────
    if diff.has_undef_o0 and (diff.has_poison_o2 or elim >= 1):
        confidence = 0.83
        description = (
            f"'{diff.func_name}': undef value in O0 IR. "
            f"Optimizer may propagate it through comparisons, eliminating reachability."
        )
        line_no = _find_ub_line_in_source(source, diff.func_name, "uninit")
        bombs.append(_make_bomb(
            idx=idx, line=line_no, col=0,
            func_name=diff.func_name,
            category="uninitialized_variable",
            confidence=confidence,
            description=description,
            o0_behavior="Reads zero or previous stack contents — appears benign at -O0",
            o2_behavior=(
                "CorrelatedValuePropagation and InstSimplify propagate undef/poison "
                "through icmp/select instructions, potentially folding branches."
            ),
            suggestion="Initialize all variables at declaration; compile with -Wuninitialized",
            ir_evidence=(
                f"'undef' present in O0 IR; "
                f"{'poison present' if diff.has_poison_o2 else 'blocks eliminated'} in O2"
            ),
            o0_ir_snippet=o0_snip, o2_ir_snippet=o2_snip,
        ))
        idx += 1

    # ── 5. Strict Aliasing ────────────────────────────────────────────────────
    if (
        diff.load_types_o0 != diff.load_types_o2
        and len(diff.load_types_o0) >= 2
    ):
        confidence = 0.88
        description = (
            f"'{diff.func_name}': Memory accessed with incompatible pointer types. "
            f"TBAA sees these as non-aliasing; O2 may reorder/cache loads."
        )
        line_no = _find_ub_line_in_source(source, diff.func_name, "aliasing")
        bombs.append(_make_bomb(
            idx=idx, line=line_no, col=0,
            func_name=diff.func_name,
            category="strict_aliasing_violation",
            confidence=confidence,
            description=description,
            o0_behavior="Loads execute in program order; correct raw bytes read",
            o2_behavior="TBAA allows reordering/elimination of loads between incompatible types",
            suggestion="Use memcpy() for type-punning or mark with __attribute__((may_alias))",
            ir_evidence=(
                f"O0 load types: {diff.load_types_o0}\n"
                f"O2 load types: {diff.load_types_o2}"
            ),
            o0_ir_snippet=o0_snip, o2_ir_snippet=o2_snip,
        ))
        idx += 1

    return bombs


# ── Static Source-Level Detectors ─────────────────────────────────────────────

_STATIC_PATTERNS = [
    # signed overflow: x + 1 > x, x + N > x, etc.
    (
        re.compile(r'\b(\w+)\s*\+\s*\d+\s*[><=!]+\s*\1\b'),
        "signed_integer_overflow", 0.96,
        "Expression '{match}' is always-true at -O2 (optimizer assumes no signed overflow)",
        "Runtime comparison — may be false when operand equals INT_MAX",
        "Optimizer (InstCombine) folds to constant 'true' using nsw assumption",
        "Use unsigned arithmetic or __builtin_add_overflow()",
    ),
    # INT_MAX ± arithmetic
    (
        re.compile(r'\bINT_MAX\s*[\+\-]|\bINT_MIN\s*[\+\-]'),
        "signed_integer_overflow", 0.95,
        "Arithmetic on INT_MAX/INT_MIN produces signed overflow (UB)",
        "Wraps to INT_MIN/INT_MAX (two's complement hardware artifact at -O0)",
        "LLVM treats result as poison; surrounding guards eliminated",
        "Use UINT_MAX for unsigned math or check bounds before arithmetic",
    ),
    # Shift overflow
    (
        re.compile(r'1\s*<<\s*3[1-9]|1\s*<<\s*[4-9]\d|\b(\w+)\s*<<\s*3[2-9]'),
        "shift_overflow", 0.94,
        "Left-shift by ≥32 bits on 32-bit signed integer is UB",
        "x86 hardware masks shift amount; appears to produce 0 or correct result",
        "LLVM marks as poison, propagates through dependent operations",
        "Ensure shift amount < bit-width; cast to uint64_t before large shifts",
    ),
    # Type punning
    (
        re.compile(r'\*\s*\(\s*(float|double|uint\w+|int\w+|uint32_t|uint64_t)\s*\*\s*\)\s*[&(]'),
        "type_punning", 0.91,
        "Type-punning via pointer cast violates strict aliasing (C99 §6.5)",
        "Reads raw bytes correctly at -O0; cast and dereference execute in order",
        "TBAA classifies accesses as non-aliasing; load may be cached and stale",
        "Use memcpy() or a union for portable type-punning",
    ),
    # Division by zero guards that may be UB-eliminated
    (
        re.compile(r'if\s*\([^)]*\s*==\s*0\s*\)[^{]*\{[^}]*return'),
        "division_by_zero", 0.72,
        "Zero-divisor guard may be eliminated if optimizer proves it unreachable via UB",
        "Guard executes normally at -O0",
        "GVN may propagate non-zero constraint from prior division, removing guard",
        "Ensure divisor guard precedes any division operation; use assert()",
    ),
]


def detect_from_source(source: str, o0_ir: str, o2_ir: str, start_idx: int = 0) -> List[UBBomb]:
    """Pattern-match source code for common UB time bombs (provides line numbers)."""
    bombs: List[UBBomb] = []
    idx = start_idx
    lines = source.split("\n")

    # Track dereferences for null-check-after-deref
    deref_map: dict = {}  # ptr_name -> (line, col)

    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("*"):
            continue

        # ── Static patterns ────────────────────────────────────────────────
        for (pat, cat, conf, desc_tmpl, o0b, o2b, suggest) in _STATIC_PATTERNS:
            m = pat.search(raw)
            if m:
                matched_text = m.group(0)[:80]
                snippet = _get_source_snippet(lines, lineno - 1)
                cat_info = UB_CATEGORIES.get(cat, {})
                bombs.append(_make_bomb(
                    idx=idx, line=lineno, col=m.start(),
                    func_name=_guess_func_name(lines, lineno - 1),
                    category=cat, confidence=conf,
                    description=f"Line {lineno}: {desc_tmpl.format(match=matched_text)}",
                    o0_behavior=o0b, o2_behavior=o2b, suggestion=suggest,
                    ir_evidence=f"See IR diff for function containing line {lineno}",
                    source_snippet=snippet,
                ))
                idx += 1
                break

        # ── Track pointer dereferences ─────────────────────────────────────
        for dm in re.finditer(r'\b(\w+)\s*->\s*\w+|\*\s*(\w+)', raw):
            ptr = dm.group(1) or dm.group(2)
            if ptr and ptr not in ("void", "NULL", "nullptr"):
                deref_map.setdefault(ptr, (lineno, dm.start()))

        # ── Null check after dereference ───────────────────────────────────
        for nm in re.finditer(r'\b(\w+)\s*==\s*(?:NULL|nullptr|0\b)|!\s*(\w+)\b', raw):
            ptr = nm.group(1) or nm.group(2)
            if ptr and ptr in deref_map:
                deref_line, deref_col = deref_map[ptr]
                if deref_line < lineno:
                    snippet = _get_source_snippet(lines, deref_line - 1)
                    bombs.append(_make_bomb(
                        idx=idx, line=deref_line, col=deref_col,
                        func_name=_guess_func_name(lines, deref_line - 1),
                        category="null_pointer_dereference",
                        confidence=0.94,
                        description=(
                            f"Lines {deref_line}–{lineno}: '{ptr}' dereferenced at line {deref_line} "
                            f"before null check at line {lineno}. Optimizer removes the guard."
                        ),
                        o0_behavior=f"Null check at line {lineno} executes and may return early",
                        o2_behavior=(
                            f"GVN records '{ptr}' as non-null after line {deref_line} dereference; "
                            f"null guard at line {lineno} eliminated as dead code."
                        ),
                        suggestion=f"Move the null check for '{ptr}' to BEFORE line {deref_line}",
                        ir_evidence=f"null icmp eliminated; {deref_line}→{lineno} path collapsed",
                        source_snippet=snippet,
                    ))
                    idx += 1
                    del deref_map[ptr]

    # ── Uninitialized variable ─────────────────────────────────────────────
    decl_re = re.compile(
        r'^\s*(?:int|char|float|double|long|short|unsigned|size_t|ssize_t|bool)\s+(\w+)\s*;'
    )
    init_re_tmpl = r'\b{v}\s*=[^=]'
    use_re_tmpl = r'\breturn\s+{v}\b|if\s*\(\s*[^)]*\b{v}\b|while\s*\(\s*[^)]*\b{v}\b|\+\+{v}|{v}\+\+'

    declared: dict = {}
    for lineno, raw in enumerate(lines, 1):
        dm = decl_re.match(raw)
        if dm:
            declared[dm.group(1)] = lineno
        for var, decl_line in list(declared.items()):
            if lineno <= decl_line:
                continue
            if re.search(init_re_tmpl.format(v=re.escape(var)), raw) and "==" not in raw:
                del declared[var]
                continue
            if re.search(use_re_tmpl.format(v=re.escape(var)), raw):
                snippet = _get_source_snippet(lines, decl_line - 1)
                bombs.append(_make_bomb(
                    idx=idx, line=decl_line, col=0,
                    end_line=lineno,
                    func_name=_guess_func_name(lines, decl_line - 1),
                    category="uninitialized_variable",
                    confidence=0.85,
                    description=(
                        f"Line {decl_line}: '{var}' declared without initializer; "
                        f"potentially used at line {lineno}."
                    ),
                    o0_behavior="Reads zero or garbage from stack — often zero in practice at -O0",
                    o2_behavior=(
                        "LLVM represents as undef; CorrelatedValuePropagation may fold "
                        "comparisons using this value, deleting branches."
                    ),
                    suggestion=f"Initialize '{var}' at declaration (e.g., {raw.strip().rstrip(';')} = 0;)",
                    ir_evidence="undef value in O0 IR propagated to comparison/branch at O2",
                    source_snippet=snippet,
                ))
                idx += 1
                del declared[var]

    return bombs


def _get_source_snippet(lines: List[str], center: int, ctx: int = 3) -> str:
    start = max(0, center - ctx)
    end = min(len(lines), center + ctx + 1)
    result = []
    for i in range(start, end):
        marker = ">>>" if i == center else "   "
        result.append(f"{marker} {i+1:4d} | {lines[i]}")
    return "\n".join(result)


def _guess_func_name(lines: List[str], center: int) -> str:
    """Walk backwards from center to find enclosing function name."""
    func_re = re.compile(r'^\s*(?:\w[\w\s*]*\s+)+(\w+)\s*\([^)]*\)\s*\{?\s*$')
    for i in range(center, max(0, center - 40), -1):
        m = func_re.match(lines[i])
        if m and not lines[i].strip().startswith("//"):
            return m.group(1)
    return ""


def _find_ub_line_in_source(source: str, func_name: str, ub_type: str) -> int:
    """Best-effort: find the most likely source line for a UB pattern inside a function."""
    lines = source.split("\n")
    in_func = False
    brace_depth = 0

    patterns = {
        "signed_overflow": re.compile(r'\+\s*1\s*>|\bINT_MAX\s*\+|nsw|overflow'),
        "null_deref": re.compile(r'->\s*\w+|\*\s*\w+'),
        "aliasing": re.compile(r'\*\s*\(\s*(float|int|double|uint)'),
        "uninit": re.compile(r';\s*$'),
        "generic": re.compile(r'if\s*\(|while\s*\(|return\s+'),
    }
    pat = patterns.get(ub_type, patterns["generic"])

    for i, raw in enumerate(lines, 1):
        if not in_func:
            if func_name and func_name in raw and "(" in raw:
                in_func = True
                brace_depth = raw.count("{") - raw.count("}")
                continue
            elif not func_name and pat.search(raw):
                return i
        else:
            brace_depth += raw.count("{") - raw.count("}")
            if brace_depth <= 0:
                in_func = False
                continue
            if pat.search(raw):
                return i
    return 0


# ── Main Entry Point ──────────────────────────────────────────────────────────

def classify_all(
    ir_diffs: list,
    source: str,
    o0_ir: str,
    o2_ir: str,
) -> List[UBBomb]:
    """Combine IR-based and source-based detection, dedup by line+category."""
    all_bombs: List[UBBomb] = []

    # IR-based (higher confidence, missing line numbers sometimes)
    idx = 0
    for diff in ir_diffs:
        found = detect_from_ir_diff(diff, source, o0_ir, o2_ir, idx)
        all_bombs.extend(found)
        idx += len(found)

    # Static source analysis (provides line numbers)
    source_bombs = detect_from_source(source, o0_ir, o2_ir, start_idx=idx)

    # Merge: if IR bomb has no line, borrow from static; avoid duplicates
    merged_lines: set = set()
    for bomb in all_bombs:
        if bomb.line == 0:
            matching = [b for b in source_bombs if b.category == bomb.category]
            if matching:
                bomb.line = matching[0].line
                bomb.source_snippet = matching[0].source_snippet
        if (bomb.line, bomb.category) not in merged_lines:
            merged_lines.add((bomb.line, bomb.category))

    for bomb in source_bombs:
        key = (bomb.line, bomb.category)
        if key not in merged_lines:
            all_bombs.append(bomb)
            merged_lines.add(key)

    # Renumber
    for i, bomb in enumerate(all_bombs):
        bomb.id = i + 1

    # Sort by line number, then severity
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    all_bombs.sort(key=lambda b: (b.line or 9999, sev_order.get(b.severity, 9)))

    return all_bombs
