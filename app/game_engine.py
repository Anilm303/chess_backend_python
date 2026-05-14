# Ludo Game Engine - Server-side game logic
import random
from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class PlayerColor(Enum):
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"
    BLUE = "blue"

class GameStatus(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"

@dataclass
class Token:
    id: int  # 0-3
    color: PlayerColor
    position: int = -1  # -1 = not opened, 0-51 = board, 52+ = home
    is_killed: bool = False
    is_in_home: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "color": self.color.value,
            "position": self.position,
            "isKilled": self.is_killed,
            "isInHome": self.is_in_home,
        }

@dataclass
class Player:
    id: str
    name: str
    color: PlayerColor
    tokens: List[Token] = field(default_factory=list)
    is_current_turn: bool = False
    consecutive_sixes: int = 0
    tokens_reached_home: int = 0
    is_ai: bool = False

    def __post_init__(self):
        if not self.tokens:
            self.tokens = [Token(i, self.color) for i in range(4)]

    def has_won(self) -> bool:
        return self.tokens_reached_home == 4

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color.value,
            "tokens": [t.to_dict() for t in self.tokens],
            "isCurrentTurn": self.is_current_turn,
            "consecutiveSixes": self.consecutive_sixes,
            "tokensReachedHome": self.tokens_reached_home,
            "isAI": self.is_ai,
        }

@dataclass
class GameState:
    id: str
    players: List[Player]
    status: GameStatus = GameStatus.WAITING
    current_player_index: int = 0
    dice_value: int = 0
    dice_rolled: bool = False
    can_move: bool = False
    winner: Optional[Player] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    move_history: List[dict] = field(default_factory=list)

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_index]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "players": [p.to_dict() for p in self.players],
            "status": self.status.value,
            "currentPlayerIndex": self.current_player_index,
            "diceValue": self.dice_value,
            "diceRolled": self.dice_rolled,
            "canMove": self.can_move,
            "winner": self.winner.to_dict() if self.winner else None,
            "createdAt": self.created_at.isoformat(),
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "endedAt": self.ended_at.isoformat() if self.ended_at else None,
        }

class BoardConfig:
    TOTAL_POSITIONS = 52
    HOME_POSITIONS = 6
    BOARD_SIZE = TOTAL_POSITIONS + HOME_POSITIONS
    
    PLAYER_START_POSITIONS = {
        PlayerColor.RED: 0,
        PlayerColor.GREEN: 13,
        PlayerColor.YELLOW: 26,
        PlayerColor.BLUE: 39,
    }
    
    SAFE_POSITIONS = [0, 9, 14, 22, 27, 35, 40, 48]
    
    HOME_ENTRY_POSITIONS = {
        PlayerColor.RED: 0,
        PlayerColor.GREEN: 13,
        PlayerColor.YELLOW: 26,
        PlayerColor.BLUE: 39,
    }

class GameEngine:
    """Server-side Ludo game logic"""

    @staticmethod
    def roll_dice() -> int:
        """Roll dice (1-6)"""
        return random.randint(1, 6)

    @staticmethod
    def can_token_be_moved(token: Token, dice_value: int) -> bool:
        """Check if token can be moved"""
        if token.is_killed:
            return False
        
        # Token must be opened first
        if token.position == -1:
            return dice_value == 6
        
        # Token in home path needs exact dice
        if token.is_in_home:
            remaining_steps = BoardConfig.HOME_POSITIONS - (token.position - BoardConfig.TOTAL_POSITIONS)
            return dice_value == remaining_steps
        
        return True

    @staticmethod
    def calculate_new_position(token: Token, dice_value: int, player_color: PlayerColor) -> int:
        """Calculate new position after dice roll"""
        # Token opening
        if token.position == -1:
            if dice_value == 6:
                return BoardConfig.PLAYER_START_POSITIONS[player_color]
            return -1
        
        # Token in home path
        if token.is_in_home:
            new_pos = token.position + dice_value
            if new_pos >= BoardConfig.BOARD_SIZE:
                return BoardConfig.BOARD_SIZE
            return new_pos
        
        # Token in main board
        new_pos = (token.position + dice_value) % BoardConfig.TOTAL_POSITIONS
        
        # Check if reaching home
        if token.position + dice_value >= BoardConfig.TOTAL_POSITIONS:
            remaining_to_home = BoardConfig.TOTAL_POSITIONS - token.position
            total_steps = dice_value
            
            if remaining_to_home < total_steps:
                home_path_pos = BoardConfig.TOTAL_POSITIONS + (total_steps - remaining_to_home)
                if home_path_pos <= BoardConfig.BOARD_SIZE:
                    return home_path_pos
        
        return new_pos

    @staticmethod
    def is_safe_position(position: int, player_color: PlayerColor) -> bool:
        """Check if position is safe (cannot be killed)"""
        if position == -1 or position >= BoardConfig.BOARD_SIZE:
            return True  # Home is safe
        return position in BoardConfig.SAFE_POSITIONS

    @staticmethod
    def get_movable_tokens(player: Player, dice_value: int) -> List[Token]:
        """Get all movable tokens for current player"""
        return [
            token for token in player.tokens
            if GameEngine.can_token_be_moved(token, dice_value)
        ]

    @staticmethod
    def get_tokens_at_position(
        players: List[Player],
        position: int,
        exclude_color: PlayerColor,
    ) -> List[Token]:
        """Get opponent tokens at position to kill"""
        tokens = []
        for player in players:
            if player.color == exclude_color:
                continue
            for token in player.tokens:
                if token.position == position and not token.is_killed:
                    tokens.append(token)
        return tokens

    @staticmethod
    def kill_tokens_at_position(
        players: List[Player],
        position: int,
        exclude_color: PlayerColor,
    ) -> None:
        """Kill opponent tokens at position"""
        for player in players:
            if player.color == exclude_color:
                continue
            for token in player.tokens:
                if token.position == position and not token.is_killed:
                    token.is_killed = True
                    token.position = -1

    @staticmethod
    def execute_move(
        game_state: GameState,
        token: Token,
        dice_value: int,
    ) -> bool:
        """Execute a move and return True if successful"""
        player = game_state.current_player
        
        if not GameEngine.can_token_be_moved(token, dice_value):
            return False
        
        old_position = token.position
        new_position = GameEngine.calculate_new_position(
            token, dice_value, player.color
        )
        
        token.position = new_position
        
        # Check if entered home
        if new_position >= BoardConfig.TOTAL_POSITIONS:
            token.is_in_home = True
            if new_position >= BoardConfig.TOTAL_POSITIONS + BoardConfig.HOME_POSITIONS:
                player.tokens_reached_home += 1
        
        # Check for kills
        if not token.is_in_home and not GameEngine.is_safe_position(new_position, player.color):
            GameEngine.kill_tokens_at_position(
                game_state.players,
                new_position,
                player.color,
            )
        
        return True

    @staticmethod
    def check_win(player: Player) -> bool:
        """Check if player has won"""
        return player.tokens_reached_home == 4

    @staticmethod
    def is_valid_move(
        token: Token,
        dice_value: int,
        expected_new_position: int,
    ) -> bool:
        """Validate if a move is legal"""
        if token.is_killed:
            return False
        
        if not GameEngine.can_token_be_moved(token, dice_value):
            return False
        
        calculated_pos = GameEngine.calculate_new_position(
            token, dice_value, token.color
        )
        
        return calculated_pos == expected_new_position
