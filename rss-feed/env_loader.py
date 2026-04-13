from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def load_env_file(path: str | Path, override: bool = False) -> int:
    env_path = Path(path)
    if not env_path.exists():
        logger.info("No .env file found at %s", env_path)
        return 0

    loaded = 0
    with env_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("export "):
                line = line[7:].strip()

            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not key:
                continue

            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]

            if not override and key in os.environ:
                continue

            os.environ[key] = value
            loaded += 1

    logger.info("Loaded %d environment variables from %s", loaded, env_path.name)
    return loaded
