from pathlib import Path

from agents.planner import PlannerAgent


def test_request_example_loads() -> None:
    root = Path(__file__).resolve().parents[1]
    request = PlannerAgent.load_request(root / "inputs" / "request_example.yaml")
    assert request.name == "screw_mount_cable_clip"
    assert request.printer == "bambulab_p1s"
    assert request.process == "FDM"
