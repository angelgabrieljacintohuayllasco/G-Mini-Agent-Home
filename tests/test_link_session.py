"""Sesion WebSocket contra un servidor falso."""

from __future__ import annotations

import asyncio

import pytest
from conftest import VALID_TOKEN, FakeGMini, eventually
from gmini_link.session import AuthError, NodeError, RemoteSession, SessionConfig, SessionHandlers


def make_session(server: FakeGMini, handlers: SessionHandlers, token: str = VALID_TOKEN,
                 surfaces: list[str] | None = None) -> RemoteSession:
    config = SessionConfig(url=server.url, token=token, device_name="Prueba", client="test-client",
                           platform="pytest", surfaces=surfaces or ["display.face", "sensor.read"],
                           meta={"display": "none"}, ping_interval=0.2, reconnect_min=0.05, reconnect_max=0.2)
    return RemoteSession(config, handlers)


def test_handshake_register_state_notify_and_invoke() -> None:
    async def go():
        server = await FakeGMini().start()
        states: list[tuple[str, str]] = []
        notes: list[tuple[str, str, str]] = []
        connected: list[bool] = []

        async def on_invoke(surface: str, params: dict) -> dict:
            if surface == "sensor.read":
                if params.get("name") != "uptime":
                    raise NodeError("not_found", "Sensor desconocido")
                return {"value": 12, "unit": "s"}
            return {"ok": True, "expression": params.get("expression")}

        session = make_session(server, SessionHandlers(
            on_state=lambda s, e: states.append((s, e)),
            on_notify=lambda t, b, p: notes.append((t, b, p)),
            on_invoke=on_invoke,
            on_connection=connected.append,
        ))
        task = asyncio.create_task(session.run())
        try:
            hello = await server.wait_for("hello")
            assert hello == {"type": "hello", "client": "test-client", "version": hello["version"],
                             "device_name": "Prueba"}
            register = await server.wait_for("node.register")
            assert register["surfaces"] == ["display.face", "sensor.read"]
            assert register["platform"] == "pytest" and register["meta"] == {"display": "none"}
            await eventually(lambda: session.connected, message="sesion lista")
            assert session.agent_name == "G-Mini" and connected == [True]
            assert server.headers[0]["Authorization"] == f"Bearer {VALID_TOKEN}"

            await server.push({"type": "state", "status": "thinking", "emotion": "happy"})
            await server.push({"type": "notify", "title": "Correo", "body": "3 nuevos", "priority": "high"})
            await eventually(lambda: states and notes, message="estado y aviso")
            assert states == [("thinking", "happy")] and notes == [("Correo", "3 nuevos", "high")]

            await server.push({"type": "node.invoke", "request_id": "r1", "surface": "display.face",
                               "params": {"expression": "love"}})
            ok = await server.wait_for("node.result", request_id="r1")
            assert ok["ok"] is True and ok["data"] == {"ok": True, "expression": "love"}

            await server.push({"type": "node.invoke", "request_id": "r2", "surface": "sensor.read",
                               "params": {"name": "humedad"}})
            bad = await server.wait_for("node.result", request_id="r2")
            assert bad["ok"] is False and bad["error"]["code"] == "not_found"

            await server.push({"type": "node.invoke", "request_id": "r3", "surface": "relay.set", "params": {}})
            undeclared = await server.wait_for("node.result", request_id="r3")
            assert undeclared["ok"] is False

            await server.wait_for("ping", timeout=2.0)
            assert await session.send_event("button", {"button": 1, "action": "down"})
            event = await server.wait_for("node.event")
            assert event["data"] == {"button": 1, "action": "down"}
        finally:
            session.stop()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await server.close()

    asyncio.run(go())


def test_rejected_token_raises_auth_error() -> None:
    async def go():
        server = await FakeGMini().start()
        session = make_session(server, SessionHandlers(), token="gm_dev_revocado")
        try:
            with pytest.raises(AuthError):
                await asyncio.wait_for(session.run(), timeout=5)
        finally:
            await server.close()

    asyncio.run(go())


def test_reconnects_after_server_drop() -> None:
    async def go():
        server = await FakeGMini().start()
        changes: list[bool] = []
        session = make_session(server, SessionHandlers(on_connection=changes.append))
        task = asyncio.create_task(session.run())
        try:
            await eventually(lambda: session.connected, message="primera conexion")
            await server.connections[-1].close()
            await eventually(lambda: changes[-1] is False, message="desconexion")
            await eventually(lambda: len(server.connections) >= 2 and session.connected, timeout=5,
                             message="reconexion")
            assert changes[:3] == [True, False, True]
        finally:
            session.stop()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await server.close()

    asyncio.run(go())
