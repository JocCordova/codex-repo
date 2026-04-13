from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

from clustering import cluster_items, select_top_clusters
from config_loader import ConfigError, load_configs
from env_loader import load_env_file
from feedback import maybe_run_weekly_update
from notion_sync import sync_to_notion
from rss import fetch_all
from scoring import score_items
from storage import ensure_dirs, load_seen_ids, render_markdown, save_digest, save_seen_ids
from timezones import resolve_timezone
from whatsapp import send_digest


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily RSS intelligence agent")
    parser.add_argument("--config", default="config.yml", help="Path to config.yml")
    parser.add_argument("--topics", default="topics.yml", help="Path to topics.yml")
    return parser.parse_args()


def main() -> int:
    configure_logging()
    logger = logging.getLogger("main")
    args = parse_args()
    load_env_file(Path(__file__).resolve().with_name(".env"))

    try:
        config, topics = load_configs(args.config, args.topics)
    except ConfigError as exc:
        logger.error("Config error: %s", exc)
        return 1

    run_cfg = config["run"]
    out_dir, state_dir = ensure_dirs(run_cfg["output_dir"], run_cfg["state_dir"])

    all_items = fetch_all(config["feeds"], int(run_cfg["max_items_per_feed"]))
    seen = load_seen_ids(state_dir)
    all_items = [{**item, "is_new": item["id"] not in seen} for item in all_items]
    new_items = [item for item in all_items if item["is_new"]]
    logger.info("Fetched %d total, %d new after dedup", len(all_items), len(new_items))

    min_selected_items = int(run_cfg.get("min_selected_items", 5))
    candidate_items = list(new_items)
    if len(candidate_items) < min_selected_items:
        seen_candidates = [item for item in all_items if not item["is_new"]]
        backfill_needed = min_selected_items - len(candidate_items)
        candidate_items.extend(seen_candidates[:backfill_needed])
        if seen_candidates:
            logger.info(
                "Only %d new items available; backfilled %d previously seen items to reach %d candidates",
                len(new_items),
                min(len(seen_candidates), backfill_needed),
                len(candidate_items),
            )

    scored = score_items(candidate_items, topics, float(run_cfg["min_relevance_score"]), min_selected_items)

    cluster_cfg = config["clustering"]
    clusters = cluster_items(scored, int(cluster_cfg["max_clusters"]), int(cluster_cfg["min_cluster_size"]))
    selected = select_top_clusters(clusters, int(run_cfg["top_clusters"]), min_selected_items)

    try:
        tz = resolve_timezone(run_cfg["timezone"])
    except ValueError as exc:
        logger.error("Config error: %s", exc)
        return 1
    run_date = datetime.now(tz).date().isoformat()
    markdown = render_markdown(run_date, selected)
    raw_items = all_items if run_cfg.get("save_raw_items", False) else None
    artifacts = save_digest(out_dir, run_date, markdown, selected, raw_items)
    logger.info("Artifacts: %s", artifacts)

    sync_to_notion(selected, config["notion"], run_cfg["timezone"])
    send_digest(selected, config["whatsapp"], config.get("notion"))
    maybe_run_weekly_update(config["feedback"])

    updated_seen = seen.union(item["id"] for item in all_items)
    save_seen_ids(state_dir, updated_seen)
    logger.info("Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
