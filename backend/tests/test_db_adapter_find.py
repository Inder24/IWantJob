import sqlite3
import pytest

from app.db_adapter import Collection


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    cur = c.cursor()
    cur.execute(
        """CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            _id TEXT,
            platform TEXT NOT NULL,
            job_id TEXT NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            description TEXT,
            url TEXT,
            posted_date TEXT,
            scraped_at TEXT NOT NULL
        )"""
    )
    c.commit()
    yield c
    c.close()


@pytest.mark.asyncio
async def test_collection_find_happy_path(conn):
    jobs = Collection(conn, "jobs")
    await jobs.insert_one(
        {
            "_id": "j1",
            "platform": "linkedin",
            "job_id": "1",
            "title": "Backend Engineer",
            "company": "Acme",
            "location": "Singapore",
            "description": "",
            "url": "https://x/1",
            "posted_date": None,
            "scraped_at": "2026-01-01T00:00:00",
        }
    )
    await jobs.insert_one(
        {
            "_id": "j2",
            "platform": "linkedin",
            "job_id": "2",
            "title": "ML Engineer",
            "company": "Beta",
            "location": "Remote",
            "description": "",
            "url": "https://x/2",
            "posted_date": None,
            "scraped_at": "2026-01-02T00:00:00",
        }
    )

    rows = await jobs.find({"platform": "linkedin"}, limit=1, order_by="scraped_at", desc=True)
    assert len(rows) == 1
    assert rows[0]["_id"] == "j2"
