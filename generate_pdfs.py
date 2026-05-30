"""Generate two PDFs for UB Time Bomb Detector presentation."""
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Preformatted
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfgen import canvas

# ─── Color Palette ────────────────────────────────────────────────────────────
DARK_BG      = colors.HexColor("#0f172a")
CARD_BG      = colors.HexColor("#1e293b")
ACCENT_CYAN  = colors.HexColor("#06b6d4")
ACCENT_RED   = colors.HexColor("#ef4444")
ACCENT_ORANGE= colors.HexColor("#f97316")
ACCENT_YELLOW= colors.HexColor("#eab308")
ACCENT_GREEN = colors.HexColor("#22c55e")
ACCENT_PURPLE= colors.HexColor("#a855f7")
TEXT_WHITE   = colors.HexColor("#f1f5f9")
TEXT_MUTED   = colors.HexColor("#94a3b8")
CODE_BG      = colors.HexColor("#0d1117")
CODE_TEXT    = colors.HexColor("#e2e8f0")
BORDER_COLOR = colors.HexColor("#334155")

W, H = A4


# ─── Shared canvas callback for dark background pages ─────────────────────────
def dark_page(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, 0, W, H, fill=1, stroke=0)
    # footer
    canvas_obj.setFillColor(TEXT_MUTED)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.drawString(20*mm, 10*mm, "UB Time Bomb Detector  |  Presentation Material")
    canvas_obj.drawRightString(W - 20*mm, 10*mm, f"Page {doc.page}")
    canvas_obj.restoreState()


# ══════════════════════════════════════════════════════════════════════════════
#  PDF 1 — DEMO CODES
# ══════════════════════════════════════════════════════════════════════════════

DEMO_CODES = [
    {
        "title": "Demo 1 — Signed Integer Overflow (Classic)",
        "subtitle": "The most common UB time bomb. Used in CVE-2014-1838, GCC PR#30475",
        "severity": "CRITICAL",
        "color": ACCENT_RED,
        "code": """\
#include <stdio.h>
#include <limits.h>

// UB TIME BOMB: signed integer overflow
// -O0: evaluates at runtime, returns 0 when x == INT_MAX
// -O2: compiler adds 'nsw' flag, folds to constant TRUE
int overflow_check(int x) {
    return x + 1 > x;   // <- UNDEFINED BEHAVIOR when x == INT_MAX
}

int main() {
    printf("INT_MAX overflow check: %d\\n", overflow_check(INT_MAX));
    printf("Normal value check:    %d\\n", overflow_check(5));
    return 0;
}
""",
        "what_to_expect": (
            "Paste this and click Analyze. You will see 1 CRITICAL finding: "
            "'signed_integer_overflow'. The IR diff shows -O2 replaces the "
            "comparison with 'ret i32 1' (constant true). Confidence: 96%."
        ),
        "fix": "Use: return (unsigned)x + 1 > (unsigned)x;  or  __builtin_add_overflow()",
    },
    {
        "title": "Demo 2 — Null Pointer Dereference After Deref",
        "subtitle": "Mirrors Linux kernel CVE-2011-1078 pattern",
        "severity": "CRITICAL",
        "color": ACCENT_RED,
        "code": """\
#include <stdio.h>
#include <stdlib.h>

// UB TIME BOMB: null check AFTER dereference
// -O0: check works at runtime
// -O2: GVN hoists non-null fact from deref → eliminates null check as dead code
int process(int *ptr) {
    int val = *ptr;          // <- dereference here proves ptr != NULL
    if (ptr == NULL) {       // <- optimizer REMOVES this as provably false
        return -1;
    }
    return val * 2;
}

int main() {
    int x = 42;
    printf("Result: %d\\n", process(&x));
    // process(NULL) would crash at -O2 with no null-guard remaining
    return 0;
}
""",
        "what_to_expect": (
            "You will see 1 CRITICAL finding: 'null_pointer_dereference'. "
            "IR diff shows the null icmp block is eliminated. "
            "Confidence: 94%. CFG viewer shows a removed basic block."
        ),
        "fix": "Always check pointer BEFORE dereferencing it.",
    },
    {
        "title": "Demo 3 — Strict Aliasing Violation (Type Punning)",
        "subtitle": "The classic Quake III fast inverse square root bug pattern",
        "severity": "HIGH",
        "color": ACCENT_ORANGE,
        "code": """\
#include <stdio.h>

// UB TIME BOMB: strict aliasing violation via type punning
// -O0: works due to no TBAA optimization
// -O2: TBAA (Type-Based Alias Analysis) reorders/eliminates loads
// because float* and int* are assumed to never alias
float fast_inv_sqrt(float number) {
    long i;
    float x2 = number * 0.5F;
    float y  = number;

    i = *(long *)&y;           // <- UB: violates strict aliasing rule
    i = 0x5f3759df - (i >> 1); // <- famous magic constant
    y = *(float *)&i;          // <- UB: back-cast also violates aliasing
    y = y * (1.5F - (x2 * y * y));
    return y;
}

int main() {
    printf("fast_inv_sqrt(4.0) = %f\\n", fast_inv_sqrt(4.0f));
    printf("Expected ~0.5, got: %f\\n", fast_inv_sqrt(4.0f));
    return 0;
}
""",
        "what_to_expect": (
            "You will see 1 HIGH finding: 'strict_aliasing_violation'. "
            "IR diff shows TBAA metadata added at -O2 causing load reordering. "
            "Confidence: 88-91%. Use memcpy or union for safe type punning."
        ),
        "fix": "Use: memcpy(&i, &y, sizeof(i));  — safe type punning via memcpy.",
    },
    {
        "title": "Demo 4 — Uninitialized Variable (Auth Bypass)",
        "subtitle": "Pattern from CVE-2014-0977 — uninitialized status used in security decision",
        "severity": "HIGH",
        "color": ACCENT_ORANGE,
        "code": """\
#include <stdio.h>

// UB TIME BOMB: uninitialized variable used in security check
// -O0: reads whatever garbage is on the stack (usually 0)
// -O2: compiler sees undef/poison propagation, may optimize assuming
//      any value — branch outcome becomes unpredictable / always-true
int authenticate(int user_id) {
    int status;              // <- UNINITIALIZED — contains garbage!

    if (user_id == 1) {
        status = 1;          // only set for admin user
    }
    // For other users, status is NEVER initialized

    if (status == 1) {       // <- UB: may always be true at -O2
        printf("Access granted to user %d\\n", user_id);
        return 1;
    }
    printf("Access denied for user %d\\n", user_id);
    return 0;
}

int main() {
    authenticate(1);    // admin — should grant
    authenticate(99);   // regular user — should DENY but may not at -O2!
    return 0;
}
""",
        "what_to_expect": (
            "You will see 1 HIGH finding: 'uninitialized_variable'. "
            "IR shows 'undef' at -O0 becoming poison-propagated at -O2. "
            "Confidence: 85%. This is how real auth bypass vulnerabilities happen."
        ),
        "fix": "Always initialize variables: int status = 0;",
    },
    {
        "title": "Demo 5 — Multiple UB Patterns (Mixed Code)",
        "subtitle": "Realistic function combining 3 UB patterns — great for full demo",
        "severity": "CRITICAL",
        "color": ACCENT_RED,
        "code": """\
#include <stdio.h>
#include <limits.h>
#include <stdlib.h>

// CONTAINS MULTIPLE UB TIME BOMBS:
// 1. Signed overflow in size calculation
// 2. Null check after dereference
// 3. Shift amount overflow
int parse_packet(int *data, int count, int shift_by) {
    // UB #1: signed overflow if count is large
    int total = count * 4;           // can overflow if count > INT_MAX/4

    // UB #2: dereference before null check
    int first = data[0];             // deref proves data != NULL
    if (data == NULL) return -1;     // optimizer removes this guard!

    // UB #3: shift overflow (undefined if shift_by >= 32)
    int mask = 1 << shift_by;       // UB when shift_by >= 32

    printf("total=%d first=%d mask=%d\\n", total, first, mask);
    return total + first + mask;
}

int main() {
    int buf[4] = {10, 20, 30, 40};
    printf("Result: %d\\n", parse_packet(buf, 100, 5));
    return 0;
}
""",
        "what_to_expect": (
            "This gives 2-3 findings across multiple categories: "
            "signed_integer_overflow (CRITICAL), null_pointer_dereference (CRITICAL), "
            "and shift_amount_overflow (HIGH). Best demo for showing the tool's power."
        ),
        "fix": "Use safe arithmetic, check pointers first, validate shift amounts.",
    },
    {
        "title": "Demo 6 — Minimal 2-Line Time Bomb",
        "subtitle": "The simplest possible demonstration — good for opening the presentation",
        "severity": "CRITICAL",
        "color": ACCENT_PURPLE,
        "code": """\
// MINIMAL UB TIME BOMB — 2 lines of logic
// Copy this as a quick opener — audience can see the problem immediately

int always_true(int x) {
    return x + 1 > x;  // Signed overflow UB → constant true at -O2
}
""",
        "what_to_expect": (
            "The simplest input. Shows 1 CRITICAL finding immediately. "
            "IR diff is very clear: -O0 has actual comparison, "
            "-O2 shows 'ret i32 1' (hardcoded constant). "
            "Perfect for explaining the core concept in 30 seconds."
        ),
        "fix": "return (unsigned)x + 1 > (unsigned)x;",
    },
]


