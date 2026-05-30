"""
LLVM IR comparison engine.
Parses LLVM IR text, extracts structure, and identifies optimizer-caused behavioral changes.
"""
import difflib
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# ── IR Parsing ────────────────────────────────────────────────────────────────

@dataclass
class BasicBlock:
    name: str
    instructions: List[str] = field(default_factory=list)
    terminator: str = ""
    predecessors: List[str] = field(default_factory=list)
    successors: List[str] = field(default_factory=list)


@dataclass
class IRFunction:
    name: str
    signature: str
    return_type: str
    blocks: Dict[str, BasicBlock] = field(default_factory=dict)
    attributes: List[str] = field(default_factory=list)
    raw: str = ""

    @property
    def block_count(self) -> int:
        return len(self.blocks)

    @property
    def instruction_count(self) -> int:
        return sum(len(b.instructions) for b in self.blocks.values())

    def get_all_instructions(self) -> List[str]:
        return [i for b in self.blocks.values() for i in b.instructions]


_FUNC_PATTERN = re.compile(
    r'define\s+[^@]*?@(\w+)\s*\(([^)]*)\)[^{]*\{(.*?)\n\}',
    re.DOTALL,
)
_BLOCK_LABEL = re.compile(r'^(\d+|[\w.]+):')
_BR_COND = re.compile(r'\bbr\s+i1\s+(%\w+),\s*label\s+(%\w+),\s*label\s+(%\w+)')
_BR_UNCOND = re.compile(r'\bbr\s+label\s+(%\w+)')
_RET = re.compile(r'\bret\s+(\w[\w*]*)\s*(.*)')
_ICMP = re.compile(r'(%\w+)\s*=\s*icmp\s+(\w+)\s+(\w[\w*]*)\s+(%[\w.]+|[-\d]+),\s*(%[\w.]+|[-\d]+)')
_SELECT = re.compile(r'%\w+\s*=\s*select\b')


def parse_ir_functions(ir_text: str) -> Dict[str, IRFunction]:
    """Extract all function definitions from LLVM IR text."""
    functions: Dict[str, IRFunction] = {}
    for m in _FUNC_PATTERN.finditer(ir_text):
        fname = m.group(1)
        body = m.group(3)
        ret_type = _extract_return_type(m.group(0))
        func = IRFunction(
            name=fname,
            signature=m.group(0).split("{")[0].strip(),
            return_type=ret_type,
            raw=body,
        )
        _parse_blocks(func, body)
        functions[fname] = func
    return functions


def _extract_return_type(signature: str) -> str:
    m = re.search(r'define\s+(\S+)', signature)
    return m.group(1) if m else "unknown"


def _parse_blocks(func: IRFunction, body: str) -> None:
    """Parse basic blocks from a function body."""
    lines = body.split("\n")
    current_block: Optional[BasicBlock] = BasicBlock(name="entry")
    func.blocks["entry"] = current_block

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        label_m = _BLOCK_LABEL.match(line)
        if label_m and line.endswith(":"):
            name = label_m.group(1)
            current_block = BasicBlock(name=name)
            func.blocks[name] = current_block
            continue
        if current_block is not None:
            current_block.instructions.append(line)
            # Parse terminator
            if line.startswith("ret ") or line.startswith("br ") or line.startswith("switch ") or line == "unreachable":
                current_block.terminator = line

    # Build successor edges
    for block in func.blocks.values():
        t = block.terminator
        if not t:
            continue
        m = _BR_COND.search(t)
        if m:
            block.successors = [m.group(2).lstrip("%"), m.group(3).lstrip("%")]
        else:
            m2 = _BR_UNCOND.search(t)
            if m2:
                block.successors = [m2.group(1).lstrip("%")]


# ── Comparison Utilities ──────────────────────────────────────────────────────

