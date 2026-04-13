from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised for malformed configuration files."""


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing YAML file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"YAML root must be a mapping in: {path}")
    return data


def load_configs(config_path: str = "config.yml", topics_path: str = "topics.yml") -> tuple[dict[str, Any], dict[str, Any]]:
    config = _read_yaml(Path(config_path))
    topics = _read_yaml(Path(topics_path))

    required_sections = ["run", "feeds", "notion", "whatsapp", "clustering", "feedback"]
    missing = [section for section in required_sections if section not in config]
    if missing:
        raise ConfigError(f"Missing config sections: {', '.join(missing)}")

    if "topics" not in topics or not isinstance(topics["topics"], list):
        raise ConfigError("topics.yml must include a list at key 'topics'")

    return config, topics
