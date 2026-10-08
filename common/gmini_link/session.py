"""Sesion WebSocket con G-Mini (/api/v1/ws) con reconexion automatica."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus, InvalidURI, WebSocketException

from . import PROTOCOL_VERSION, __version__

log = logging.getLogger(__name__)

AUTH_CLOSE_CODE = 4401


class AuthError(Exception):
    """El servidor rechazo el token (revocado o invalido): hay que volver a emparejar."""


class NodeError(Exception):
    """Error al ejecutar una superficie; se devuelve como node.result con ok=false."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


Handler = Callable[..., Awaitable[Any] | Any]


async def _call(handler: Handler | None, *args: Any) -> Any:
    if handler is None:
        return None
    result = handler(*args)
    if inspect.isawaitable(result):
        return await result
    return result


@dataclass
class SessionConfig:
    url: str
    token: str
    device_name: str
    client: str = "gmini-home"
    version: str = __version__
    platform: str = "python"
    surfaces: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    ping_interval: float = 25.0
    reconnect_min: float = 1.0
    reconnect_max: float = 30.0
    open_timeout: float = 10.0


@dataclass
class SessionHandlers:
    on_ready: Handler | None = None  # (frame)
    on_state: Handler | None = None  # (status, emotion)
    on_notify: Handler | None = None  # (title, body, priority)
    on_invoke: Handler | None = None  # (surface, params) -> dict (o NodeError)
    on_connection: Handler | None = None  # (connected: bool)
    on_frame: Handler | None = None  # (frame) cualquier otro mensaje


