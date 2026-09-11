"""WebSocket connection manager."""
from __future__ import annotations
from typing import List
from fastapi import WebSocket
import logging, json

logger = logging.getLogger("ws_manager")

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info("WS connected — total: %d", len(self.active))

    def disconnect(self, ws: WebSocket):
        self.active = [c for c in self.active if c != ws]
        logger.info("WS disconnected — total: %d", len(self.active))

    async def broadcast(self, data: dict):
        dead = []
        payload = json.dumps(data)
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()
