"""Verify the DATABASE_URL can reach the database from this machine.

Works for both local Postgres and Neon/Supabase/RDS. The script:
  1. Parses the URL and prints what it found.
  2. Picks the right sslmode automatically (local -> disable, cloud -> require).
  3. Connects and prints server version + list of tables.
  4. If the required chess tables are missing, prints next steps.

Usage:
    cd chess_backend
    set DATABASE_URL=postgresql://...   (or use the existing .env)
    python test_neon_connection.py

If you have DATABASE_URL in .env, just run it - no env var needed.
"""
import os
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from sqlalchemy.engine import make_url

# Load .env into os.environ if present (so users don't need to set vars manually)
ENV_FILE = Path(__file__).resolve().parent / '.env'
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        os.environ.setdefault(key.strip(), value.strip())


def _is_local(url) -> bool:
    return (url.host or '').lower() in {'localhost', '127.0.0.1', '::1'}


def main() -> int:
    database_url = os.getenv('DATABASE_URL', '').strip()
    if not database_url:
        print('ERROR: DATABASE_URL is not set.')
        print('  1. Add it to chess_backend/.env, or')
        print('  2. Run:  set DATABASE_URL=postgresql://...')
        return 1

    try:
        url = make_url(database_url)
    except Exception as exc:
        print(f'ERROR: Invalid DATABASE_URL: {exc}')
        return 1

    is_local = _is_local(url)
    query = dict(url.query) if url.query else {}
    if is_local:
        sslmode = query.get('sslmode') or 'disable'
    else:
        if 'sslmode' not in query:
            sep = '&' if '?' in database_url else '?'
            database_url = database_url + sep + 'sslmode=require'
            os.environ['DATABASE_URL'] = database_url
            url = make_url(database_url)
            query = dict(url.query)
        sslmode = query.get('sslmode', 'require')

    print('Detected:')
    print(f'  Host:     {url.host}')
    print(f'  Port:     {url.port or 5432}')
    print(f'  Database: {url.database}')
    print(f'  User:     {url.username}')
    print(f'  sslmode:  {sslmode}  ({"local Postgres" if is_local else "cloud (Neon/Supabase)"})')
    print()

    print('Connecting...')
    start = time.time()
    try:
        conn = psycopg2.connect(
            host=url.host,
            port=url.port or 5432,
            user=url.username,
            password=url.password,
            dbname=url.database,
            cursor_factory=RealDictCursor,
            connect_timeout=10,
            sslmode=sslmode,
            application_name='chess-backend-test',
        )
    except OperationalError as exc:
        print(f'CONNECT FAILED: {exc}')
        print()
        if is_local:
            print('Local Postgres tips:')
            print('  - Make sure PostgreSQL is running:  services.msc -> postgresql-x64')
            print('  - Or in another terminal:  pg_ctl -D "C:\\Program Files\\PostgreSQL\\16\\data" start')
            print('  - Verify the password with:  psql -U postgres -h localhost')
        else:
            print('Cloud tips:')
            print('  1. Wrong password (Neon shows it once - copy carefully)')
            print('  2. Wrong host (must end in .neon.tech or .aws.neon.tech)')
            print('  3. Neon project is paused - check console.neon.tech')
            print('  4. Network blocked - try a different network')
        return 2
    except Exception as exc:
        print(f'UNEXPECTED ERROR: {exc!r}')
        return 3

    elapsed = (time.time() - start) * 1000
    print(f'Connected in {elapsed:.0f} ms')

    try:
        with conn.cursor() as cur:
            cur.execute('SELECT version()')
            version = cur.fetchone()['version']
            print(f'Server: {version[:80]}')

            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
            tables = [row['tablename'] for row in cur.fetchall()]
        print(f'Existing tables ({len(tables)}): {", ".join(tables) if tables else "(none)"}')

        required = {'users', 'tournaments', 'tournament_participants', 'payments'}
        missing = required - set(tables)
        if missing:
            print()
            print(f'MISSING required tables: {", ".join(sorted(missing))}')
            print()
            print('Run migrations with:')
            print('  python auto_migrate.py')
        else:
            print()
            print('OK! All required tables exist. Backend is ready.')
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
