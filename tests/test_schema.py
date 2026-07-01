import sqlite3

import pytest

EXPECTED_TABLES = {
    "domains", "sources", "source_items", "techniques",
    "technique_sources", "tags", "technique_tags", "parameters",
    "ingest_state", "schema_migrations",
}


def test_all_core_tables_exist(db):
    rows = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r["name"] for r in rows}
    assert EXPECTED_TABLES <= names


def test_techniques_columns(db):
    cols = {r["name"] for r in db.execute("PRAGMA table_info(techniques)").fetchall()}
    assert {
        "id", "title", "summary", "body", "domain_id", "dedup_key",
        "cluster_id", "confidence", "is_actionable", "status",
        "domain_meta", "created_at", "updated_at", "first_seen_at",
    } <= cols


def test_status_defaults_to_published(db):
    db.execute("INSERT INTO domains(name) VALUES ('LoRA training')")
    db.execute(
        "INSERT INTO techniques(title, summary, body, domain_id, dedup_key, confidence)"
        " VALUES ('t','s','b',1,'k',0.9)"
    )
    row = db.execute("SELECT status FROM techniques").fetchone()
    assert row["status"] == "published"


def test_foreign_keys_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO techniques(title, summary, body, domain_id, dedup_key, confidence)"
            " VALUES ('t','s','b',999,'k',0.9)"
        )
