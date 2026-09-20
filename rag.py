"""
rag.py — Retrieval-Augmented Generation engine for EcoMind AI.

Loads the curated sustainability knowledge base (data/kb.json), builds a
TF-IDF vector for each entry, and answers a query by:
  1. retrieving the top-k most similar knowledge-base entries
     (cosine similarity over TF-IDF vectors), and
  2. composing a grounded answer from the retrieved passages —
     nothing is generated beyond what the knowledge base contains.

This mirrors the retrieval logic used in the browser demo (ecomind_ai.html)
so both surfaces stay consistent, and it's what the frontend's "Connected
to backend" mode actually calls.
"""

import json
import random
from pathlib import Path
from typing import List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import settings
from logging_config import logger

CATEGORY_LABELS = {
    "energy": "Energy",
    "water": "Water",
    "waste": "Waste",
    "transport": "Transport",
    "food": "Food & agriculture",
    "biodiversity": "Biodiversity",
    "climate": "Climate action",
    "cities": "Cities & policy",
}

OPENERS = [
    "Here's what tends to make the biggest difference:",
    "A few things are worth trying here:",
    "Based on the knowledge base, this is a solid place to start:",
    "This is a common question — here's what usually helps:",
]

REQUIRED_KB_FIELDS = {"id", "category", "title", "tags", "content"}

# Deliberately NOT using scikit-learn's built-in stop_words="english" list:
# it's the old, widely-flagged Glasgow stop-word list, and it treats plainly
# useful nouns as noise — "bill" and "system" among them — while leaving
# generic verbs like "cut" untouched. That mismatch was causing the backend
# to silently drop "bill" from queries like "lower my energy bill", so a
# generic word like "cut" (matched by many unrelated entries, e.g. water
# conservation tips) dominated retrieval instead. This list mirrors the one
# used by the offline JS engine in ecomind_ai.html, so both surfaces agree.
STOPWORDS = sorted({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "for", "and", "or", "but", "with", "as", "at",
    "by", "from", "this", "that", "these", "those", "it", "its", "i", "you",
    "your", "my", "how", "what", "why", "do", "does", "can", "could",
    "should", "would", "will", "get", "make", "reduce", "cut", "lower",
    "into", "about", "more", "less", "than", "not", "so", "if", "then",
})


class KnowledgeBaseError(RuntimeError):
    """Raised when the knowledge base file is missing or malformed."""


class EcoMindRAG:
    """A small, self-contained retrieval-augmented assistant."""

    def __init__(self, data_path: Path = None):
        self.data_path = Path(data_path) if data_path else settings.kb_path
        self.kb = self._load_kb(self.data_path)

        corpus = [
            f"{d['title']} {d['tags']} {d['content']} {d['category']}"
            for d in self.kb
        ]
        self.vectorizer = TfidfVectorizer(stop_words=STOPWORDS)
        self.doc_matrix = self.vectorizer.fit_transform(corpus)
        logger.info(
            "RAG engine ready: %d knowledge-base entries loaded from %s",
            len(self.kb), self.data_path,
        )

    def _load_kb(self, path: Path) -> list:
        if not path.exists():
            raise KnowledgeBaseError(f"Knowledge base file not found: {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise KnowledgeBaseError(f"Knowledge base file is not valid JSON: {exc}") from exc

        if not isinstance(data, list) or not data:
            raise KnowledgeBaseError("Knowledge base must be a non-empty JSON array")

        for i, entry in enumerate(data):
            missing = REQUIRED_KB_FIELDS - entry.keys()
            if missing:
                raise KnowledgeBaseError(
                    f"Knowledge base entry {i} is missing required field(s): {sorted(missing)}"
                )
            if entry["category"] not in CATEGORY_LABELS:
                raise KnowledgeBaseError(
                    f"Knowledge base entry {i} has unknown category '{entry['category']}'"
                )
        return data

    def retrieve(self, query: str, k: int = None, min_score: float = None) -> List[Tuple[dict, float]]:
        """Return the top-k KB entries most similar to the query."""
        if not query or not query.strip():
            raise ValueError("Query must not be empty")
        if len(query) > settings.max_query_len:
            raise ValueError(
                f"Query is too long ({len(query)} chars, max {settings.max_query_len})"
            )

        k = k if k is not None else settings.retrieval_k
        min_score = min_score if min_score is not None else settings.min_score

        q_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.doc_matrix)[0]
        ranked = sorted(
            zip(self.kb, scores), key=lambda pair: pair[1], reverse=True
        )
        return [(doc, score) for doc, score in ranked[:k] if score > min_score]

    def compose_answer(self, matches: List[Tuple[dict, float]]) -> dict:
        """Turn retrieved KB entries into a grounded, templated answer."""
        if not matches:
            cats = ", ".join(CATEGORY_LABELS.values())
            return {
                "answer": (
                    "I don't have a confident match for that in my knowledge "
                    f"base yet. I can currently speak to: {cats}. Try "
                    "rephrasing, or ask about one of those topics directly."
                ),
                "sources": [],
            }

        lines = [random.choice(OPENERS)]
        for doc, _ in matches:
            lines.append(f"- {doc['content']}")
        if len(matches) > 1:
            lines.append(
                "Start with whichever fits your situation — small, "
                "repeatable changes add up faster than one big gesture."
            )

        sources = sorted({CATEGORY_LABELS[doc["category"]] for doc, _ in matches})
        return {"answer": "\n".join(lines), "sources": sources}

    def answer(self, query: str, k: int = None) -> dict:
        matches = self.retrieve(query, k=k)
        result = self.compose_answer(matches)
        result["matched_entries"] = [
            {"id": doc["id"], "title": doc["title"], "score": round(float(score), 4)}
            for doc, score in matches
        ]
        logger.debug(
            "query=%r matched=%d top_score=%.3f",
            query, len(matches), matches[0][1] if matches else 0.0,
        )
        return result


