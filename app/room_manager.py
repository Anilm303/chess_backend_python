# Ludo Room Manager - Handle multiplayer rooms
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from app.game_engine import GameState, Player, PlayerColor, GameStatus, GameEngine
import logging

logger = logging.getLogger(__name__)

class GameRoom:
    """Represents a single multiplayer game room"""
    
    def __init__(
        self,
        room_id: str,
        name: str,
        creator_id: str,
        max_players: int = 4,
    ):
        self.room_id = room_id
        self.name = name
        self.creator_id = creator_id
        self.max_players = max_players
        self.players: Dict[str, Player] = {}
        self.game_state: Optional[GameState] = None
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.is_started = False
        self.spectators: set = set()
        self.locked_by: Optional[str] = None
        self.state_version = 0

    @property
    def is_full(self) -> bool:
        return len(self.players) >= self.max_players

    @property
    def player_ids(self) -> List[str]:
        return list(self.players.keys())

    def add_player(self, player: Player) -> bool:
        """Add player to room"""
        if self.is_full:
            logger.warning(f"Room {self.room_id} is full")
            return False
        
        if player.id in self.players:
            logger.warning(f"Player {player.id} already in room {self.room_id}")
            return False
        
        self.players[player.id] = player
        logger.info(f"Player {player.name} added to room {self.room_id}")
        return True

    def remove_player(self, player_id: str) -> bool:
        """Remove player from room"""
        if player_id in self.players:
            del self.players[player_id]
            logger.info(f"Player {player_id} removed from room {self.room_id}")
            return True
        return False

    def add_spectator(self, spectator_id: str) -> None:
        """Add spectator"""
        self.spectators.add(spectator_id)

    def remove_spectator(self, spectator_id: str) -> None:
        """Remove spectator"""
        self.spectators.discard(spectator_id)

    def start_game(self) -> bool:
        """Start the game"""
        if len(self.players) < 2:
            logger.warning(f"Cannot start game in room {self.room_id}: not enough players")
            return False
        
        if self.is_started:
            logger.warning(f"Game in room {self.room_id} already started")
            return False
        
        # Create game state
        players = list(self.players.values())
        self.game_state = GameState(
            id=self.room_id,
            players=players,
            status=GameStatus.PLAYING,
        )
        self.game_state.started_at = datetime.now()
        self.is_started = True
        self.started_at = datetime.now()
        
        logger.info(f"Game started in room {self.room_id} with {len(players)} players")
        return True

    def to_dict(self) -> dict:
        return {
            "roomId": self.room_id,
            "name": self.name,
            "creatorId": self.creator_id,
            "maxPlayers": self.max_players,
            "playerCount": len(self.players),
            "playerIds": self.player_ids,
            "isStarted": self.is_started,
            "isFull": self.is_full,
            "createdAt": self.created_at.isoformat(),
        }

class RoomManager:
    """Manage all multiplayer game rooms"""
    
    def __init__(self):
        self.rooms: Dict[str, GameRoom] = {}
        self.player_rooms: Dict[str, str] = {}  # player_id -> room_id
        logger.info("RoomManager initialized")

    def create_room(
        self,
        room_name: str,
        creator_id: str,
        max_players: int = 4,
    ) -> GameRoom:
        """Create a new game room"""
        room_id = str(uuid.uuid4())[:8].upper()
        room = GameRoom(room_id, room_name, creator_id, max_players)
        self.rooms[room_id] = room
        logger.info(f"Room {room_id} created by {creator_id}")
        return room

    def join_room(self, room_id: str, player: Player) -> bool:
        """Join existing room"""
        if room_id not in self.rooms:
            logger.warning(f"Room {room_id} not found")
            return False
        
        room = self.rooms[room_id]
        
        if room.is_started:
            # Can only watch if game started
            room.add_spectator(player.id)
            logger.info(f"Player {player.id} joined as spectator in room {room_id}")
            return True
        
        if room.is_full:
            logger.warning(f"Room {room_id} is full")
            return False
        
        if room.add_player(player):
            self.player_rooms[player.id] = room_id
            return True
        
        return False

    def leave_room(self, room_id: str, player_id: str) -> None:
        """Leave room"""
        if room_id not in self.rooms:
            return
        
        room = self.rooms[room_id]
        room.remove_player(player_id)
        room.remove_spectator(player_id)
        
        if player_id in self.player_rooms:
            del self.player_rooms[player_id]
        
        # Delete room if empty
        if len(room.players) == 0 and len(room.spectators) == 0:
            del self.rooms[room_id]
            logger.info(f"Room {room_id} deleted (empty)")

    def get_room(self, room_id: str) -> Optional[GameRoom]:
        """Get room by ID"""
        return self.rooms.get(room_id)

    def get_player_room(self, player_id: str) -> Optional[GameRoom]:
        """Get room where player is playing"""
        room_id = self.player_rooms.get(player_id)
        if room_id:
            return self.rooms.get(room_id)
        return None

    def list_available_rooms(self) -> List[GameRoom]:
        """List all available rooms (not started or not full)"""
        return [
            room for room in self.rooms.values()
            if not room.is_started and not room.is_full
        ]

    def start_room_game(self, room_id: str) -> bool:
        """Start game in room"""
        room = self.get_room(room_id)
        if room:
            return room.start_game()
        return False

    def validate_move(
        self,
        room_id: str,
        player_id: str,
        token_id: int,
        new_position: int,
        dice_value: int,
    ) -> bool:
        """Validate if move is legal"""
        room = self.get_room(room_id)
        if not room or not room.game_state:
            return False
        
        game_state = room.game_state
        
        # Check if it's player's turn
        if game_state.current_player.id != player_id:
            logger.warning(f"Not player {player_id}'s turn in room {room_id}")
            return False
        
        # Get token
        player = room.players.get(player_id)
        if not player or token_id >= len(player.tokens):
            return False
        
        token = player.tokens[token_id]
        
        # Validate move
        return GameEngine.is_valid_move(token, dice_value, new_position)

    def execute_move(
        self,
        room_id: str,
        player_id: str,
        token_id: int,
    ) -> bool:
        """Execute move in room"""
        room = self.get_room(room_id)
        if not room or not room.game_state:
            return False
        
        game_state = room.game_state
        player = room.players.get(player_id)
        
        if not player or token_id >= len(player.tokens):
            return False
        
        token = player.tokens[token_id]
        return GameEngine.execute_move(game_state, token, game_state.dice_value)

    def end_turn(self, room_id: str) -> None:
        """End current player's turn"""
        room = self.get_room(room_id)
        if not room or not room.game_state:
            return
        
        game_state = room.game_state
        game_state.current_player_index = (
            game_state.current_player_index + 1
        ) % len(game_state.players)
        room.state_version += 1
