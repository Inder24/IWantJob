import sqlite3
import pytest

from app.db_adapter import Collection


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    cur = c.cursor()
    cur.execute(
        """CREATE TABLE user_job_views (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            job_key TEXT NOT NULL,
            viewed_date TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    c.commit()
    yield c
    c.close()


@pytest.mark.asyncio
async def test_insert_one_does_not_write__id_column_when_missing_in_table(conn):
    views = Collection(conn, "user_job_views")
    await views.insert_one(
        {
            "_id": "v1",
            "user_id": "u1",
            "job_key": "https://example.com/job1",
            "viewed_date": "2026-04-05",
            "created_at": "2026-04-05T00:00:00",
        }
    )
    row = await views.find_one({"id": "v1"})
    assert row is not None
    assert row["user_id"] == "u1"
