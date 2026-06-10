PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_session (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    model TEXT,
    title TEXT NOT NULL,
    language TEXT,
    import_path TEXT NOT NULL,
    archive_path TEXT,
    archive_codec TEXT,
    raw_sha256 TEXT NOT NULL UNIQUE,
    normalized_sha256 TEXT NOT NULL,
    raw_size_bytes INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    ended_at TEXT,
    tags_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(tags_json)),
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS turn (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES source_session(id) ON DELETE CASCADE,
    sequence_no INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('system', 'user', 'assistant', 'tool', 'unknown')),
    author_name TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    inserted_at TEXT NOT NULL,
    UNIQUE (session_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS document (
    id TEXT PRIMARY KEY,
    source_session_id TEXT REFERENCES source_session(id) ON DELETE SET NULL,
    doc_kind TEXT NOT NULL CHECK (
        doc_kind IN ('raw_session', 'knowledge_card', 'identity_insight', 'operating_rule')
    ),
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    language TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    tags_json TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(tags_json)),
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (doc_kind, slug)
);

CREATE TABLE IF NOT EXISTS evidence_link (
    id TEXT PRIMARY KEY,
    target_document_id TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    source_document_id TEXT REFERENCES document(id) ON DELETE CASCADE,
    source_turn_id TEXT REFERENCES turn(id) ON DELETE CASCADE,
    session_id TEXT REFERENCES source_session(id) ON DELETE CASCADE,
    snippet TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS insight_claim (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE REFERENCES document(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    statement TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    status TEXT NOT NULL DEFAULT 'candidate',
    evidence_count INTEGER NOT NULL DEFAULT 0,
    contradiction_count INTEGER NOT NULL DEFAULT 0,
    first_observed_at TEXT,
    last_observed_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_source_session_platform ON source_session(platform);
CREATE INDEX IF NOT EXISTS idx_source_session_model ON source_session(model);
CREATE INDEX IF NOT EXISTS idx_source_session_created_at ON source_session(created_at);
CREATE INDEX IF NOT EXISTS idx_turn_session_id ON turn(session_id);
CREATE INDEX IF NOT EXISTS idx_turn_role ON turn(role);
CREATE INDEX IF NOT EXISTS idx_document_kind ON document(doc_kind);
CREATE INDEX IF NOT EXISTS idx_document_status ON document(status);
CREATE INDEX IF NOT EXISTS idx_document_created_at ON document(created_at);
CREATE INDEX IF NOT EXISTS idx_document_source_session_id ON document(source_session_id);
CREATE INDEX IF NOT EXISTS idx_evidence_target_document_id ON evidence_link(target_document_id);
CREATE INDEX IF NOT EXISTS idx_evidence_session_id ON evidence_link(session_id);
CREATE INDEX IF NOT EXISTS idx_insight_category ON insight_claim(category);
CREATE INDEX IF NOT EXISTS idx_insight_status ON insight_claim(status);

CREATE VIRTUAL TABLE IF NOT EXISTS turn_fts USING fts5(
    content,
    role UNINDEXED,
    content='turn',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS document_fts USING fts5(
    title,
    summary,
    body,
    doc_kind UNINDEXED,
    status UNINDEXED,
    content='document',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE VIRTUAL TABLE IF NOT EXISTS insight_claim_fts USING fts5(
    statement,
    category UNINDEXED,
    status UNINDEXED,
    content='insight_claim',
    content_rowid='rowid',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS turn_ai AFTER INSERT ON turn BEGIN
    INSERT INTO turn_fts(rowid, content, role) VALUES (new.rowid, new.content, new.role);
END;

CREATE TRIGGER IF NOT EXISTS turn_ad AFTER DELETE ON turn BEGIN
    INSERT INTO turn_fts(turn_fts, rowid, content, role) VALUES ('delete', old.rowid, old.content, old.role);
END;

CREATE TRIGGER IF NOT EXISTS turn_au AFTER UPDATE ON turn BEGIN
    INSERT INTO turn_fts(turn_fts, rowid, content, role) VALUES ('delete', old.rowid, old.content, old.role);
    INSERT INTO turn_fts(rowid, content, role) VALUES (new.rowid, new.content, new.role);
END;

CREATE TRIGGER IF NOT EXISTS document_ai AFTER INSERT ON document BEGIN
    INSERT INTO document_fts(rowid, title, summary, body, doc_kind, status)
    VALUES (new.rowid, new.title, new.summary, new.body, new.doc_kind, new.status);
END;

CREATE TRIGGER IF NOT EXISTS document_ad AFTER DELETE ON document BEGIN
    INSERT INTO document_fts(document_fts, rowid, title, summary, body, doc_kind, status)
    VALUES ('delete', old.rowid, old.title, old.summary, old.body, old.doc_kind, old.status);
END;

CREATE TRIGGER IF NOT EXISTS document_au AFTER UPDATE ON document BEGIN
    INSERT INTO document_fts(document_fts, rowid, title, summary, body, doc_kind, status)
    VALUES ('delete', old.rowid, old.title, old.summary, old.body, old.doc_kind, old.status);
    INSERT INTO document_fts(rowid, title, summary, body, doc_kind, status)
    VALUES (new.rowid, new.title, new.summary, new.body, new.doc_kind, new.status);
END;

CREATE TRIGGER IF NOT EXISTS insight_claim_ai AFTER INSERT ON insight_claim BEGIN
    INSERT INTO insight_claim_fts(rowid, statement, category, status)
    VALUES (new.rowid, new.statement, new.category, new.status);
END;

CREATE TRIGGER IF NOT EXISTS insight_claim_ad AFTER DELETE ON insight_claim BEGIN
    INSERT INTO insight_claim_fts(insight_claim_fts, rowid, statement, category, status)
    VALUES ('delete', old.rowid, old.statement, old.category, old.status);
END;

CREATE TRIGGER IF NOT EXISTS insight_claim_au AFTER UPDATE ON insight_claim BEGIN
    INSERT INTO insight_claim_fts(insight_claim_fts, rowid, statement, category, status)
    VALUES ('delete', old.rowid, old.statement, old.category, old.status);
    INSERT INTO insight_claim_fts(rowid, statement, category, status)
    VALUES (new.rowid, new.statement, new.category, new.status);
END;
