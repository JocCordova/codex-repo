from __future__ import annotations

import logging
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)


def _count_matches(text: str, terms: list[str]) -> int:
    t = text.lower()
    return sum(1 for term in terms if term.lower() in t)


def score_items(items: list[dict[str, Any]], topics_cfg: dict[str, Any], min_score: float, min_items: int = 0) -> list[dict[str, Any]]:
    topics = topics_cfg.get("topics", [])
    method_terms = topics_cfg.get("method_terms", [])
    rules = topics_cfg.get("selection_rules", {})

    scored: list[dict[str, Any]] = []
    below_threshold: list[dict[str, Any]] = []
    source_counter = Counter(item["source"] for item in items)

    for item in items:
        text = f"{item['title']}\n{item.get('summary', '')}"
        per_topic_scores: dict[str, float] = {}
        matched_topics: list[str] = []
        total = 0.0

        for topic in topics:
            name = topic["name"]
            topic_weight = float(topic.get("weight", 1.0))
            pos = _count_matches(text, topic.get("keywords", []))
            neg = _count_matches(text, topic.get("negative_keywords", []))
            topic_score = max((pos * topic_weight) - (neg * 0.75), 0.0)
            if topic_score > 0:
                per_topic_scores[name] = round(topic_score, 3)
                matched_topics.append(name)
                total += topic_score

        if rules.get("boost_if_matches_multiple_topics") and len(matched_topics) > 1:
            total += float(rules["boost_if_matches_multiple_topics"])

        if rules.get("boost_if_contains_method_terms") and _count_matches(text, method_terms) > 0:
            total += float(rules["boost_if_contains_method_terms"])

        if rules.get("penalize_duplicate_publishers") and source_counter[item["source"]] > 3:
            total *= 0.9

        total *= float(item.get("feed_weight", 1.0))
        final_score = round(total, 3)

        enriched = {**item, "score": final_score, "matched_topics": matched_topics, "topic_scores": per_topic_scores}
        if final_score >= min_score:
            scored.append(enriched)
        else:
            below_threshold.append(enriched)

    scored.sort(key=lambda x: x["score"], reverse=True)
    below_threshold.sort(key=lambda x: x["score"], reverse=True)

    if min_items > 0 and len(scored) < min_items:
        needed = min(min_items - len(scored), len(below_threshold))
        if needed:
            scored.extend(below_threshold[:needed])
            scored.sort(key=lambda x: x["score"], reverse=True)
            logger.info(
                "Kept %d items above threshold and topped up with %d more to reach %d",
                len(scored) - needed,
                needed,
                len(scored),
            )
        else:
            logger.info("Kept %d relevant items after scoring", len(scored))
    else:
        logger.info("Kept %d relevant items after scoring", len(scored))

    return scored
