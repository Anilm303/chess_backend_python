import sys
sys.path.insert(0, '.')
from app.room_manager import RoomManager
from app.game_engine import Player, PlayerColor


def test_create_room_and_add_bot():
    rm = RoomManager()
    room = rm.create_room('r','c')
    bot = rm.add_bot(room.room_id, 'AI')
    assert bot is not None
    assert bot.is_ai
