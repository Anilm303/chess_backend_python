import os
from contextlib import contextmanager
from typing import Any, Iterable, Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from sqlalchemy.engine import make_url


def get_database_url() -> str:
    database_url = os.getenv('DATABASE_URL', '').strip()
    if not database_url:
        raise RuntimeError('DATABASE_URL is not set')

    url = make_url(database_url)
    if not url.host or url.host in {'host', '#host#'}:
        raise RuntimeError(
            'DATABASE_URL is still using a placeholder host. Replace "host" with your real PostgreSQL hostname.'
        )

    return database_url


@contextmanager
def get_connection():
    url = make_url(get_database_url())
    connection = psycopg2.connect(
        host=url.host,
        port=url.port,
        user=url.username,
        password=url.password,
        dbname=url.database,
        cursor_factory=RealDictCursor,
    )
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def fetch_one(query: str, params: Optional[dict] = None) -> Optional[dict]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or {})
            row = cursor.fetchone()
            return dict(row) if row else None


def fetch_all(query: str, params: Optional[dict] = None) -> list[dict]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or {})
            return [dict(row) for row in cursor.fetchall()]


def execute(query: str, params: Optional[dict] = None) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or {})
            return cursor.rowcount


def execute_returning(query: str, params: Optional[dict] = None) -> Optional[dict]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or {})
            row = cursor.fetchone()
            return dict(row) if row else None


def json_value(value: Any) -> Json:
    return Json(value)