from __future__ import annotations

from pathlib import Path
from typing import Any

import cadquery as cq

from agents.planner import NormalizedSpec
from models.generated_part import build_part


class ModelerAgent:
    """Builds CAD model and exports artifacts from normalized spec."""

    def __init__(self, export_root: Path) -> None:
        self.export_root = export_root
        self.stl_dir = export_root / "stl"
        self.step_dir = export_root / "step"
        self.stl_dir.mkdir(parents=True, exist_ok=True)
        self.step_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, spec: NormalizedSpec) -> dict[str, Any]:
        params = dict(spec.dimensions)
        params.setdefault("part_name", spec.name)
        params.setdefault("fillet_radius_mm", 1.0)

        model = build_part(params)
        if not isinstance(model, cq.Workplane):
            raise TypeError("build_part(params) must return a cadquery.Workplane")

        generated_paths: dict[str, str] = {}
        if spec.output.get("export_stl", True):
            stl_path = self.stl_dir / f"{spec.name}.stl"
            cq.exporters.export(model, str(stl_path))
            generated_paths["stl"] = str(stl_path)

        if spec.output.get("export_step", True):
            step_path = self.step_dir / f"{spec.name}.step"
            cq.exporters.export(model, str(step_path))
            generated_paths["step"] = str(step_path)

        return {
            "part_name": spec.name,
            "params": params,
            "paths": generated_paths,
            "status": "ok",
        }
