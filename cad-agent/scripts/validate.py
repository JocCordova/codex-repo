from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.modeler import ModelerAgent
from agents.planner import PlannerAgent
from agents.validator import ValidatorAgent


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a request YAML and write markdown report.")
    parser.add_argument("--input", required=True, help="Path to request YAML file.")
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    input_path = (project_root / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)

    planner = PlannerAgent()
    request = planner.load_request(input_path)
    normalized = planner.normalize(request)

    modeler = ModelerAgent(project_root / "exports")
    model_output = modeler.generate(normalized)

    validator = ValidatorAgent(project_root / "specs", project_root / "reports" / "validation")
    result = validator.validate(normalized, model_output)

    print(f"[cad-agent] Validation passed: {result.passed}")
    print(f"[cad-agent] Report: {result.report_path}")
    if result.failures:
        print("[cad-agent] Failures:")
        for item in result.failures:
            print(f"  - {item}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
