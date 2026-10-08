"""Utilidades compartidas: un servidor WebSocket falso que imita /api/v1/ws."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

VALID_TOKEN = "gm_dev_prueba"


@dataclass
class FakeGMini:
    """Servidor /api/v1/ws minimo. Guarda lo que recibe y permite empujar frames."""

    token: str = VALID_TOKEN
    received: list[dict[str, Any]] = field(default_factory=list)
    headers: list[Headers] = field(default_factory=list)
    connections: list[ServerConnection] = field(default_factory=list)
    on_frame: Callable[[dict[str, Any]], None] | None = None
    port: int = 0
    _server: Any = None
    _frame_event: asyncio.Event = field(default_factory=asyncio.Event)

    async def start(self) -> FakeGMini:
        async def process_request(connection: ServerConnection, request: Request) -> Response | None:
            self.headers.append(request.headers)
            if request.headers.get("Authorization") != f"Bearer {self.token}":
                return connection.respond(403, "token invalido\n")
            return None

        self._server = await serve(self._handler, "127.0.0.1", 0, process_request=process_request)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}/api/v1/ws"

    async def _handler(self, ws: ServerConnection) -> None:
        self.connections.append(ws)
        async for raw in ws:
            frame = json.loads(raw)
            self.received.append(frame)
            self._frame_event.set()
            kind = frame.get("type")
            if kind == "hello":
                await ws.send(json.dumps({"type": "ready", "agent_name": "G-Mini", "protocol": 1,
                                          "session_id": "ses_test"}))
            elif kind == "ping":
                await ws.send('{"type": "pong"}')
            elif kind == "node.register":
                await ws.send(json.dumps({"type": "node.registered", "surfaces": frame.get("surfaces")}))
            if self.on_frame:
                self.on_frame(frame)

    async def push(self, frame: dict[str, Any]) -> None:
        await self.connections[-1].send(json.dumps(frame))

    async def wait_for(self, kind: str, timeout: float = 3.0, **match: Any) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            for frame in self.received:
                if frame.get("type") == kind and all(frame.get(k) == v for k, v in match.items()):
                    return frame
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise AssertionError(f"No llego un frame {kind} {match}; recibidos: {self.received}")
            self._frame_event.clear()
            try:
                await asyncio.wait_for(self._frame_event.wait(), timeout=remaining)
            except TimeoutError:
                pass

    async def close(self) -> None:
        self._server.close()
        await self._server.wait_closed()


async def eventually(check: Callable[[], bool], timeout: float = 3.0, message: str = "condicion") -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"No se cumplio: {message}")
        await asyncio.sleep(0.01)
