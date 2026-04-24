from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.orchestrator import Orchestrator


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full CAD generation pipeline on one input YAML.")
    parser.add_argument("--input", required=True, help="Path to request YAML file.")
    args = parser.parse_args()

    project_root = PROJECT_ROOT
    input_path = (project_root / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)

    print(f"[cad-agent] Running pipeline for: {input_path}")
    result = Orchestrator(project_root).run(input_path)

    print("[cad-agent] Pipeline complete")
    print(f"[cad-agent] Exports: {result['model_output']['paths']}")
    print(f"[cad-agent] Validation report: {result['validation']['report_path']}")
    print(f"[cad-agent] Validation passed: {result['validation']['passed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
