"""
Admin router for browsing SQLite tables and records.
"""
import re
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.database import get_database
from app.routers.auth import get_current_user

router = APIRouter()

SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_safe_identifier(identifier: str) -> bool:
    return bool(identifier and SAFE_IDENTIFIER_RE.fullmatch(identifier))


def _quote_identifier(identifier: str) -> str:
    return f'"{identifier}"'


def list_user_tables(conn: sqlite3.Connection) -> list[str]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    return [row[0] for row in cursor.fetchall() if is_safe_identifier(row[0])]


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    if not is_safe_identifier(table_name):
        raise ValueError("Unsafe table name")

    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({_quote_identifier(table_name)})")
    rows = cursor.fetchall()
    return [
        {
            "name": row[1],
            "type": row[2],
            "notnull": bool(row[3]),
            "default": row[4],
            "primary_key": bool(row[5]),
        }
        for row in rows
    ]


def ensure_allowed_table(conn: sqlite3.Connection, table_name: str) -> None:
    if not is_safe_identifier(table_name):
        raise HTTPException(status_code=400, detail="Invalid table name")
    if table_name not in set(list_user_tables(conn)):
        raise HTTPException(status_code=404, detail="Table not found")


def _serialize_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return f"<BLOB {len(value)} bytes>"
    return value


@router.get("/tables")
async def admin_list_tables(current_user: dict = Depends(get_current_user)):
    del current_user
    db = get_database()
    conn = getattr(db, "conn", None) if db else None
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection is unavailable")

    table_names = list_user_tables(conn)
    tables = []
    for name in table_names:
        tables.append(
            {
                "name": name,
                "columns": get_table_columns(conn, name),
            }
        )

    return {"tables": tables}


@router.get("/tables/{table_name}/rows")
async def admin_get_table_rows(
    table_name: str,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    del current_user
    db = get_database()
    conn = getattr(db, "conn", None) if db else None
    if conn is None:
        raise HTTPException(status_code=503, detail="Database connection is unavailable")

    ensure_allowed_table(conn, table_name)

    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {_quote_identifier(table_name)} LIMIT ?", (limit,))
    db_rows = cursor.fetchall()

    rows = []
    for row in db_rows:
        item = {}
        for key in row.keys():
            item[key] = _serialize_value(row[key])
        rows.append(item)

    return {
        "table": table_name,
        "limit": limit,
        "count": len(rows),
        "columns": get_table_columns(conn, table_name),
        "rows": rows,
    }
