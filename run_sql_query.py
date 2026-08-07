import os
import sys
import psycopg2

DB_URL = os.getenv('DATABASE_URL') or 'postgresql://postgres:Rana1515@localhost:5432/chess_db'

if len(sys.argv) < 2:
    print("Usage: python run_sql_query.py \"YOUR SQL HERE\"")
    sys.exit(1)

sql = sys.argv[1]
print('Using DB URL:', DB_URL)

try:
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql)
        if cur.description:
            rows = cur.fetchall()
            for row in rows:
                print(row)
        else:
            print(f"Executed successfully. Row count: {cur.rowcount}")
except Exception as e:
    print('Error executing SQL:', e)
    sys.exit(2)
finally:
    try:
        conn.close()
    except Exception:
        pass
