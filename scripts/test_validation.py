import sys
sys.path.insert(0, '.')
from app.room_manager import RoomManager
from app.game_engine import Player, PlayerColor, GameEngine

rm = RoomManager()
room = rm.create_room('testroom','creator')
# create player
p1 = Player(id='p1', name='Alice', color=PlayerColor.RED)
rm.join_room(room.room_id, p1)
rm.start_room_game(room.room_id)
room = rm.get_room(room.room_id)
# set players to only p1 for test
room.game_state.players = [p1]
room.game_state.current_player_index = 0
# simulate roll
room.game_state.dice_value = 6
room.game_state.dice_rolled = True
# token unopened
token = p1.tokens[0]
print('token pos before', token.position)
# expected new pos
expected = GameEngine.calculate_new_position(token, 6, p1.color)
print('expected new pos', expected)
valid = rm.validate_move(room.room_id, 'p1', 0, expected, 6)
print('validate_move returned', valid)
# try invalid dice value
invalid = rm.validate_move(room.room_id, 'p1', 0, expected, 5)
print('validate with wrong dice returned', invalid)
