import json
import os
import threading
from datetime import datetime, timedelta
import secrets
import logging
from werkzeug.security import generate_password_hash

from app.models.user import get_users, save_users

_FILE = os.getenv('PASSWORD_RESET_FILE', 'password_reset_tokens.json')
_LOCK = threading.Lock()


def _load_tokens():
    if not os.path.exists(_FILE):
        return []
    try:
        with open(_FILE, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
            if not isinstance(data, list):
                return []

            # Remove expired tokens on load to keep the token store clean
            now = datetime.utcnow()
            kept = []
            changed = False
            for it in data:
                expires_at = it.get('expires_at')
                try:
                    expires = datetime.fromisoformat(str(expires_at).replace('Z', '+00:00'))
                except Exception:
                    # If parsing fails, consider it expired to be safe
                    expires = now
                if expires >= now:
                    kept.append(it)
                else:
                    changed = True

            if changed:
                try:
                    _save_tokens(kept)
                except Exception:
                    pass

            return kept
    except Exception:
        return []


def _save_tokens(items):
    directory = os.path.dirname(_FILE)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception:
            pass
    with open(_FILE, 'w', encoding='utf-8') as fh:
        json.dump(items, fh, indent=2)


def _find_user_by_email(email):
    users = get_users()
    for username, data in users.items():
        if data.get('email') == email:
            return username
    return None


def create_token_for_email(email, expiry_seconds=3600):
    """Create a one-time token for the user registered with `email`.

    Returns (True, {'token': token, 'dev': True}) on success when SMTP is not configured
    or (True, {'sent': True}) if the token was created and (attempted) to be emailed.
    Returns (False, 'message') on failure.
    """
    username = _find_user_by_email(email)
    if not username:
        return False, 'Email not found'

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(seconds=expiry_seconds)).isoformat()

    with _LOCK:
        items = _load_tokens()
        # store token mapping
        items.append({'token': token, 'username': username, 'expires_at': expires_at})
        _save_tokens(items)

    # Try to send email if SMTP configured
    try:
        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = os.getenv('SMTP_PORT')
        smtp_user = os.getenv('SMTP_USER')
        smtp_pass = os.getenv('SMTP_PASSWORD')
        sender = os.getenv('SENDER_EMAIL')
        if smtp_host and smtp_port and sender:
            import smtplib
            from email.message import EmailMessage

            msg = EmailMessage()
            msg['Subject'] = 'Password reset for your Chess account'
            msg['From'] = sender
            msg['To'] = email
            # Basic instructions: token can be pasted into the app reset screen
            msg.set_content(f"To reset your password, open the app and paste this token:\n\n{token}\n\nThis token expires in 1 hour.")

            server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=10)
            try:
                server.starttls()
            except Exception:
                pass
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            return True, {'sent': True}
    except Exception:
        logging.getLogger(__name__).exception('Failed to send password reset email')

    # If email not configured or sending failed, decide whether to return token in response for dev use.
    # Enable returning the token in responses only when the environment variable
    # `PASSWORD_RESET_RETURN_TOKEN` is set to a truthy value (1/true/yes).
    if os.getenv('PASSWORD_RESET_RETURN_TOKEN', 'false').lower() in ('1', 'true', 'yes'):
        return True, {'token': token, 'dev': True}

    # Otherwise, indicate that an attempt was made but no email was sent from the app.
    return True, {'sent': False}


def verify_and_consume_token(token, new_password):
    """Verify token, set new password for the corresponding user, and consume the token."""
    if not token:
        return False, 'Token required'

    with _LOCK:
        items = _load_tokens()
        matched = None
        now = datetime.utcnow()
        kept = []
        for it in items:
            if it.get('token') == token:
                # check expiry
                try:
                    expires = datetime.fromisoformat(it.get('expires_at').replace('Z', '+00:00'))
                except Exception:
                    expires = now
                if expires < now:
                    return False, 'Token expired'
                matched = it
            else:
                kept.append(it)

        if not matched:
            return False, 'Invalid token'

        # consume token
        _save_tokens(kept)

    # change user's password
    username = matched.get('username')
    users = get_users()
    if username not in users:
        return False, 'User not found'

    users[username]['password_hash'] = generate_password_hash(new_password)
    save_users(users)
    return True, 'Password updated'
