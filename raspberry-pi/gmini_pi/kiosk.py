"""Kiosco para tablets y PCs viejas: sirve la pagina kiosk/ y le envia el estado por SSE.

El navegador nunca recibe el token de G-Mini: este proceso es el unico que
habla con el servidor y solo reenvia el estado de la cara (estado, emocion,
subtitulo y avisos). Ojo: los subtitulos pueden contener las respuestas del
agente; por defecto solo se escucha en 127.0.0.1.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

STATIC_FILES = ("index.html", "face.js", "presets.js", "style.css")


class KioskServer:
    def __init__(self, host: str, port: int, static_dir: Path, *, max_clients: int = 8) -> None:
        self.host = host
        self.port = port
        self.static_dir = static_dir
        self.max_clients = max_clients
        self._clients: set[asyncio.Queue[str]] = set()
        self._writers: set[asyncio.StreamWriter] = set()
        self._state: dict[str, Any] = {}
        self._server: asyncio.AbstractServer | None = None
        self._last_level_push = 0.0

    @property
    def clients(self) -> int:
        return len(self._clients)

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, self.host, self.port)
        sockets = self._server.sockets or []
        if sockets:
            self.port = sockets[0].getsockname()[1]
        log.info("Kiosco en http://%s:%d/", self.host, self.port)

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            # Las conexiones SSE quedan abiertas: se cierran para no esperar al keep-alive.
            for writer in list(self._writers):
                writer.close()
            await self._server.wait_closed()

    def publish(self, state: dict[str, Any]) -> None:
        """Reemplaza el estado y lo envia a todos los navegadores conectados."""
        self._state = dict(state)
        message = "data: " + json.dumps(self._state, ensure_ascii=False) + "\n\n"
        for queue in list(self._clients):
            if queue.qsize() < 50:
                queue.put_nowait(message)

    def publish_level(self, level: float, now: float) -> None:
        """El nivel de audio cambia muy seguido: se limita a ~15 envios por segundo."""
        if now - self._last_level_push < 1 / 15:
            return
        self._last_level_push = now
        self.publish({**self._state, "level": round(level, 2)})

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await asyncio.wait_for(reader.readline(), timeout=10)
            while (await asyncio.wait_for(reader.readline(), timeout=10)).strip():
                pass  # las cabeceras no se usan
            parts = request.decode("latin-1").split()
            if len(parts) < 2 or parts[0] != "GET":
                await self._reply(writer, 405, "text/plain; charset=utf-8", b"Solo GET")
                return
            path = parts[1].split("?", 1)[0]
            if path == "/events":
                await self._events(writer)
                return
            name = "index.html" if path in ("/", "") else path.lstrip("/")
            if name not in STATIC_FILES:
                await self._reply(writer, 404, "text/plain; charset=utf-8", b"No encontrado")
                return
            body = (self.static_dir / name).read_bytes()
            ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype.endswith("javascript"):
                ctype += "; charset=utf-8"
            await self._reply(writer, 200, ctype, body)
        except (TimeoutError, ConnectionError, OSError):
            pass
        finally:
            writer.close()

    async def _reply(self, writer: asyncio.StreamWriter, status: int, ctype: str, body: bytes) -> None:
        reason = {200: "OK", 404: "Not Found", 405: "Method Not Allowed", 503: "Service Unavailable"}[status]
        head = (f"HTTP/1.1 {status} {reason}\r\nContent-Type: {ctype}\r\nContent-Length: {len(body)}\r\n"
                "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n")
        writer.write(head.encode("latin-1") + body)
        await writer.drain()

    async def _events(self, writer: asyncio.StreamWriter) -> None:
        if len(self._clients) >= self.max_clients:
            await self._reply(writer, 503, "text/plain; charset=utf-8", b"Demasiados clientes")
            return
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._clients.add(queue)
        self._writers.add(writer)
        try:
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-store\r\n"
                         b"Connection: keep-alive\r\n\r\nretry: 2000\n\n")
            writer.write(("data: " + json.dumps(self._state, ensure_ascii=False) + "\n\n").encode("utf-8"))
            await writer.drain()
            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    message = ": keep-alive\n\n"
                writer.write(message.encode("utf-8"))
                await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            self._clients.discard(queue)
            self._writers.discard(writer)
