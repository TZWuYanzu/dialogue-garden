# Dialogue Garden Architecture

`dialogue-garden` is organized as a local-first dialogue repository with a database-first canonical store.

## Core Flow

1. Drop Markdown exports into `imports/inbox/`.
2. Run `python3 -m tools.cli ingest ...` to normalize and store them in `store/garden.db`.
3. Raw imports are deduplicated by SHA256 and compressed into `archives/raw/`.
4. Generate draft knowledge cards with `python3 -m tools.cli extract-cards`.
5. Export human-readable artifacts and Git-friendly manifests with `python3 -m tools.cli rebuild-index --with-cards`.
6. Search across turns, documents, and identity claims with `python3 -m tools.cli search`.

## Canonical Entities

- `source_session`: one imported conversation session with platform/model/tags and archive metadata
- `turn`: one normalized message block inside a session
- `document`: exported knowledge object, split by `raw_session`, `knowledge_card`, `identity_insight`, and `operating_rule`
- `evidence_link`: traceability bridge from a derived document back to supporting turns
- `insight_claim`: evidence-backed abstract claims about values, work style, or preferences

## Important Paths

- `store/garden.db`: canonical SQLite database
- `store/migrations/001_init.sql`: schema and FTS5 indexes
- `schemas/dialogue_import.schema.json`: normalized import contract
- `exports/manifests/documents.jsonl`: Git-diff-friendly document manifest
- `exports/manifests/insights.jsonl`: Git-diff-friendly insight manifest
- `exports/cards/`: Markdown knowledge card exports
- `exports/profiles/`: identity and value exports

## Notes

- The current card extraction is heuristic and local-only. It builds traceable draft cards without depending on an online LLM.
- Identity and operating-rule storage is reserved in the schema now, but higher-quality extraction should be added in a later phase.
- The repository keeps Markdown as the import and export boundary, while SQLite stays the source of truth.