def build_code_pdf(out_path):
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=18*mm, bottomMargin=20*mm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MyTitle", fontName="Helvetica-Bold", fontSize=22,
        textColor=ACCENT_CYAN, spaceAfter=4, alignment=TA_CENTER
    )
    sub_style = ParagraphStyle(
        "MySub", fontName="Helvetica", fontSize=11,
        textColor=TEXT_MUTED, spaceAfter=2, alignment=TA_CENTER
    )
    h1 = ParagraphStyle(
        "H1", fontName="Helvetica-Bold", fontSize=14,
        textColor=TEXT_WHITE, spaceBefore=6, spaceAfter=2
    )
    h2 = ParagraphStyle(
        "H2", fontName="Helvetica", fontSize=10,
        textColor=TEXT_MUTED, spaceAfter=4
    )
    body = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=9,
        textColor=TEXT_WHITE, spaceAfter=4, leading=14
    )
    label = ParagraphStyle(
        "Label", fontName="Helvetica-Bold", fontSize=8,
        textColor=ACCENT_CYAN, spaceAfter=2
    )
    fix_style = ParagraphStyle(
        "Fix", fontName="Helvetica-Oblique", fontSize=9,
        textColor=ACCENT_GREEN, spaceAfter=4, leftIndent=4
    )

    story = []

    # ── Cover ──────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("💣 UB Time Bomb Detector", title_style))
    story.append(Paragraph("Demo Code Examples — Presentation Cheat Sheet", sub_style))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT_CYAN))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "This PDF contains all demo codes to paste into the Scan page during your presentation.<br/>"
        "Each demo includes: what to expect, the UB category, severity, and the fix.",
        ParagraphStyle("intro", fontName="Helvetica", fontSize=10,
                       textColor=TEXT_MUTED, alignment=TA_CENTER, leading=16)
    ))
    story.append(Spacer(1, 6*mm))

    # Quick guide table
    quick_data = [
        [Paragraph("<b>Demo</b>", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN)),
         Paragraph("<b>UB Type</b>", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN)),
         Paragraph("<b>Severity</b>", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN)),
         Paragraph("<b>Best For</b>", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN))],
        ["Demo 1", "Signed Integer Overflow", "CRITICAL", "Opening"],
        ["Demo 2", "Null Ptr After Deref",    "CRITICAL", "Show IR diff"],
        ["Demo 3", "Strict Aliasing",          "HIGH",     "Quake reference"],
        ["Demo 4", "Uninitialized Variable",   "HIGH",     "Security angle"],
        ["Demo 5", "Multiple UB Patterns",     "CRITICAL", "Full capability demo"],
        ["Demo 6", "Minimal 2-liner",          "CRITICAL", "Quick opener"],
    ]
    qt = Table(quick_data, colWidths=[25*mm, 55*mm, 30*mm, 45*mm])
    qt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CARD_BG),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#111827")),
        ("TEXTCOLOR",  (0, 1), (-1, -1), TEXT_WHITE),
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#111827"), CARD_BG]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(qt)
    story.append(PageBreak())

    # ── Instructions ───────────────────────────────────────────────────────────
    story.append(Paragraph("How to Use During Presentation", h1))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR))
    story.append(Spacer(1, 3*mm))

    steps = [
        ("Step 1", "Open your browser to http://localhost:5173 (or wherever the app is running)"),
        ("Step 2", "Click the 'Scan' tab in the left sidebar"),
        ("Step 3", "The Monaco code editor will be visible on the left side"),
        ("Step 4", "Select ALL text in the editor (Cmd+A / Ctrl+A) and DELETE it"),
        ("Step 5", "Copy the desired demo code from this PDF and paste it (Cmd+V / Ctrl+V)"),
        ("Step 6", "Ensure Language is set to 'C' and click the 'Analyze Code' button"),
        ("Step 7", "Watch the animated progress bar (Compiling → IR Analysis → Classification → CFG)"),
        ("Step 8", "Click 'View Results' when analysis completes to see the full breakdown"),
    ]

    for num, text in steps:
        row = Table(
            [[Paragraph(f"<b>{num}</b>", ParagraphStyle("sn", fontName="Helvetica-Bold",
               fontSize=9, textColor=ACCENT_CYAN)),
              Paragraph(text, body)]],
            colWidths=[18*mm, None]
        )
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(row)
        story.append(Spacer(1, 1*mm))

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "<b>Tip:</b> Start with Demo 6 (2-liner) to introduce the concept, "
        "then use Demo 5 (multi-pattern) to show the tool's full power.",
        ParagraphStyle("tip", fontName="Helvetica-Oblique", fontSize=9,
                       textColor=ACCENT_YELLOW, leading=14)
    ))
    story.append(PageBreak())

    # ── Each Demo ──────────────────────────────────────────────────────────────
    for i, demo in enumerate(DEMO_CODES):
        # Header bar
        sev_color = demo["color"]
        header_data = [[
            Paragraph(demo["title"],
                      ParagraphStyle("dh", fontName="Helvetica-Bold", fontSize=12, textColor=TEXT_WHITE)),
            Paragraph(demo["severity"],
                      ParagraphStyle("sev", fontName="Helvetica-Bold", fontSize=10,
                                     textColor=sev_color, alignment=TA_CENTER)),
        ]]
        ht = Table(header_data, colWidths=[130*mm, 30*mm])
        ht.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
            ("LEFTPADDING", (0, 0), (0, 0), 6),
            ("RIGHTPADDING", (-1, 0), (-1, 0), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BOX", (0, 0), (-1, -1), 1, sev_color),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(ht)

        story.append(Paragraph(demo["subtitle"], h2))
        story.append(Spacer(1, 2*mm))

        # Code block
        story.append(Paragraph("CODE TO PASTE:", label))
        code_pre = Preformatted(
            demo["code"],
            ParagraphStyle("code", fontName="Courier", fontSize=8,
                           textColor=CODE_TEXT, backColor=CODE_BG,
                           leading=12, leftIndent=4, rightIndent=4,
                           spaceBefore=2, spaceAfter=2)
        )
        code_table = Table([[code_pre]], colWidths=[175*mm])
        code_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(code_table)
        story.append(Spacer(1, 3*mm))

        # Expect + Fix side-by-side
        expect_cell = [
            Paragraph("WHAT TO EXPECT:", label),
            Paragraph(demo["what_to_expect"], body),
        ]
        fix_cell = [
            Paragraph("QUICK FIX:", ParagraphStyle("fl", fontName="Helvetica-Bold",
                       fontSize=8, textColor=ACCENT_GREEN, spaceAfter=2)),
            Paragraph(demo["fix"], fix_style),
        ]
        ef_table = Table([[expect_cell, fix_cell]], colWidths=[100*mm, 75*mm])
        ef_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(ef_table)

        if i < len(DEMO_CODES) - 1:
            story.append(Spacer(1, 4*mm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR))
            story.append(Spacer(1, 4*mm))

        # Page break after every 2 demos
        if (i + 1) % 2 == 0 and i < len(DEMO_CODES) - 1:
            story.append(PageBreak())

    story.append(PageBreak())

    # ── Built-in Examples reminder ─────────────────────────────────────────────
    story.append(Paragraph("Built-in Examples (Click 'Load Example' in the Scan page)", h1))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "The app also has 4 built-in examples accessible via the 'Load Example' dropdown "
        "on the Scan page. You can use these without pasting any code:",
        body
    ))
    story.append(Spacer(1, 2*mm))

    builtin = [
        [Paragraph("<b>#</b>", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN)),
         Paragraph("<b>Example Name</b>", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN)),
         Paragraph("<b>UB Pattern</b>", ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN))],
        ["1", "Signed Integer Overflow",    "x + 1 > x comparison folded to true"],
        ["2", "Null Check After Deref",     "GVN eliminates null guard"],
        ["3", "Strict Aliasing (Quake)",    "TBAA reorders float/int loads"],
        ["4", "Uninitialized Auth Bypass",  "undef propagation in security check"],
    ]
    bt = Table(builtin, colWidths=[10*mm, 70*mm, 95*mm])
    bt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CARD_BG),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#111827")),
        ("TEXTCOLOR",  (0, 1), (-1, -1), TEXT_WHITE),
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#111827"), CARD_BG]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(bt)

    doc.build(story, onFirstPage=dark_page, onLaterPages=dark_page)
    print(f"[OK] Created: {out_path}")


