import importlib.util
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.room_manager import RoomManager
from app.game_engine import GameEngine, Player, PlayerColor, Token, GameState
from app.audit import LOG_FILE

failures = 0

print('Running minimal test runner...')

# Test: room manager create room and add bot
try:
    rm = RoomManager()
    room = rm.create_room('r','c')
    bot = rm.add_bot(room.room_id, 'AI')
    assert bot is not None and bot.is_ai
    print('test_create_room_and_add_bot: PASS')
except AssertionError:
    print('test_create_room_and_add_bot: FAIL')
    failures += 1
except Exception as e:
    print('test_create_room_and_add_bot: ERROR', e)
    failures += 1

# Test: game engine open and move
try:
    p_color = PlayerColor.RED
    token = Token(0, p_color, position=-1)
    pos = GameEngine.calculate_new_position(token, 6, p_color)
    assert pos == 0
    print('test_calculate_open_and_move: PASS')
except AssertionError:
    print('test_calculate_open_and_move: FAIL')
    failures += 1
except Exception as e:
    print('test_calculate_open_and_move: ERROR', e)
    failures += 1

# Test: audit log written by add_bot
try:
    assert os.path.exists(LOG_FILE)
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'bot_added' in content or 'Bot' in content
    print('test_audit_log_exists: PASS')
except AssertionError:
    print('test_audit_log_exists: FAIL')
    failures += 1
except Exception as e:
    print('test_audit_log_exists: ERROR', e)
    failures += 1

if failures:
    print(f'Failed: {failures} test(s)')
    sys.exit(2)

print('All tests passed')

# Additional check: delete room audit
try:
    rm2 = RoomManager()
    room2 = rm2.create_room('t2', 'u3')
    # remove the only player and trigger deletion
    rm2.leave_room(room2.room_id, 'u3')
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        content2 = f.read()
    if 'room_deleted' in content2:
        print('test_room_deleted_audit: PASS')
    else:
        print('test_room_deleted_audit: FAIL')
        sys.exit(2)
except Exception as e:
    print('test_room_deleted_audit: ERROR', e)
    sys.exit(2)
