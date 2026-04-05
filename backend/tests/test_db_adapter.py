import sqlite3
import pytest

from app.db_adapter import Collection, GridFS


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    cur = c.cursor()
    cur.execute(
        """CREATE TABLE users (
            id TEXT PRIMARY KEY,
            _id TEXT,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE resumes (
            id TEXT PRIMARY KEY,
            _id TEXT,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            content_hash TEXT,
            file_id TEXT,
            parsed_data TEXT,
            search_terms TEXT,
            parsing_status TEXT NOT NULL,
            parsing_error TEXT,
            upload_date TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE gridfs (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            data BLOB NOT NULL,
            upload_date TEXT NOT NULL
        )"""
    )
    c.commit()
    yield c
    c.close()


@pytest.mark.asyncio
async def test_collection_insert_find_update_delete_happy_path(conn):
    users = Collection(conn, "users")
    await users.insert_one(
        {
            "_id": "u1",
            "username": "inder",
            "email": "inder@example.com",
            "password_hash": "x",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
        }
    )
    row = await users.find_one({"_id": "u1"})
    assert row["username"] == "inder"
    await users.update_one({"_id": "u1"}, {"$set": {"email": "new@example.com"}})
    row2 = await users.find_one({"id": "u1"})
    assert row2["email"] == "new@example.com"
    res = await users.delete_one({"_id": "u1"})
    assert res.deleted_count == 1


@pytest.mark.asyncio
async def test_collection_sad_path_duplicate_username(conn):
    users = Collection(conn, "users")
    doc = {
        "_id": "u1",
        "username": "inder",
        "email": "inder@example.com",
        "password_hash": "x",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    await users.insert_one(doc)
    with pytest.raises(Exception, match="Duplicate key error"):
        await users.insert_one({**doc, "_id": "u2"})


@pytest.mark.asyncio
async def test_gridfs_put_get_delete_happy_path(conn):
    fs = GridFS(conn)
    file_id = await fs.put(b"hello", filename="a.pdf")
    out = await fs.get(file_id)
    assert out is not None
    assert await out.read() == b"hello"
    await fs.delete(file_id)
    out2 = await fs.get(file_id)
    assert out2 is None
