from typing import Dict, Set, Optional
from fastapi import WebSocket
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.last_ping: Dict[str, datetime] = {}
        self.initialized = False
        self.ping_interval = 30  # seconds

    async def startup(self):
        """Initialize the WebSocket manager during application startup"""
        if self.initialized:
            return
        
        self.active_connections = {
            "metrics": set(),
            "alerts": set()
        }
        self.initialized = True
        
        # Start background ping task
        asyncio.create_task(self._ping_clients())
        logger.info("WebSocket manager initialized with ping monitoring")

    async def connect(self, websocket: WebSocket, channel: str):
        """Connect a client to a specific channel"""
        try:
            await websocket.accept()
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            self.active_connections[channel].add(websocket)
            self.last_ping[websocket] = datetime.now()
            logger.info(f"Client connected to channel: {channel}")
        except Exception as e:
            logger.error(f"Error connecting client to {channel}: {str(e)}")
            raise

    def disconnect(self, websocket: WebSocket, channel: str):
        """Disconnect a client from a specific channel"""
        try:
            if channel in self.active_connections:
                self.active_connections[channel].discard(websocket)
            if websocket in self.last_ping:
                del self.last_ping[websocket]
            logger.info(f"Client disconnected from channel: {channel}")
        except Exception as e:
            logger.error(f"Error disconnecting client from {channel}: {str(e)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {str(e)}")
            await self._handle_connection_error(websocket)

    async def broadcast(self, message: dict, channel: str):
        """Broadcast a message to all clients in a channel"""
        if channel not in self.active_connections:
            logger.warning(f"Attempted to broadcast to non-existent channel: {channel}")
            return

        disconnected = set()
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {str(e)}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection, channel)

    async def _ping_clients(self):
        """Send periodic pings to check client connection status"""
        while True:
            try:
                current_time = datetime.now()
                for channel in self.active_connections:
                    disconnected = set()
                    for connection in self.active_connections[channel]:
                        try:
                            # Check if client hasn't responded for too long
                            if (current_time - self.last_ping[connection]).total_seconds() > self.ping_interval * 2:
                                logger.warning(f"Client in channel {channel} not responding")
                                disconnected.add(connection)
                                continue

                            # Send ping
                            await connection.send_json({"type": "ping"})
                            self.last_ping[connection] = current_time
                        except Exception as e:
                            logger.error(f"Error pinging client in {channel}: {str(e)}")
                            disconnected.add(connection)

                    # Clean up disconnected clients
                    for connection in disconnected:
                        self.disconnect(connection, channel)

            except Exception as e:
                logger.error(f"Error in ping monitoring: {str(e)}")

            await asyncio.sleep(self.ping_interval)

    async def _handle_connection_error(self, websocket: WebSocket):
        """Handle connection errors by cleaning up the connection"""
        for channel in self.active_connections:
            if websocket in self.active_connections[channel]:
                self.disconnect(websocket, channel)
                break

manager = ConnectionManager() 