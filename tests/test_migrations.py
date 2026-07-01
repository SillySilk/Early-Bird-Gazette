from gazette.storage import connect
from gazette.migrations import run_migrations, current_version


def test_run_migrations_is_idempotent(tmp_path):
    conn = connect(tmp_path / "g.db")
    applied_first = run_migrations(conn)
    assert applied_first >= 1
    version_after = current_version(conn)
    applied_second = run_migrations(conn)
    assert applied_second == 0
    assert current_version(conn) == version_after


def test_schema_migrations_table_records_versions(tmp_path):
    conn = connect(tmp_path / "g.db")
    run_migrations(conn)
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    assert [r["version"] for r in rows] == [m[0] for m in __import__("gazette.migrations", fromlist=["MIGRATIONS"]).MIGRATIONS]
