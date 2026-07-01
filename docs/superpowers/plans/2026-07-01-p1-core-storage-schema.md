# P1 — Core Storage & Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `gazette` package foundation — a WAL-mode SQLite database with the full domain-agnostic schema, FTS5 + sqlite-vec search tables, a migration runner, Pydantic models, and low-level CRUD access.

**Architecture:** A single core library package `gazette` (no PyQt6 dependency). `storage.py` owns connection setup (WAL pragmas, sqlite-vec extension loading) and the migration runner. `migrations.py` holds ordered, idempotent SQL migrations that create every table plus the `techniques_fts` (FTS5 external-content) and `technique_vec` (sqlite-vec vec0) virtual tables. `models.py` holds Pydantic v2 models. `repo.py` holds low-level insert/get helpers used by later sub-projects.

**Tech Stack:** Python 3.10, stdlib `sqlite3`, `sqlite-vec` (pip, provides loadable extension), FTS5 (compiled into stdlib sqlite), Pydantic v2, pytest.

## Global Constraints

- Python 3.10 (target interpreter under `C:\AI\Python310`).
- **All `python`/`pip`/`pytest` commands run through the project virtualenv** created in Task 0: `.venv/Scripts/python -m ...` (Windows). Never install into the global interpreter.
- Two-package repo layout: `gazette` (core, **no PyQt6 dependency**) and `gazette_app` (PyQt6, not in this plan).
- **No fallbacks, no dummy data, no placeholders** — a missing required capability (e.g. sqlite-vec fails to load) is a hard error, never a silent fallback to a stub.
- Every DB connection applies: `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON;`
- Shared DB source-of-truth path: `C:\AI\Early Bird Gazette\data\gazette.db` (the `data/` dir is git-ignored).
- Embedding dimension is config-driven, **default 384** (matches `sentence-transformers all-MiniLM-L6-v2`). The `technique_vec` table dimension must match.
- Domain-specific fields live in a `domain_meta` JSON column, never per-domain columns.
- Writes serialize through one writer using `BEGIN IMMEDIATE`; sibling readers use `mode=ro`.
- TDD: every behavior gets a failing test first. Commit after each task.

## File Structure

- `.venv/` — project virtualenv (git-ignored).
- `pyproject.toml` — package metadata + deps for `gazette`.
- `gazette/__init__.py` — package marker, version.
- `gazette/storage.py` — `connect()`, extension loading, `run_migrations()`.
- `gazette/migrations.py` — ordered `MIGRATIONS` list of `(version, sql)`.
- `gazette/models.py` — Pydantic v2 models.
- `gazette/repo.py` — low-level CRUD helpers.
- `tests/conftest.py` — shared pytest fixtures (temp db).
- `tests/test_capabilities.py` — sqlite-vec + FTS5 spike.
- `tests/test_storage.py` — connection pragmas + migration runner.
- `tests/test_schema.py` — schema shape, FTS5 + vec tables.
- `tests/test_models.py` — model validation.
- `tests/test_repo.py` — CRUD round-trips.

---

### Task 0: Project virtualenv

**Files:**
- Create: `.venv/` (via command; git-ignored)
- Modify: `.gitignore` (ensure `.venv/` is ignored — already present)

**Interfaces:**
- Consumes: nothing.
- Produces: a project-local Python 3.10 virtualenv at `.venv/` used by every later command as `.venv/Scripts/python`.

- [ ] **Step 1: Create the virtualenv**

Run:
```bash
cd "C:/AI/Early Bird Gazette"
py -3.10 -m venv .venv
```
Expected: `.venv/` directory created, no output.

- [ ] **Step 2: Verify the interpreter and upgrade pip**

Run:
```bash
.venv/Scripts/python --version
.venv/Scripts/python -m pip install --upgrade pip
```
Expected: `Python 3.10.x`, then pip upgrades successfully.

- [ ] **Step 3: Confirm `.venv/` is git-ignored**

Run: `git check-ignore .venv`
Expected: prints `.venv` (already covered by the `.gitignore` `.venv/` line). No commit needed — nothing tracked changes.

---

### Task 1: Package scaffolding & environment

