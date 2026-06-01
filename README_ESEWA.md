eSewa integration - testing and ngrok

1) Configure environment (use sandbox/test merchant credentials)

- Set these in your environment or .env file:
  - ESEWA_MERCHANT_ID
  - ESEWA_SECRET (if provided)
  - ESEWA_SUCCESS_URL (point to public URL e.g. https://<ngrok>.ngrok.io/api/payments/esewa/callback)
  - ESEWA_FAIL_URL
  - BASE_URL (https://<ngrok>.ngrok.io)

2) Expose your local backend using ngrok

- Start your backend (example):

```powershell
# from chess_backend folder
uvicorn main:app --reload --port 8000
ngrok http 8000
```

- Note the public forwarding URL from ngrok (e.g. https://abcd1234.ngrok.io)
- Set `ESEWA_SUCCESS_URL` to `https://abcd1234.ngrok.io/api/payments/esewa/callback`
- Set `BASE_URL` to `https://abcd1234.ngrok.io`

3) Test flow from Flutter app

- In the Flutter `TournamentPaymentButton`, set `backendBaseUrl` to your ngrok URL.
- Tap Pay -> WebView opens -> complete eSewa sandbox payment -> eSewa will redirect to your callback.
- Verify backend logs and DB `payments` table for `status = paid`.

4) Troubleshooting

- Check network and ngrok logs if callback not received.
- Inspect raw response stored in `raw_response` column for debugging.
- Ensure merchant sandbox credentials are valid and eSewa supports sandbox testing.

5) Security

- Always verify payment server-side (we do) before granting tournament access.
- Do not trust client responses.
