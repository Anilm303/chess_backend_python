import psycopg2

DB_URL = 'postgresql://postgres:Rana1515@localhost:5432/chess_db'

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("SELECT username, email, created_at FROM users ORDER BY created_at DESC LIMIT 5")
rows = cur.fetchall()
for r in rows:
    print(r)
cur.close()
conn.close()
