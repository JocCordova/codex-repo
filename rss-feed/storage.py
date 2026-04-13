from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def ensure_dirs(output_dir: str, state_dir: str) -> tuple[Path, Path]:
    out = Path(output_dir)
    state = Path(state_dir)
    out.mkdir(parents=True, exist_ok=True)
    state.mkdir(parents=True, exist_ok=True)
    return out, state


def load_seen_ids(state_dir: Path) -> set[str]:
    path = state_dir / "seen_items.json"
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return set(data)


def save_seen_ids(state_dir: Path, ids: set[str]) -> None:
    path = state_dir / "seen_items.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(sorted(ids), handle, indent=2)


def save_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def render_markdown(run_date: str, clusters: list[dict[str, Any]]) -> str:
    lines = [f"# RSS Intelligence Digest — {run_date}", ""]
    if not clusters:
        lines.append("No relevant items today.")
        return "\n".join(lines)

    for idx, cluster in enumerate(clusters, start=1):
        lines.append(f"## {idx}. {cluster.get('headline', 'Untitled cluster')}")
        lines.append(f"- Cluster size: **{cluster['size']}**")
        lines.append(f"- Avg score: **{cluster['avg_score']}**")
        lines.append(f"- Topics: {', '.join(cluster.get('topics', [])) or 'none'}")
        lines.append("")
        for item in cluster["items"]:
            lines.append(f"- [{item['title']}]({item['url']}) — {item['source']} (score: {item['score']})")
        lines.append("")
    return "\n".join(lines)


def save_digest(output_dir: Path, run_date: str, markdown: str, clusters: list[dict[str, Any]], raw_items: list[dict[str, Any]] | None) -> dict[str, str]:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = output_dir / f"digest_{stamp}.md"
    json_path = output_dir / f"digest_{stamp}.json"

    md_path.write_text(markdown, encoding="utf-8")
    save_json(json_path, {"date": run_date, "clusters": clusters})

    paths = {"markdown": str(md_path), "json": str(json_path)}
    if raw_items is not None:
        raw_path = output_dir / f"raw_items_{stamp}.json"
        save_json(raw_path, raw_items)
        paths["raw"] = str(raw_path)

    logger.info("Wrote digest artifacts to %s", output_dir)
    return paths
