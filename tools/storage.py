from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from tools.common import DEFAULT_DB_PATH, MIGRATIONS_DIR, ensure_directory, iso_now, stable_json


def connect_db(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    ensure_directory(db_path.parent)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


class GardenDB:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.conn = connect_db(db_path)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "GardenDB":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def init_db(self) -> None:
        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            self.conn.executescript(migration.read_text(encoding="utf-8"))
        self.conn.commit()

    def get_session_by_raw_sha(self, raw_sha256: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM source_session WHERE raw_sha256 = ?",
            (raw_sha256,),
        ).fetchone()

    def insert_source_session(self, payload: dict[str, Any]) -> str:
        now = iso_now()
        session_id = payload.get("id") or uuid.uuid4().hex
        self.conn.execute(
            """
            INSERT INTO source_session (
                id, platform, model, title, language, import_path, archive_path, archive_codec,
                raw_sha256, normalized_sha256, raw_size_bytes, started_at, ended_at,
                tags_json, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                payload["platform"],
                payload.get("model"),
                payload["title"],
                payload.get("language"),
                payload["import_path"],
                payload.get("archive_path"),
                payload.get("archive_codec"),
                payload["raw_sha256"],
                payload["normalized_sha256"],
                payload["raw_size_bytes"],
                payload.get("started_at"),
                payload.get("ended_at"),
                stable_json(payload.get("tags", [])),
                stable_json(payload.get("metadata", {})),
                payload.get("created_at", now),
                now,
            ),
        )
        return session_id

    def insert_turns(self, session_id: str, turns: Iterable[dict[str, Any]]) -> list[str]:
        turn_ids: list[str] = []
        now = iso_now()
        for sequence_no, turn in enumerate(turns, start=1):
            turn_id = turn.get("id") or uuid.uuid4().hex
            self.conn.execute(
                """
                INSERT INTO turn (
                    id, session_id, sequence_no, role, author_name, content,
                    content_hash, created_at, metadata_json, inserted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_id,
                    session_id,
                    sequence_no,
                    turn["role"],
                    turn.get("author_name"),
                    turn["content"],
                    turn["content_hash"],
                    turn.get("created_at"),
                    stable_json(turn.get("metadata", {})),
                    now,
                ),
            )
            turn_ids.append(turn_id)
        return turn_ids

    def upsert_document(self, payload: dict[str, Any]) -> str:
        now = iso_now()
        document_id = payload.get("id") or uuid.uuid4().hex
        existing = self.conn.execute(
            "SELECT id FROM document WHERE doc_kind = ? AND slug = ?",
            (payload["doc_kind"], payload["slug"]),
        ).fetchone()
        if existing:
            document_id = existing["id"]
            self.conn.execute(
                """
                UPDATE document
                SET source_session_id = ?,
                    title = ?,
                    summary = ?,
                    body = ?,
                    language = ?,
                    status = ?,
                    tags_json = ?,
                    metadata_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    payload.get("source_session_id"),
                    payload["title"],
                    payload.get("summary", ""),
                    payload.get("body", ""),
                    payload.get("language"),
                    payload.get("status", "active"),
                    stable_json(payload.get("tags", [])),
                    stable_json(payload.get("metadata", {})),
                    now,
                    document_id,
                ),
            )
            return document_id

        self.conn.execute(
            """
            INSERT INTO document (
                id, source_session_id, doc_kind, title, slug, summary, body, language,
                status, tags_json, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                payload.get("source_session_id"),
                payload["doc_kind"],
                payload["title"],
                payload["slug"],
                payload.get("summary", ""),
                payload.get("body", ""),
                payload.get("language"),
                payload.get("status", "active"),
                stable_json(payload.get("tags", [])),
                stable_json(payload.get("metadata", {})),
                payload.get("created_at", now),
                now,
            ),
        )
        return document_id

    def replace_evidence_links(self, target_document_id: str, links: Iterable[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM evidence_link WHERE target_document_id = ?", (target_document_id,))
        now = iso_now()
        for sort_order, link in enumerate(links, start=1):
            self.conn.execute(
                """
                INSERT INTO evidence_link (
                    id, target_document_id, source_document_id, source_turn_id, session_id,
                    snippet, rationale, sort_order, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    target_document_id,
                    link.get("source_document_id"),
                    link.get("source_turn_id"),
                    link.get("session_id"),
                    link.get("snippet", ""),
                    link.get("rationale", ""),
                    link.get("sort_order", sort_order),
                    now,
                ),
            )

    def upsert_insight_claim(self, payload: dict[str, Any]) -> str:
        now = iso_now()
        insight_id = payload.get("id") or uuid.uuid4().hex
        existing = self.conn.execute(
            "SELECT id FROM insight_claim WHERE document_id = ?",
            (payload["document_id"],),
        ).fetchone()
        if existing:
            insight_id = existing["id"]
            self.conn.execute(
                """
                UPDATE insight_claim
                SET category = ?,
                    statement = ?,
                    confidence = ?,
                    status = ?,
                    evidence_count = ?,
                    contradiction_count = ?,
                    first_observed_at = ?,
                    last_observed_at = ?,
                    metadata_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["category"],
                    payload["statement"],
                    payload["confidence"],
                    payload.get("status", "candidate"),
                    payload.get("evidence_count", 0),
                    payload.get("contradiction_count", 0),
                    payload.get("first_observed_at"),
                    payload.get("last_observed_at"),
                    stable_json(payload.get("metadata", {})),
                    now,
                    insight_id,
                ),
            )
            return insight_id

        self.conn.execute(
            """
            INSERT INTO insight_claim (
                id, document_id, category, statement, confidence, status, evidence_count,
                contradiction_count, first_observed_at, last_observed_at, metadata_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                insight_id,
                payload["document_id"],
                payload["category"],
                payload["statement"],
                payload["confidence"],
                payload.get("status", "candidate"),
                payload.get("evidence_count", 0),
                payload.get("contradiction_count", 0),
                payload.get("first_observed_at"),
                payload.get("last_observed_at"),
                stable_json(payload.get("metadata", {})),
                payload.get("created_at", now),
                now,
            ),
        )
        return insight_id

    def fetch_documents(self, doc_kind: str | None = None) -> list[sqlite3.Row]:
        if doc_kind:
            return self.conn.execute(
                "SELECT * FROM document WHERE doc_kind = ? ORDER BY updated_at DESC, title ASC",
                (doc_kind,),
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM document ORDER BY updated_at DESC, title ASC"
        ).fetchall()

    def fetch_insight_claims(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT insight_claim.*, document.title AS document_title, document.slug AS document_slug
            FROM insight_claim
            INNER JOIN document ON document.id = insight_claim.document_id
            ORDER BY category ASC, confidence DESC, statement ASC
            """
        ).fetchall()

    def fetch_document_evidence(self, document_id: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """
            SELECT evidence_link.*, turn.role AS turn_role, turn.content AS turn_content
            FROM evidence_link
            LEFT JOIN turn ON turn.id = evidence_link.source_turn_id
            WHERE evidence_link.target_document_id = ?
            ORDER BY evidence_link.sort_order ASC, evidence_link.created_at ASC
            """,
            (document_id,),
        ).fetchall()

    def commit(self) -> None:
        self.conn.commit()
