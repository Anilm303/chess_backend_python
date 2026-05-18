import json
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime
from app.game_engine import (
    Player, PlayerColor, Token, GameState, GameStatus
)
# Import GameRoom inside functions to avoid circular import with room_manager

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "games"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_room(room) -> None:
    """Save room metadata and game state to disk as JSON"""
    out = room.to_dict()
    if room.game_state:
        out["gameState"] = room.game_state.to_dict()
    out["stateVersion"] = room.state_version
    path = DATA_DIR / f"{room.room_id}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)


def delete_room(room_id: str) -> None:
    path = DATA_DIR / f"{room_id}.json"
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def load_room(room_id: str) -> Optional[object]:
    path = DATA_DIR / f"{room_id}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # local import to avoid circular dependency at module import time
    from app.room_manager import GameRoom

    room = GameRoom(data.get("roomId"), data.get("name"), data.get("creatorId"), data.get("maxPlayers", 4))
    room.state_version = data.get("stateVersion", 0)

    # load players if present
    gs = data.get("gameState")
    if gs:
        players = []
        for p in gs.get("players", []):
            color = PlayerColor(p.get("color"))
            tokens = []
            for t in p.get("tokens", []):
                token = Token(
                    id=int(t.get("id")),
                    color=color,
                    position=int(t.get("position", -1)),
                    is_killed=bool(t.get("isKilled", False)),
                    is_in_home=bool(t.get("isInHome", False)),
                )
                tokens.append(token)

            player = Player(
                id=p.get("id"),
                name=p.get("name"),
                color=color,
                tokens=tokens,
            )
            player.consecutive_sixes = int(p.get("consecutiveSixes", 0))
            player.tokens_reached_home = int(p.get("tokensReachedHome", 0))
            players.append(player)

        game_state = GameState(id=gs.get("id"), players=players)
        game_state.status = GameStatus(gs.get("status")) if gs.get("status") else GameStatus.WAITING
        game_state.current_player_index = int(gs.get("currentPlayerIndex", 0))
        game_state.dice_value = int(gs.get("diceValue", 0))
        game_state.dice_rolled = bool(gs.get("diceRolled", False))
        game_state.can_move = bool(gs.get("canMove", False))
        game_state.rankings = gs.get("rankings", [])
        try:
            if gs.get("startedAt"):
                game_state.started_at = datetime.fromisoformat(gs.get("startedAt"))
        except Exception:
            pass
        room.game_state = game_state

    return room


def load_all_rooms() -> Dict[str, object]:
    rooms = {}
    for p in DATA_DIR.glob("*.json"):
        rid = p.stem
        r = load_room(rid)
        if r:
            rooms[rid] = r
    return rooms