**Files:**
- Create: `pyproject.toml`
- Create: `gazette/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: importable `gazette` package with `gazette.__version__: str`; pytest runnable.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "gazette"
version = "0.1.0"
description = "Early Bird Gazette core library"
requires-python = ">=3.10"
dependencies = [
    "pydantic>=2.5",
    "sqlite-vec>=0.1.1",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["gazette*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write the package marker**

`gazette/__init__.py`:
```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Write the smoke test**

`tests/test_smoke.py`:
```python
import gazette


def test_package_imports():
    assert gazette.__version__ == "0.1.0"
```

`tests/conftest.py` (empty for now, real fixtures added in Task 3):
```python
```

- [ ] **Step 4: Install and run**

Run:
```bash
cd "C:/AI/Early Bird Gazette"
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest tests/test_smoke.py -v
```
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml gazette/__init__.py tests/
git commit -m "feat(p1): package scaffolding and pytest setup"
```

---

### Task 2: sqlite-vec + FTS5 capability spike

This is the de-risking task called out in the spec. If the stock interpreter cannot load extensions, STOP and report — the fallback (`apsw` or a sqlite build with load-extension enabled) is a plan change, not a silent workaround.

**Files:**
- Create: `tests/test_capabilities.py`

**Interfaces:**
- Consumes: `sqlite_vec` (pip package).
- Produces: proven ability to load sqlite-vec and use FTS5 on this interpreter.

- [ ] **Step 1: Write the capability tests**

`tests/test_capabilities.py`:
```python
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
        "SELECT id, distance FROM t WHERE embedding MATCH ? ORDER BY distance LIMIT 1",
        (sqlite_vec.serialize_float32([0.1, 0.2, 0.3, 0.4]),),
    ).fetchall()
    assert rows[0][0] == 1


def test_fts5_available():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE ft USING fts5(body)")
    conn.execute("INSERT INTO ft(body) VALUES ('lora training trick')")
    hits = conn.execute("SELECT body FROM ft WHERE ft MATCH 'lora'").fetchall()
    assert len(hits) == 1
```

- [ ] **Step 2: Run the tests**

Run:
```bash
.venv/Scripts/python -m pytest tests/test_capabilities.py -v
```
Expected: 3 passed. If `test_can_load_sqlite_vec` errors with "not authorized" / disabled extension loading, or `test_fts5_available` errors with "no such module: fts5" — STOP and report; do not proceed to Task 3.

- [ ] **Step 3: Commit**

```bash
git add tests/test_capabilities.py
git commit -m "test(p1): prove sqlite-vec loading and FTS5 availability"
```

---

### Task 3: Connection management with WAL pragmas

**Files:**
- Create: `gazette/storage.py`
- Modify: `tests/conftest.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: `sqlite_vec`.
- Produces:
  - `gazette.storage.connect(db_path: str | os.PathLike, *, read_only: bool = False) -> sqlite3.Connection` — returns a connection with pragmas applied, `row_factory = sqlite3.Row`, and sqlite-vec loaded. `read_only=True` opens with URI `mode=ro`.

- [ ] **Step 1: Write the failing test**

`tests/test_storage.py`:
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_storage.py -v`
Expected: FAIL (ModuleNotFoundError: gazette.storage).

- [ ] **Step 3: Implement `gazette/storage.py`**

```python
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import sqlite_vec

_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
)


def connect(db_path: str | os.PathLike, *, read_only: bool = False) -> sqlite3.Connection:
    path = Path(db_path)
    if read_only:
        uri = f"file:{path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    for pragma in _PRAGMAS:
        conn.execute(pragma)
    return conn
```

- [ ] **Step 4: Add the shared fixture**

`tests/conftest.py`:
```python
import pytest

from gazette.storage import connect
from gazette.migrations import run_migrations


@pytest.fixture
def db(tmp_path):
    conn = connect(tmp_path / "gazette.db")
    run_migrations(conn)
    yield conn
    conn.close()
