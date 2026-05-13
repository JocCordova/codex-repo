"""Compatibility wrapper for the home_storage_agent CLI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from home_storage_agent.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["report", *sys.argv[1:]]))
