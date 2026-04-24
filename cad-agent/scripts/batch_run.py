from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.orchestrator import Orchestrator


def main() -> int:
    project_root = PROJECT_ROOT
    inputs_dir = project_root / "inputs"
    orchestrator = Orchestrator(project_root)

    yaml_files = sorted([p for p in inputs_dir.glob("*.yaml")])
    if not yaml_files:
        print("[cad-agent] No input YAML files found in inputs/.")
        return 0

    print(f"[cad-agent] Found {len(yaml_files)} input file(s).")
    failures = 0

    for input_path in yaml_files:
        print(f"[cad-agent] Processing {input_path.name} ...")
        result = orchestrator.run(input_path)
        passed = result["validation"]["passed"]
        print(f"[cad-agent]   -> validation passed: {passed}")
        if not passed:
            failures += 1

    print(f"[cad-agent] Batch complete. failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
