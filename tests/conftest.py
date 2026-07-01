import pytest

from gazette.storage import connect
from gazette.migrations import run_migrations


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "gazette.db")
    run_migrations(conn)
    yield conn
    conn.close()
