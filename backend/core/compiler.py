"""
Differential compilation engine.
Invokes clang at multiple optimization levels and returns LLVM IR.
"""
import asyncio
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import CLANG_PATH, CLANGPP_PATH, COMPILE_TIMEOUT


@dataclass
class CompileResult:
    opt_level: str
    ir: str
    error: Optional[str] = None
    ok: bool = True


@dataclass
class DifferentialResult:
    results: Dict[str, CompileResult] = field(default_factory=dict)
    has_clang: bool = True
    language: str = "c"
    source: str = ""
    filename: str = "source.c"
    global_error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return all(r.ok for r in self.results.values())

    def get_ir(self, level: str) -> str:
        r = self.results.get(level)
        return r.ir if r and r.ok else ""


def _clang_bin(language: str) -> str:
    return CLANGPP_PATH if language == "cpp" else CLANG_PATH


def _compile_sync(src_path: str, ir_path: str, opt: str, language: str) -> Tuple[bool, str, str]:
    """Synchronously compile source to LLVM IR at given optimization level."""
    compiler = _clang_bin(language)
    cmd = [
        compiler,
        f"-{opt}",
        "-S", "-emit-llvm",
        "-fno-discard-value-names",   # keep readable variable names
        "-g",                          # debug info for source mapping
        "-Wall", "-Wno-unused",
    ]
    if language == "cpp":
        cmd += ["-std=c++17"]
    else:
        cmd += ["-std=c11"]
    cmd += ["-o", ir_path, src_path]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT,
        )
        if result.returncode != 0:
            return False, "", result.stderr.strip()
        with open(ir_path) as f:
            return True, f.read(), ""
    except subprocess.TimeoutExpired:
        return False, "", f"Compilation timed out after {COMPILE_TIMEOUT}s"
    except FileNotFoundError:
        return False, "", f"Compiler not found: {compiler}"
    except Exception as e:
        return False, "", str(e)


async def compile_differential(
    source: str,
    language: str = "c",
    filename: str = "source.c",
    opt_levels: Optional[List[str]] = None,
) -> DifferentialResult:
    """
    Compile source at each optimization level in parallel,
    returning LLVM IR for each level.
    """
    if opt_levels is None:
        opt_levels = ["O0", "O2"]

    result = DifferentialResult(language=language, source=source, filename=filename)

    # Check clang availability
    try:
        probe = subprocess.run(
            [_clang_bin(language), "--version"],
            capture_output=True, timeout=5,
        )
        result.has_clang = (probe.returncode == 0)
    except Exception:
        result.has_clang = False
        result.global_error = "clang not found — install LLVM/Clang to enable IR analysis"
        for opt in opt_levels:
            result.results[opt] = CompileResult(
                opt_level=opt, ir="", error=result.global_error, ok=False
            )
        return result

    suffix = ".c" if language == "c" else ".cpp"

    # Write source to temp file once, compile to multiple IR files
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, f"source{suffix}")
        with open(src_path, "w") as f:
            f.write(source)

        # Compile all levels (run in executor to avoid blocking the event loop)
        loop = asyncio.get_event_loop()
        tasks = []
        for opt in opt_levels:
            ir_path = os.path.join(tmpdir, f"{opt}.ll")
            tasks.append(
                loop.run_in_executor(
                    None, _compile_sync, src_path, ir_path, opt, language
                )
            )

        compile_results = await asyncio.gather(*tasks)

        for opt, (ok, ir, err) in zip(opt_levels, compile_results):
            result.results[opt] = CompileResult(
                opt_level=opt, ir=_strip_metadata_noise(ir), error=err or None, ok=ok
            )
            if not ok and not result.global_error:
                result.global_error = err

    return result


def _strip_metadata_noise(ir: str) -> str:
    """Remove verbose LLVM metadata that clutters the IR view."""
    # Keep source-location DILocation comments but strip raw metadata dumps
    lines = ir.splitlines()
    cleaned = []
    in_metadata_block = False
    for line in lines:
        stripped = line.strip()
        # Keep the main IR structure
        if stripped.startswith("!") and "=" in stripped and not stripped.startswith("!llvm"):
            # Skip verbose metadata definitions except useful ones
            if any(kw in stripped for kw in ("DIFile", "DISubprogram", "DILocation", "DIBasicType")):
                cleaned.append(line)
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def extract_source_lines(source: str) -> Dict[int, str]:
    """Return {line_number: line_text} for quick lookup."""
    return {i + 1: line for i, line in enumerate(source.splitlines())}


def get_source_snippet(source: str, line: int, context: int = 3) -> str:
    """Extract a few lines around `line` from source."""
    lines = source.splitlines()
    total = len(lines)
    start = max(0, line - 1 - context)
    end = min(total, line - 1 + context + 1)
    result = []
    for i in range(start, end):
        marker = ">>>" if i == line - 1 else "   "
        result.append(f"{marker} {i+1:4d} | {lines[i]}")
    return "\n".join(result)
