# cad-agent Agent Instructions

This file is a practical operator guide for how the tool works and how to use each agent.

## Agent architecture (fixed in MVP)

The MVP uses exactly **three functional agents**:

1. **Planner** (`agents/planner.py`)
2. **Modeler** (`agents/modeler.py`)
3. **Validator** (`agents/validator.py`)

`agents/orchestrator.py` wires them together in a deterministic local workflow.

---

## Core operating rules

- Local-first only (filesystem based).
- No MCP and no cloud orchestration in MVP.
- Source of truth is code and YAML specs.
- Default assumptions when unspecified: **FDM + PLA + bambulab_p1s**.
- All dimensions are in **mm** unless explicitly overridden.
- Never silently invent missing critical dimensions.

---

## Planner instructions

### Input
- Path to request YAML matching `specs/part_request.schema.json`.

### Responsibilities
- Load YAML and validate strict structure.
- Produce normalized spec object.
- Carry assumptions forward and add explicit manufacturing assumptions.
- Emit modeling strategy notes and planning notes.

### Output contract
- `NormalizedSpec` with:
  - `name`, `units`, `process`, `material`, `printer`, `part_type`
  - `dimensions` dict (parameter source of truth)
  - explicit `assumptions`
  - `modeling_strategy`
  - `planning_notes`
  - `output` flags for STL/STEP/report

### Failure behavior
- Fail fast on malformed input or unsupported process.
- Return actionable error message (field-level where possible).

---

## Modeler instructions

### Input
- `NormalizedSpec` from planner.

### Responsibilities
- Build geometry with CadQuery from explicit parameters.
- Keep model editable and dimension-driven.
- Use `build_part(params)` in `models/generated_part.py`.
- Export according to output flags:
  - STL → `exports/stl/<part>.stl`
  - STEP → `exports/step/<part>.step`

### Modeling standards
- No magic numbers if a dimension can be parameterized.
- Avoid hidden tolerances; add tunables to input dimensions/rules.
- Keep geometry support-aware for FDM where practical.

### Failure behavior
- Raise clear errors for missing required dimensions.
- Fail if CAD build does not return `cadquery.Workplane`.

---

## Validator instructions

### Input
- `NormalizedSpec`
- model output metadata (export paths/status)

### Responsibilities
- Load printer preset from `specs/printers.yaml`.
- Load default print rules from `specs/default_print_rules.yaml`.
- Perform practical checks:
  - build volume fit
  - minimum wall thickness
  - fragile feature warning
  - overhang heuristic note
  - export/report success
- Write markdown report to `reports/validation/<part>_validation.md`.

### Result semantics
- **Fail** if hard constraints are violated (e.g., build volume, minimum wall).
- **Warn** on practical risk areas.
- **Info** for traceability and assumptions.

---

## How to use the tool

From repository root (`cad-agent/`):

```bash
python scripts/generate.py --input inputs/request_example.yaml
```
Runs planner + modeler + validator end-to-end.

```bash
python scripts/validate.py --input inputs/request_example.yaml
```
Re-runs model + validator and emits report.

```bash
python scripts/batch_run.py
```
Processes all `inputs/*.yaml` files.

---

## Adding new part types safely

1. Add or copy a parameterized model function under `models/`.
2. Keep required dimensions explicit in YAML input.
3. Update modeler routing if selecting by `style.part_type`.
4. Add focused tests for new required dimensions and output files.
5. Extend validation heuristics only when practical and deterministic.

---

## Troubleshooting checklist

- Missing dependency errors: install `requirements.txt` in active venv.
- Invalid request: validate against `specs/part_request.schema.json` and planner model.
- Export missing: verify `output.export_stl/export_step` flags.
- Validation fail: inspect report under `reports/validation/` and adjust dimensions/constraints.
