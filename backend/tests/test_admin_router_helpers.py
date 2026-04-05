import sqlite3

import pytest
from fastapi import HTTPException

from app.routers.admin import (
    ensure_allowed_table,
    get_table_columns,
    is_safe_identifier,
    list_user_tables,
)


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()
    cursor.execute("CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL)")
    cursor.execute("CREATE TABLE jobs (id TEXT PRIMARY KEY, title TEXT NOT NULL)")
    connection.commit()
    yield connection
    connection.close()


def test_is_safe_identifier():
    assert is_safe_identifier("users")
    assert is_safe_identifier("user_job_views")
    assert not is_safe_identifier("users; DROP TABLE users")
    assert not is_safe_identifier("users --")
    assert not is_safe_identifier("1users")
    assert not is_safe_identifier("users-name")


def test_list_user_tables_only_safe_names(conn):
    tables = list_user_tables(conn)
    assert set(tables) == {"jobs", "users"}


def test_get_table_columns_returns_metadata(conn):
    columns = get_table_columns(conn, "users")
    assert columns == [
        {
            "name": "id",
            "type": "TEXT",
            "notnull": False,
            "default": None,
            "primary_key": True,
        },
        {
            "name": "username",
            "type": "TEXT",
            "notnull": True,
            "default": None,
            "primary_key": False,
        },
    ]


def test_ensure_allowed_table_rejects_bad_name(conn):
    with pytest.raises(HTTPException) as exc:
        ensure_allowed_table(conn, "users;DROP")
    assert exc.value.status_code == 400


def test_ensure_allowed_table_rejects_unknown_table(conn):
    with pytest.raises(HTTPException) as exc:
        ensure_allowed_table(conn, "applications")
    assert exc.value.status_code == 404
