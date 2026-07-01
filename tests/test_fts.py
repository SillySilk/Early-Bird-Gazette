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
