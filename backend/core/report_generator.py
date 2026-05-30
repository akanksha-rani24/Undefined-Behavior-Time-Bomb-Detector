"""
Report generator: JSON and PDF outputs for scan results.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from models.schemas import ScanResult


def generate_json_report(result: ScanResult) -> dict:
    """Return a structured JSON-serializable report."""
    return {
        "report_type": "ub_time_bomb_analysis",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "scan": {
            "id": result.id,
            "filename": result.filename,
            "language": result.language,
            "opt_levels": result.opt_levels,
            "status": result.status,
            "created_at": result.created_at.isoformat(),
        },
        "summary": result.summary.model_dump() if result.summary else {},
        "findings": [b.model_dump() for b in result.bombs],
        "function_analysis": [f.model_dump() for f in result.function_diffs],
        "metadata": {
            "tool": "UB Time Bomb Detector",
            "version": "1.0.0",
            "clang_used": result.has_clang,
        },
    }


def generate_pdf_report(result: ScanResult, output_path: str) -> str:
    """Generate a PDF report using reportlab."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable, Preformatted,
        )

        doc = SimpleDocTemplate(output_path, pagesize=letter,
                                rightMargin=0.75*inch, leftMargin=0.75*inch,
                                topMargin=0.75*inch, bottomMargin=0.75*inch)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=20,
                                     textColor=colors.HexColor("#1a1a2e"), spaceAfter=6)
        story.append(Paragraph("UB Time Bomb Detector — Analysis Report", title_style))
        story.append(Paragraph(f"File: {result.filename}  |  Language: {result.language.upper()}  |  {result.created_at.strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
        story.append(Spacer(1, 12))

        # Summary
        if result.summary:
            s = result.summary
            story.append(Paragraph("Summary", styles["Heading2"]))
            summary_data = [
                ["Total Issues", str(s.total_bombs)],
                ["Critical", str(s.critical)],
                ["High", str(s.high)],
                ["Medium", str(s.medium)],
                ["Avg Confidence", f"{s.confidence_avg:.1%}"],
            ]
            t = Table(summary_data, colWidths=[2*inch, 2*inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8e8")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]))
            story.append(t)
            story.append(Spacer(1, 12))

        # Findings
        sev_colors = {
            "critical": colors.HexColor("#ef4444"),
            "high": colors.HexColor("#f97316"),
            "medium": colors.HexColor("#eab308"),
            "low": colors.HexColor("#22c55e"),
        }
        for i, bomb in enumerate(result.bombs, 1):
            story.append(Paragraph(f"Finding #{i}: {bomb.category_label}", styles["Heading3"]))
            meta_data = [
                ["Severity", bomb.severity.upper()],
                ["Line", str(bomb.line)],
                ["Function", bomb.func_name or "—"],
                ["CWE", bomb.cwe],
                ["Confidence", f"{bomb.confidence:.0%}"],
            ]
            t = Table(meta_data, colWidths=[1.5*inch, 5*inch])
            t.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("TEXTCOLOR", (1, 0), (1, 0), sev_colors.get(bomb.severity, colors.black)),
                ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
            ]))
            story.append(t)
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>Description:</b> {bomb.description}", styles["Normal"]))
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>At -O0:</b> {bomb.o0_behavior}", styles["Normal"]))
            story.append(Paragraph(f"<b>At -O2:</b> {bomb.o2_behavior}", styles["Normal"]))
            story.append(Spacer(1, 4))
            story.append(Paragraph(f"<b>Fix:</b> {bomb.suggestion}", styles["Normal"]))
            if bomb.source_snippet:
                story.append(Spacer(1, 4))
                story.append(Preformatted(bomb.source_snippet, styles["Code"], maxLineLength=90))
            story.append(Spacer(1, 16))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
            story.append(Spacer(1, 8))

        doc.build(story)
        return output_path
    except ImportError:
        raise RuntimeError("reportlab not installed; cannot generate PDF")
