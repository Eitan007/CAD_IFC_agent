from pathlib import Path

from app.evaluation import score_answer, score_sample_files
from app.services.deterministic_checks import build_pipeline_checks, source_data_contract


def test_step_contract_does_not_promise_bim_properties():
    contract = source_data_contract("step")
    assert "CAD geometry" in contract
    assert "unknown" in contract


def test_step_answer_score_rejects_invented_standard():
    result = score_answer("step", "This CAD geometry is an ISO threaded bolt.")
    assert result["score"] == 40
    assert result["passed"] is False


def test_step_answer_score_accepts_honest_boundary():
    result = score_answer(
        "step",
        "This STEP CAD geometry shows a bolt, but its thread pitch and material grade are not supplied.",
    )
    assert result["score"] == 100
    assert result["passed"] is True


def test_step_pipeline_includes_preview_check():
    checks = build_pipeline_checks("step", graph_ready=True, preview_status="ready", element_count=1)
    assert any(check["id"] == "cad_preview_ready" and check["passed"] for check in checks)


def test_threaded_sample_and_preview_exist():
    samples = Path(__file__).resolve().parents[1] / "samples"
    result = score_sample_files([samples / "ThreadedHexBolt.step"])
    assert result["average_score"] == 100
