from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)


def cluster_items(items: list[dict[str, Any]], max_clusters: int, min_cluster_size: int) -> list[dict[str, Any]]:
    if not items:
        return []
    if len(items) == 1:
        return [{"cluster_id": 0, "items": items, "size": 1, "avg_score": items[0]["score"], "topics": items[0]["matched_topics"]}]

    corpus = [f"{item['title']} {item.get('summary', '')}" for item in items]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform(corpus)

    n_clusters = min(max_clusters, len(items))
    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = model.fit_predict(matrix)

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item, label in zip(items, labels, strict=True):
        grouped[int(label)].append(item)

    clusters: list[dict[str, Any]] = []
    for cluster_id, cluster_items in grouped.items():
        if len(cluster_items) < min_cluster_size:
            continue
        cluster_items.sort(key=lambda x: x["score"], reverse=True)
        avg_score = sum(x["score"] for x in cluster_items) / len(cluster_items)
        topics = sorted({t for x in cluster_items for t in x.get("matched_topics", [])})
        clusters.append(
            {
                "cluster_id": cluster_id,
                "items": cluster_items,
                "size": len(cluster_items),
                "avg_score": round(avg_score, 3),
                "topics": topics,
                "headline": cluster_items[0]["title"],
            }
        )

    clusters.sort(key=lambda c: (c["avg_score"], c["size"]), reverse=True)
    logger.info("Built %d clusters", len(clusters))
    return clusters


def select_top_clusters(clusters: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    return clusters[:top_n]