```

Note: this fixture imports `run_migrations`, added in Task 4. `test_storage.py` does not use the fixture, so run it in isolation until Task 4 lands.

- [ ] **Step 5: Run to verify storage tests pass**

Run: `.venv/Scripts/python -m pytest tests/test_storage.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add gazette/storage.py tests/test_storage.py tests/conftest.py
git commit -m "feat(p1): WAL connection management with sqlite-vec loading"
```

---

### Task 4: Migration runner

**Files:**
- Create: `gazette/migrations.py`
- Create: `tests/test_migrations.py`

**Interfaces:**
- Consumes: a `sqlite3.Connection` from `storage.connect`.
- Produces:
  - `gazette.migrations.MIGRATIONS: list[tuple[int, str]]` — ordered `(version, sql)`.
  - `gazette.migrations.run_migrations(conn: sqlite3.Connection) -> int` — applies all pending migrations inside transactions, records them in `schema_migrations`, returns the count applied. Idempotent.
  - `gazette.migrations.current_version(conn) -> int` — highest applied version, or 0.

- [ ] **Step 1: Write the failing test**

`tests/test_migrations.py`:
```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_migrations.py -v`
Expected: FAIL (ModuleNotFoundError: gazette.migrations).

- [ ] **Step 3: Implement the runner (schema SQL comes in Task 5)**

`gazette/migrations.py`:
```python
from __future__ import annotations

import sqlite3

# Filled in by later tasks. (version, sql) in ascending order.
MIGRATIONS: list[tuple[int, str]] = []


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
```

- [ ] **Step 4: Add a temporary migration so the runner has something to apply**

Temporarily set (removed/replaced in Task 5):
```python
MIGRATIONS: list[tuple[int, str]] = [
    (1, "CREATE TABLE _probe(id INTEGER PRIMARY KEY);"),
]
```

- [ ] **Step 5: Run to verify migration tests pass**

Run: `.venv/Scripts/python -m pytest tests/test_migrations.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add gazette/migrations.py tests/test_migrations.py
git commit -m "feat(p1): idempotent migration runner"
```

---

### Task 5: Core relational schema

Replaces the probe migration with the real schema. Splits FTS5 (Task 6) and vec (Task 7) into their own migrations so each is independently testable.

**Files:**
- Modify: `gazette/migrations.py` (replace `MIGRATIONS`)
- Create: `tests/test_schema.py`

**Interfaces:**
- Consumes: the Task 4 runner.
- Produces: migration version `1` creating tables: `domains`, `sources`, `source_items`, `techniques`, `technique_sources`, `tags`, `technique_tags`, `parameters`, `ingest_state`.

- [ ] **Step 1: Write the failing test**

`tests/test_schema.py`:
```python
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
    import sqlite3
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO techniques(title, summary, body, domain_id, dedup_key, confidence)"
            " VALUES ('t','s','b',999,'k',0.9)"
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_schema.py -v`
Expected: FAIL (probe schema has no `techniques` table).

- [ ] **Step 3: Replace `MIGRATIONS` in `gazette/migrations.py`**

```python
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
```

- [ ] **Step 4: Run schema + migration + storage tests**

Run: `.venv/Scripts/python -m pytest tests/test_schema.py tests/test_migrations.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add gazette/migrations.py tests/test_schema.py
git commit -m "feat(p1): core relational schema (migration v1)"
```

---

### Task 6: FTS5 external-content search table

**Files:**
- Modify: `gazette/migrations.py` (append migration `2`)
- Create: `tests/test_fts.py`

**Interfaces:**
- Consumes: migration v1 `techniques` table.
- Produces: migration `2` creating `techniques_fts` (FTS5, external content of `techniques`) + insert/update/delete triggers keeping it in sync.

- [ ] **Step 1: Write the failing test**

`tests/test_fts.py`:
```python
def _seed(db):
    db.execute("INSERT INTO domains(name) VALUES ('LoRA training')")
    db.execute(
        "INSERT INTO techniques(title, summary, body, domain_id, dedup_key, confidence)"
        " VALUES ('Fused backward pass','speedup','use --fused_backward_pass',1,'k1',0.9)"
    )


def test_fts_finds_seeded_technique(db):
    _seed(db)
    rows = db.execute(
        "SELECT t.title FROM techniques_fts f JOIN techniques t ON t.id = f.rowid"
        " WHERE techniques_fts MATCH 'fused'"
    ).fetchall()
    assert rows[0]["title"] == "Fused backward pass"


