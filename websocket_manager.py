from typing import Dict, List, Optional
from fastapi import WebSocket
import json
import logging
import asyncio
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Usar listas em vez de dicionários para armazenar conexões
        self.active_connections: Dict[str, List[tuple[str, WebSocket]]] = {}
        self.last_ping: Dict[str, datetime] = {}
        self.initialized = False
        self.ping_interval = 30  # seconds

    async def startup(self):
        """Initialize the WebSocket manager during application startup"""
        if self.initialized:
            return
        
        self.active_connections = {
            "metrics": [],
            "alerts": []
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
                self.active_connections[channel] = []
            
            # Generate unique ID for this connection
            connection_id = str(uuid.uuid4())
            self.active_connections[channel].append((connection_id, websocket))
            self.last_ping[connection_id] = datetime.now()
            logger.info(f"Client connected to channel: {channel} with ID: {connection_id}")
        except Exception as e:
            logger.error(f"Error connecting client to {channel}: {str(e)}")
            raise

    def disconnect(self, websocket: WebSocket, channel: str):
        """Disconnect a client from a specific channel"""
        try:
            if channel in self.active_connections:
                # Encontrar e remover a conexão da lista
                for idx, (conn_id, ws) in enumerate(self.active_connections[channel]):
                    if ws == websocket:
                        self.active_connections[channel].pop(idx)
                        if conn_id in self.last_ping:
                            del self.last_ping[conn_id]
                        break
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

        # Criar uma cópia da lista para evitar modificações durante a iteração
        connections = self.active_connections[channel].copy()
        disconnected = []

        for connection_id, websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client {connection_id}: {str(e)}")
                disconnected.append((connection_id, websocket))

        # Clean up disconnected clients
        for conn_id, ws in disconnected:
            self.disconnect(ws, channel)

    async def _ping_clients(self):
        """Send periodic pings to check client connection status"""
        while True:
            try:
                current_time = datetime.now()
                for channel in self.active_connections:
                    # Criar uma cópia da lista para evitar modificações durante a iteração
                    connections = self.active_connections[channel].copy()
                    disconnected = []

                    for connection_id, websocket in connections:
                        try:
                            # Check if client hasn't responded for too long
                            if (current_time - self.last_ping[connection_id]).total_seconds() > self.ping_interval * 2:
                                logger.warning(f"Client {connection_id} in channel {channel} not responding")
                                disconnected.append((connection_id, websocket))
                                continue

                            # Send ping
                            await websocket.send_json({"type": "ping"})
                            self.last_ping[connection_id] = current_time
                        except Exception as e:
                            logger.error(f"Error pinging client {connection_id} in {channel}: {str(e)}")
                            disconnected.append((connection_id, websocket))

                    # Clean up disconnected clients
                    for conn_id, ws in disconnected:
                        self.disconnect(ws, channel)

            except Exception as e:
                logger.error(f"Error in ping monitoring: {str(e)}")

            await asyncio.sleep(self.ping_interval)

    async def _handle_connection_error(self, websocket: WebSocket):
        """Handle connection errors by cleaning up the connection"""
        for channel in self.active_connections:
            for connection_id, ws in self.active_connections[channel]:
                if ws == websocket:
                    self.disconnect(websocket, channel)
                    break

manager = ConnectionManager() 