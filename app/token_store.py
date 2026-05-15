import json
import os
import threading
from datetime import datetime

TOKEN_BLOCKLIST_FILE = 'token_blocklist.json'
_TOKEN_LOCK = threading.Lock()


def _load_blocklist():
    if not os.path.exists(TOKEN_BLOCKLIST_FILE):
        return []
    try:
        with open(TOKEN_BLOCKLIST_FILE, 'r', encoding='utf-8') as file_handle:
            data = json.load(file_handle)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_blocklist(items):
    with open(TOKEN_BLOCKLIST_FILE, 'w', encoding='utf-8') as file_handle:
        json.dump(items, file_handle, indent=2)


def revoke_token(jti, token_type='access', expires_at=None):
    if not jti:
        return
    with _TOKEN_LOCK:
        items = _load_blocklist()
        if any(item.get('jti') == jti for item in items):
            return
        items.append({
            'jti': jti,
            'token_type': token_type,
            'revoked_at': datetime.utcnow().isoformat(),
            'expires_at': expires_at,
        })
        _save_blocklist(items)


def is_token_revoked(jti):
    if not jti:
        return True
    items = _load_blocklist()
    return any(item.get('jti') == jti for item in items)


def cleanup_blocklist():
    with _TOKEN_LOCK:
        items = _load_blocklist()
        if not items:
            return
        now = datetime.utcnow()
        kept = []
        for item in items:
            expires_at = item.get('expires_at')
            if not expires_at:
                kept.append(item)
                continue
            try:
                expires_dt = datetime.fromisoformat(str(expires_at).replace('Z', '+00:00'))
                if expires_dt > now:
                    kept.append(item)
            except Exception:
                kept.append(item)
        _save_blocklist(kept)
