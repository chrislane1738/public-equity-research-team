import json
import pytest
from backend.db.sqlite_client import SqliteClient


@pytest.fixture
async def db(tmp_path):
    client = SqliteClient(tmp_path / "test.sqlite")
    await client.connect()
    await client.init_schema()
    yield client
    await client.close()


async def test_init_schema_creates_tables(db):
    rows = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = [r["name"] for r in rows]
    assert "agents" in table_names
    assert "chat_messages" in table_names
    assert "jobs" in table_names
    assert "tickers" in table_names


async def test_create_and_get_job(db):
    await db.execute(
        "INSERT INTO jobs (id, ticker, workflow, status) VALUES (?, ?, ?, ?)",
        ("job-1", "NVDA", "full-deep-dive", "queued"),
    )
    row = await db.fetch_one("SELECT * FROM jobs WHERE id = ?", ("job-1",))
    assert row["ticker"] == "NVDA"
    assert row["workflow"] == "full-deep-dive"
    assert row["status"] == "queued"


async def test_insert_chat_message_with_tool_calls(db):
    tool_calls = [{"name": "fmp_get_financials", "input": {"ticker": "NVDA"}}]
    await db.execute(
        "INSERT INTO chat_messages (agent_id, ticker, role, content, tool_calls) "
        "VALUES (?, ?, ?, ?, ?)",
        ("md", "NVDA", "assistant", "hello", json.dumps(tool_calls)),
    )
    row = await db.fetch_one(
        "SELECT * FROM chat_messages WHERE agent_id = ?", ("md",)
    )
    assert row["content"] == "hello"
    assert json.loads(row["tool_calls"]) == tool_calls
