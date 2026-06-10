from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from tools.common import DEFAULT_DB_PATH, parse_metadata_pairs
from tools.pipelines.extract_cards import extract_cards
from tools.pipelines.ingest import ingest_paths
from tools.pipelines.rebuild_index import rebuild_exports
from tools.search import format_search_results, search_records
from tools.storage import GardenDB


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dialogue Garden local knowledge repository CLI.")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to the SQLite database. Defaults to store/garden.db.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="Create the SQLite database and FTS indexes.")

    ingest_parser = subparsers.add_parser("ingest", help="Import Markdown files into the canonical store.")
    ingest_parser.add_argument("paths", nargs="+", help="Markdown files or directories to ingest.")
    ingest_parser.add_argument("--platform", required=True, help="Source platform name, e.g. chatgpt or claude.")
    ingest_parser.add_argument("--model", help="Model identifier used for the conversation.")
    ingest_parser.add_argument("--language", help="Primary language of the conversation.")
    ingest_parser.add_argument("--title", help="Optional forced title for the imported session.")
    ingest_parser.add_argument("--tag", action="append", default=[], help="Tag to attach to the imported session.")
    ingest_parser.add_argument(
        "--metadata",
        action="append",
        default=[],
        help="Additional metadata in KEY=VALUE form. Repeat for multiple values.",
    )

    cards_parser = subparsers.add_parser("extract-cards", help="Generate heuristic knowledge cards.")
    cards_parser.add_argument("--session-id", help="Only generate a card for the specified source session.")

    index_parser = subparsers.add_parser("rebuild-index", help="Export manifests and readable Markdown artifacts.")
    index_parser.add_argument(
        "--with-cards",
        action="store_true",
        help="Regenerate heuristic knowledge cards before exporting.",
    )

    search_parser = subparsers.add_parser("search", help="Search turns, documents, and insights.")
    search_parser.add_argument("query", nargs="?", help="Full-text query. If omitted, recent records are listed.")
    search_parser.add_argument(
        "--kind",
        choices=["turn", "raw_session", "knowledge_card", "identity_insight", "operating_rule"],
        help="Limit search to one result kind.",
    )
    search_parser.add_argument("--platform", help="Filter by source platform.")
    search_parser.add_argument("--model", help="Filter by source model.")
    search_parser.add_argument("--tag", help="Filter by tag.")
    search_parser.add_argument("--status", help="Filter by document or insight status.")
    search_parser.add_argument("--from-date", help="Lower ISO date boundary.")
    search_parser.add_argument("--to-date", help="Upper ISO date boundary.")
    search_parser.add_argument("--limit", type=int, default=20, help="Maximum number of results to return.")
    search_parser.add_argument("--json", action="store_true", help="Return results as JSON.")

    return parser


def _init_db(db_path: Path) -> dict[str, str]:
    with GardenDB(db_path) as db:
        db.init_db()
        db.commit()
    return {"db_path": str(db_path), "status": "initialized"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db_path = Path(args.db).expanduser().resolve()

    if args.command == "init-db":
        print(json.dumps(_init_db(db_path), ensure_ascii=False, indent=2))
        return 0

    if args.command == "ingest":
        results = ingest_paths(
            db_path,
            args.paths,
            platform=args.platform,
            model=args.model,
            language=args.language,
            title=args.title,
            tags=args.tag,
            metadata=parse_metadata_pairs(args.metadata),
        )
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if args.command == "extract-cards":
        results = extract_cards(db_path, session_id=args.session_id)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if args.command == "rebuild-index":
        if args.with_cards:
            extract_cards(db_path)
        results = rebuild_exports(db_path)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if args.command == "search":
        results = search_records(
            db_path,
            query=args.query,
            kind=args.kind,
            platform=args.platform,
            model=args.model,
            tag=args.tag,
            status=args.status,
            from_date=args.from_date,
            to_date=args.to_date,
            limit=args.limit,
        )
        print(format_search_results(results, as_json=args.json))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
