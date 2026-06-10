from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.common import CARDS_DIR, MANIFESTS_DIR, PROFILES_DIR, ensure_directory
from tools.storage import GardenDB


def _write_lines(path: Path, lines: list[str]) -> None:
    ensure_directory(path.parent)
    payload = "\n".join(lines)
    if lines:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def export_manifests(db: GardenDB) -> dict[str, Path]:
    documents = db.conn.execute(
        """
        SELECT
            document.*,
            source_session.platform AS source_platform,
            source_session.model AS source_model,
            source_session.started_at AS source_started_at
        FROM document
        LEFT JOIN source_session ON source_session.id = document.source_session_id
        ORDER BY document.doc_kind ASC, document.slug ASC
        """
    ).fetchall()

    document_lines = [
        json.dumps(
            {
                "id": row["id"],
                "doc_kind": row["doc_kind"],
                "slug": row["slug"],
                "title": row["title"],
                "summary": row["summary"],
                "status": row["status"],
                "language": row["language"],
                "source_session_id": row["source_session_id"],
                "source_platform": row["source_platform"],
                "source_model": row["source_model"],
                "source_started_at": row["source_started_at"],
                "tags": json.loads(row["tags_json"] or "[]"),
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "updated_at": row["updated_at"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for row in documents
    ]
    documents_manifest = MANIFESTS_DIR / "documents.jsonl"
    _write_lines(documents_manifest, document_lines)

    insights = db.fetch_insight_claims()
    insight_lines = [
        json.dumps(
            {
                "id": row["id"],
                "document_id": row["document_id"],
                "document_slug": row["document_slug"],
                "document_title": row["document_title"],
                "category": row["category"],
                "statement": row["statement"],
                "confidence": row["confidence"],
                "status": row["status"],
                "evidence_count": row["evidence_count"],
                "contradiction_count": row["contradiction_count"],
                "first_observed_at": row["first_observed_at"],
                "last_observed_at": row["last_observed_at"],
                "metadata": json.loads(row["metadata_json"] or "{}"),
                "updated_at": row["updated_at"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for row in insights
    ]
    insights_manifest = MANIFESTS_DIR / "insights.jsonl"
    _write_lines(insights_manifest, insight_lines)

    return {
        "documents": documents_manifest,
        "insights": insights_manifest,
    }


def export_cards(db: GardenDB) -> list[Path]:
    ensure_directory(CARDS_DIR)
    written_paths: list[Path] = []
    cards = db.fetch_documents("knowledge_card")
    for card in cards:
        tags = json.loads(card["tags_json"] or "[]")
        frontmatter_lines = [
            "---",
            f"doc_kind: {card['doc_kind']}",
            f"slug: {card['slug']}",
            f"status: {card['status']}",
            f"source_session_id: {card['source_session_id']}",
            f"updated_at: {card['updated_at']}",
            "tags:",
        ]
        for tag in tags:
            frontmatter_lines.append(f"  - {tag}")
        frontmatter_lines.extend(["---", "", card["body"].strip(), ""])
        content = "\n".join(frontmatter_lines)
        path = CARDS_DIR / f"{card['slug']}.md"
        path.write_text(content, encoding="utf-8")
        written_paths.append(path)
    return written_paths


def export_profiles(db: GardenDB) -> list[Path]:
    ensure_directory(PROFILES_DIR)
    path = PROFILES_DIR / "identity_overview.md"
    insights = db.fetch_insight_claims()
    sections = ["# Identity Overview", ""]
    if not insights:
        sections.extend(
            [
                "No identity insights have been promoted yet.",
                "",
                "This export is reserved for evidence-backed claims about values, work style, preferences, and operating rules.",
            ]
        )
    else:
        current_category = None
        for insight in insights:
            if insight["category"] != current_category:
                current_category = insight["category"]
                sections.extend(["", f"## {current_category.replace('_', ' ').title()}"])
            sections.append(
                f"- {insight['statement']} (confidence={insight['confidence']:.2f}, evidence={insight['evidence_count']}, status={insight['status']})"
            )

    path.write_text("\n".join(sections).strip() + "\n", encoding="utf-8")
    return [path]


def rebuild_exports(db_path: Path) -> dict[str, Any]:
    with GardenDB(db_path) as db:
        db.init_db()
        manifests = export_manifests(db)
        cards = export_cards(db)
        profiles = export_profiles(db)

    return {
        "manifests": {name: str(path) for name, path in manifests.items()},
        "cards": [str(path) for path in cards],
        "profiles": [str(path) for path in profiles],
    }
