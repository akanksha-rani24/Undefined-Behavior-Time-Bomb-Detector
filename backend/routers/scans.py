"""
Scan history endpoints: list, get, delete, export.
"""
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import REPORTS_DIR
from core.report_generator import generate_json_report, generate_pdf_report
from models.database import ScanRecord, get_session
from models.schemas import (
    GlobalStats, ScanListItem, ScanResult, ScanSummary,
)

router = APIRouter(prefix="/api/v1", tags=["scans"])


def _record_to_result(rec: ScanRecord) -> ScanResult:
    from models.schemas import (
        CFGData, FunctionDiff, ScanSummary, UBBomb,
    )
    summary = ScanSummary(**rec.summary_json) if rec.summary_json else None
    bombs = [UBBomb(**b) for b in (rec.bombs_json or [])]
    fds = [FunctionDiff(**f) for f in (rec.function_diffs_json or [])]
    cfg = CFGData(**rec.cfg_json) if rec.cfg_json else None
    return ScanResult(
        id=rec.id,
        filename=rec.filename,
        language=rec.language,
        source_code=rec.source_code,
        status=rec.status,
        created_at=rec.created_at,
        completed_at=rec.completed_at,
        duration_ms=rec.duration_ms,
        opt_levels=rec.opt_levels or [],
        summary=summary,
        bombs=bombs,
        function_diffs=fds,
        o0_ir=rec.o0_ir or "",
        o2_ir=rec.o2_ir or "",
        o3_ir=rec.o3_ir or "",
        ir_diff=rec.ir_diff or "",
        cfg=cfg,
        compile_error=rec.compile_error,
        has_clang=rec.has_clang,
    )


@router.get("/scans", response_model=list[ScanListItem])
async def list_scans(db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(ScanRecord).order_by(ScanRecord.created_at.desc()).limit(100)
    )
    records = result.scalars().all()
    return [
        ScanListItem(
            id=r.id,
            filename=r.filename,
            language=r.language,
            status=r.status,
            created_at=r.created_at,
            summary=ScanSummary(**r.summary_json) if r.summary_json else None,
        )
        for r in records
    ]


@router.get("/scans/{scan_id}", response_model=ScanResult)
async def get_scan(scan_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(ScanRecord).where(ScanRecord.id == scan_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, f"Scan {scan_id} not found")
    return _record_to_result(rec)


@router.delete("/scans/{scan_id}", status_code=204)
async def delete_scan(scan_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(ScanRecord).where(ScanRecord.id == scan_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, f"Scan {scan_id} not found")
    await db.execute(delete(ScanRecord).where(ScanRecord.id == scan_id))
    await db.commit()


@router.get("/scans/{scan_id}/export/json")
async def export_json(scan_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(ScanRecord).where(ScanRecord.id == scan_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Scan not found")
    scan = _record_to_result(rec)
    report = generate_json_report(scan)
    return JSONResponse(content=report, headers={
        "Content-Disposition": f'attachment; filename="ub_report_{scan_id[:8]}.json"'
    })


@router.get("/scans/{scan_id}/export/pdf")
async def export_pdf(scan_id: str, db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(ScanRecord).where(ScanRecord.id == scan_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(404, "Scan not found")
    scan = _record_to_result(rec)
    pdf_path = str(REPORTS_DIR / f"ub_report_{scan_id[:8]}.pdf")
    try:
        generate_pdf_report(scan, pdf_path)
        return FileResponse(pdf_path, media_type="application/pdf",
                            filename=f"ub_report_{scan_id[:8]}.pdf")
    except RuntimeError as e:
        raise HTTPException(501, str(e))


@router.get("/stats", response_model=GlobalStats)
async def get_stats(db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(ScanRecord).order_by(ScanRecord.created_at.desc())
    )
    records = result.scalars().all()

    total_bombs = 0
    crit = high = med = low = 0
    cat_dist: dict[str, int] = {}
    confidences: list[float] = []

    for r in records:
        if r.summary_json:
            s = r.summary_json
            total_bombs += s.get("total_bombs", 0)
            crit += s.get("critical", 0)
            high += s.get("high", 0)
            med += s.get("medium", 0)
            low += s.get("low", 0)
            if s.get("confidence_avg", 0) > 0:
                confidences.append(s["confidence_avg"])
        for b in r.bombs_json or []:
            cat = b.get("category", "unknown")
            cat_dist[cat] = cat_dist.get(cat, 0) + 1

    recent = records[:10]
    recent_items = [
        ScanListItem(
            id=r.id, filename=r.filename, language=r.language,
            status=r.status, created_at=r.created_at,
            summary=ScanSummary(**r.summary_json) if r.summary_json else None,
        )
        for r in recent
    ]

    return GlobalStats(
        total_scans=len(records),
        total_bombs=total_bombs,
        critical_count=crit,
        high_count=high,
        medium_count=med,
        low_count=low,
        category_distribution=cat_dist,
        recent_scans=recent_items,
        avg_confidence=round(sum(confidences) / len(confidences), 3) if confidences else 0.0,
    )
