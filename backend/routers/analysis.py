"""
/api/v1/analyze  — primary analysis endpoint.
Orchestrates: compile → IR diff → UB classify → CFG → persist.
"""
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.cfg_analyzer import build_cfg_data
from core.compiler import compile_differential, get_source_snippet
from core.ir_analyzer import compare_functions, compute_unified_diff, parse_ir_functions
from core.ub_classifier import classify_all
from models.database import ScanRecord, get_session
from models.schemas import (
    FunctionDiff, ScanRequest, ScanResult, ScanSummary,
)

router = APIRouter(prefix="/api/v1", tags=["analysis"])


@router.post("/analyze", response_model=ScanResult)
async def analyze(req: ScanRequest, db: AsyncSession = Depends(get_session)):
    if len(req.source_code.encode()) > 200_000:
        raise HTTPException(413, "Source code too large (max 200 KB)")
    if req.language not in ("c", "cpp"):
        raise HTTPException(400, "language must be 'c' or 'cpp'")

    scan_id = str(uuid.uuid4())
    opt_levels = list(dict.fromkeys(["O0"] + req.opt_levels))  # O0 always included
    if req.include_o3 and "O3" not in opt_levels:
        opt_levels.append("O3")

    t_start = time.monotonic()

    # ── Differential compilation ──────────────────────────────────────────────
    diff_result = await compile_differential(
        req.source_code, req.language, req.filename, opt_levels
    )

    compile_error: Optional[str] = diff_result.global_error
    o0_ir = diff_result.get_ir("O0")
    o2_ir = diff_result.get_ir("O2")
    o3_ir = diff_result.get_ir("O3") if "O3" in opt_levels else ""

    # ── IR comparison ─────────────────────────────────────────────────────────
    ir_diffs = []
    function_diffs: list[FunctionDiff] = []
    if o0_ir and o2_ir:
        f0_all = parse_ir_functions(o0_ir)
        f2_all = parse_ir_functions(o2_ir)
        for fname in f0_all:
            if fname in f2_all:
                d = compare_functions(fname, f0_all[fname], f2_all[fname])
                ir_diffs.append(d)
                function_diffs.append(FunctionDiff(
                    name=fname,
                    o0_lines=f0_all[fname].raw.count("\n"),
                    o2_lines=f2_all[fname].raw.count("\n"),
                    o0_blocks=f0_all[fname].block_count,
                    o2_blocks=f2_all[fname].block_count,
                    changed=f0_all[fname].raw != f2_all[fname].raw,
                    bombs=0,  # updated below
                ))

    ir_diff_text = compute_unified_diff(o0_ir, o2_ir) if o0_ir and o2_ir else ""

    # ── UB classification ─────────────────────────────────────────────────────
    bombs = classify_all(ir_diffs, req.source_code, o0_ir, o2_ir)

    # Enrich source snippets
    for bomb in bombs:
        if not bomb.source_snippet and bomb.line > 0:
            bomb.source_snippet = get_source_snippet(req.source_code, bomb.line)

    # Update function_diffs bomb counts
    for fd in function_diffs:
        fd.bombs = sum(1 for b in bombs if b.func_name == fd.name)

    # ── CFG analysis ──────────────────────────────────────────────────────────
    cfg_data = None
    if o0_ir and o2_ir:
        try:
            cfg_data = build_cfg_data(o0_ir, o2_ir)
        except Exception:
            cfg_data = None

    # ── Summary ───────────────────────────────────────────────────────────────
    summary = ScanSummary(
        total_bombs=len(bombs),
        critical=sum(1 for b in bombs if b.severity == "critical"),
        high=sum(1 for b in bombs if b.severity == "high"),
        medium=sum(1 for b in bombs if b.severity == "medium"),
        low=sum(1 for b in bombs if b.severity == "low"),
        confidence_avg=round(sum(b.confidence for b in bombs) / len(bombs), 3) if bombs else 0.0,
        functions_changed=sum(1 for fd in function_diffs if fd.changed),
        blocks_eliminated=sum(
            max(0, d.o0_block_count - d.o2_block_count) for d in ir_diffs
        ),
    )

    duration_ms = int((time.monotonic() - t_start) * 1000)
    now = datetime.utcnow()

    result = ScanResult(
        id=scan_id,
        filename=req.filename,
        language=req.language,
        source_code=req.source_code,
        status="completed",
        created_at=now,
        completed_at=now,
        duration_ms=duration_ms,
        opt_levels=opt_levels,
        summary=summary,
        bombs=bombs,
        function_diffs=function_diffs,
        o0_ir=o0_ir,
        o2_ir=o2_ir,
        o3_ir=o3_ir,
        ir_diff=ir_diff_text,
        cfg=cfg_data,
        compile_error=compile_error,
        has_clang=diff_result.has_clang,
    )

    # ── Persist to DB ─────────────────────────────────────────────────────────
    record = ScanRecord(
        id=scan_id,
        filename=req.filename,
        language=req.language,
        source_code=req.source_code,
        status="completed",
        created_at=now,
        completed_at=now,
        duration_ms=duration_ms,
        opt_levels=opt_levels,
        summary_json=summary.model_dump(),
        bombs_json=[b.model_dump() for b in bombs],
        function_diffs_json=[f.model_dump() for f in function_diffs],
        o0_ir=o0_ir,
        o2_ir=o2_ir,
        o3_ir=o3_ir,
        ir_diff=ir_diff_text,
        cfg_json=cfg_data.model_dump() if cfg_data else None,
        compile_error=compile_error,
        has_clang=diff_result.has_clang,
    )
    db.add(record)
    await db.commit()

    return result
