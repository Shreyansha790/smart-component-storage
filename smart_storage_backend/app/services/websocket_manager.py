"""
WebSocket Connection Manager.

Manages persistent client connections and facilitates real-time broadcasting
of smoothed environmental telemetry and actuator states to connected frontends.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("websocket_manager")


class ConnectionManager:
    """Manages active WebSocket connections and broadcasting."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Accepts and stores an incoming WebSocket client connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "WebSocket client connected. Total active connections: %d",
            len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket):
        """Removes a WebSocket client connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                "WebSocket client disconnected. Total active connections: %d",
                len(self.active_connections),
            )

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Sends a JSON message directly to a specific client."""
        try:
            await websocket.send_json(message)
        except Exception as exc:
            logger.warning("Error sending message to client: %s", exc)
            self.disconnect(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcasts a JSON payload concurrently to all connected WebSocket clients with a timeout.
        Dead, disconnected, or timed-out connections are cleanly pruned without stalling the caller.
        """
        if not self.active_connections:
            return

        connections = list(self.active_connections)
        tasks = [
            asyncio.wait_for(conn.send_json(message), timeout=1.0)
            for conn in connections
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        dead_connections: List[WebSocket] = []
        for conn, result in zip(connections, results):
            if isinstance(result, Exception):
                logger.debug("Pruning dead or timed-out WebSocket connection during broadcast: %s", result)
                dead_connections.append(conn)

        for dead in dead_connections:
            self.disconnect(dead)


# Global singleton connection manager
ws_manager = ConnectionManager()
