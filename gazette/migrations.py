from __future__ import annotations

import sqlite3

# Filled in by later tasks. (version, sql) in ascending order.
MIGRATIONS: list[tuple[int, str]] = [
    (1, "CREATE TABLE _probe(id INTEGER PRIMARY KEY);"),
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
