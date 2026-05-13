"""Shared pydantic models for the home storage agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SourceConfig(BaseModel):
    laptop_paths: list[Path] = Field(default_factory=list)
    external_2tb_paths: list[Path] = Field(default_factory=list)
    excluded_paths: list[Path] = Field(default_factory=list)
    max_scan_depth: int | None = None

    @property
    def source_paths(self) -> list[Path]:
        return [*self.laptop_paths, *self.external_2tb_paths]


class DestinationConfig(BaseModel):
    archive_root: Path = Path("archive_5tb")
    category_destinations: dict[str, str] = Field(default_factory=dict)
    manual_review_folders: dict[str, str] = Field(default_factory=dict)


class LlmBudgetConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    max_files_per_run: int = 100
    max_folder_summaries_per_run: int = 20
    max_estimated_cost: float = 1.0
    metadata_only_default: bool = True
    allow_content_inspection: bool = False


class ClassificationResult(BaseModel):
    category: str
    recommended_destination: str
    risk_level: str = "low"
    confidence: float = 0.0
    reason: str = ""
    requires_manual_review: bool = False


class FileMetadata(BaseModel):
    path: str
    filename: str
    extension: str
    size_mb: float
    created_at: str | None = None
    modified_at: str | None = None
    file_type: str = "unknown"
    source_root: str = ""
    parent_folder: str = ""
    hash_status: str = "not_hashed"

    def llm_safe_payload(self) -> dict[str, Any]:
        """Return metadata permitted for LLM classification by default."""
        return {
            "filename": self.filename,
            "extension": self.extension,
            "size_mb": self.size_mb,
            "parent_folder": self.parent_folder,
            "modified_at": self.modified_at,
            "file_type": self.file_type,
        }
