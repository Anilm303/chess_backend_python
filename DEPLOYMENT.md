# Chess Backend Deployment

This backend is ready for a permanent public URL using Render or a VPS.

## Recommended production settings

- `MEDIA_STORAGE=s3`
- `MEDIA_PUBLIC_BASE_URL=https://cdn.yourdomain.com` or a public S3 URL
- `ALLOWED_ORIGINS=https://app.yourdomain.com,https://yourdomain.com`
- `SECRET_KEY` and `JWT_SECRET_KEY` must be long random values
- `DATABASE_URL` should point to PostgreSQL in production
- `REDIS_URL` is recommended for realtime state and scale-out

## Render

1. Push the repo to GitHub.
2. Create a new Render Web Service from the repo.
3. Render will use `render.yaml`.
4. Add secrets in the Render dashboard:
   - `DATABASE_URL`
   - `REDIS_URL`
   - `S3_BUCKET`
   - `S3_REGION`
   - `S3_ACCESS_KEY_ID`
   - `S3_SECRET_ACCESS_KEY`
   - `MEDIA_PUBLIC_BASE_URL`
5. Deploy.
6. Your service URL becomes the stable backend URL.

## Custom domain

- Point `api.yourdomain.com` to the Render service.
- Render provides HTTPS automatically.
- Use that URL in Flutter:

```bash
flutter build apk --release --dart-define=API_BASE_URL=https://api.yourdomain.com/api --dart-define=SOCKET_BASE_URL=https://api.yourdomain.com
```

## Media storage

If `MEDIA_STORAGE=s3`, the backend stores uploads in S3.
If `MEDIA_PUBLIC_BASE_URL` is set, uploaded media URLs will use that base.
