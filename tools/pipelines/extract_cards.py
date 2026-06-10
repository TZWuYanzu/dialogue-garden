from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.common import slugify, summarize_text
from tools.storage import GardenDB


def _load_tags(row: dict[str, Any]) -> list[str]:
    raw_tags = row["tags_json"] if "tags_json" in row.keys() else "[]"
    return json.loads(raw_tags or "[]")


def _build_card_body(session: Any, turns: list[Any]) -> str:
    header = [
        f"# {session['title']}",
        "",
        "## Context",
        f"- Platform: {session['platform']}",
        f"- Model: {session['model'] or 'unknown'}",
        f"- Language: {session['language'] or 'unknown'}",
        f"- Turns: {len(turns)}",
    ]
    if session["started_at"]:
        header.append(f"- Started At: {session['started_at']}")
    if session["ended_at"]:
        header.append(f"- Ended At: {session['ended_at']}")

    highlights = ["", "## Highlights"]
    for turn in turns[:6]:
        snippet = summarize_text(turn["content"], limit=180)
        highlights.append(f"- [{turn['role']}] {snippet}")

    references = [
        "",
        "## Provenance",
        f"- Session ID: `{session['id']}`",
        f"- Raw SHA256: `{session['raw_sha256']}`",
        f"- Import Path: `{session['import_path']}`",
    ]
    return "\n".join(header + highlights + references).strip() + "\n"


def extract_cards(db_path: Path, *, session_id: str | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    with GardenDB(db_path) as db:
        db.init_db()
        params: tuple[str, ...] = ()
        query = "SELECT * FROM source_session"
        if session_id:
            query += " WHERE id = ?"
            params = (session_id,)
        query += " ORDER BY created_at ASC"
        sessions = db.conn.execute(query, params).fetchall()

        for session in sessions:
            turns = db.conn.execute(
                "SELECT * FROM turn WHERE session_id = ? ORDER BY sequence_no ASC",
                (session["id"],),
            ).fetchall()
            if not turns:
                continue

            source_document = db.conn.execute(
                """
                SELECT * FROM document
                WHERE source_session_id = ? AND doc_kind = 'raw_session'
                LIMIT 1
                """,
                (session["id"],),
            ).fetchone()

            card_title = f"{session['title']} Knowledge Card"
            card_slug = f"{slugify(session['title'])}-knowledge-{session['id'][:8]}"
            card_summary = " | ".join(
                summarize_text(turn["content"], limit=90) for turn in turns[:3]
            )
            document_id = db.upsert_document(
                {
                    "source_session_id": session["id"],
                    "doc_kind": "knowledge_card",
                    "title": card_title,
                    "slug": card_slug,
                    "summary": summarize_text(card_summary, limit=240),
                    "body": _build_card_body(session, turns),
                    "language": session["language"],
                    "status": "draft",
                    "tags": _load_tags(session),
                    "metadata": {
                        "generator": "heuristic-v1",
                        "generated_from_session_id": session["id"],
                        "generated_from_raw_document_id": source_document["id"] if source_document else None,
                    },
                }
            )
            evidence_links = []
            for order, turn in enumerate(turns[:6], start=1):
                evidence_links.append(
                    {
                        "source_document_id": source_document["id"] if source_document else None,
                        "source_turn_id": turn["id"],
                        "session_id": session["id"],
                        "snippet": summarize_text(turn["content"], limit=180),
                        "rationale": f"Representative {turn['role']} turn from session summary.",
                        "sort_order": order,
                    }
                )
            db.replace_evidence_links(document_id, evidence_links)
            results.append(
                {
                    "session_id": session["id"],
                    "document_id": document_id,
                    "title": card_title,
                    "evidence_count": len(evidence_links),
                }
            )

        db.commit()
    return results
