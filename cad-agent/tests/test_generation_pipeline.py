from pathlib import Path

from agents.orchestrator import Orchestrator


def test_pipeline_produces_outputs() -> None:
    root = Path(__file__).resolve().parents[1]
    result = Orchestrator(root).run(root / "inputs" / "request_example.yaml")

    assert "stl" in result["model_output"]["paths"]
    assert "step" in result["model_output"]["paths"]
    assert Path(result["validation"]["report_path"]).exists()
