# Ludo WebSocket Handler - Real-time multiplayer communication
from fastapi import WebSocket
from typing import Dict, Set, List
import json
import logging
from app.game_engine import GameEngine, Player, PlayerColor, GameStatus

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # room_id -> set of websockets
        self.player_connections: Dict[str, WebSocket] = {}  # player_id -> websocket

    async def connect(self, websocket: WebSocket, room_id: str, player_id: str):
        """Add a new connection"""
        await websocket.accept()
        
        if room_id not in self.active_connections:
            self.active_connections[room_id] = set()
        
        self.active_connections[room_id].add(websocket)
        self.player_connections[player_id] = websocket
        
        logger.info(f"Player {player_id} connected to room {room_id}")

    def disconnect(self, room_id: str, player_id: str):
        """Remove a connection"""
        if room_id in self.active_connections:
            # Find and remove websocket
            for ws in list(self.active_connections[room_id]):
                try:
                    if self.player_connections.get(player_id) == ws:
                        self.active_connections[room_id].discard(ws)
                        break
                except:
                    pass
        
        if player_id in self.player_connections:
            del self.player_connections[player_id]
        
        logger.info(f"Player {player_id} disconnected from room {room_id}")

    async def broadcast_to_room(self, room_id: str, message: dict):
        """Send message to all players in room"""
        if room_id not in self.active_connections:
            return
        
        disconnected = set()
        for connection in self.active_connections[room_id]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected
        self.active_connections[room_id] -= disconnected

    async def send_personal_message(self, player_id: str, message: dict):
        """Send message to specific player"""
        if player_id in self.player_connections:
            try:
                await self.player_connections[player_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending personal message: {e}")

# Global connection manager
connection_manager = ConnectionManager()

def setup_websocket_handlers(app, room_manager, game_engine):
    """Setup WebSocket handlers for the app"""
    
    @app.websocket("/ws/{room_id}/{player_id}")
    async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
        """Main WebSocket endpoint for multiplayer games"""
        
        await connection_manager.connect(websocket, room_id, player_id)
        
        try:
            while True:
                data = await websocket.receive_json()
                event_type = data.get("type")
                
                # Handle different event types
                if event_type == "join_room":
                    await handle_join_room(
                        websocket, room_id, player_id, data, room_manager
                    )
                
                elif event_type == "start_game":
                    await handle_start_game(
                        websocket, room_id, player_id, data, room_manager
                    )
                
                elif event_type == "roll_dice":
                    await handle_roll_dice(
                        websocket, room_id, player_id, data, room_manager, game_engine
                    )
                
                elif event_type == "move_token":
                    await handle_move_token(
                        websocket, room_id, player_id, data, room_manager, game_engine
                    )
                
                elif event_type == "get_state":
                    await handle_get_state(
                        websocket, room_id, player_id, data, room_manager
                    )
                
                elif event_type == "chat":
                    await handle_chat(
                        websocket, room_id, player_id, data
                    )
        
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        
        finally:
            connection_manager.disconnect(room_id, player_id)
            # Notify others that player left
            await connection_manager.broadcast_to_room(
                room_id,
                {
                    "type": "player_left",
                    "playerId": player_id,
                }
            )

async def handle_join_room(websocket, room_id, player_id, data, room_manager):
    """Handle player joining room"""
    room = room_manager.get_room(room_id)
    if room:
        await connection_manager.broadcast_to_room(
            room_id,
            {
                "type": "player_joined",
                "room": room.to_dict(),
                "playerId": player_id,
                "playerName": data.get("playerName"),
            }
        )
        logger.info(f"Player {player_id} joined room {room_id}")

async def handle_start_game(websocket, room_id, player_id, data, room_manager):
    """Handle game start"""
    if room_manager.start_room_game(room_id):
        room = room_manager.get_room(room_id)
        await connection_manager.broadcast_to_room(
            room_id,
            {
                "type": "game_started",
                "gameState": room.game_state.to_dict() if room.game_state else None,
            }
        )
        logger.info(f"Game started in room {room_id}")

async def handle_roll_dice(websocket, room_id, player_id, data, room_manager, game_engine):
    """Handle dice roll"""
    room = room_manager.get_room(room_id)
    if not room or not room.game_state:
        return
    
    game_state = room.game_state
    
    # Only current player can roll
    if game_state.current_player.id != player_id:
        await connection_manager.send_personal_message(
            player_id,
            {
                "type": "error",
                "message": "Not your turn",
            }
        )
        return
    
    # Roll dice
    dice_value = GameEngine.roll_dice()
    game_state.dice_value = dice_value
    game_state.dice_rolled = True
    room.state_version += 1
    
    # Get movable tokens
    movable_tokens = GameEngine.get_movable_tokens(game_state.current_player, dice_value)
    game_state.can_move = len(movable_tokens) > 0
    
    # Broadcast dice roll
    await connection_manager.broadcast_to_room(
        room_id,
        {
            "type": "dice_rolled",
            "playerId": player_id,
            "diceValue": dice_value,
            "canMove": game_state.can_move,
            "gameState": game_state.to_dict(),
        }
    )

async def handle_move_token(websocket, room_id, player_id, data, room_manager, game_engine):
    """Handle token move"""
    room = room_manager.get_room(room_id)
    if not room or not room.game_state:
        return
    
    game_state = room.game_state
    token_id = data.get("tokenId")
    new_position = data.get("newPosition")
    
    # Validate move
    if not room_manager.validate_move(room_id, player_id, token_id, new_position, game_state.dice_value):
        await connection_manager.send_personal_message(
            player_id,
            {
                "type": "move_invalid",
                "message": "Invalid move",
            }
        )
        return
    
    # Execute move
    if room_manager.execute_move(room_id, player_id, token_id):
        player = game_state.current_player
        
        # Check for win
        if GameEngine.check_win(player):
            game_state.winner = player
            game_state.status = GameStatus.FINISHED
            
            await connection_manager.broadcast_to_room(
                room_id,
                {
                    "type": "game_ended",
                    "winner": player.to_dict(),
                    "gameState": game_state.to_dict(),
                }
            )
            return
        
        # Check if 6 rolled
        if game_state.dice_value != 6:
            # End turn
            room_manager.end_turn(room_id)
        
        room.state_version += 1
        
        # Broadcast move
        await connection_manager.broadcast_to_room(
            room_id,
            {
                "type": "token_moved",
                "playerId": player_id,
                "tokenId": token_id,
                "newPosition": new_position,
                "gameState": game_state.to_dict(),
            }
        )

async def handle_get_state(websocket, room_id, player_id, data, room_manager):
    """Handle get game state request"""
    room = room_manager.get_room(room_id)
    if room and room.game_state:
        await connection_manager.send_personal_message(
            player_id,
            {
                "type": "game_state",
                "gameState": room.game_state.to_dict(),
            }
        )

async def handle_chat(websocket, room_id, player_id, data):
    """Handle chat message"""
    message = data.get("message")
    await connection_manager.broadcast_to_room(
        room_id,
        {
            "type": "chat",
            "playerId": player_id,
            "message": message,
        }
    )
