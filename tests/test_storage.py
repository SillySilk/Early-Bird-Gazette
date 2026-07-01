import sqlite3

import pytest

from gazette.storage import connect


def test_connect_applies_wal_and_pragmas(tmp_path):
    conn = connect(tmp_path / "g.db")
    assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_connect_loads_sqlite_vec(tmp_path):
    conn = connect(tmp_path / "g.db")
    assert conn.execute("SELECT vec_version()").fetchone()[0].startswith("v")


def test_connect_row_factory(tmp_path):
    conn = connect(tmp_path / "g.db")
    row = conn.execute("SELECT 1 AS n").fetchone()
    assert row["n"] == 1


def test_read_only_rejects_writes(tmp_path):
    db = tmp_path / "g.db"
    connect(db).close()  # create the file first
    ro = connect(db, read_only=True)
    with pytest.raises(sqlite3.OperationalError):
        ro.execute("CREATE TABLE x(a)")
