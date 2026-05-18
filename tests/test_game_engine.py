import sys
sys.path.insert(0, '.')
from app.game_engine import GameEngine, Player, PlayerColor, Token, GameState


def test_calculate_open_and_move():
    p_color = PlayerColor.RED
    token = Token(0, p_color, position=-1)
    pos = GameEngine.calculate_new_position(token, 6, p_color)
    assert pos == 0


def test_enter_home_and_undo():
    # create player and simulate moves to enter home
    p = Player(id='p1', name='T', color=PlayerColor.RED)
    gs = GameState(id='g1', players=[p])
    t = p.tokens[0]
    # open
    GameEngine.execute_move(gs, t, 6)
    assert t.position == 0
    # move many steps to simulate reaching home path (fast-forward by setting position near end)
    t.position = 51
    GameEngine.execute_move(gs, t, 6)
    # should move into home area (>=52)
    assert t.position >= 52
    last = gs.move_history[-1]
    assert 'newPosition' in last
    # undo
    ok = GameEngine.undo_last_move(gs)
    assert ok
    # token position reverted
    assert t.position == last['oldPosition']
