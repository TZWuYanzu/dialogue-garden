from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
STORE_DIR = ROOT_DIR / "store"
MIGRATIONS_DIR = STORE_DIR / "migrations"
DEFAULT_DB_PATH = STORE_DIR / "garden.db"
IMPORTS_DIR = ROOT_DIR / "imports" / "inbox"
ARCHIVES_DIR = ROOT_DIR / "archives" / "raw"
EXPORTS_DIR = ROOT_DIR / "exports"
CARDS_DIR = EXPORTS_DIR / "cards"
PROFILES_DIR = EXPORTS_DIR / "profiles"
MANIFESTS_DIR = EXPORTS_DIR / "manifests"
SKILLS_DIR = EXPORTS_DIR / "skills"


def iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def stable_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def slugify(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"[^\w\s-]", "", lowered)
    lowered = re.sub(r"[-\s]+", "-", lowered)
    return lowered.strip("-") or "untitled"


def summarize_text(text: str, *, limit: int = 240) -> str:
    squashed = re.sub(r"\s+", " ", text).strip()
    if len(squashed) <= limit:
        return squashed
    return squashed[: limit - 1].rstrip() + "…"


def parse_metadata_pairs(pairs: Iterable[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Metadata entry must be KEY=VALUE, got: {pair!r}")
        key, value = pair.split("=", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def iter_markdown_files(paths: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if path.is_dir():
            files.extend(
                sorted(
                    p
                    for p in path.rglob("*.md")
                    if p.is_file() and not p.name.lower().startswith("readme")
                )
            )
            continue
        if path.suffix.lower() != ".md":
            raise ValueError(f"Only Markdown imports are supported right now: {path}")
        files.append(path)
    return files