@dataclass
class IRDiff:
    func_name: str
    o0_block_count: int
    o2_block_count: int
    o0_instr_count: int
    o2_instr_count: int
    eliminated_blocks: List[str] = field(default_factory=list)
    added_blocks: List[str] = field(default_factory=list)
    # Structural observations
    has_nsw_added: bool = False          # O2 added nsw
    has_nuw_added: bool = False          # O2 added nuw
    has_undef_o0: bool = False           # O0 has undef values
    has_poison_o2: bool = False          # O2 uses poison
    null_checks_o0: int = 0             # icmp eq ptr null in O0
    null_checks_o2: int = 0             # icmp eq ptr null in O2
    cond_branches_o0: int = 0
    cond_branches_o2: int = 0
    comparisons_o0: int = 0
    comparisons_o2: int = 0
    constant_ret_o2: List[str] = field(default_factory=list)  # "ret i32 1" etc
    loop_back_edges_o0: int = 0
    loop_back_edges_o2: int = 0
    load_types_o0: Set[str] = field(default_factory=set)
    load_types_o2: Set[str] = field(default_factory=set)
    # Raw snippets for display
    o0_snippet: str = ""
    o2_snippet: str = ""


def compare_functions(name: str, f0: IRFunction, f2: IRFunction) -> IRDiff:
    """Compute structural diff between O0 and O2 versions of a function."""
    diff = IRDiff(
        func_name=name,
        o0_block_count=f0.block_count,
        o2_block_count=f2.block_count,
        o0_instr_count=f0.instruction_count,
        o2_instr_count=f2.instruction_count,
    )

    # Block changes
    o0_names = set(f0.blocks.keys())
    o2_names = set(f2.blocks.keys())
    diff.eliminated_blocks = list(o0_names - o2_names)
    diff.added_blocks = list(o2_names - o0_names)

    r0, r2 = f0.raw, f2.raw

    # Flag checks
    diff.has_nsw_added = bool(re.search(r'\bnsw\b', r2)) and not bool(re.search(r'\bnsw\b', r0))
    diff.has_nuw_added = bool(re.search(r'\bnuw\b', r2)) and not bool(re.search(r'\bnuw\b', r0))
    diff.has_undef_o0 = bool(re.search(r'\bundef\b', r0))
    diff.has_poison_o2 = bool(re.search(r'\bpoison\b', r2))

    # Null checks
    null_pat = re.compile(r'icmp\s+eq\s+\w[\w*]*\*?\s+%\w+,\s+null')
    diff.null_checks_o0 = len(null_pat.findall(r0))
    diff.null_checks_o2 = len(null_pat.findall(r2))

    # Conditional branches
    diff.cond_branches_o0 = len(re.findall(r'\bbr\s+i1\b', r0))
    diff.cond_branches_o2 = len(re.findall(r'\bbr\s+i1\b', r2))

    # Comparisons
    diff.comparisons_o0 = len(re.findall(r'=\s*icmp\b', r0))
    diff.comparisons_o2 = len(re.findall(r'=\s*icmp\b', r2))

    # Constant returns in O2 (sign of folding)
    diff.constant_ret_o2 = re.findall(r'ret\s+\w+\s+(?:true|false|[0-9]+)', r2)

    # Loop back-edges (simplified: look for switch or unconditional br to earlier block)
    diff.loop_back_edges_o0 = len(re.findall(r'\bbr\s+label\b', r0))
    diff.loop_back_edges_o2 = len(re.findall(r'\bbr\s+label\b', r2))

    # Load types (strict aliasing)
    diff.load_types_o0 = set(re.findall(r'load\s+(\S+),', r0))
    diff.load_types_o2 = set(re.findall(r'load\s+(\S+),', r2))

    # Snippets (first 40 lines of each for display)
    diff.o0_snippet = "\n".join(r0.split("\n")[:50])
    diff.o2_snippet = "\n".join(r2.split("\n")[:50])

    return diff


def compute_unified_diff(o0_ir: str, o2_ir: str) -> str:
    """Generate unified diff between O0 and O2 IR."""
    a = o0_ir.splitlines(keepends=True)
    b = o2_ir.splitlines(keepends=True)
    return "".join(difflib.unified_diff(a, b, fromfile="IR at -O0", tofile="IR at -O2", n=3))


def get_function_ir_snippet(ir: str, func_name: str, max_lines: int = 60) -> str:
    """Extract the IR snippet for a specific function."""
    pattern = re.compile(
        rf'define\b[^@]*@{re.escape(func_name)}\s*\([^{{]*\{{(.*?)\n\}}',
        re.DOTALL,
    )
    m = pattern.search(ir)
    if not m:
        return ""
    body = m.group(1)
    lines = body.split("\n")[:max_lines]
    return "\n".join(lines) + ("\n..." if len(body.split("\n")) > max_lines else "")
