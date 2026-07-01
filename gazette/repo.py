from __future__ import annotations

import json
import sqlite3

import sqlite_vec

from gazette.models import Parameter, Technique


def get_or_create_domain(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM domains WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO domains(name) VALUES (?)", (name,))
    return cur.lastrowid


def get_or_create_tag(conn: sqlite3.Connection, name: str, tag_type: str | None = None) -> int:
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute(
        "INSERT INTO tags(name, tag_type) VALUES (?, ?)", (name, tag_type)
    )
    return cur.lastrowid


def insert_source(conn, type: str, name: str, url: str | None = None,
                  config_ref: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO sources(type, name, url, config_ref) VALUES (?, ?, ?, ?)",
        (type, name, url, config_ref),
    )
    return cur.lastrowid


def insert_source_item(conn, source_id: int, external_id: str, raw_text: str,
                       content_hash: str, url: str | None = None,
                       author: str | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO source_items(source_id, external_id, url, author, raw_text, content_hash)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (source_id, external_id, url, author, raw_text, content_hash),
    )
    return cur.lastrowid


def insert_technique(conn, tech: Technique, *, embedding: list[float] | None = None,
                     source_item_ids: list[int] = []) -> int:
    # Close any implicit transaction opened by prior statements on this
    # connection (Python's sqlite3 auto-begins before DML), so the explicit
    # BEGIN IMMEDIATE below does not fail with "cannot start a transaction
    # within a transaction".
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        domain_id = get_or_create_domain(conn, tech.domain)
        cur = conn.execute(
            "INSERT INTO techniques(title, summary, body, domain_id, dedup_key,"
            " cluster_id, confidence, is_actionable, status, domain_meta)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (tech.title, tech.summary, tech.body, domain_id, tech.dedup_key,
             tech.cluster_id, tech.confidence, int(tech.is_actionable),
             tech.status, json.dumps(tech.domain_meta)),
        )
        tid = cur.lastrowid
        for tag in tech.tags:
            tag_id = get_or_create_tag(conn, tag)
            conn.execute(
                "INSERT OR IGNORE INTO technique_tags(technique_id, tag_id) VALUES (?, ?)",
                (tid, tag_id),
            )
        for p in tech.parameters:
            conn.execute(
                "INSERT INTO parameters(technique_id, key, value, unit) VALUES (?, ?, ?, ?)",
                (tid, p.key, p.value, p.unit),
            )
        for sid in source_item_ids:
            conn.execute(
                "INSERT INTO technique_sources(technique_id, source_item_id) VALUES (?, ?)",
                (tid, sid),
            )
        if embedding is not None:
            conn.execute(
                "INSERT INTO technique_vec(technique_id, embedding) VALUES (?, ?)",
                (tid, sqlite_vec.serialize_float32(embedding)),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return tid


def get_technique(conn, technique_id: int) -> Technique | None:
    row = conn.execute(
        "SELECT t.*, d.name AS domain_name FROM techniques t"
        " JOIN domains d ON d.id = t.domain_id WHERE t.id = ?",
        (technique_id,),
    ).fetchone()
    if row is None:
        return None
    tags = [
        r["name"] for r in conn.execute(
            "SELECT g.name FROM technique_tags tt JOIN tags g ON g.id = tt.tag_id"
            " WHERE tt.technique_id = ?", (technique_id,)
        ).fetchall()
    ]
    params = [
        Parameter(key=r["key"], value=r["value"], unit=r["unit"])
        for r in conn.execute(
            "SELECT key, value, unit FROM parameters WHERE technique_id = ?",
            (technique_id,),
        ).fetchall()
    ]
    return Technique(
        id=row["id"], title=row["title"], summary=row["summary"], body=row["body"],
        domain=row["domain_name"], dedup_key=row["dedup_key"],
        cluster_id=row["cluster_id"], confidence=row["confidence"],
        is_actionable=bool(row["is_actionable"]), status=row["status"],
        domain_meta=json.loads(row["domain_meta"]), tags=tags, parameters=params,
    )
