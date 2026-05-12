# Deploy Chess Backend to Hugging Face Spaces

This backend is deploy-ready for a Hugging Face Space using Docker.

## 1) Create a Space

1. Go to Hugging Face -> New Space.
2. Choose a name.
3. Select SDK: `Docker`.
4. Create the Space.

## 2) Push backend code

Push the contents of this folder (`chess-backend`) to your Space repository.

Required files:

- `Dockerfile`
- `run.py`
- `requirements.txt`
- `app/` and other backend files

## 3) Runtime environment variables (recommended)

In Space Settings -> Variables, set:

- `SECRET_KEY`: your strong secret
- `JWT_SECRET_KEY`: your strong JWT secret
- `FLASK_DEBUG`: `false`

Note: `run.py` already supports `PORT` for Hugging Face and falls back to `FLASK_PORT`.

## 4) Verify deployment

Once build is successful, open:

`https://<your-username>-<your-space-name>.hf.space/api/auth/health`

Expected JSON:

```json
{
  "status": "healthy",
  "service": "chess-auth-api"
}
```

## 5) Update Flutter app base URL

Use this API base URL in Flutter:

`https://<your-username>-<your-space-name>.hf.space/api`

You can set it in app UI from Login/Register screen backend URL dialog,
or via `--dart-define=API_BASE_URL=...` during build.

## Important note

Current storage uses local JSON files (`users.json`, `messages.json`, etc.).
On free hosting, local filesystem may not be durable across restarts/redeploys.
For production use, move data to an external database.