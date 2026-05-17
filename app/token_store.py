import json
import os
import threading
from datetime import datetime

TOKEN_BLOCKLIST_FILE = 'token_blocklist.json'
# Allow configuring the blocklist path via env so deployments can opt to keep it ephemeral
_BLOCKLIST_PATH = os.getenv('TOKEN_BLOCKLIST_PATH', TOKEN_BLOCKLIST_FILE)
_TOKEN_LOCK = threading.Lock()


def _load_blocklist():
    if not os.path.exists(_BLOCKLIST_PATH):
        return []
    try:
        with open(_BLOCKLIST_PATH, 'r', encoding='utf-8') as file_handle:
            data = json.load(file_handle)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_blocklist(items):
    # Ensure directory exists
    directory = os.path.dirname(_BLOCKLIST_PATH)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception:
            pass
    with open(_BLOCKLIST_PATH, 'w', encoding='utf-8') as file_handle:
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


def clear_blocklist():
    """Remove the persistent blocklist file entirely.

    Useful for deployment scripts that want to reset authentication state.
    """
    with _TOKEN_LOCK:
        try:
            if os.path.exists(_BLOCKLIST_PATH):
                os.remove(_BLOCKLIST_PATH)
        except Exception:
            pass
