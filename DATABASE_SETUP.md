# Database Setup for Hugging Face Deployment

`pgAdmin` is only a database client. If your Postgres server runs on your PC, it is still local and will not be reachable from Hugging Face Spaces.

## Recommended setup

Use a managed PostgreSQL service for production:

- Supabase
- Neon
- Render Postgres

## Steps

1. Create a managed PostgreSQL database.
2. Copy the connection string.
3. Set `DATABASE_URL` in the Hugging Face Space variables.
4. Set these other variables too:
   - `SECRET_KEY`
   - `JWT_SECRET_KEY`
   - `FLASK_DEBUG=false`
   - `ALLOWED_ORIGINS`
5. Deploy the backend Space again.

## Migrate existing local data

If you already have local JSON or legacy data on your PC, migrate it into the new database from your machine:

```powershell
setx DATABASE_URL "postgresql://user:password@host:5432/chess"
python scripts/migrate_json_to_postgres.py
```

Use the same `DATABASE_URL` format in the Hugging Face Space.

## What happens after deploy

- Your frontend and backend can run on Hugging Face.
- The data will live in the external Postgres database, not on your PC.
- If you restart the Space, your data stays available as long as the managed database stays online.