def test_fts_reflects_update(db):
    _seed(db)
    db.execute("UPDATE techniques SET summary='training speedup trick' WHERE id=1")
    rows = db.execute(
        "SELECT rowid FROM techniques_fts WHERE techniques_fts MATCH 'trick'"
    ).fetchall()
    assert len(rows) == 1


def test_fts_reflects_delete(db):
    _seed(db)
    db.execute("DELETE FROM techniques WHERE id=1")
    rows = db.execute(
        "SELECT rowid FROM techniques_fts WHERE techniques_fts MATCH 'fused'"
    ).fetchall()
    assert rows == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_fts.py -v`
Expected: FAIL (no such table: techniques_fts).

- [ ] **Step 3: Append migration `2` to `MIGRATIONS`**

```python
_FTS_V2 = """
CREATE VIRTUAL TABLE techniques_fts USING fts5(
    title, summary, body,
    content='techniques', content_rowid='id'
);

CREATE TRIGGER techniques_ai AFTER INSERT ON techniques BEGIN
    INSERT INTO techniques_fts(rowid, title, summary, body)
    VALUES (new.id, new.title, new.summary, new.body);
END;

CREATE TRIGGER techniques_ad AFTER DELETE ON techniques BEGIN
    INSERT INTO techniques_fts(techniques_fts, rowid, title, summary, body)
    VALUES ('delete', old.id, old.title, old.summary, old.body);
END;

CREATE TRIGGER techniques_au AFTER UPDATE ON techniques BEGIN
    INSERT INTO techniques_fts(techniques_fts, rowid, title, summary, body)
    VALUES ('delete', old.id, old.title, old.summary, old.body);
    INSERT INTO techniques_fts(rowid, title, summary, body)
    VALUES (new.id, new.title, new.summary, new.body);
END;
"""
```
Then update the list:
```python
MIGRATIONS: list[tuple[int, str]] = [
    (1, _SCHEMA_V1),
    (2, _FTS_V2),
]
```

- [ ] **Step 4: Run to verify FTS tests pass**

Run: `.venv/Scripts/python -m pytest tests/test_fts.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add gazette/migrations.py tests/test_fts.py
git commit -m "feat(p1): FTS5 external-content table with sync triggers (migration v2)"
```

---

### Task 7: sqlite-vec embedding table

**Files:**
- Modify: `gazette/migrations.py` (append migration `3`)
- Create: `tests/test_vec.py`

**Interfaces:**
- Consumes: sqlite-vec (loaded by `connect`).
- Produces: migration `3` creating `technique_vec` as `vec0(technique_id integer primary key, embedding float[384])`.

- [ ] **Step 1: Write the failing test**

`tests/test_vec.py`:
```python
import sqlite_vec


