"""Command line interface for the local-first home storage agent."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

try:
    from rich.console import Console
except ImportError:  # pragma: no cover - used only before optional dependencies are installed.
    class Console:  # type: ignore[no-redef]
        """Small fallback so `--help` works before installing dependencies."""

        def print(self, *objects: Any, **_: Any) -> None:
            print(*objects)

from .config import load_destinations, load_llm_budget, load_rules, load_sensitive_patterns, load_sources
from .logging_utils import setup_logging

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="home-storage-agent",
        description="Local-first safe audit, classification, and migration planning for home storage archives.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="scan configured source paths and build local inventory")
    scan.add_argument("--config", type=Path, default=None, help="path to sources.yaml")
    scan.add_argument("--full-hash", action="store_true", help="calculate sha256 for every scanned file")

    duplicates = subparsers.add_parser("duplicates", help="detect duplicate candidates without deleting anything")
    duplicates.add_argument("--weak", action="store_true", help="use filename + size only")
    duplicates.add_argument("--sha256", action="store_true", help="verify duplicate candidates with sha256")

    classify = subparsers.add_parser("classify", help="classify files with deterministic local rules")
    classify.add_argument("--rules", type=Path, default=None, help="path to classification_rules.yaml")
    classify.add_argument("--sensitive-patterns", type=Path, default=None, help="path to sensitive_patterns.yaml")
    classify.add_argument("--destinations", type=Path, default=None, help="path to destinations.yaml")

    classify_llm = subparsers.add_parser("classify-llm", help="metadata-only LLM-assisted classification for ambiguous files")
    classify_llm.add_argument("--budget", type=Path, default=None, help="path to llm_budget.yaml")
    classify_llm.add_argument("--destinations", type=Path, default=None, help="path to destinations.yaml")
    classify_llm.add_argument("--ambiguous-only", action="store_true", default=True, help="only classify unknown or manual-review files")
    classify_llm.add_argument("--all-non-sensitive", action="store_true", help="allow all non-sensitive rows within budget")

    subparsers.add_parser("plan", help="generate migration plan and manual review report")

    copy = subparsers.add_parser("copy", help="copy files from migration plan; dry-run by default")
    copy.add_argument("--dry-run", action="store_true", help="preview copy operations without copying")
    copy.add_argument("--execute", action="store_true", help="required to actually copy files")
    copy.add_argument("--archive-root", type=Path, default=None, help="override archive_5tb root path")

    verify = subparsers.add_parser("verify", help="verify copied files")
    verify.add_argument("--sample-checksums", type=int, default=0, help="number of copied files to checksum")

    subparsers.add_parser("report", help="generate readable migration report")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    from .core import LOGS_DIR

    logger = setup_logging(LOGS_DIR / "migration.log")

    if args.command == "scan":
        from .core import scan_inventory

        count = scan_inventory(load_sources(args.config), full_hash=args.full_hash, logger=logger)
        console.print(f"[green]scanned {count} files[/green]")
        return 0
    if args.command == "duplicates":
        from .core import detect_duplicates

        strong = bool(args.sha256 and not args.weak)
        count = detect_duplicates(strong=strong, logger=logger)
        console.print(f"[green]wrote {count} duplicate candidate rows[/green]")
        return 0
    if args.command == "classify":
        from .core import classify_inventory

        count = classify_inventory(
            load_rules(args.rules),
            load_sensitive_patterns(args.sensitive_patterns),
            load_destinations(args.destinations),
            logger,
        )
        console.print(f"[green]classified {count} files[/green]")
        return 0
    if args.command == "classify-llm":
        from .core import classify_with_llm

        count = classify_with_llm(
            load_llm_budget(args.budget),
            load_destinations(args.destinations),
            ambiguous_only=not args.all_non_sensitive,
            logger=logger,
        )
        console.print(f"[green]processed {count} metadata-only llm candidates[/green]")
        return 0
    if args.command == "plan":
        from .core import generate_plan

        count = generate_plan(logger)
        console.print(f"[green]planned {count} files[/green]")
        return 0
    if args.command == "copy":
        from .core import copy_from_plan

        if args.execute and args.dry_run:
            parser.error("choose either --dry-run or --execute, not both")
        copied = copy_from_plan(args.archive_root, execute=args.execute, logger=logger)
        if args.execute:
            console.print(f"[yellow]copied {copied} files[/yellow]")
        else:
            console.print("[green]dry-run complete; no files copied[/green]")
        return 0
    if args.command == "verify":
        from .core import verify_copy

        result = verify_copy(args.sample_checksums, logger)
        console.print(result)
        return 0
    if args.command == "report":
        from .core import generate_report

        generate_report(logger)
        console.print("[green]wrote reports/migration_report.md[/green]")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
