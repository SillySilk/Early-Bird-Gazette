from __future__ import annotations

import sqlite3

_SCHEMA_V1 = """
CREATE TABLE domains (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    parent_id INTEGER REFERENCES domains(id)
);

CREATE TABLE sources (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL UNIQUE,
    url TEXT,
    config_ref TEXT
);

CREATE TABLE source_items (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    external_id TEXT NOT NULL,
    url TEXT,
    author TEXT,
    raw_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(source_id, external_id)
);

CREATE TABLE techniques (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    body TEXT NOT NULL,
    domain_id INTEGER NOT NULL REFERENCES domains(id),
    dedup_key TEXT NOT NULL UNIQUE,
    cluster_id INTEGER,
    confidence REAL NOT NULL,
    is_actionable INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'published',
    domain_meta TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    first_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE technique_sources (
    technique_id INTEGER NOT NULL REFERENCES techniques(id) ON DELETE CASCADE,
    source_item_id INTEGER NOT NULL REFERENCES source_items(id) ON DELETE CASCADE,
    score REAL,
    upvotes INTEGER,
    PRIMARY KEY (technique_id, source_item_id)
);

CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    tag_type TEXT
);

CREATE TABLE technique_tags (
    technique_id INTEGER NOT NULL REFERENCES techniques(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (technique_id, tag_id)
);

CREATE TABLE parameters (
    id INTEGER PRIMARY KEY,
    technique_id INTEGER NOT NULL REFERENCES techniques(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT
);

CREATE TABLE ingest_state (
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (source_id, key)
);

CREATE INDEX idx_techniques_domain ON techniques(domain_id);
CREATE INDEX idx_techniques_cluster ON techniques(cluster_id);
CREATE INDEX idx_source_items_source ON source_items(source_id);
"""

MIGRATIONS: list[tuple[int, str]] = [
    (1, _SCHEMA_V1),
]


def current_version(conn: sqlite3.Connection) -> int:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    return row["v"] or 0


def run_migrations(conn: sqlite3.Connection) -> int:
    applied = 0
    start = current_version(conn)
    for version, sql in sorted(MIGRATIONS):
        if version <= start:
            continue
        with conn:  # transaction
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)", (version,)
            )
        applied += 1
    return applied