def test_vec_table_knn(db):
    db.execute("INSERT INTO domains(name) VALUES ('LoRA training')")
    for i, base in enumerate([0.0, 0.9], start=1):
        db.execute(
            "INSERT INTO techniques(title, summary, body, domain_id, dedup_key, confidence)"
            " VALUES (?, 's', 'b', 1, ?, 0.9)",
            (f"t{i}", f"k{i}"),
        )
        vec = sqlite_vec.serialize_float32([base] * 384)
        db.execute(
            "INSERT INTO technique_vec(technique_id, embedding) VALUES (?, ?)",
            (i, vec),
        )
    query = sqlite_vec.serialize_float32([0.0] * 384)
    rows = db.execute(
        "SELECT technique_id FROM technique_vec"
        " WHERE embedding MATCH ? ORDER BY distance LIMIT 1",
        (query,),
    ).fetchall()
    assert rows[0]["technique_id"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_vec.py -v`
Expected: FAIL (no such module/table: technique_vec).

- [ ] **Step 3: Append migration `3`**

```python
_VEC_V3 = """
CREATE VIRTUAL TABLE technique_vec USING vec0(
    technique_id integer primary key,
    embedding float[384]
);
"""
```
Update the list:
```python
MIGRATIONS: list[tuple[int, str]] = [
    (1, _SCHEMA_V1),
    (2, _FTS_V2),
    (3, _VEC_V3),
]
```
Note: dimension 384 matches the global-constraint default. A future migration will handle a configurable dimension; P1 fixes it at 384.

- [ ] **Step 4: Run to verify vec test passes**

Run: `.venv/Scripts/python -m pytest tests/test_vec.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add gazette/migrations.py tests/test_vec.py
git commit -m "feat(p1): sqlite-vec embedding table (migration v3)"
```

---

### Task 8: Pydantic models

**Files:**
- Create: `gazette/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces (all Pydantic v2 `BaseModel`):
  - `Parameter(key: str, value: str, unit: str | None = None)`
  - `RawRecord(external_id: str, url: str | None, author: str | None, raw_text: str, score: float | None = None, upvotes: int | None = None, metadata: dict = {})` — the normalized connector output shape (consumed by P3/P4).
  - `Technique(id: int | None = None, title: str, summary: str, body: str, domain: str, dedup_key: str, cluster_id: int | None = None, confidence: float, is_actionable: bool = True, status: str = "published", domain_meta: dict = {}, tags: list[str] = [], parameters: list[Parameter] = [])` with `confidence` constrained to `0.0..1.0`.

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
import pytest
from pydantic import ValidationError

from gazette.models import Technique, Parameter, RawRecord


def test_technique_defaults():
    t = Technique(title="t", summary="s", body="b", domain="LoRA training",
                  dedup_key="k", confidence=0.8)
    assert t.status == "published"
    assert t.is_actionable is True
    assert t.tags == []
    assert t.domain_meta == {}


def test_confidence_is_bounded():
    with pytest.raises(ValidationError):
        Technique(title="t", summary="s", body="b", domain="d",
                  dedup_key="k", confidence=1.5)


def test_parameter_and_rawrecord():
    p = Parameter(key="network_dim", value="32")
    assert p.unit is None
    r = RawRecord(external_id="pr-2379", url=None, author="kohya",
                  raw_text="use --fused_backward_pass")
    assert r.metadata == {}
    assert r.score is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: FAIL (ModuleNotFoundError: gazette.models).

- [ ] **Step 3: Implement `gazette/models.py`**

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class Parameter(BaseModel):
    key: str
    value: str
    unit: str | None = None


class RawRecord(BaseModel):
    external_id: str
    url: str | None = None
    author: str | None = None
    raw_text: str
    score: float | None = None
    upvotes: int | None = None
    metadata: dict = Field(default_factory=dict)


class Technique(BaseModel):
    id: int | None = None
    title: str
    summary: str
    body: str
    domain: str
    dedup_key: str
    cluster_id: int | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    is_actionable: bool = True
    status: str = "published"
    domain_meta: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
```

- [ ] **Step 4: Run to verify models tests pass**

Run: `.venv/Scripts/python -m pytest tests/test_models.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add gazette/models.py tests/test_models.py
git commit -m "feat(p1): pydantic models for Technique, Parameter, RawRecord"
```

---

### Task 9: Low-level repository (CRUD)

Minimal persistence used by later sub-projects: resolve/create domains and tags, insert a source item, insert a full technique (with tags + parameters + embedding), and fetch a technique by id. Hybrid RRF search is deferred to P2.

**Files:**
- Create: `gazette/repo.py`
- Create: `tests/test_repo.py`

**Interfaces:**
- Consumes: `storage.connect`, migrated schema, `models.Technique`, `models.Parameter`, `sqlite_vec`.
- Produces:
  - `get_or_create_domain(conn, name: str) -> int`
  - `get_or_create_tag(conn, name: str, tag_type: str | None = None) -> int`
  - `insert_source(conn, type: str, name: str, url: str | None = None, config_ref: str | None = None) -> int`
  - `insert_source_item(conn, source_id: int, external_id: str, raw_text: str, content_hash: str, url: str | None = None, author: str | None = None) -> int`
  - `insert_technique(conn, tech: Technique, *, embedding: list[float] | None = None, source_item_ids: list[int] = []) -> int` — inserts the row, resolves domain, writes tags/parameters, links `technique_sources`, and (if `embedding` given) writes to `technique_vec`. Wrapped in one `BEGIN IMMEDIATE` transaction.
  - `get_technique(conn, technique_id: int) -> Technique | None` — reassembles the model with tags + parameters.

- [ ] **Step 1: Write the failing test**

`tests/test_repo.py`:
```python
from gazette.models import Technique, Parameter
from gazette import repo


def test_get_or_create_domain_is_stable(db):
    a = repo.get_or_create_domain(db, "LoRA training")
    b = repo.get_or_create_domain(db, "LoRA training")
    assert a == b


def test_insert_and_get_technique_roundtrip(db):
    src = repo.insert_source(db, type="github", name="kohya sd-scripts")
    item = repo.insert_source_item(
        db, source_id=src, external_id="pr-2379",
        raw_text="use --fused_backward_pass", content_hash="h1",
    )
    tech = Technique(
        title="Fused backward pass", summary="~20% speedup",
        body="pass --fused_backward_pass", domain="LoRA training",
        dedup_key="k1", confidence=0.92,
        tags=["speedup", "kohya"],
        parameters=[Parameter(key="flag", value="--fused_backward_pass")],
    )
    tid = repo.insert_technique(
        db, tech, embedding=[0.1] * 384, source_item_ids=[item]
    )
    got = repo.get_technique(db, tid)
    assert got.title == "Fused backward pass"
    assert set(got.tags) == {"speedup", "kohya"}
    assert got.parameters[0].value == "--fused_backward_pass"


def test_insert_technique_writes_fts_and_vec(db):
    tech = Technique(title="Qwen VAE 2D", summary="2d only",
                     body="--qwen_image_vae_2d", domain="SD",
                     dedup_key="k2", confidence=0.8)
    tid = repo.insert_technique(db, tech, embedding=[0.0] * 384)
    fts = db.execute(
        "SELECT rowid FROM techniques_fts WHERE techniques_fts MATCH 'qwen'"
    ).fetchall()
    assert fts[0]["rowid"] == tid
    vec = db.execute(
        "SELECT technique_id FROM technique_vec WHERE technique_id = ?", (tid,)
    ).fetchall()
    assert len(vec) == 1


def test_get_missing_technique_returns_none(db):
    assert repo.get_technique(db, 999) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_repo.py -v`
Expected: FAIL (ModuleNotFoundError: gazette.repo).

- [ ] **Step 3: Implement `gazette/repo.py`**

```python
from __future__ import annotations

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
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        domain_id = get_or_create_domain(conn, tech.domain)
        import json
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
    import json
    return Technique(
        id=row["id"], title=row["title"], summary=row["summary"], body=row["body"],
        domain=row["domain_name"], dedup_key=row["dedup_key"],
        cluster_id=row["cluster_id"], confidence=row["confidence"],
        is_actionable=bool(row["is_actionable"]), status=row["status"],
        domain_meta=json.loads(row["domain_meta"]), tags=tags, parameters=params,
    )
```

- [ ] **Step 4: Run to verify repo tests pass**

Run: `.venv/Scripts/python -m pytest tests/test_repo.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run the full suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add gazette/repo.py tests/test_repo.py
git commit -m "feat(p1): low-level repository CRUD with FTS+vec persistence"
```

---

## Self-Review

**Spec coverage (P1 scope = "gazette skeleton, SQLite WAL schema, migrations, FTS5 + sqlite-vec setup, low-level DB access"):**
- Package skeleton → Task 1.
- sqlite-vec extension-loading spike (spec's flagged first task) → Task 2.
- WAL pragmas / connection mgmt → Task 3.
- Migration runner → Task 4; full relational schema → Task 5.
- FTS5 → Task 6; sqlite-vec table → Task 7.
- Pydantic models → Task 8; low-level CRUD → Task 9.
- Read-only connection contract (integration requirement) → Task 3 (`read_only=True`).
- All core tables from spec §4 present in Task 5. Hybrid RRF search is correctly deferred to P2.

**Placeholder scan:** No TBD/TODO. The Task 4 probe migration is explicitly temporary and replaced in Task 5 (called out in both). Every code step shows complete code.

**Type consistency:** `Technique` fields identical across Tasks 8 and 9. `insert_technique(..., embedding, source_item_ids)` signature matches its Task 9 test usage. `serialize_float32` used consistently (Tasks 2, 7, 9). `run_migrations`/`current_version` names consistent (Tasks 3, 4). 384-dim consistent (constraints, Tasks 7, 9).

**Note on `conftest.py`:** the `db` fixture imports `run_migrations` (Task 4), so `tests/test_storage.py` (Task 3) is run standalone in Task 3 Step 5; from Task 4 onward the full suite works.
