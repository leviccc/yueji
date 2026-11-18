from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3

from yueji_qa.storage import Storage


def test_chat_usage_persists_measurements_and_missing_usage(tmp_path):
    storage = Storage(tmp_path)
    assert storage.chat_usage() == {
        "responses": 0, "responses_with_usage": 0,
        "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
        "prompt_cache_hit_tokens": 0, "prompt_cache_miss_tokens": 0,
        "reasoning_tokens": 0, "models": [],
    }
    assert storage.reserve_calls("chat", 3, 10)
    storage.record_chat_usage({
        "requested_model": "deepseek-chat", "model": "deepseek-v3",
        "usage_reported": True,
        "usage": {
            "prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
            "prompt_cache_hit_tokens": 80, "prompt_cache_miss_tokens": 20,
            "reasoning_tokens": 5,
        },
    })
    storage.record_chat_usage({
        "requested_model": "deepseek-chat", "model": "deepseek-v3",
        "usage_reported": True, "usage": {"prompt_tokens": 10, "completion_tokens": 3},
    })
    storage.record_chat_usage({
        "requested_model": "fallback-model", "model": "",
        "usage_reported": False, "usage": {},
    })

    reopened = Storage(tmp_path)
    assert reopened.usage() == {"chat": 3}
    assert not reopened.reserve_calls("chat", 8, 10)
    assert reopened.chat_usage() == {
        "responses": 3, "responses_with_usage": 2,
        "prompt_tokens": 110, "completion_tokens": 23, "total_tokens": 120,
        "prompt_cache_hit_tokens": 80, "prompt_cache_miss_tokens": 20,
        "reasoning_tokens": 5, "models": ["deepseek-v3", "fallback-model"],
    }
    with reopened.connect() as db:
        assert db.execute("SELECT total_tokens FROM chat_responses ORDER BY id").fetchall() == [
            (120,), (None,), (None,),
        ]


def test_chat_usage_filters_current_utc_date(tmp_path):
    storage = Storage(tmp_path)
    today = datetime.now(timezone.utc).date()
    with storage.connect() as db:
        db.executemany(
            """INSERT INTO chat_responses
               (day, requested_model, model, usage_reported, total_tokens)
               VALUES (?, ?, ?, ?, ?)""",
            [
                ((today - timedelta(days=1)).isoformat(), "old", "old", 1, 999),
                (today.isoformat(), "today", "today", 1, 7),
                ((today + timedelta(days=1)).isoformat(), "future", "future", 1, 999),
            ],
        )
    result = storage.chat_usage()
    assert result["responses"] == result["responses_with_usage"] == 1
    assert result["total_tokens"] == 7
    assert result["models"] == ["today"]


def test_chat_usage_stores_only_allowlisted_fields(tmp_path):
    storage = Storage(tmp_path)
    secret = "secret-that-must-never-be-persisted"
    storage.record_chat_usage({
        "requested_model": "chat", "model": "chat-v1", "usage_reported": True,
        "api_key": secret, "prompt": secret, "answer": secret,
        "headers": {"Authorization": secret},
        "usage": {
            "total_tokens": 9, "provider_metadata": secret,
            "prompt_tokens": secret, "completion_tokens": -1,
            "prompt_cache_hit_tokens": True, "reasoning_tokens": 1.5,
        },
    })
    with storage.connect() as db:
        dump = "\n".join(db.iterdump())
        counts = db.execute(
            "SELECT prompt_tokens, completion_tokens, prompt_cache_hit_tokens, reasoning_tokens "
            "FROM chat_responses"
        ).fetchone()
    assert secret not in dump
    assert counts == (None, None, None, None)
    assert storage.chat_usage()["total_tokens"] == 9


def test_chat_usage_additive_migration_preserves_existing_data(tmp_path):
    path = tmp_path / "yueji.sqlite3"
    today = datetime.now(timezone.utc).date().isoformat()
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE usage (day TEXT, kind TEXT, calls INTEGER, PRIMARY KEY(day,kind))")
        db.execute("INSERT INTO usage VALUES (?, 'chat', 4)", (today,))
        db.execute("CREATE TABLE answers (key TEXT PRIMARY KEY, body TEXT NOT NULL)")
        db.execute("INSERT INTO answers VALUES ('old-answer', '{\"answer\": \"kept\"}')")
    storage = Storage(tmp_path)
    assert storage.usage() == {"chat": 4}
    assert storage.cached("answers", "old-answer") == {"answer": "kept"}
    assert storage.chat_usage()["responses"] == 0


def test_chat_usage_records_concurrent_responses(tmp_path):
    storage = Storage(tmp_path)
    metadata = {
        "requested_model": "chat", "model": "chat", "usage_reported": True,
        "usage": {"total_tokens": 3},
    }
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(storage.record_chat_usage, [metadata] * 12))
    result = Storage(tmp_path).chat_usage()
    assert result["responses"] == result["responses_with_usage"] == 12
    assert result["total_tokens"] == 36
