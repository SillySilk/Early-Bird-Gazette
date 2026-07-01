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
        " WHERE embedding MATCH ? AND k = 1 ORDER BY distance",
        (query,),
    ).fetchall()
    assert rows[0]["technique_id"] == 1
