import os
import sys
import psycopg2

SQL_FILE = os.path.join(os.path.dirname(__file__), 'sql', 'create_tables.sql')
DB_URL = os.getenv('DATABASE_URL') or 'postgresql://postgres:Rana1515@localhost:5432/chess'

print('Using DB URL:', DB_URL)

if not os.path.exists(SQL_FILE):
    print('SQL file not found:', SQL_FILE)
    sys.exit(1)

with open(SQL_FILE, 'r', encoding='utf-8') as fh:
    sql = fh.read()

try:
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql)
    print('SQL executed successfully')
except Exception as e:
    print('Error executing SQL:', e)
    sys.exit(2)
finally:
    try:
        conn.close()
    except Exception:
        pass
