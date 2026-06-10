from __future__ import annotations

import gzip
import re
from pathlib import Path
from typing import Any

from tools.common import (
    ARCHIVES_DIR,
    ROOT_DIR,
    ensure_directory,
    iter_markdown_files,
    sha256_bytes,
    sha256_text,
    slugify,
    summarize_text,
)
from tools.storage import GardenDB

TURN_INLINE_PATTERNS = [
    re.compile(r"^\*\*(system|user|assistant|tool)\*\*:\s*(.*)$", re.IGNORECASE),
    re.compile(r"^(system|user|assistant|tool)\s*:\s*(.*)$", re.IGNORECASE),
]

TURN_HEADER_PATTERNS = [
    re.compile(r"^(?:#{1,6}\s*)?(system|user|assistant|tool)(?:\s*\([^)]+\))?\s*:?\s*$", re.IGNORECASE),
    re.compile(r"^\*\*(system|user|assistant|tool)\*\*$", re.IGNORECASE),
]


def normalize_markdown(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _parse_tags(value: str) -> list[str]:
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]
    if "," in stripped:
        items = stripped.split(",")
    else:
        items = stripped.split()
    return [item.strip().strip("'\"") for item in items if item.strip()]


def parse_frontmatter(raw_text: str) -> tuple[dict[str, Any], str]:
    if not raw_text.startswith("---\n"):
        return {}, raw_text

    parts = raw_text.split("\n---\n", 1)
    if len(parts) != 2:
        return {}, raw_text

    frontmatter_block = parts[0][4:]
    body = parts[1]
    metadata: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in frontmatter_block.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue

        stripped = line.lstrip()
        if stripped.startswith("- ") and current_list_key:
            metadata.setdefault(current_list_key, []).append(stripped[2:].strip().strip("'\""))
            continue

        if ":" not in line:
            current_list_key = None
            continue

        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        current_list_key = None

        if not value:
            metadata[key] = []
            current_list_key = key
            continue

        if key == "tags":
            metadata[key] = _parse_tags(value)
            continue

        metadata[key] = value.strip("'\"")

    return metadata, body


def detect_turn_marker(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    for pattern in TURN_INLINE_PATTERNS:
        match = pattern.match(stripped)
        if match:
            return match.group(1).lower(), match.group(2).strip()
    for pattern in TURN_HEADER_PATTERNS:
        match = pattern.match(stripped)
        if match:
            return match.group(1).lower(), ""
    return None


def split_turns(body: str) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    current_role: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_role, current_lines
        content = normalize_markdown("\n".join(current_lines))
        if current_role and content:
            turns.append(
                {
                    "role": current_role,
                    "author_name": None,
                    "content": content,
                    "content_hash": sha256_text(content),
                    "metadata": {},
                }
            )
        current_role = None
        current_lines = []

    for line in body.splitlines():
        marker = detect_turn_marker(line)
        if marker:
            flush()
            current_role, initial_content = marker
            if initial_content:
                current_lines.append(initial_content)
            continue
        current_lines.append(line)

    flush()

    if turns:
        return turns

    normalized = normalize_markdown(body)
    return [
        {
            "role": "unknown",
            "author_name": None,
            "content": normalized,
            "content_hash": sha256_text(normalized),
            "metadata": {"parser": "fallback-single-block"},
        }
    ]


def archive_raw_markdown(source_path: Path, raw_bytes: bytes, raw_sha256: str, platform: str) -> tuple[str, str]:
    archive_dir = ensure_directory(ARCHIVES_DIR / slugify(platform))
    try:
        import zstandard

        archive_path = archive_dir / f"{raw_sha256}.md.zst"
        compressor = zstandard.ZstdCompressor(level=6)
        with archive_path.open("wb") as handle:
            handle.write(compressor.compress(raw_bytes))
        return str(archive_path.relative_to(ROOT_DIR)), "zstd"
    except ImportError:
        archive_path = archive_dir / f"{raw_sha256}.md.gz"
        with gzip.open(archive_path, "wb") as handle:
            handle.write(raw_bytes)
        return str(archive_path.relative_to(ROOT_DIR)), "gzip"


def ingest_file(
    db: GardenDB,
    source_path: Path,
    *,
    platform: str,
    model: str | None = None,
    language: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_bytes = source_path.read_bytes()
    raw_text = raw_bytes.decode("utf-8", errors="replace")
    frontmatter, body = parse_frontmatter(raw_text)
    normalized_body = normalize_markdown(body)
    raw_sha256 = sha256_bytes(raw_bytes)
    existing = db.get_session_by_raw_sha(raw_sha256)
    if existing:
        return {"status": "duplicate", "session_id": existing["id"], "path": str(source_path)}

    merged_tags = sorted(
        {
            *frontmatter.get("tags", []),
            *(tags or []),
        }
    )
    merged_metadata = {
        "imported_from": str(source_path),
        "frontmatter": frontmatter,
        **(metadata or {}),
    }
    session_title = (
        title
        or frontmatter.get("title")
        or source_path.stem.replace("_", " ").replace("-", " ").strip()
        or f"{platform} session {raw_sha256[:8]}"
    )
    turns = split_turns(normalized_body)
    archive_path, archive_codec = archive_raw_markdown(source_path, raw_bytes, raw_sha256, platform)
    session_id = db.insert_source_session(
        {
            "platform": platform,
            "model": model or frontmatter.get("model"),
            "title": session_title,
            "language": language or frontmatter.get("language"),
            "import_path": str(source_path),
            "archive_path": archive_path,
            "archive_codec": archive_codec,
            "raw_sha256": raw_sha256,
            "normalized_sha256": sha256_text(normalized_body),
            "raw_size_bytes": len(raw_bytes),
            "started_at": frontmatter.get("started_at"),
            "ended_at": frontmatter.get("ended_at"),
            "tags": merged_tags,
            "metadata": merged_metadata,
        }
    )
    turn_ids = db.insert_turns(session_id, turns)

    raw_session_slug = f"{slugify(session_title)}-{raw_sha256[:12]}"
    raw_document_id = db.upsert_document(
        {
            "source_session_id": session_id,
            "doc_kind": "raw_session",
            "title": session_title,
            "slug": raw_session_slug,
            "summary": summarize_text(normalized_body),
            "body": normalized_body,
            "language": language or frontmatter.get("language"),
            "status": "active",
            "tags": merged_tags,
            "metadata": {
                "platform": platform,
                "model": model or frontmatter.get("model"),
                "source_turn_count": len(turns),
                "archive_path": archive_path,
                "archive_codec": archive_codec,
            },
        }
    )
    db.commit()
    return {
        "status": "ingested",
        "session_id": session_id,
        "document_id": raw_document_id,
        "turn_count": len(turn_ids),
        "path": str(source_path),
    }


def ingest_paths(
    db_path: Path,
    paths: list[str],
    *,
    platform: str,
    model: str | None = None,
    language: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    files = iter_markdown_files(paths)
    results: list[dict[str, Any]] = []
    with GardenDB(db_path) as db:
        db.init_db()
        for source_path in files:
            result = ingest_file(
                db,
                source_path,
                platform=platform,
                model=model,
                language=language,
                title=title,
                tags=tags,
                metadata=metadata,
            )
            results.append(result)
    return results
