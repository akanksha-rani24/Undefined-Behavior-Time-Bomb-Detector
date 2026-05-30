"""
Evaluation endpoint: runs the 5 real-world benchmark cases
and returns precision/recall metrics.
"""
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse

from config import DATASETS_DIR
from core.compiler import compile_differential
from core.ir_analyzer import compare_functions, parse_ir_functions
from core.ub_classifier import classify_all
from models.schemas import EvalCase, EvalResult, EvaluationReport

router = APIRouter(prefix="/api/v1", tags=["evaluation"])

EXPECTED_RESULTS_PATH = DATASETS_DIR / "evaluation" / "expected_results.json"


def _load_expected() -> list[dict]:
    with open(EXPECTED_RESULTS_PATH) as f:
        return json.load(f)


@router.get("/evaluation", response_model=EvaluationReport)
async def run_evaluation():
    """Run analysis on all benchmark test cases and return evaluation metrics."""
    expected = _load_expected()
    results: list[EvalResult] = []
    real_world_dir = DATASETS_DIR / "real_world"

    for case_data in expected:
        case = EvalCase(**case_data)
        src_path = real_world_dir / case.filename
        if not src_path.exists():
            results.append(EvalResult(
                case=case, detected=False, detected_category=None,
                detected_line=None, confidence=None,
                true_positive=False, false_positive=False, false_negative=True,
                notes="Test file not found",
            ))
            continue

        source = src_path.read_text()
        lang = "cpp" if case.filename.endswith(".cpp") else "c"

        diff_result = await compile_differential(source, lang, case.filename, ["O0", "O2"])
        o0_ir = diff_result.get_ir("O0")
        o2_ir = diff_result.get_ir("O2")

        ir_diffs = []
        if o0_ir and o2_ir:
            f0 = parse_ir_functions(o0_ir)
            f2 = parse_ir_functions(o2_ir)
            for fn in f0:
                if fn in f2:
                    ir_diffs.append(compare_functions(fn, f0[fn], f2[fn]))

        bombs = classify_all(ir_diffs, source, o0_ir, o2_ir)

        # Did we detect the expected category?
        matching = [b for b in bombs if b.category == case.expected_category]
        detected = len(matching) > 0
        best = max(matching, key=lambda b: b.confidence) if matching else None

        # Determine TP/FP/FN
        line_tolerance = 5
        tp = detected and (
            best and abs((best.line or 0) - case.expected_line) <= line_tolerance
        )
        fp = detected and not tp
        fn = not detected

        results.append(EvalResult(
            case=case,
            detected=detected,
            detected_category=best.category if best else None,
            detected_line=best.line if best else None,
            confidence=best.confidence if best else None,
            true_positive=bool(tp),
            false_positive=bool(fp),
            false_negative=bool(fn),
            notes=(
                f"Detected {len(bombs)} bomb(s) total; "
                f"{len(matching)} match(es) for {case.expected_category}"
            ),
        ))

    tp_count = sum(1 for r in results if r.true_positive)
    fp_count = sum(1 for r in results if r.false_positive)
    fn_count = sum(1 for r in results if r.false_negative)

    precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
    recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return EvaluationReport(
        total_cases=len(results),
        true_positives=tp_count,
        false_positives=fp_count,
        false_negatives=fn_count,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        results=results,
    )
