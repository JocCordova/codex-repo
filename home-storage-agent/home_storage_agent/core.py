"""Core file inventory, classification, planning, copying, and reporting logic."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import mimetypes
import os
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .models import ClassificationResult, DestinationConfig, FileMetadata, LlmBudgetConfig, SourceConfig

DATA_DIR = Path("data")
REPORTS_DIR = Path("reports")
LOGS_DIR = Path("logs")
INVENTORY_DB = DATA_DIR / "inventory.duckdb"
INVENTORY_CSV = DATA_DIR / "inventory.csv"
DUPLICATES_CSV = DATA_DIR / "duplicates.csv"
MIGRATION_PLAN_CSV = DATA_DIR / "migration_plan.csv"
CLASSIFICATION_CSV = DATA_DIR / "classified_inventory.csv"
LLM_CLASSIFICATION_CSV = DATA_DIR / "llm_classifications.csv"

INVENTORY_COLUMNS = [
    "path",
    "filename",
    "extension",
    "size_mb",
    "created_at",
    "modified_at",
    "file_type",
    "source_root",
    "parent_folder",
    "hash_status",
]

CLASSIFICATION_COLUMNS = [
    *INVENTORY_COLUMNS,
    "category",
    "recommended_destination",
    "risk_level",
    "confidence",
    "reason",
    "requires_manual_review",
]

PLAN_COLUMNS = [
    "source_path",
    "recommended_destination",
    "category",
    "risk_level",
    "action",
    "reason",
    "confidence",
    "requires_manual_review",
]

console = Console()


def ensure_workspace() -> None:
    for directory in (DATA_DIR, REPORTS_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def utc_datetime(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def within_excluded(path: Path, excluded_paths: Iterable[Path]) -> bool:
    resolved = safe_resolve(path)
    for excluded in excluded_paths:
        excluded_resolved = safe_resolve(excluded)
        try:
            resolved.relative_to(excluded_resolved)
            return True
        except ValueError:
            continue
    return False


def safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser().absolute()


def depth_from_root(path: Path, root: Path) -> int:
    try:
        return len(path.relative_to(root).parts)
    except ValueError:
        return 0


def infer_file_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime:
        return mime
    suffix = path.suffix.lower().lstrip(".")
    if suffix:
        return f"extension/{suffix}"
    return "unknown"


def iter_files(config: SourceConfig, logger: logging.Logger) -> Iterable[tuple[Path, Path]]:
    for source_root in config.source_paths:
        root = safe_resolve(source_root)
        if not root.exists():
            logger.warning("source path does not exist: %s", root)
            continue
        if root.is_file():
            yield root, root.parent
            continue
        for current_root, dirs, files in os.walk(root):
            current_path = Path(current_root)
            dirs[:] = [d for d in dirs if not within_excluded(current_path / d, config.excluded_paths)]
            if config.max_scan_depth is not None and depth_from_root(current_path, root) >= config.max_scan_depth:
                dirs[:] = []
            for filename in files:
                path = current_path / filename
                if not within_excluded(path, config.excluded_paths):
                    yield path, root


def scan_inventory(config: SourceConfig, full_hash: bool, logger: logging.Logger) -> int:
    ensure_workspace()
    rows: list[dict[str, Any]] = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), TimeElapsedColumn(), console=console) as progress:
        task = progress.add_task("scanning source paths", total=None)
        for path, source_root in iter_files(config, logger):
            try:
                stat = path.stat()
            except OSError as exc:
                logger.warning("could not stat file %s: %s", path, exc)
                continue
            hash_status = "not_hashed"
            if full_hash:
                hash_status = sha256_file(path) or "hash_error"
            rows.append(
                {
                    "path": str(path),
                    "filename": path.name,
                    "extension": path.suffix.lower().lstrip("."),
                    "size_mb": round(stat.st_size / 1024 / 1024, 6),
                    "created_at": utc_datetime(getattr(stat, "st_birthtime", stat.st_ctime)),
                    "modified_at": utc_datetime(stat.st_mtime),
                    "file_type": infer_file_type(path),
                    "source_root": str(source_root),
                    "parent_folder": path.parent.name.lower(),
                    "hash_status": hash_status,
                }
            )
            progress.update(task, description=f"scanned {len(rows)} files")
    write_csv(INVENTORY_CSV, INVENTORY_COLUMNS, rows)
    write_inventory_duckdb(rows)
    logger.info("scanned %s files", len(rows))
    return len(rows)


def write_inventory_duckdb(rows: list[dict[str, Any]]) -> None:
    con = duckdb.connect(str(INVENTORY_DB))
    try:
        con.execute("drop table if exists inventory")
        column_defs = [f"{column} double" if column == "size_mb" else f"{column} varchar" for column in INVENTORY_COLUMNS]
        con.execute(f"create table inventory ({', '.join(column_defs)})")
        if rows:
            con.executemany(
                "insert into inventory values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [[row[column] for column in INVENTORY_COLUMNS] for row in rows],
            )
    finally:
        con.close()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, columns: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_size), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def detect_duplicates(strong: bool, logger: logging.Logger) -> int:
    rows = read_csv(INVENTORY_CSV)
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["filename"].lower(), row["size_mb"])].append(row)
    output: list[dict[str, Any]] = []
    group_id = 1
    for (filename, size_mb), items in groups.items():
        if len(items) < 2:
            continue
        hashes: dict[str, list[dict[str, str]]] = defaultdict(list)
        if strong:
            for item in items:
                checksum = sha256_file(Path(item["path"])) or "hash_error"
                hashes[checksum].append(item)
        for item in items:
            checksum = ""
            duplicate_type = "likely_duplicate"
            if strong:
                checksum = sha256_file(Path(item["path"])) or "hash_error"
                duplicate_type = "exact_duplicate" if checksum != "hash_error" and len(hashes[checksum]) > 1 else "likely_duplicate"
            output.append(
                {
                    "group_id": group_id,
                    "duplicate_type": duplicate_type,
                    "path": item["path"],
                    "filename": filename,
                    "size_mb": size_mb,
                    "sha256": checksum,
                    "recommended_action": "manual_review",
                }
            )
        group_id += 1
    write_csv(DUPLICATES_CSV, ["group_id", "duplicate_type", "path", "filename", "size_mb", "sha256", "recommended_action"], output)
    logger.info("found %s duplicate candidate rows", len(output))
    return len(output)


def lower_terms(values: Iterable[str]) -> list[str]:
    return [value.lower() for value in values]


def contains_any(haystack: str, needles: Iterable[str]) -> str | None:
    lowered = haystack.lower()
    for needle in needles:
        if needle and needle.lower() in lowered:
            return needle
    return None


def classify_row(row: dict[str, str], rules: dict[str, Any], sensitive: dict[str, Any], destinations: DestinationConfig) -> ClassificationResult:
    filename = row.get("filename", "").lower()
    extension = row.get("extension", "").lower()
    parent = row.get("parent_folder", "").lower()
    path_text = row.get("path", "").lower()

    sensitive_exts = set(lower_terms(sensitive.get("extensions", [])))
    sensitive_keywords = lower_terms(sensitive.get("filename_keywords", []) + sensitive.get("folder_keywords", []))
    matched_sensitive = extension in sensitive_exts or contains_any(path_text, sensitive_keywords)
    if matched_sensitive:
        return ClassificationResult(
            category="sensitive",
            recommended_destination=destinations.category_destinations.get("sensitive", "archive_5tb/03_documents/manual_review/"),
            risk_level="high",
            confidence=0.95,
            reason=f"matched sensitive pattern: {matched_sensitive if isinstance(matched_sensitive, str) else extension}",
            requires_manual_review=True,
        )

    ext_map: dict[str, str] = rules.get("extension_mappings", {})
    category = ext_map.get(extension, "unknown")
    reason = f"extension mapping: .{extension}" if category != "unknown" else "no deterministic rule matched"
    confidence = 0.85 if category != "unknown" else 0.2

    for key, mapped_category in rules.get("filename_keyword_mappings", {}).items():
        if key.lower() in filename:
            category = mapped_category
            reason = f"filename keyword mapping: {key}"
            confidence = 0.8
            break
    for key, mapped_category in rules.get("folder_keyword_mappings", {}).items():
        if key.lower() in parent or key.lower() in path_text:
            category = mapped_category
            reason = f"folder keyword mapping: {key}"
            confidence = 0.78
            break

    risk = "low"
    requires_review = category == "unknown"
    if category in {"document", "archive", "code", "config"}:
        risk = "medium"
    if category == "unknown":
        risk = "medium"

    destination = destinations.category_destinations.get(category, destinations.manual_review_folders.get("unknown", "archive_5tb/99_cold_storage/manual_review/"))
    return ClassificationResult(
        category=category,
        recommended_destination=destination,
        risk_level=risk,
        confidence=confidence,
        reason=reason,
        requires_manual_review=requires_review,
    )


def classify_inventory(rules: dict[str, Any], sensitive: dict[str, Any], destinations: DestinationConfig, logger: logging.Logger) -> int:
    rows = read_csv(INVENTORY_CSV)
    output: list[dict[str, Any]] = []
    for row in rows:
        result = classify_row(row, rules, sensitive, destinations)
        output.append({**row, **result.model_dump()})
    write_csv(CLASSIFICATION_CSV, CLASSIFICATION_COLUMNS, output)
    logger.info("classified %s files", len(output))
    return len(output)


def metadata_from_row(row: dict[str, str]) -> FileMetadata:
    return FileMetadata(
        path=row.get("path", ""),
        filename=row.get("filename", ""),
        extension=row.get("extension", ""),
        size_mb=float(row.get("size_mb") or 0),
        created_at=row.get("created_at") or None,
        modified_at=row.get("modified_at") or None,
        file_type=row.get("file_type", "unknown"),
        source_root=row.get("source_root", ""),
        parent_folder=row.get("parent_folder", ""),
        hash_status=row.get("hash_status", "not_hashed"),
    )


def heuristic_llm_fallback(row: dict[str, str], destinations: DestinationConfig) -> ClassificationResult:
    """Offline fallback used when no LLM client is configured."""
    payload = metadata_from_row(row).llm_safe_payload()
    text = json.dumps(payload).lower()
    if "movie" in text or "1080p" in text or "bluray" in text:
        category = "media_video"
        dest = "archive_5tb/01_media/movies/"
    elif "episode" in text or "season" in text or "s01" in text:
        category = "media_video"
        dest = "archive_5tb/01_media/series/"
    elif "project" in text or "repo" in text:
        category = "code"
        dest = "archive_5tb/04_code_projects/manual_review/"
    else:
        category = "unknown"
        dest = destinations.manual_review_folders.get("unknown", "archive_5tb/99_cold_storage/manual_review/")
    return ClassificationResult(
        category=category,
        recommended_destination=dest,
        risk_level="medium",
        confidence=0.45,
        reason="offline metadata-only llm fallback; configure provider for real llm calls",
        requires_manual_review=True,
    )


def classify_with_llm(budget: LlmBudgetConfig, destinations: DestinationConfig, ambiguous_only: bool, logger: logging.Logger) -> int:
    rows = read_csv(CLASSIFICATION_CSV) or read_csv(INVENTORY_CSV)
    output: list[dict[str, Any]] = []
    calls = 0
    for row in rows:
        is_ambiguous = row.get("category", "unknown") == "unknown" or row.get("requires_manual_review", "False") == "True"
        is_sensitive = row.get("category") == "sensitive" or row.get("risk_level") == "high"
        if is_sensitive or (ambiguous_only and not is_ambiguous):
            continue
        if calls >= budget.max_files_per_run:
            logger.info("llm budget reached at %s files", calls)
            break
        # Privacy default: metadata only. No file contents are read or sent here.
        result = heuristic_llm_fallback(row, destinations)
        output.append({"source_path": row.get("path", ""), **result.model_dump()})
        calls += 1
    write_csv(LLM_CLASSIFICATION_CSV, ["source_path", "category", "recommended_destination", "risk_level", "confidence", "reason", "requires_manual_review"], output)
    logger.info("processed %s llm classification candidates", len(output))
    return len(output)


def generate_plan(logger: logging.Logger) -> int:
    rows = read_csv(CLASSIFICATION_CSV)
    llm_by_path = {row["source_path"]: row for row in read_csv(LLM_CLASSIFICATION_CSV)}
    output: list[dict[str, Any]] = []
    manual_lines = ["# manual review", "", "items below should be reviewed before copying.", ""]
    for row in rows:
        llm_row = llm_by_path.get(row.get("path", ""))
        if llm_row:
            row = {**row, **{k: v for k, v in llm_row.items() if k != "source_path"}}
        confidence = float(row.get("confidence") or 0)
        review = str(row.get("requires_manual_review", "False")).lower() == "true"
        risk = row.get("risk_level", "medium")
        if review or risk == "high" or confidence < 0.6:
            action = "manual_review" if risk == "high" or confidence < 0.5 else "copy_review_required"
        else:
            action = "copy"
        plan_row = {
            "source_path": row.get("path", ""),
            "recommended_destination": row.get("recommended_destination", ""),
            "category": row.get("category", "unknown"),
            "risk_level": risk,
            "action": action,
            "reason": row.get("reason", ""),
            "confidence": row.get("confidence", ""),
            "requires_manual_review": action != "copy",
        }
        output.append(plan_row)
        if action != "copy":
            manual_lines.append(f"- `{plan_row['source_path']}` → `{plan_row['recommended_destination']}` ({risk}, {plan_row['reason']})")
    write_csv(MIGRATION_PLAN_CSV, PLAN_COLUMNS, output)
    (REPORTS_DIR / "manual_review.md").write_text("\n".join(manual_lines) + "\n", encoding="utf-8")
    logger.info("generated migration plan with %s rows", len(output))
    return len(output)


def safe_destination(dest_dir: Path, filename: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        next_candidate = dest_dir / f"{stem}_{counter:03d}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        counter += 1


def copy_from_plan(archive_root: Path | None, execute: bool, logger: logging.Logger) -> int:
    rows = read_csv(MIGRATION_PLAN_CSV)
    copied = 0
    log_rows: list[str] = []
    for row in rows:
        if row.get("action") != "copy":
            continue
        src = Path(row["source_path"])
        configured_dest = Path(row["recommended_destination"])
        if archive_root and configured_dest.parts and configured_dest.parts[0] == "archive_5tb":
            configured_dest = archive_root / Path(*configured_dest.parts[1:])
        dest = safe_destination(configured_dest, src.name)
        message = f"{'copy' if execute else 'dry_run'}: {src} -> {dest}"
        logger.info(message)
        log_rows.append(message)
        if execute:
            shutil.copy2(src, dest)
            copied += 1
    mode = "executed" if execute else "dry_run"
    (REPORTS_DIR / f"copy_{mode}.log").write_text("\n".join(log_rows) + "\n", encoding="utf-8")
    return copied


def verify_copy(sample_checksums: int, logger: logging.Logger) -> dict[str, Any]:
    rows = [row for row in read_csv(MIGRATION_PLAN_CSV) if row.get("action") == "copy"]
    source_count = len(rows)
    source_size = 0
    existing_destinations = 0
    checksum_checked = 0
    for row in rows:
        src = Path(row["source_path"])
        if src.exists():
            source_size += src.stat().st_size
        dest_dir = Path(row["recommended_destination"])
        dest = dest_dir / src.name
        if dest.exists():
            existing_destinations += 1
            if checksum_checked < sample_checksums and src.exists():
                checksum_checked += 1
                if sha256_file(src) != sha256_file(dest):
                    logger.warning("checksum mismatch: %s", src)
    result = {
        "planned_copy_count": source_count,
        "planned_copy_size_mb": round(source_size / 1024 / 1024, 3),
        "matching_destination_filenames": existing_destinations,
        "checksum_samples": checksum_checked,
    }
    lines = ["# backup verification", ""] + [f"- {key}: {value}" for key, value in result.items()]
    (REPORTS_DIR / "backup_verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def generate_report(logger: logging.Logger) -> None:
    inventory = read_csv(INVENTORY_CSV)
    duplicates = read_csv(DUPLICATES_CSV)
    classified = read_csv(CLASSIFICATION_CSV)
    plan = read_csv(MIGRATION_PLAN_CSV)
    total_size = sum(float(row.get("size_mb") or 0) for row in inventory)
    type_counts = Counter(row.get("file_type", "unknown") for row in inventory)
    category_counts = Counter(row.get("category", "unknown") for row in classified)
    action_counts = Counter(row.get("action", "unknown") for row in plan)
    largest_files = sorted(inventory, key=lambda r: float(r.get("size_mb") or 0), reverse=True)[:20]
    folder_sizes: dict[str, float] = defaultdict(float)
    for row in inventory:
        folder_sizes[row.get("parent_folder", "unknown")] += float(row.get("size_mb") or 0)
    lines = [
        "# migration report",
        "",
        f"- total files scanned: {len(inventory)}",
        f"- total size scanned mb: {total_size:.2f}",
        f"- duplicate candidate rows: {len(duplicates)}",
        f"- high-risk files: {sum(1 for row in classified if row.get('risk_level') == 'high')}",
        f"- manual review items: {sum(1 for row in plan if row.get('action') in {'manual_review', 'copy_review_required'})}",
        "",
        "## file type distribution",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in type_counts.most_common(20))
    lines.extend(["", "## category distribution", ""])
    lines.extend(f"- {key}: {value}" for key, value in category_counts.most_common())
    lines.extend(["", "## action distribution", ""])
    lines.extend(f"- {key}: {value}" for key, value in action_counts.most_common())
    lines.extend(["", "## largest folders", ""])
    lines.extend(f"- {folder}: {size:.2f} mb" for folder, size in sorted(folder_sizes.items(), key=lambda item: item[1], reverse=True)[:20])
    lines.extend(["", "## largest files", ""])
    lines.extend(f"- `{row.get('path')}`: {float(row.get('size_mb') or 0):.2f} mb" for row in largest_files)
    (REPORTS_DIR / "migration_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not (REPORTS_DIR / "folder_summaries.md").exists():
        (REPORTS_DIR / "folder_summaries.md").write_text("# folder summaries\n\nrun `classify-llm` in a configured environment to add folder summaries.\n", encoding="utf-8")
    logger.info("generated migration report")
