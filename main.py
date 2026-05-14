# Ludo Game Backend - Main Application
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging

# Import game modules
from app.game_engine import GameEngine
from app.room_manager import RoomManager
from app.websocket_handler import setup_websocket_handlers
from app.api_routes import router as api_router
from app.db_connection import init_db, close_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize managers (singleton)
room_manager = RoomManager()
game_engine = GameEngine()

# Global lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage app lifecycle
    """
    logger.info("Starting Ludo Game Server...")
    await init_db()
    yield
    await close_db()
    logger.info("Ludo Game Server stopped")

app = FastAPI(
    title="Ludo Game Server",
    description="Multiplayer Ludo Game API with WebSocket Support",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api", tags=["api"])

# Setup WebSocket handlers
setup_websocket_handlers(app, room_manager, game_engine)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Ludo Game Server is running",
        "version": "1.0.0",
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Ludo Game Server",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "api": "/api",
            "docs": "/docs",
            "websocket": "/ws",
        },
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