# ══════════════════════════════════════════════════════════════════════════════
#  PDF 2 — PROJECT UNDERSTANDING GUIDE
# ══════════════════════════════════════════════════════════════════════════════

def build_guide_pdf(out_path):
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=18*mm, bottomMargin=20*mm
    )

    styles = getSampleStyleSheet()

    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    title_s   = S("GT", fontName="Helvetica-Bold", fontSize=24, textColor=ACCENT_CYAN,
                  spaceAfter=4, alignment=TA_CENTER)
    sub_s     = S("GS", fontName="Helvetica", fontSize=12, textColor=TEXT_MUTED,
                  spaceAfter=2, alignment=TA_CENTER)
    h1_s      = S("GH1", fontName="Helvetica-Bold", fontSize=16, textColor=ACCENT_CYAN,
                  spaceBefore=8, spaceAfter=4)
    h2_s      = S("GH2", fontName="Helvetica-Bold", fontSize=12, textColor=TEXT_WHITE,
                  spaceBefore=6, spaceAfter=3)
    h3_s      = S("GH3", fontName="Helvetica-Bold", fontSize=10, textColor=ACCENT_YELLOW,
                  spaceBefore=4, spaceAfter=2)
    body_s    = S("GB", fontName="Helvetica", fontSize=9, textColor=TEXT_WHITE,
                  spaceAfter=5, leading=15, alignment=TA_JUSTIFY)
    bullet_s  = S("GBul", fontName="Helvetica", fontSize=9, textColor=TEXT_WHITE,
                  spaceAfter=3, leading=13, leftIndent=10, bulletIndent=0)
    code_s    = S("GCode", fontName="Courier", fontSize=8, textColor=CODE_TEXT,
                  backColor=CODE_BG, leading=12, leftIndent=4)
    label_s   = S("GL", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN,
                  spaceAfter=2)
    callout_s = S("GCall", fontName="Helvetica-Oblique", fontSize=9,
                  textColor=ACCENT_YELLOW, spaceAfter=4, leading=14,
                  leftIndent=8, borderPad=4)

    def hr():
        return HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR,
                          spaceAfter=4, spaceBefore=2)

    def section(title):
        return [Paragraph(title, h1_s), hr()]

    def box(content_rows, color=CARD_BG, border=BORDER_COLOR):
        t = Table([[r] for r in content_rows], colWidths=[165*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), color),
            ("BOX", (0, 0), (-1, -1), 0.5, border),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    story = []

    # ── Cover ──────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 25*mm))
    story.append(Paragraph("💣 UB Time Bomb Detector", title_s))
    story.append(Paragraph("Complete Project Understanding Guide", sub_s))
    story.append(Paragraph("For Presentation Preparation", sub_s))
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT_CYAN))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(
        "This guide explains every component, concept, and decision in the project. "
        "Read this to understand what to say during your presentation. "
        "Each section includes: what it is, how it works, and talking points.",
        S("cov", fontName="Helvetica", fontSize=10, textColor=TEXT_MUTED,
          alignment=TA_CENTER, leading=16)
    ))
    story.append(Spacer(1, 8*mm))

    # TOC
    toc_items = [
        "1. What is Undefined Behavior?",
        "2. What is a UB Time Bomb?",
        "3. Project Architecture Overview",
        "4. Backend Components",
        "5. Frontend Components",
        "6. The Analysis Pipeline (Step by Step)",
        "7. UB Categories — All 6 Types",
        "8. Tech Stack Explained",
        "9. How to Read the Results",
        "10. Presentation Talking Points",
        "11. Q&A Preparation",
    ]
    toc_data = [[Paragraph(f"<b>Table of Contents</b>",
                            S("toch", fontName="Helvetica-Bold", fontSize=10, textColor=ACCENT_CYAN))]]
    for item in toc_items:
        toc_data.append([Paragraph(f"  {item}",
                          S("toci", fontName="Helvetica", fontSize=9, textColor=TEXT_WHITE, leading=14))])
    toc_t = Table(toc_data, colWidths=[165*mm])
    toc_t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 1, ACCENT_CYAN),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(toc_t)
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 1. WHAT IS UNDEFINED BEHAVIOR
    # ─────────────────────────────────────────────────────────────────────────
    story += section("1. What is Undefined Behavior (UB)?")
    story.append(Paragraph(
        "Undefined Behavior (UB) is a concept in C and C++ where certain code constructs "
        "have no defined meaning according to the C/C++ standard. When UB occurs, the compiler "
        "is allowed to do ANYTHING — including deleting your code, reordering instructions, "
        "or making security checks vanish.", body_s
    ))
    story.append(Paragraph("Common examples of UB:", h3_s))
    ub_examples = [
        "Signed integer overflow (e.g., INT_MAX + 1)",
        "Dereferencing a NULL pointer",
        "Using an uninitialized variable",
        "Reading/writing out of array bounds",
        "Shifting an integer by >= its bit width",
        "Accessing memory through incompatible pointer types (strict aliasing)",
    ]
    for ex in ub_examples:
        story.append(Paragraph(f"• {ex}", bullet_s))
    story.append(Spacer(1, 3*mm))
    story.append(box([
        Paragraph("Key Insight for Presentation", S("ki", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_YELLOW)),
        Paragraph(
            "The C standard says these behaviors are 'undefined' — not 'crash' or 'wrong answer'. "
            "The compiler can literally assume these never happen and optimize accordingly. "
            "This is what makes them dangerous time bombs.",
            S("kib", fontName="Helvetica", fontSize=9, textColor=TEXT_WHITE, leading=14)
        )
    ], color=colors.HexColor("#1c1917"), border=ACCENT_YELLOW))
    story.append(Spacer(1, 4*mm))

    # ─────────────────────────────────────────────────────────────────────────
    # 2. WHAT IS A UB TIME BOMB
    # ─────────────────────────────────────────────────────────────────────────
    story += section("2. What is a UB Time Bomb?")
    story.append(Paragraph(
        "A UB time bomb is code that appears to work correctly at low optimization levels "
        "(-O0, no optimizations) but silently breaks at high optimization levels (-O2 or -O3). "
        "This is the most dangerous kind of bug because:", body_s
    ))
    dangers = [
        "It passes all unit tests (tests usually run at -O0 or -O1)",
        "It works in debug builds but fails in production (production uses -O2)",
        "The bug is invisible — the source code looks fine",
        "The compiler isn't breaking anything — it's following the C standard",
        "These have caused real-world security vulnerabilities (Linux kernel, OpenSSL, etc.)",
    ]
    for d in dangers:
        story.append(Paragraph(f"• {d}", bullet_s))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("Classic Example:", h3_s))
    story.append(Preformatted(
        "int f(int x) { return x + 1 > x; }\n"
        "\n"
        "// At -O0: actually compares x+1 vs x at runtime\n"
        "//         returns 0 when x == INT_MAX (correct!)\n"
        "// At -O2: compiler adds 'nsw' (no signed wrap) flag\n"
        "//         assumes overflow never happens → folds to constant TRUE\n"
        "//         always returns 1, even for INT_MAX (WRONG!)",
        code_s
    ))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        "The compiler is not buggy. It is correctly applying the C standard rule that "
        "signed integer overflow is undefined behavior, so it assumes it never happens. "
        "Your code has the bug.", callout_s
    ))
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 3. ARCHITECTURE
    # ─────────────────────────────────────────────────────────────────────────
    story += section("3. Project Architecture Overview")
    story.append(Paragraph(
        "The project is a full-stack web application with a Python backend and a React frontend. "
        "Here is the high-level architecture:", body_s
    ))

    arch_data = [
        [Paragraph("<b>Layer</b>", S("ah", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN)),
         Paragraph("<b>Technology</b>", S("ah", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN)),
         Paragraph("<b>Purpose</b>", S("ah", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN))],
        ["User Browser", "React 18 + Vite",       "Interactive UI: code editor, charts, results"],
        ["HTTP API",     "FastAPI + Python",       "REST endpoints for analysis and data"],
        ["Analysis",     "clang/LLVM",             "Compile C/C++ code, emit LLVM IR"],
        ["IR Parsing",   "Python regex/parser",    "Extract functions, detect nsw/undef/null flags"],
        ["Classification","Rule-based classifier", "Match IR patterns to UB categories"],
        ["CFG Analysis", "NetworkX (Python)",      "Build control flow graphs, find eliminated blocks"],
        ["Storage",      "SQLite + SQLAlchemy",    "Persist scan history, results"],
        ["Reports",      "reportlab",              "Export PDF/JSON reports"],
    ]
    at = Table(arch_data, colWidths=[38*mm, 45*mm, 82*mm])
    at.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), CARD_BG),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#111827")),
        ("TEXTCOLOR",  (0, 1), (-1, -1), TEXT_WHITE),
        ("FONTNAME",   (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#111827"), CARD_BG]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(at)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("Directory Structure:", h3_s))
    story.append(Preformatted(
        "ub-detector/\n"
        "├── backend/                 ← Python FastAPI server\n"
        "│   ├── main.py              ← App entry, CORS, DB init\n"
        "│   ├── config.py            ← Settings (clang path, DB URL)\n"
        "│   ├── core/\n"
        "│   │   ├── compiler.py      ← Calls clang, gets IR output\n"
        "│   │   ├── ir_analyzer.py   ← Parses LLVM IR, finds differences\n"
        "│   │   ├── ub_classifier.py ← Maps IR diffs to UB categories\n"
        "│   │   ├── cfg_analyzer.py  ← Builds CFG with NetworkX\n"
        "│   │   └── report_generator.py ← PDF/JSON exports\n"
        "│   ├── models/\n"
        "│   │   ├── database.py      ← SQLAlchemy DB model\n"
        "│   │   └── schemas.py       ← Pydantic data types\n"
        "│   └── routers/\n"
        "│       ├── analysis.py      ← POST /api/v1/analyze\n"
        "│       ├── scans.py         ← GET/DELETE scan history\n"
        "│       └── evaluation.py    ← Benchmark evaluation\n"
        "├── frontend/                ← React 18 + TypeScript\n"
        "│   └── src/\n"
        "│       ├── pages/           ← Dashboard, Scan, Results...\n"
        "│       └── components/      ← BombCard, IRDiffViewer, CFGViewer\n"
        "└── datasets/\n"
        "    ├── real_world/          ← 5 CVE-based test files\n"
        "    └── evaluation/          ← Ground truth JSON",
        code_s
    ))
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 4. BACKEND COMPONENTS
    # ─────────────────────────────────────────────────────────────────────────
    story += section("4. Backend Components — Explained")

    backend_components = [
        {
            "file": "main.py",
            "title": "Application Entry Point",
            "what": (
                "This is where the FastAPI application is created. It sets up CORS (allowing "
                "the frontend to talk to the backend from a different port), initializes the "
                "SQLite database on startup, and registers the API routers."
            ),
            "say": "Think of main.py as the front door of the backend — it handles startup and routing.",
        },
        {
            "file": "core/compiler.py",
            "title": "Differential Compilation Engine",
            "what": (
                "This file takes the user's C/C++ source code and compiles it TWICE using clang: "
                "once with -O0 (no optimizations) and once with -O2 (full optimizations). "
                "Each compilation produces LLVM IR (Intermediate Representation) — a human-readable "
                "assembly-like format. The IR is saved and passed to the analyzer."
            ),
            "say": (
                "The key idea: we compile the SAME code at two optimization levels and compare "
                "what the compiler produced. If they differ in suspicious ways, there's UB."
            ),
        },
        {
            "file": "core/ir_analyzer.py",
            "title": "LLVM IR Parser and Differ",
            "what": (
                "Parses the two IR files (O0 and O2) using regex to extract functions. "
                "For each function, it compares: presence of 'nsw' flags (no signed wrap), "
                "presence of 'undef' or 'poison' values, null comparison instructions, "
                "block count changes (eliminated branches), and TBAA metadata (aliasing info). "
                "Returns an IRDiff object summarizing all differences found."
            ),
            "say": (
                "This is the heart of the detection. We look for specific LLVM IR markers "
                "that indicate the compiler exploited UB assumptions during optimization."
            ),
        },
        {
            "file": "core/ub_classifier.py",
            "title": "UB Pattern Classifier",
            "what": (
                "Takes the IRDiff and source code, then applies rules to determine which UB "
                "category is present. Has two detection modes: IR-based (checks nsw flags, "
                "undef values, block elimination, TBAA metadata) and source-based "
                "(regex patterns looking for suspicious C constructs like 'x+1>x', "
                "NULL dereferences, uninitialized vars, etc.). Assigns confidence scores "
                "and severity levels (critical/high/medium/low)."
            ),
            "say": (
                "The classifier is like a security analyst reading the compiler's output. "
                "It knows what each suspicious IR pattern means in terms of real UB."
            ),
        },
        {
            "file": "core/cfg_analyzer.py",
            "title": "Control Flow Graph Builder",
            "what": (
                "Builds a Control Flow Graph (CFG) from the LLVM IR using NetworkX. "
                "A CFG is a graph where each node is a basic block (a sequence of instructions "
                "with no branches) and edges represent possible execution paths. "
                "Compares the O0 and O2 CFGs to find blocks that were eliminated — these "
                "eliminated blocks often represent dead code branches that the compiler "
                "removed because it proved they were unreachable (due to UB assumptions)."
            ),
            "say": (
                "The CFG visualizer shows you visually which branches the optimizer deleted. "
                "Red dashed nodes = code that existed at -O0 but was eliminated at -O2."
            ),
        },
        {
            "file": "models/schemas.py",
            "title": "Data Models (Pydantic)",
            "what": (
                "Defines all the data structures used in the API: UBBomb (a single finding), "
                "ScanResult (all findings for one analysis), ScanSummary (for listing history), "
                "FunctionDiff (IR comparison for one function), CFGData (graph structure). "
                "Pydantic validates all data automatically — if the backend returns wrong types, "
                "it raises an error immediately."
            ),
            "say": "Think of schemas.py as the contract between backend and frontend.",
        },
        {
            "file": "routers/analysis.py",
            "title": "Main API Endpoint",
            "what": (
                "Handles POST /api/v1/analyze — the most important endpoint. "
                "Orchestrates the full pipeline: receives code → compile → parse IR → "
                "diff IR → classify UB → build CFG → save to database → return results. "
                "All steps run asynchronously for performance."
            ),
            "say": "This is the endpoint the frontend calls when you click 'Analyze Code'.",
        },
    ]

    for comp in backend_components:
        story.append(Paragraph(f"{comp['file']} — {comp['title']}", h2_s))
        story.append(Paragraph(comp["what"], body_s))
        story.append(box([
            Paragraph("What to say:", S("ws", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_GREEN)),
            Paragraph(comp["say"], S("wsb", fontName="Helvetica-Oblique", fontSize=9,
                                     textColor=TEXT_WHITE, leading=13)),
        ], color=colors.HexColor("#052e16"), border=ACCENT_GREEN))
        story.append(Spacer(1, 3*mm))

    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 5. FRONTEND COMPONENTS
    # ─────────────────────────────────────────────────────────────────────────
    story += section("5. Frontend Components — Explained")

    frontend_pages = [
        {
            "file": "pages/Dashboard.tsx",
            "title": "Dashboard Page",
            "what": (
                "Shows overall statistics from all past scans: total scans, total bombs found, "
                "most common UB type, average confidence. Displays a pie chart of UB categories "
                "and a bar chart showing severity distribution. Lists recent scans for quick access."
            ),
            "say": "The Dashboard is the home screen — shows the big picture of what the tool has found.",
        },
        {
            "file": "pages/Scan.tsx",
            "title": "Scan Page (Code Editor)",
            "what": (
                "The main input page. Features a Monaco Editor (same editor as VS Code) for "
                "writing or pasting C/C++ code. Supports: drag & drop of .c/.cpp files, "
                "load built-in example snippets, select language (C/C++), select optimization "
                "level (O0/O1/O2/O3). Shows an animated progress bar with 4 phases while "
                "the backend runs the analysis."
            ),
            "say": "The Scan page is where the magic happens. Monaco gives us VS Code-quality editing.",
        },
        {
            "file": "pages/Results.tsx",
            "title": "Results Page",
            "what": (
                "Displays analysis results in a split layout: left panel shows the source "
                "code with colored gutter markers highlighting affected lines "
                "(red=critical, orange=high, yellow=medium), right panel shows the list "
                "of UB findings as BombCards. Tabs at the bottom show the IR diff viewer "
                "and CFG visualization."
            ),
            "say": "The Results page is the most complex UI — it visualizes exactly where and why each UB bomb was found.",
        },
        {
            "file": "pages/Evaluation.tsx",
            "title": "Evaluation / Benchmark Page",
            "what": (
                "Runs the tool against 5 known real-world UB cases (based on actual CVEs) "
                "and compares results against expected ground truth. Shows precision, recall, "
                "and F1 score for each UB category. Displays a confusion matrix. "
                "This proves the tool actually works correctly."
            ),
            "say": "The Evaluation page shows scientific validation — these are real CVEs with known expected answers.",
        },
        {
            "file": "components/BombCard.tsx",
            "title": "Bomb Card Component",
            "what": (
                "Each UB finding is displayed as an expandable card. Shows: UB type, severity, "
                "confidence percentage, line number, CWE reference. When expanded: O0 behavior "
                "(what happens without optimizations), O2 behavior (what the optimizer does), "
                "IR evidence (actual LLVM IR code), compiler reasoning (which LLVM pass did it), "
                "and the suggested fix."
            ),
            "say": "The BombCard is the main output — every piece of info needed to understand and fix the bug.",
        },
        {
            "file": "components/IRDiffViewer.tsx",
            "title": "IR Diff Viewer",
            "what": (
                "Shows three tabs: the diff between O0 and O2 IR (added/removed lines), "
                "the full O0 IR, and the full O2 IR. Lines added in O2 are highlighted "
                "green, lines removed are highlighted red. This lets you see exactly "
                "what the compiler changed."
            ),
            "say": "The IRDiffViewer shows the exact LLVM IR changes — this is the evidence for the UB detection.",
        },
        {
            "file": "components/CFGViewer.tsx",
            "title": "Control Flow Graph Viewer",
            "what": (
                "Renders the control flow graph as an interactive SVG. Each basic block is "
                "a node (rectangle), edges are arrows representing jumps/branches. "
                "Nodes that exist at O0 but are eliminated at O2 are shown with a red dashed "
                "border — these are the dead branches the compiler removed because of UB."
            ),
            "say": "The CFG viewer makes the abstract concept visual — you can literally see which code paths were deleted.",
        },
    ]

    for comp in frontend_pages:
        story.append(Paragraph(f"{comp['file']} — {comp['title']}", h2_s))
        story.append(Paragraph(comp["what"], body_s))
        story.append(box([
            Paragraph("What to say:", S("ws2", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_GREEN)),
            Paragraph(comp["say"], S("wsb2", fontName="Helvetica-Oblique", fontSize=9,
                                     textColor=TEXT_WHITE, leading=13)),
        ], color=colors.HexColor("#052e16"), border=ACCENT_GREEN))
        story.append(Spacer(1, 3*mm))

    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 6. ANALYSIS PIPELINE
    # ─────────────────────────────────────────────────────────────────────────
    story += section("6. The Analysis Pipeline — Step by Step")
    story.append(Paragraph(
        "When you click 'Analyze Code', here is exactly what happens:", body_s
    ))

    pipeline_steps = [
        ("Step 1: Code Submission",
         "The frontend sends the C/C++ source code to POST /api/v1/analyze via HTTP.",
         "The Monaco editor content is sent as a JSON request body."),
        ("Step 2: Differential Compilation",
         "The backend writes the code to a temp file, then calls clang TWICE:\n"
         "  clang -O0 -S -emit-llvm code.c -o code_O0.ll\n"
         "  clang -O2 -S -emit-llvm code.c -o code_O2.ll\n"
         "This produces two LLVM IR files.",
         "LLVM IR is like assembly but at a higher level. It's what all LLVM-based compilers "
         "(clang, rustc, etc.) use internally."),
        ("Step 3: IR Parsing",
         "The ir_analyzer.py reads both .ll files and extracts:\n"
         "  • Function definitions (by name)\n"
         "  • Instructions inside each function\n"
         "  • Flags: nsw, nuw, undef, poison, TBAA metadata\n"
         "  • Basic block count (how many branches exist)",
         "We parse the text of the IR with regex — no LLVM Python bindings needed."),
        ("Step 4: IR Diffing",
         "For each function present in both O0 and O2, we compare:\n"
         "  • Did nsw (no signed wrap) flags appear? → possible signed overflow UB\n"
         "  • Did 'undef' values appear? → uninitialized variable UB\n"
         "  • Did null comparison icmps disappear? → null check eliminated\n"
         "  • Did block count decrease? → branches eliminated\n"
         "  • Did TBAA metadata appear? → strict aliasing UB",
         "Each difference is a clue. Multiple clues = higher confidence."),
        ("Step 5: UB Classification",
         "The classifier maps IR diffs + source patterns to UB categories:\n"
         "  • nsw added AND block eliminated → signed_integer_overflow\n"
         "  • null icmp removed AND deref present → null_pointer_dereference\n"
         "  • TBAA metadata added → strict_aliasing_violation\n"
         "  • undef present → uninitialized_variable\n"
         "  • poison in shift → shift_amount_overflow\n"
         "Assigns confidence (0.0-1.0) and severity (critical/high/medium/low).",
         "Confidence is based on how many matching signals we found."),
        ("Step 6: CFG Analysis",
         "NetworkX builds a directed graph from the IR's branch structure.\n"
         "We compare the O0 CFG vs O2 CFG node-by-node.\n"
         "Missing nodes in O2 = 'eliminated blocks' = code the optimizer removed.",
         "This is the visual proof that the optimizer changed control flow."),
        ("Step 7: Results Saved & Returned",
         "The full result (all findings, IR text, CFG data) is saved to SQLite "
         "via SQLAlchemy async. The JSON response is returned to the frontend.",
         "Saving to DB enables the scan history and statistics features."),
        ("Step 8: Frontend Renders Results",
         "The frontend receives the JSON, navigates to the Results page, "
         "and renders BombCards, IR diff, and CFG visualization.",
         "Monaco editor adds gutter decorations (colored squares) on affected lines."),
    ]

    for i, (step, detail, note) in enumerate(pipeline_steps):
        num_cell = Paragraph(f"<b>{i+1}</b>",
                             S("pn", fontName="Helvetica-Bold", fontSize=14,
                               textColor=ACCENT_CYAN, alignment=TA_CENTER))
        content_cells = [
            Paragraph(step, h3_s),
            Preformatted(detail, S("pd", fontName="Courier", fontSize=7.5,
                                   textColor=CODE_TEXT, leading=11)) if "\n" in detail
            else Paragraph(detail, body_s),
            Paragraph(f"Note: {note}", callout_s),
        ]
        row_t = Table([[num_cell, content_cells]], colWidths=[12*mm, 153*mm])
        row_t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(row_t)
        story.append(HRFlowable(width="100%", thickness=0.3, color=BORDER_COLOR,
                                spaceBefore=3, spaceAfter=3))

    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 7. UB CATEGORIES
    # ─────────────────────────────────────────────────────────────────────────
    story += section("7. UB Categories — All 6 Detected Types")

    ub_cats = [
        {
            "name": "signed_integer_overflow",
            "cwe": "CWE-190",
            "confidence": "96%",
            "severity": "CRITICAL",
            "color": ACCENT_RED,
            "llvm_mechanism": "InstCombine adds nsw flag → SimplifyCFG eliminates overflow-guarding branches",
            "example": "x + 1 > x  (INT_MAX case)",
            "real_world": "GCC PR#30475, Linux kernel overflow checks",
            "o0": "Actual runtime comparison — can return false for INT_MAX",
            "o2": "Folds to constant TRUE — overflow check always passes",
            "explain": (
                "When you add two signed integers, C says overflow is UB. LLVM uses this "
                "to add 'nsw' (no signed wrap) to arithmetic operations. Then SimplifyCFG "
                "sees the overflow-checking branch and removes it as 'provably dead'."
            ),
        },
        {
            "name": "null_pointer_dereference",
            "cwe": "CWE-476",
            "confidence": "94%",
            "severity": "CRITICAL",
            "color": ACCENT_RED,
            "llvm_mechanism": "GVN (Global Value Numbering) hoists non-null fact from deref to eliminate null icmp",
            "example": "int val = *ptr; if (ptr == NULL) return -1;",
            "real_world": "Linux CVE-2011-1078",
            "o0": "Null check works at runtime (though it's logically too late)",
            "o2": "GVN proves ptr != NULL (because it was dereferenced) → removes the if-block",
            "explain": (
                "If you dereference a pointer on line 5 and check if it's null on line 7, "
                "LLVM's GVN pass says: 'If we got to line 7, line 5 didn't crash, so ptr "
                "was not null.' The null check on line 7 is then eliminated as dead code."
            ),
        },
        {
            "name": "strict_aliasing_violation",
            "cwe": "CWE-843",
            "confidence": "88-91%",
            "severity": "HIGH",
            "color": ACCENT_ORANGE,
            "llvm_mechanism": "TBAA metadata causes loads/stores through different pointer types to be reordered",
            "example": "*(int*)&float_var  (Quake fast inverse sqrt)",
            "real_world": "Quake III Arena, OpenSSL",
            "o0": "Memory reads happen in source order — type pun 'works'",
            "o2": "TBAA says float* and int* cannot alias → reorders or eliminates loads",
            "explain": (
                "The C standard says pointers of different types cannot point to the same "
                "memory (with few exceptions). LLVM uses this (called TBAA = Type-Based "
                "Alias Analysis) to reorder memory operations for performance. "
                "If you cast float* to int* and read it, TBAA may decide those are "
                "independent and reorder the reads."
            ),
        },
        {
            "name": "uninitialized_variable",
            "cwe": "CWE-457",
            "confidence": "85%",
            "severity": "HIGH",
            "color": ACCENT_ORANGE,
            "llvm_mechanism": "undef/poison values propagate through operations — optimizer assumes any value",
            "example": "int status; if (user_id == 1) status = 1; if (status == 1) grant();",
            "real_world": "CVE-2014-0977, many auth bypass vulnerabilities",
            "o0": "Reads stack garbage — usually 0 (often appears to deny access)",
            "o2": "undef propagation: optimizer may make branch always-true",
            "explain": (
                "LLVM represents uninitialized variables as 'undef'. Any operation on undef "
                "is itself undef. The optimizer can choose ANY concrete value for undef "
                "that makes the code 'optimal' — which might mean always taking the "
                "'access granted' branch."
            ),
        },
        {
            "name": "shift_amount_overflow",
            "cwe": "CWE-190",
            "confidence": "94%",
            "severity": "HIGH",
            "color": ACCENT_ORANGE,
            "llvm_mechanism": "Shift by >= bit-width becomes poison → CorrelatedValuePropagation propagates",
            "example": "1 << shift_by  (where shift_by >= 32)",
            "real_world": "Common in bit manipulation code",
            "o0": "Hardware typically masks shift amount — may still return wrong value",
            "o2": "Poison value propagates, expression may be eliminated entirely",
            "explain": (
                "C says shifting by >= the bit width of the type is undefined behavior. "
                "LLVM marks this as 'poison' — a value that contaminates everything that "
                "depends on it. This can cause entire expressions to be deleted."
            ),
        },
        {
            "name": "out_of_bounds_access",
            "cwe": "CWE-125",
            "confidence": "72%",
            "severity": "MEDIUM",
            "color": ACCENT_YELLOW,
            "llvm_mechanism": "inbounds GEP (GetElementPointer) assumption enables alias analysis to eliminate checks",
            "example": "arr[i] where i may exceed array size",
            "real_world": "Buffer overflows, many CVEs",
            "o0": "May or may not crash depending on memory layout",
            "o2": "inbounds assumption allows optimizer to remove bounds-related guards",
            "explain": (
                "LLVM's GEP (GetElementPointer) instruction has an 'inbounds' flag. "
                "When the optimizer adds this flag (assuming your index is valid), "
                "it can then use alias analysis to eliminate related safety checks."
            ),
        },
    ]

    for cat in ub_cats:
        story.append(Paragraph(
            f"{cat['name']}",
            S("catn", fontName="Helvetica-Bold", fontSize=11, textColor=cat["color"],
              spaceBefore=4, spaceAfter=2)
        ))
        row1 = [
            [Paragraph(f"CWE: {cat['cwe']}", S("cw", fontName="Helvetica", fontSize=8, textColor=TEXT_MUTED)),
             Paragraph(f"Confidence: {cat['confidence']}", S("cf", fontName="Helvetica", fontSize=8, textColor=TEXT_MUTED)),
             Paragraph(f"Severity: {cat['severity']}", S("sv", fontName="Helvetica-Bold", fontSize=8, textColor=cat["color"]))],
        ]
        meta_t = Table(row1, colWidths=[40*mm, 45*mm, 45*mm])
        meta_t.setStyle(TableStyle([("LEFTPADDING", (0,0),(-1,-1), 0)]))
        story.append(meta_t)

        story.append(Paragraph(cat["explain"], body_s))

        detail_data = [
            [Paragraph("<b>-O0 behavior:</b>", S("dl", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_GREEN)),
             Paragraph(cat["o0"], S("dv", fontName="Helvetica", fontSize=8, textColor=TEXT_WHITE, leading=12))],
            [Paragraph("<b>-O2 behavior:</b>", S("dl2", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_RED)),
             Paragraph(cat["o2"], S("dv2", fontName="Helvetica", fontSize=8, textColor=TEXT_WHITE, leading=12))],
            [Paragraph("<b>LLVM mechanism:</b>", S("dl3", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN)),
             Paragraph(cat["llvm_mechanism"], S("dv3", fontName="Helvetica", fontSize=8, textColor=TEXT_WHITE, leading=12))],
            [Paragraph("<b>Real-world:</b>", S("dl4", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_YELLOW)),
             Paragraph(cat["real_world"], S("dv4", fontName="Helvetica", fontSize=8, textColor=TEXT_WHITE, leading=12))],
        ]
        dt = Table(detail_data, colWidths=[30*mm, 135*mm])
        dt.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), CARD_BG),
            ("BOX", (0,0), (-1,-1), 0.5, BORDER_COLOR),
            ("TOPPADDING", (0,0),(-1,-1), 3),
            ("BOTTOMPADDING", (0,0),(-1,-1), 3),
            ("LEFTPADDING", (0,0),(-1,-1), 6),
            ("VALIGN", (0,0),(-1,-1), "TOP"),
        ]))
        story.append(dt)
        story.append(Spacer(1, 4*mm))

    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 8. TECH STACK
    # ─────────────────────────────────────────────────────────────────────────
    story += section("8. Tech Stack — Why Each Technology Was Chosen")

    tech = [
        ("FastAPI", "Python", "High-performance async REST framework. Auto-generates Swagger docs. Perfect for IO-heavy analysis tasks."),
        ("SQLAlchemy + SQLite", "Python", "Async ORM for scan history persistence. SQLite = zero config, file-based DB, great for local tools."),
        ("Pydantic v2", "Python", "Data validation and serialization. Ensures API responses always have correct types."),
        ("networkx", "Python", "Graph analysis library for building and comparing CFGs. Simple API, no external deps."),
        ("reportlab", "Python", "PDF generation. Used for exporting analysis reports as formatted PDFs."),
        ("React 18", "TypeScript", "Component-based UI framework. Hooks + concurrent mode for smooth interactions."),
        ("Vite", "TypeScript", "Ultra-fast development build tool. Hot module replacement for instant feedback."),
        ("TypeScript", "Language", "Static typing catches bugs at compile time. IDE autocomplete for API response shapes."),
        ("Tailwind CSS", "CSS", "Utility-first CSS. Enables rapid dark-theme UI without writing custom CSS."),
        ("Monaco Editor", "JS", "The same editor as VS Code. Gives professional-grade code editing with syntax highlighting."),
        ("Recharts", "JS", "React charting library. Used for dashboard pie/bar charts."),
        ("Framer Motion", "JS", "Animation library. Powers the animated bomb cards and page transitions."),
        ("clang/LLVM", "Compiler", "Industry-standard C/C++ compiler. Produces textual IR output that we can parse and diff."),
    ]

    tech_data = [
        [Paragraph("<b>Library</b>", S("th", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN)),
         Paragraph("<b>Context</b>", S("th", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN)),
         Paragraph("<b>Why Used</b>", S("th", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN))],
    ]
    for lib, ctx, why in tech:
        tech_data.append([
            Paragraph(lib, S("td", fontName="Helvetica-Bold", fontSize=8, textColor=TEXT_WHITE)),
            Paragraph(ctx, S("td2", fontName="Helvetica", fontSize=8, textColor=TEXT_MUTED)),
            Paragraph(why, S("td3", fontName="Helvetica", fontSize=8, textColor=TEXT_WHITE, leading=11)),
        ])

    tech_t = Table(tech_data, colWidths=[35*mm, 25*mm, 105*mm])
    tech_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), CARD_BG),
        ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#111827")),
        ("GRID", (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#111827"), CARD_BG]),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(tech_t)
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 9. HOW TO READ RESULTS
    # ─────────────────────────────────────────────────────────────────────────
    story += section("9. How to Read the Results Page")

    story.append(Paragraph("Left Panel — Source Code with Gutter Markers", h2_s))
    story.append(Paragraph(
        "The Monaco editor shows your original source code with colored squares in the left margin:", body_s
    ))
    gutter_items = [
        ("Red square", "CRITICAL severity — immediate security risk, must fix"),
        ("Orange square", "HIGH severity — significant UB, likely to cause bugs"),
        ("Yellow square", "MEDIUM severity — potential issue, review recommended"),
        ("Blue square", "LOW severity — possible UB, lower certainty"),
    ]
    for color_name, meaning in gutter_items:
        story.append(Paragraph(f"  • {color_name}: {meaning}", bullet_s))
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("Right Panel — Bomb Cards", h2_s))
    story.append(Paragraph("Each card shows one UB finding. Click to expand:", body_s))
    card_fields = [
        ("Type", "The UB category (e.g., signed_integer_overflow)"),
        ("Line", "The source line where the UB occurs"),
        ("Confidence", "How certain the detector is (0-100%). Based on number of matching IR signals"),
        ("Severity", "Critical/High/Medium/Low based on exploitability"),
        ("CWE", "Common Weakness Enumeration number — the industry standard bug taxonomy"),
        ("-O0 behavior", "What happens without optimizations (what you observe in debug builds)"),
        ("-O2 behavior", "What the optimizer does (what you see in production builds)"),
        ("IR Evidence", "The actual LLVM IR instruction that shows the UB signal"),
        ("Compiler Reasoning", "Which LLVM optimization pass caused this and why"),
        ("Fix Suggestion", "How to rewrite the code to avoid the UB"),
    ]
    cf_data = [[
        Paragraph("<b>Field</b>", S("th", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN)),
        Paragraph("<b>Meaning</b>", S("th", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN)),
    ]]
    for field, meaning in card_fields:
        cf_data.append([
            Paragraph(field, S("cff", fontName="Helvetica-Bold", fontSize=8, textColor=TEXT_WHITE)),
            Paragraph(meaning, S("cfm", fontName="Helvetica", fontSize=8, textColor=TEXT_WHITE, leading=11)),
        ])
    cft = Table(cf_data, colWidths=[35*mm, 130*mm])
    cft.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), CARD_BG),
        ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#111827")),
        ("GRID", (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#111827"), CARD_BG]),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(cft)
    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 10. PRESENTATION TALKING POINTS
    # ─────────────────────────────────────────────────────────────────────────
    story += section("10. Presentation Talking Points")

    talk_sections = [
        ("Opening (30 seconds)", [
            "Start with Demo 6 (the 2-liner): 'Here is 2 lines of C code that looks perfectly fine...'",
            "Paste it, analyze, show the result: 'The compiler at -O2 turns this comparison into a constant true.'",
            "'This is called a UB Time Bomb — code that works in debug but breaks in production.'",
            "'Our tool automatically finds these bugs by comparing compiler output at different optimization levels.'",
        ]),
        ("Architecture Explanation (1 minute)", [
            "'The backend is a Python FastAPI server that calls clang to compile your code twice.'",
            "'We compare the LLVM IR output — that's the intermediate representation between C and machine code.'",
            "'The frontend is built with React and TypeScript, using Monaco Editor — the same editor as VS Code.'",
            "'All findings are stored in SQLite and you can export them as PDF or JSON reports.'",
        ]),
        ("Technical Depth (1 minute)", [
            "'We detect 6 categories of undefined behavior based on specific LLVM IR markers.'",
            "'For example, the nsw flag (no signed wrap) on arithmetic means the compiler assumed no overflow.'",
            "'The CFG viewer shows you exactly which code branches the optimizer deleted.'",
            "'Each finding includes the CWE number — the industry standard bug taxonomy.'",
        ]),
        ("Real-World Impact (30 seconds)", [
            "'These aren't theoretical bugs. Linux CVE-2011-1078 was this exact null-check-after-deref pattern.'",
            "'The Quake III fast inverse square root is a real strict aliasing violation.'",
            "'CVE-2014-0977 was an auth bypass caused by an uninitialized variable — exactly what our tool detects.'",
        ]),
        ("Demo Sequence (2 minutes)", [
            "Start: Demo 6 (minimal) → explain core concept",
            "Then: Demo 1 (signed overflow) → show IR diff clearly",
            "Then: Demo 5 (multiple patterns) → show tool detecting 3 bugs at once",
            "Show: Dashboard page with statistics after multiple scans",
            "Show: Evaluation page to prove accuracy (precision/recall/F1)",
        ]),
    ]

    for section_title, points in talk_sections:
        story.append(Paragraph(section_title, h2_s))
        for point in points:
            story.append(Paragraph(f"→ {point}", bullet_s))
        story.append(Spacer(1, 3*mm))

    story.append(PageBreak())

    # ─────────────────────────────────────────────────────────────────────────
    # 11. Q&A PREP
    # ─────────────────────────────────────────────────────────────────────────
    story += section("11. Q&A Preparation — Likely Teacher Questions")

    qas = [
        ("Q: Why is signed integer overflow undefined behavior?",
         "The C standard (C11 §6.5) explicitly states that signed arithmetic overflow has "
         "undefined behavior. This was a design choice to allow compilers to generate efficient "
         "code — they don't need to handle overflow cases. The trade-off is that code that "
         "relies on overflow behavior is non-portable and can break with optimization."),
        ("Q: Why not just use AddressSanitizer or Valgrind?",
         "ASan and Valgrind detect runtime crashes. UB time bombs are different — the code "
         "often doesn't crash. Instead, the optimizer silently changes the behavior. "
         "Our tool does static analysis on compiler IR, catching bugs that never crash "
         "but produce wrong results silently. They're complementary tools."),
        ("Q: How is this different from clang's UBSan (Undefined Behavior Sanitizer)?",
         "UBSan instruments the binary to detect UB at runtime — you need to actually run the "
         "code with specific inputs that trigger the UB. Our tool is static — it analyzes the "
         "IR structure without running the code, so it catches potential UB regardless of "
         "what inputs you provide."),
        ("Q: What is LLVM IR exactly?",
         "LLVM IR (Intermediate Representation) is a platform-independent assembly-like language "
         "that compilers like clang use internally. It's a static single assignment (SSA) form "
         "that all LLVM optimization passes read and modify. We analyze the textual IR "
         "(-emit-llvm -S flags) before it becomes machine code."),
        ("Q: How accurate is the detection? What about false positives?",
         "On our 5-case benchmark (real-world CVEs), we achieve 85-96% confidence per category. "
         "False positives are possible — the tool may flag code that is technically UB but "
         "happens to produce correct results on a specific platform. The confidence score "
         "indicates certainty. Lower confidence findings should be manually reviewed."),
        ("Q: Could this be used in a real CI/CD pipeline?",
         "Yes — the API is stateless and the analysis runs in milliseconds (typically <100ms "
         "for small files). You could call POST /api/v1/analyze from a GitHub Action and "
         "fail the build if any CRITICAL findings are returned. The JSON export endpoint "
         "makes integration with other tools straightforward."),
        ("Q: Why use Python for the backend instead of something closer to the compiler?",
         "Python is ideal for rapid development of analysis tools. The clang compilation "
         "itself is handled by the clang binary — we just parse the text output. "
         "Python's regex, string handling, and networkx library make the IR parsing "
         "and CFG analysis code clear and maintainable."),
        ("Q: What happens if the user submits C++ instead of C?",
         "The compiler selector allows choosing C++ mode. The analysis works the same way — "
         "clang handles C++ templates and classes and still produces LLVM IR. UB in C++ "
         "is even more extensive than in C (additional rules around vtables, dynamic_cast, etc.)."),
    ]

    for q, a in qas:
        story.append(box([
            Paragraph(q, S("qs", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT_CYAN)),
            Paragraph(a, S("as", fontName="Helvetica", fontSize=9, textColor=TEXT_WHITE, leading=14)),
        ], color=CARD_BG, border=BORDER_COLOR))
        story.append(Spacer(1, 3*mm))

    story.append(PageBreak())

    # ── Final page: Quick reference ────────────────────────────────────────────
    story += section("Quick Reference Card")
    story.append(Paragraph("API Endpoints:", h2_s))
    endpoints = [
        ("POST", "/api/v1/analyze",           "Submit code for analysis"),
        ("GET",  "/api/v1/scans",             "List all past scans"),
        ("GET",  "/api/v1/scans/{id}",        "Get one scan result"),
        ("GET",  "/api/v1/scans/{id}/export/pdf",  "Download PDF report"),
        ("GET",  "/api/v1/scans/{id}/export/json", "Download JSON report"),
        ("GET",  "/api/v1/stats",             "Dashboard statistics"),
        ("GET",  "/api/v1/evaluation",        "Run benchmark evaluation"),
        ("GET",  "/api/v1/health",            "Health check + clang version"),
        ("GET",  "/api/docs",                 "Swagger UI (interactive API docs)"),
    ]
    ep_data = [[
        Paragraph("<b>Method</b>", S("eth", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN)),
        Paragraph("<b>Path</b>", S("eth2", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN)),
        Paragraph("<b>Description</b>", S("eth3", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT_CYAN)),
    ]]
    for method, path, desc in endpoints:
        m_color = ACCENT_GREEN if method == "GET" else ACCENT_ORANGE
        ep_data.append([
            Paragraph(method, S("em", fontName="Helvetica-Bold", fontSize=8, textColor=m_color)),
            Paragraph(path, S("ep", fontName="Courier", fontSize=8, textColor=TEXT_WHITE)),
            Paragraph(desc, S("ed", fontName="Helvetica", fontSize=8, textColor=TEXT_MUTED, leading=11)),
        ])
    ep_t = Table(ep_data, colWidths=[18*mm, 75*mm, 72*mm])
    ep_t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), CARD_BG),
        ("BACKGROUND", (0,1), (-1,-1), colors.HexColor("#111827")),
        ("GRID", (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#111827"), CARD_BG]),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(ep_t)
    story.append(Spacer(1, 5*mm))

    story.append(Paragraph("Start Commands:", h2_s))
    story.append(Preformatted(
        "# Backend\n"
        "cd /Users/akanksha/ub-detector/backend\n"
        "python -m uvicorn main:app --reload --port 8001\n"
        "\n"
        "# Frontend (separate terminal)\n"
        "cd /Users/akanksha/ub-detector/frontend\n"
        "npm run dev\n"
        "\n"
        "# Frontend URL:  http://localhost:5173\n"
        "# Backend API:   http://localhost:8001\n"
        "# Swagger docs:  http://localhost:8001/api/docs",
        code_s
    ))

    doc.build(story, onFirstPage=dark_page, onLaterPages=dark_page)
    print(f"[OK] Created: {out_path}")


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    pdf1 = os.path.join(out_dir, "UB_Detector_Demo_Codes.pdf")
    pdf2 = os.path.join(out_dir, "UB_Detector_Project_Guide.pdf")
    print("Generating PDFs...")
    build_code_pdf(pdf1)
    build_guide_pdf(pdf2)
    print("\nDone! Files saved to:")
    print(f"  {pdf1}")
    print(f"  {pdf2}")
