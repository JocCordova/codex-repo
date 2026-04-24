from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agents.planner import NormalizedSpec


@dataclass(slots=True)
class ValidationResult:
    passed: bool
    failures: list[str]
    warnings: list[str]
    info: list[str]
    report_path: str


class ValidatorAgent:
    """Performs practical FDM-oriented validation checks."""

    def __init__(self, specs_dir: Path, report_dir: Path) -> None:
        self.specs_dir = specs_dir
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _load_printer(self, printer_name: str) -> dict[str, Any]:
        with (self.specs_dir / "printers.yaml").open("r", encoding="utf-8") as f:
            printers = yaml.safe_load(f) or {}
        data = printers.get("printers", {}).get(printer_name)
        if not data:
            raise ValueError(f"Unknown printer preset: {printer_name}")
        return data

    def _load_rules(self) -> dict[str, Any]:
        with (self.specs_dir / "default_print_rules.yaml").open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def validate(self, spec: NormalizedSpec, model_output: dict[str, Any]) -> ValidationResult:
        printer = self._load_printer(spec.printer)
        rules = self._load_rules()

        failures: list[str] = []
        warnings: list[str] = []
        info: list[str] = []

        dims = spec.dimensions
        bv = printer["build_volume_mm"]
        x = dims.get("base_length_mm", 0.0)
        y = dims.get("base_width_mm", 0.0)
        z = dims.get("clip_depth_mm", dims.get("base_thickness_mm", 0.0))

        if x > bv["x"] or y > bv["y"] or z > bv["z"]:
            failures.append(
                f"Part extents ({x:.1f}, {y:.1f}, {z:.1f}) exceed build volume ({bv['x']}, {bv['y']}, {bv['z']}) mm."
            )
        else:
            info.append("Part appears to fit within printer build volume.")

        wall = dims.get("wall_thickness_mm")
        min_wall = float(rules.get("minimum_wall_mm", 1.2))
        if wall is not None and wall < min_wall:
            failures.append(f"Wall thickness {wall:.2f} mm is below minimum {min_wall:.2f} mm.")

        minimum_feature = float(rules.get("minimum_feature_mm", 0.8))
        if dims.get("base_thickness_mm", 0.0) < minimum_feature:
            warnings.append("Base thickness may be too fragile for repeated use.")

        max_overhang = float(rules.get("max_overhang_deg", 50))
        info.append(f"Overhang heuristic max: {max_overhang:.0f}°; ensure model orientation supports this.")

        if not model_output.get("paths"):
            failures.append("No export paths produced by modeler.")
        else:
            info.append(f"Exports generated: {', '.join(sorted(model_output['paths'].keys()))}")

        if not spec.assumptions:
            warnings.append("No assumptions listed; add explicit manufacturing assumptions.")

        passed = not failures
        report_path = self._write_report(spec, failures, warnings, info)
        return ValidationResult(
            passed=passed,
            failures=failures,
            warnings=warnings,
            info=info,
            report_path=str(report_path),
        )

    def _write_report(
        self,
        spec: NormalizedSpec,
        failures: list[str],
        warnings: list[str],
        info: list[str],
    ) -> Path:
        report_path = self.report_dir / f"{spec.name}_validation.md"
        status = "PASS" if not failures else "FAIL"
        lines = [
            f"# Validation Report: {spec.name}",
            "",
            f"**Status:** {status}",
            f"**Printer:** {spec.printer}",
            f"**Process/Material:** {spec.process}/{spec.material}",
            "",
            "## Failures",
        ]
        lines.extend([f"- {item}" for item in failures] or ["- None"])
        lines.append("")
        lines.append("## Warnings")
        lines.extend([f"- {item}" for item in warnings] or ["- None"])
        lines.append("")
        lines.append("## Info")
        lines.extend([f"- {item}" for item in info] or ["- None"])
        lines.append("")
        lines.append("## Assumptions")
        lines.extend([f"- {item}" for item in spec.assumptions] or ["- None"])
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path
