import json
from datetime import datetime
import os

LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'audit.log')

os.makedirs(LOG_DIR, exist_ok=True)

def audit_event(event_type: str, payload: dict) -> None:
    entry = {
        'ts': datetime.utcnow().isoformat() + 'Z',
        'type': event_type,
        'payload': payload,
    }
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # avoid raising in production paths
        pass
