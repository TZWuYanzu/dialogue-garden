from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.common import summarize_text
from tools.storage import GardenDB


def _append_session_filters(
    clauses: list[str],
    params: list[Any],
    *,
    platform: str | None = None,
    model: str | None = None,
    tag: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    session_alias: str = "source_session",
    tags_expr: str | None = None,
) -> None:
    if platform:
        clauses.append(f"{session_alias}.platform = ?")
        params.append(platform)
    if model:
        clauses.append(f"{session_alias}.model = ?")
        params.append(model)
    if tag and tags_expr:
        clauses.append(f"EXISTS (SELECT 1 FROM json_each({tags_expr}) WHERE value = ?)")
        params.append(tag)
    if from_date:
        clauses.append(f"{session_alias}.started_at >= ?")
        params.append(from_date)
    if to_date:
        clauses.append(f"{session_alias}.started_at <= ?")
        params.append(to_date)


def _append_document_filters(
    clauses: list[str],
    params: list[Any],
    *,
    kind: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    document_alias: str = "document",
) -> None:
    if kind:
        clauses.append(f"{document_alias}.doc_kind = ?")
        params.append(kind)
    if status:
        clauses.append(f"{document_alias}.status = ?")
        params.append(status)
    if tag:
        clauses.append(f"EXISTS (SELECT 1 FROM json_each({document_alias}.tags_json) WHERE value = ?)")
        params.append(tag)
    if from_date:
        clauses.append(f"{document_alias}.created_at >= ?")
        params.append(from_date)
    if to_date:
        clauses.append(f"{document_alias}.created_at <= ?")
        params.append(to_date)


def _search_turns(db: GardenDB, *, query: str | None, limit: int, **filters: Any) -> list[dict[str, Any]]:
    params: list[Any] = []
    where: list[str] = []
    if query:
        where.append("turn_fts MATCH ?")
        params.append(query)
    _append_session_filters(
        where,
        params,
        platform=filters.get("platform"),
        model=filters.get("model"),
        tag=filters.get("tag"),
        from_date=filters.get("from_date"),
        to_date=filters.get("to_date"),
        tags_expr="source_session.tags_json",
    )
    sql_params: list[Any] = []
    if query:
        sql = """
            SELECT
                turn.id,
                turn.session_id,
                turn.sequence_no,
                turn.role,
                turn.content,
                source_session.title AS session_title,
                source_session.platform,
                source_session.model,
                source_session.started_at,
                bm25(turn_fts) AS score
            FROM turn_fts
            INNER JOIN turn ON turn.rowid = turn_fts.rowid
            INNER JOIN source_session ON source_session.id = turn.session_id
        """
    else:
        sql = """
            SELECT
                turn.id,
                turn.session_id,
                turn.sequence_no,
                turn.role,
                turn.content,
                source_session.title AS session_title,
                source_session.platform,
                source_session.model,
                source_session.started_at,
                0.0 AS score
            FROM turn
            INNER JOIN source_session ON source_session.id = turn.session_id
        """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score ASC, source_session.started_at DESC, turn.sequence_no ASC LIMIT ?"
    sql_params.extend(params)
    sql_params.append(limit)
    rows = db.conn.execute(sql, sql_params).fetchall()
    return [
        {
            "result_type": "turn",
            "kind": "turn",
            "score": row["score"],
            "title": row["session_title"],
            "snippet": summarize_text(row["content"], limit=220),
            "source": {
                "session_id": row["session_id"],
                "sequence_no": row["sequence_no"],
                "role": row["role"],
                "platform": row["platform"],
                "model": row["model"],
                "started_at": row["started_at"],
            },
        }
        for row in rows
    ]


def _search_documents(db: GardenDB, *, query: str | None, limit: int, **filters: Any) -> list[dict[str, Any]]:
    params: list[Any] = []
    where: list[str] = []
    if query:
        where.append("document_fts MATCH ?")
        params.append(query)
    _append_document_filters(
        where,
        params,
        kind=filters.get("kind"),
        status=filters.get("status"),
        tag=filters.get("tag"),
        from_date=filters.get("from_date"),
        to_date=filters.get("to_date"),
    )
    if filters.get("platform"):
        where.append("source_session.platform = ?")
        params.append(filters["platform"])
    if filters.get("model"):
        where.append("source_session.model = ?")
        params.append(filters["model"])

    sql_params: list[Any] = []
    if query:
        sql = """
            SELECT
                document.id,
                document.doc_kind,
                document.title,
                document.slug,
                document.summary,
                document.status,
                document.source_session_id,
                source_session.platform,
                source_session.model,
                source_session.started_at,
                bm25(document_fts) AS score
            FROM document_fts
            INNER JOIN document ON document.rowid = document_fts.rowid
            LEFT JOIN source_session ON source_session.id = document.source_session_id
        """
    else:
        sql = """
            SELECT
                document.id,
                document.doc_kind,
                document.title,
                document.slug,
                document.summary,
                document.status,
                document.source_session_id,
                source_session.platform,
                source_session.model,
                source_session.started_at,
                0.0 AS score
            FROM document
            LEFT JOIN source_session ON source_session.id = document.source_session_id
        """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score ASC, document.updated_at DESC, document.title ASC LIMIT ?"
    sql_params.extend(params)
    sql_params.append(limit)
    rows = db.conn.execute(sql, sql_params).fetchall()
    return [
        {
            "result_type": "document",
            "kind": row["doc_kind"],
            "score": row["score"],
            "title": row["title"],
            "snippet": summarize_text(row["summary"], limit=220),
            "source": {
                "document_id": row["id"],
                "slug": row["slug"],
                "status": row["status"],
                "session_id": row["source_session_id"],
                "platform": row["platform"],
                "model": row["model"],
                "started_at": row["started_at"],
            },
        }
        for row in rows
    ]


