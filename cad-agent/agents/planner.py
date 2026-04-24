from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


class OutputOptions(BaseModel):
    export_stl: bool = True
    export_step: bool = True
    report: bool = True


class StyleOptions(BaseModel):
    part_type: str = "cable_clip"
    fillet_radius_mm: float = 1.0


class PartRequest(BaseModel):
    name: str
    units: str = "mm"
    process: str = "FDM"
    material: str = "PLA"
    printer: str = "bambulab_p1s"
    functional_requirements: list[str] = Field(default_factory=list)
    dimensions: dict[str, float]
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    style: StyleOptions = Field(default_factory=StyleOptions)
    output: OutputOptions = Field(default_factory=OutputOptions)

    @field_validator("units")
    @classmethod
    def validate_units(cls, value: str) -> str:
        if value not in {"mm", "inch"}:
            raise ValueError("units must be 'mm' or 'inch'")
        return value

    @field_validator("process")
    @classmethod
    def validate_process(cls, value: str) -> str:
        if value != "FDM":
            raise ValueError("MVP supports FDM only")
        return value


@dataclass(slots=True)
class NormalizedSpec:
    name: str
    units: str
    process: str
    material: str
    printer: str
    part_type: str
    dimensions: dict[str, float]
    assumptions: list[str]
    modeling_strategy: list[str]
    planning_notes: list[str]
    output: dict[str, bool]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "units": self.units,
            "process": self.process,
            "material": self.material,
            "printer": self.printer,
            "part_type": self.part_type,
            "dimensions": self.dimensions,
            "assumptions": self.assumptions,
            "modeling_strategy": self.modeling_strategy,
            "planning_notes": self.planning_notes,
            "output": self.output,
        }


class PlannerAgent:
    """Normalizes request YAML into a strict, explicit modeling spec."""

    @staticmethod
    def load_request(path: Path) -> PartRequest:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict):
            raise ValueError("Input YAML must define an object.")
        try:
            return PartRequest.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"Request validation failed: {exc}") from exc

    @staticmethod
    def normalize(request: PartRequest) -> NormalizedSpec:
        assumptions = list(request.assumptions)
        if request.process == "FDM" and request.material.upper() == "PLA":
            assumptions.append("PLA shrink/fit variance may require hole/tolerance tuning.")

        modeling_strategy = [
            "Model base solid first from explicit dimensions.",
            "Add cable retention geometry using parameterized dimensions.",
            "Apply fillets if requested to reduce stress concentrations.",
            "Subtract mounting hole and optional screw-head clearance.",
        ]
        planning_notes = [
            "All dimensions interpreted in mm unless units override is explicit.",
            "Avoid unsupported bridges where possible.",
            "No silent dimension invention; missing values should fail fast.",
        ]

        return NormalizedSpec(
            name=request.name,
            units=request.units,
            process=request.process,
            material=request.material,
            printer=request.printer,
            part_type=request.style.part_type,
            dimensions=request.dimensions,
            assumptions=assumptions,
            modeling_strategy=modeling_strategy,
            planning_notes=planning_notes,
            output=request.output.model_dump(),
        )
