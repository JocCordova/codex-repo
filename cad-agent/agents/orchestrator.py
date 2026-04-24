from __future__ import annotations

from pathlib import Path
from typing import Any

from agents.modeler import ModelerAgent
from agents.planner import PlannerAgent
from agents.validator import ValidatorAgent


class Orchestrator:
    """File-based orchestrator that wires planner -> modeler -> validator."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.specs_dir = project_root / "specs"
        self.exports_dir = project_root / "exports"
        self.report_dir = project_root / "reports" / "validation"

        self.planner = PlannerAgent()
        self.modeler = ModelerAgent(self.exports_dir)
        self.validator = ValidatorAgent(self.specs_dir, self.report_dir)

    def run(self, input_path: Path) -> dict[str, Any]:
        request = self.planner.load_request(input_path)
        normalized = self.planner.normalize(request)
        model_output = self.modeler.generate(normalized)
        validation = self.validator.validate(normalized, model_output)

        return {
            "request": request.model_dump(),
            "normalized_spec": normalized.as_dict(),
            "model_output": model_output,
            "validation": {
                "passed": validation.passed,
                "failures": validation.failures,
                "warnings": validation.warnings,
                "info": validation.info,
                "report_path": validation.report_path,
            },
        }
