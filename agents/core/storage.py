from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .types import FormulaEntry, ReviewRecord, TopicCard


def _read_json(path: Path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class KnowledgeStore:

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "reviews").mkdir(exist_ok=True)
        (self.base_dir / "bloggers").mkdir(exist_ok=True)

    @property
    def _formulas_path(self) -> Path:
        return self.base_dir / "formulas.json"

    @property
    def _topics_path(self) -> Path:
        return self.base_dir / "topics.json"

    # ── Formulas ──

    def load_formulas(self) -> list[FormulaEntry]:
        raw = _read_json(self._formulas_path)
        return [FormulaEntry(**item) for item in raw]

    def save_formulas(self, entries: list[FormulaEntry]) -> None:
        _write_json(self._formulas_path, [e.model_dump() for e in entries])

    def add_formula(self, entry: FormulaEntry) -> None:
        entries = self.load_formulas()
        entries.append(entry)
        self.save_formulas(entries)

    # ── Topics ──

    def load_topics(self) -> list[TopicCard]:
        raw = _read_json(self._topics_path)
        return [TopicCard(**item) for item in raw]

    def save_topics(self, topics: list[TopicCard]) -> None:
        _write_json(self._topics_path, [t.model_dump() for t in topics])

    def add_topic(self, topic: TopicCard) -> None:
        topics = self.load_topics()
        topics.append(topic)
        self.save_topics(topics)

    def update_topic(self, name: str, **kwargs) -> bool:
        topics = self.load_topics()
        for t in topics:
            if t.name == name:
                for k, v in kwargs.items():
                    if hasattr(t, k):
                        setattr(t, k, v)
                self.save_topics(topics)
                return True
        return False

    # ── Reviews ──

    def load_reviews(self) -> list[ReviewRecord]:
        reviews_dir = self.base_dir / "reviews"
        results = []
        for f in sorted(reviews_dir.glob("*.json")):
            raw = json.loads(f.read_text(encoding="utf-8"))
            results.append(ReviewRecord(**raw))
        return results

    def save_review(self, record: ReviewRecord) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.base_dir / "reviews" / f"review_{ts}.json"
        _write_json(path, record.model_dump())
        return path

    # ── Bloggers ──

    def load_blogger_profiles(self) -> list[dict]:
        bloggers_dir = self.base_dir / "bloggers"
        results = []
        for f in sorted(bloggers_dir.glob("*.json")):
            results.append(json.loads(f.read_text(encoding="utf-8")))
        return results

    def save_blogger_profile(self, profile: dict) -> Path:
        user_id = profile.get("user_id", "unknown")
        path = self.base_dir / "bloggers" / f"{user_id}.json"
        _write_json(path, profile)
        return path
