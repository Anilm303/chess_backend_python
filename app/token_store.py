import os
import threading
from datetime import datetime

from app.postgres_store import execute, fetch_all, fetch_one

_TOKEN_LOCK = threading.Lock()


def _ensure_table():
    execute(
        """
        CREATE TABLE IF NOT EXISTS auth_token_blocklist (
          jti TEXT PRIMARY KEY,
          token_type TEXT,
          revoked_at TIMESTAMPTZ,
          expires_at TIMESTAMPTZ
        )
        """
    )


def revoke_token(jti, token_type='access', expires_at=None):
    if not jti:
        return
    with _TOKEN_LOCK:
        _ensure_table()
        execute(
            """
            INSERT INTO auth_token_blocklist (jti, token_type, revoked_at, expires_at)
            VALUES (%(jti)s, %(token_type)s, %(revoked_at)s, %(expires_at)s)
            ON CONFLICT (jti) DO UPDATE SET
                token_type = EXCLUDED.token_type,
                revoked_at = EXCLUDED.revoked_at,
                expires_at = EXCLUDED.expires_at
            """,
            {
                'jti': jti,
                'token_type': token_type,
                'revoked_at': datetime.utcnow(),
                'expires_at': expires_at,
            }
        )


def is_token_revoked(jti):
    if not jti:
        return True
    _ensure_table()
    row = fetch_one('SELECT 1 FROM auth_token_blocklist WHERE jti = %(jti)s', {'jti': jti})
    return bool(row)


def cleanup_blocklist():
    with _TOKEN_LOCK:
        _ensure_table()
        execute(
            """
            DELETE FROM auth_token_blocklist
            WHERE expires_at IS NOT NULL AND expires_at <= %(now)s
            """,
            {'now': datetime.utcnow()},
        )


def clear_blocklist():
    """Remove all revoked tokens from the database."""
    with _TOKEN_LOCK:
        _ensure_table()
        execute('DELETE FROM auth_token_blocklist')