class RemoteSession:
    """Mantiene la conexion abierta, responde invocaciones y reconecta con espera exponencial."""

    def __init__(self, config: SessionConfig, handlers: SessionHandlers) -> None:
        self.config = config
        self.handlers = handlers
        self.ready = asyncio.Event()
        self.agent_name = ""
        self._ws: ClientConnection | None = None
        self._send_lock = asyncio.Lock()
        self._stopping = False
        # Referencias a tareas en segundo plano (asyncio solo guarda referencias debiles).
        self._tasks: set[asyncio.Task[Any]] = set()

    def _spawn(self, coro: Any) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    @property
    def connected(self) -> bool:
        return self._ws is not None and self.ready.is_set()

    async def send(self, frame: dict[str, Any]) -> bool:
        ws = self._ws
        if ws is None:
            return False
        try:
            async with self._send_lock:
                await ws.send(json.dumps(frame, ensure_ascii=False))
        except ConnectionClosed:
            return False
        return True

    async def send_event(self, event: str, data: dict[str, Any]) -> bool:
        return await self.send({"type": "node.event", "event": event, "data": data})

    async def cancel(self) -> bool:
        return await self.send({"type": "cancel"})

    async def chat(self, text: str, request_id: str, session_id: str | None = None) -> bool:
        frame: dict[str, Any] = {"type": "chat", "id": request_id, "text": text}
        if session_id:
            frame["session_id"] = session_id
        return await self.send(frame)

    def stop(self) -> None:
        self._stopping = True
        ws = self._ws
        if ws is not None:
            self._spawn(ws.close())

    # ------------------------------------------------------------ bucle

    async def run(self) -> None:
        """Conecta y reconecta hasta stop(). Lanza AuthError si el token no sirve."""
        delay = self.config.reconnect_min
        while not self._stopping:
            try:
                await self._connect_once()
                delay = self.config.reconnect_min
            except AuthError:
                raise
            except (TimeoutError, OSError, WebSocketException) as exc:
                log.info("Sin conexion con %s: %s", self.config.url, exc)
            finally:
                if self.ready.is_set():
                    self.ready.clear()
                    await _call(self.handlers.on_connection, False)
                self._ws = None
            if self._stopping:
                break
            # Espera exponencial con variacion para no sincronizar reintentos.
            await asyncio.sleep(delay * (0.8 + 0.4 * random.random()))
            delay = min(self.config.reconnect_max, delay * 2)

    async def _connect_once(self) -> None:
        headers = {"Authorization": f"Bearer {self.config.token}"}
        try:
            ws = await connect(self.config.url, additional_headers=headers, open_timeout=self.config.open_timeout,
                               max_size=4 * 1024 * 1024)
        except InvalidStatus as exc:
            status = exc.response.status_code
            if status in (401, 403):
                raise AuthError(f"El servidor rechazo la conexion (HTTP {status})") from exc
            raise
        except InvalidURI as exc:
            raise AuthError(f"URL invalida: {self.config.url}") from exc
        self._ws = ws
        pinger = asyncio.create_task(self._ping_loop(ws))
        try:
            await self.send({"type": "hello", "client": self.config.client, "version": self.config.version,
                             "device_name": self.config.device_name})
            async for raw in ws:
                if isinstance(raw, bytes):
                    continue
                try:
                    frame = json.loads(raw)
                except ValueError:
                    log.warning("Frame no JSON ignorado")
                    continue
                if isinstance(frame, dict):
                    await self._dispatch(frame)
        except ConnectionClosed as exc:
            if exc.rcvd is not None and exc.rcvd.code == AUTH_CLOSE_CODE:
                raise AuthError("Token rechazado (4401)") from exc
            log.info("Conexion cerrada: %s", exc)
        finally:
            pinger.cancel()
            await ws.close()

    async def _ping_loop(self, ws: ClientConnection) -> None:
        while True:
            await asyncio.sleep(self.config.ping_interval)
            try:
                async with self._send_lock:
                    await ws.send('{"type": "ping"}')
            except ConnectionClosed:
                return

    async def _dispatch(self, frame: dict[str, Any]) -> None:
        kind = str(frame.get("type") or "")
        if kind == "ready":
            self.agent_name = str(frame.get("agent_name") or "G-Mini")
            if int(frame.get("protocol") or PROTOCOL_VERSION) != PROTOCOL_VERSION:
                log.warning("El servidor usa el protocolo %s; este cliente es v%s", frame.get("protocol"),
                            PROTOCOL_VERSION)
            if self.config.surfaces:
                await self.send({"type": "node.register", "surfaces": self.config.surfaces,
                                 "platform": self.config.platform, "meta": self.config.meta})
            self.ready.set()
            await _call(self.handlers.on_connection, True)
            await _call(self.handlers.on_ready, frame)
        elif kind == "state":
            await _call(self.handlers.on_state, str(frame.get("status") or ""), str(frame.get("emotion") or ""))
        elif kind == "notify":
            await _call(self.handlers.on_notify, str(frame.get("title") or ""), str(frame.get("body") or ""),
                        str(frame.get("priority") or "normal"))
        elif kind == "node.invoke":
            # Cada invocacion corre aparte: una superficie lenta no bloquea el resto.
            self._spawn(self._invoke(frame))
        elif kind == "pong":
            return
        else:
            if kind == "error":
                log.warning("Error del servidor: %s %s", frame.get("code"), frame.get("message"))
            await _call(self.handlers.on_frame, frame)

    async def _invoke(self, frame: dict[str, Any]) -> None:
        request_id = str(frame.get("request_id") or "")
        surface = str(frame.get("surface") or "")
        params = frame.get("params") if isinstance(frame.get("params"), dict) else {}
        result: dict[str, Any] = {"type": "node.result", "request_id": request_id}
        try:
            if self.handlers.on_invoke is None or surface not in self.config.surfaces:
                raise NodeError("not_found", f"Superficie no disponible: {surface}")
            data = await _call(self.handlers.on_invoke, surface, params)
            result.update({"ok": True, "data": data if isinstance(data, dict) else {"ok": True}})
        except NodeError as exc:
            result.update({"ok": False, "error": {"code": exc.code, "message": exc.message}})
        except Exception as exc:
            log.exception("Fallo la superficie %s", surface)
            result.update({"ok": False, "error": {"code": "internal_error", "message": str(exc)[:200]}})
        await self.send(result)