def _search_insights(db: GardenDB, *, query: str | None, limit: int, **filters: Any) -> list[dict[str, Any]]:
    params: list[Any] = []
    where: list[str] = []
    if query:
        where.append("insight_claim_fts MATCH ?")
        params.append(query)
    if filters.get("status"):
        where.append("insight_claim.status = ?")
        params.append(filters["status"])
    if filters.get("tag"):
        where.append("EXISTS (SELECT 1 FROM json_each(document.tags_json) WHERE value = ?)")
        params.append(filters["tag"])
    if filters.get("platform"):
        where.append("source_session.platform = ?")
        params.append(filters["platform"])
    if filters.get("model"):
        where.append("source_session.model = ?")
        params.append(filters["model"])

    sql_params: list[Any] = []
    if query:
        sql = """
            SELECT
                insight_claim.id,
                insight_claim.category,
                insight_claim.statement,
                insight_claim.confidence,
                insight_claim.evidence_count,
                insight_claim.status,
                document.id AS document_id,
                document.slug,
                document.title,
                source_session.platform,
                source_session.model,
                bm25(insight_claim_fts) AS score
            FROM insight_claim_fts
            INNER JOIN insight_claim ON insight_claim.rowid = insight_claim_fts.rowid
            INNER JOIN document ON document.id = insight_claim.document_id
            LEFT JOIN source_session ON source_session.id = document.source_session_id
        """
    else:
        sql = """
            SELECT
                insight_claim.id,
                insight_claim.category,
                insight_claim.statement,
                insight_claim.confidence,
                insight_claim.evidence_count,
                insight_claim.status,
                document.id AS document_id,
                document.slug,
                document.title,
                source_session.platform,
                source_session.model,
                0.0 AS score
            FROM insight_claim
            INNER JOIN document ON document.id = insight_claim.document_id
            LEFT JOIN source_session ON source_session.id = document.source_session_id
        """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY score ASC, insight_claim.confidence DESC, insight_claim.statement ASC LIMIT ?"
    sql_params.extend(params)
    sql_params.append(limit)
    rows = db.conn.execute(sql, sql_params).fetchall()
    return [
        {
            "result_type": "insight",
            "kind": "identity_insight",
            "score": row["score"],
            "title": row["title"],
            "snippet": row["statement"],
            "source": {
                "document_id": row["document_id"],
                "slug": row["slug"],
                "category": row["category"],
                "confidence": row["confidence"],
                "evidence_count": row["evidence_count"],
                "status": row["status"],
                "platform": row["platform"],
                "model": row["model"],
            },
        }
        for row in rows
    ]


def search_records(
    db_path: Path,
    *,
    query: str | None = None,
    kind: str | None = None,
    platform: str | None = None,
    model: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    with GardenDB(db_path) as db:
        db.init_db()
        filters = {
            "kind": kind if kind not in {None, "turn"} else None,
            "platform": platform,
            "model": model,
            "tag": tag,
            "status": status,
            "from_date": from_date,
            "to_date": to_date,
        }
        results: list[dict[str, Any]] = []
        if kind in {None, "turn"}:
            results.extend(_search_turns(db, query=query, limit=limit, **filters))
        if kind != "turn":
            results.extend(_search_documents(db, query=query, limit=limit, **filters))
        if kind in {None, "identity_insight"}:
            results.extend(_search_insights(db, query=query, limit=limit, **filters))
    return sorted(results, key=lambda item: (item["score"], item["title"]))[:limit]


def format_search_results(results: list[dict[str, Any]], *, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(results, ensure_ascii=False, indent=2)
    if not results:
        return "No results."

    lines: list[str] = []
    for index, item in enumerate(results, start=1):
        lines.append(f"{index}. [{item['kind']}] {item['title']}")
        lines.append(f"   {item['snippet']}")
        lines.append(f"   source={json.dumps(item['source'], ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines)
