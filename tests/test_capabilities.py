import sqlite3

import sqlite_vec


def test_can_load_sqlite_vec():
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    (version,) = conn.execute("SELECT vec_version()").fetchone()
    assert version.startswith("v")


def test_vec0_virtual_table_roundtrip():
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute(
        "CREATE VIRTUAL TABLE t USING vec0(id integer primary key, embedding float[4])"
    )
    conn.execute(
        "INSERT INTO t(id, embedding) VALUES (1, ?)",
        (sqlite_vec.serialize_float32([0.1, 0.2, 0.3, 0.4]),),
    )
    rows = conn.execute(
        "SELECT id, distance FROM t WHERE embedding MATCH ? AND k = 1 ORDER BY distance",
        (sqlite_vec.serialize_float32([0.1, 0.2, 0.3, 0.4]),),
    ).fetchall()
    assert rows[0][0] == 1


def test_fts5_available():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE ft USING fts5(body)")
    conn.execute("INSERT INTO ft(body) VALUES ('lora training trick')")
    hits = conn.execute("SELECT body FROM ft WHERE ft MATCH 'lora'").fetchall()
    assert len(hits) == 1