# ---- Carbon footprint estimator (shares the RAG engine for its tip) ----

DIET_FACTORS_TONNES = {"meat": 3.3, "average": 2.5, "veg": 1.7, "vegan": 1.5}
CAR_KG_PER_KM = 0.192
ELEC_KG_PER_KWH = 0.475
FLIGHT_SHORT_TONNES = 0.09
FLIGHT_LONG_TONNES = 0.5
GLOBAL_AVG_TONNES = 4.7


def estimate_footprint(rag: EcoMindRAG, car_km_week: float, elec_kwh_month: float,
                        diet: str, short_flights: int, long_flights: int) -> dict:
    # Validation — mirrors what Pydantic already checks at the API layer,
    # but this function is also called directly (e.g. from tests, from
    # test_rag.py, from a future CLI), so it has to hold its own ground.
    for name, value in (
        ("car_km_week", car_km_week),
        ("elec_kwh_month", elec_kwh_month),
    ):
        if value < 0:
            raise ValueError(f"{name} must be >= 0, got {value}")
    for name, value in (("short_flights", short_flights), ("long_flights", long_flights)):
        if value < 0:
            raise ValueError(f"{name} must be >= 0, got {value}")
    if diet not in DIET_FACTORS_TONNES:
        raise ValueError(
            f"diet must be one of {sorted(DIET_FACTORS_TONNES)}, got '{diet}'"
        )

    transport_t = (car_km_week * 52 * CAR_KG_PER_KM) / 1000
    energy_t = (elec_kwh_month * 12 * ELEC_KG_PER_KWH) / 1000
    diet_t = DIET_FACTORS_TONNES[diet]
    flights_t = short_flights * FLIGHT_SHORT_TONNES + long_flights * FLIGHT_LONG_TONNES
    total = transport_t + energy_t + diet_t + flights_t

    breakdown = {
        "transport": round(transport_t, 2),
        "energy": round(energy_t, 2),
        "food": round(diet_t, 2),
        "flights": round(flights_t, 2),
    }
    biggest_key = max(breakdown, key=breakdown.get)
    tip = rag.answer(f"{biggest_key} reduce lower emissions", k=1)

    logger.debug("footprint total=%.2ft biggest=%s", total, biggest_key)

    return {
        "total_tonnes_co2e": round(total, 2),
        "vs_global_average_tonnes": GLOBAL_AVG_TONNES,
        "breakdown": breakdown,
        "biggest_category": biggest_key,
        "tip": tip["answer"],
    }
