import os
import sqlite3
import db

def test_init_db(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()
    assert os.path.exists(test_db)

    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='llm_calls'")
    assert cursor.fetchone() is not None
    conn.close()

def test_log_call(tmp_path, monkeypatch):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init_db()

    usage = {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
    }
    db.log_call(
        model="test-model",
        prompt="hello",
        response="world",
        usage=usage,
        finish_reason="stop",
    )

    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT model, prompt, response, total_tokens, finish_reason FROM llm_calls")
    row = cursor.fetchone()
    assert row == ("test-model", "hello", "world", 30, "stop")
    conn.close()
