import os
import sqlite3
import pytest

from app import database as dbmod


@pytest.mark.asyncio
async def test_connect_creates_expected_tables_and_columns(tmp_path):
    dbfile = tmp_path / "test_job_search.db"
    original = dbmod.DATABASE_FILE
    dbmod.DATABASE_FILE = str(dbfile)
    try:
        await dbmod.connect_to_mongo()
        conn = sqlite3.connect(str(dbfile))
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        assert {"users", "resumes", "jobs", "applications", "gridfs"}.issubset(tables)

        cur.execute("PRAGMA table_info(resumes)")
        cols = {r[1] for r in cur.fetchall()}
        assert {
            "id",
            "_id",
            "user_id",
            "filename",
            "content_hash",
            "file_id",
            "parsed_data",
            "search_terms",
            "parsing_status",
            "parsing_error",
            "upload_date",
            "updated_at",
        }.issubset(cols)
        conn.close()
    finally:
        await dbmod.close_mongo_connection()
        dbmod.DATABASE_FILE = original


@pytest.mark.asyncio
async def test_user_and_resume_insert_data_shape(tmp_path):
    dbfile = tmp_path / "test_insert.db"
    original = dbmod.DATABASE_FILE
    dbmod.DATABASE_FILE = str(dbfile)
    try:
        await dbmod.connect_to_mongo()
        db = dbmod.get_database()
        fs = dbmod.get_gridfs()

        await db.users.insert_one(
            {
                "_id": "u1",
                "username": "inder",
                "email": "inder@example.com",
                "password_hash": "hashed",
                "created_at": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            }
        )
        fid = await fs.put(b"%PDF-1.4", "resume.pdf")
        await db.resumes.insert_one(
            {
                "_id": "r1",
                "user_id": "u1",
                "filename": "resume.pdf",
                "content_hash": "abc123",
                "file_id": fid,
                "parsed_data": {"raw_text": "hello", "skills": []},
                "search_terms": ["python dev"],
                "parsing_status": "completed",
                "upload_date": "2026-01-01T00:00:00",
                "updated_at": "2026-01-01T00:00:00",
            }
        )
        row = await db.resumes.find_one({"_id": "r1"})
        assert row["user_id"] == "u1"
        assert row["filename"] == "resume.pdf"
        assert row["parsed_data"]["raw_text"] == "hello"
        assert row["search_terms"] == ["python dev"]
    finally:
        await dbmod.close_mongo_connection()
        dbmod.DATABASE_FILE = original
