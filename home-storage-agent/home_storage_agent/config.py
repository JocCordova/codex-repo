"""Configuration loading helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from .models import DestinationConfig, LlmBudgetConfig, SourceConfig

T = TypeVar("T", bound=BaseModel)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"expected mapping in config file: {path}")
    return data


def load_model(path: Path, model: type[T]) -> T:
    return model.model_validate(load_yaml(path))


def default_path(name: str) -> Path:
    return PROJECT_ROOT / "config" / name


def load_sources(path: Path | None = None) -> SourceConfig:
    return load_model(path or default_path("sources.yaml"), SourceConfig)


def load_destinations(path: Path | None = None) -> DestinationConfig:
    return load_model(path or default_path("destinations.yaml"), DestinationConfig)


def load_llm_budget(path: Path | None = None) -> LlmBudgetConfig:
    return load_model(path or default_path("llm_budget.yaml"), LlmBudgetConfig)


def load_rules(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or default_path("classification_rules.yaml"))


def load_sensitive_patterns(path: Path | None = None) -> dict[str, Any]:
    return load_yaml(path or default_path("sensitive_patterns.yaml"))
