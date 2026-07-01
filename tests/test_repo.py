import sqlite3

import pytest

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


def test_insert_technique_rolls_back_on_error(db):
    tech = Technique(
        title="Rollback probe", summary="s", body="b", domain="SD",
        dedup_key="kbad", confidence=0.5,
        tags=["rbtag"], parameters=[Parameter(key="k", value="v")],
    )
    # source_item_id 999 does not exist -> FK violation on technique_sources,
    # after the technique/tags/parameters rows have been inserted in-transaction.
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert_technique(db, tech, embedding=[0.0] * 384, source_item_ids=[999])

    assert db.execute(
        "SELECT COUNT(*) FROM techniques WHERE dedup_key='kbad'"
    ).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM parameters").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM technique_tags").fetchone()[0] == 0
    assert db.execute(
        "SELECT COUNT(*) FROM techniques_fts WHERE techniques_fts MATCH 'rollback'"
    ).fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM technique_vec").fetchone()[0] == 0


def test_insert_technique_composes_in_outer_transaction(db):
    # Two inserts inside one caller-managed transaction; rolling the outer
    # transaction back must discard BOTH (proves insert_technique nests via
    # SAVEPOINT and does not force-commit the caller's work).
    t1 = Technique(title="First", summary="s", body="b", domain="SD",
                   dedup_key="c1", confidence=0.5)
    t2 = Technique(title="Second", summary="s", body="b", domain="SD",
                   dedup_key="c2", confidence=0.5)
    db.execute("BEGIN")
    repo.insert_technique(db, t1, embedding=[0.0] * 384)
    repo.insert_technique(db, t2, embedding=[0.1] * 384)
    db.execute("ROLLBACK")
    assert db.execute("SELECT COUNT(*) FROM techniques").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM technique_vec").fetchone()[0] == 0


def test_domain_meta_roundtrips_non_empty(db):
    tech = Technique(title="Meta", summary="s", body="b", domain="SD",
                     dedup_key="cm", confidence=0.7,
                     domain_meta={"base_model": "Anima", "steps": 30})
    tid = repo.insert_technique(db, tech, embedding=[0.0] * 384)
    got = repo.get_technique(db, tid)
    assert got.domain_meta == {"base_model": "Anima", "steps": 30}
