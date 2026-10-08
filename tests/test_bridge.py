"""Puente USB: protocolo serie y flujo completo con una placa y un G-Mini falsos."""

from __future__ import annotations

import asyncio
import base64
import queue
import threading

import httpx
import pytest
from conftest import VALID_TOKEN, FakeGMini, eventually
from gmini_bridge import protocol as proto
from gmini_bridge.app import BridgeApp, BridgeConfig
from gmini_link.api import GMiniClient
from gmini_link.tokens import Credentials
from gmini_link.wav import Pcm, encode_wav, tone

# ---------------------------------------------------------------- protocolo


def test_latin1_sanitizing_keeps_spanish_and_drops_the_rest() -> None:
    assert proto.to_latin1("¿Qué tal, Ñandú?") == "¿Qué tal, Ñandú?"
    assert proto.to_latin1("Hola “mundo” — ok…") == 'Hola "mundo" - ok...'
    assert proto.to_latin1("Listo \U0001f44d\nsegunda línea") == "Listo segunda línea"
    assert proto.to_latin1("x" * 60, 10) == "xxxxxxx..."
    assert proto.encode_text("Señal") == "T:Señal"
    assert proto.encode_text("Señal").encode("latin-1") == b"T:Se\xf1al"
    assert proto.encode_notify("A|B", "cuerpo") == "N:A/B|cuerpo"
    assert proto.encode_level(0.5) == "L:4" and proto.encode_level(2) == "L:9"
    assert proto.encode_look(1.2, -0.5) == "G:100,-50" and proto.encode_look(None) == "G:"
    assert proto.encode_status("thinking") == "S:thinking"
    with pytest.raises(ValueError):
        proto.encode_status("dancing")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("H:gmini-usb-face;0.1.0;1", proto.Hello("gmini-usb-face", "0.1.0", 1)),
        ("OK", proto.Ok()),
        ("B:1:down", proto.ButtonEvent(1, "down")),
        ("B:2:long", proto.ButtonEvent(2, "long")),
        ("ERR:value", proto.DeviceError("value")),
        ("# depuracion", None),
        ("B:1:dance", None),
        ("basura", None),
    ],
)
def test_parse_device_lines(line: str, expected: object) -> None:
    assert proto.parse_device_line(line) == expected


# ---------------------------------------------------------------- simulaciones


class FakeSerial:
    """Puerto serie en memoria: lo escrito por el puente queda en `written`."""

    def __init__(self) -> None:
        self.written: list[str] = []
        self._incoming: queue.Queue[bytes] = queue.Queue()
        self._closed = threading.Event()
        self.feed("H:gmini-usb-face;0.1.0;1")

    def feed(self, line: str) -> None:
        self._incoming.put((line + "\r\n").encode("latin-1"))

    def readline(self) -> bytes:
        if self._closed.is_set():
            raise OSError("cerrado")
        try:
            return self._incoming.get(timeout=0.05)
        except queue.Empty:
            return b""

    def write(self, data: bytes) -> int:
        self.written.append(data.decode("latin-1").rstrip("\n"))
        return len(data)

    def close(self) -> None:
        self._closed.set()


class FakeRecorder:
    def __init__(self) -> None:
        self.active = False
        self.listeners = []

    def add_listener(self, listener) -> None:
        self.listeners.append(listener)

    def start(self) -> None:
        self.active = True

    def take(self) -> bytes:
        return b""

    def stop(self) -> bytes:
        self.active = False
        return tone(300, 800)  # 0,8 s "grabados"


class FakePlayer:
    def __init__(self) -> None:
        self.played: list[Pcm] = []

    def play(self, pcm: Pcm, on_level=None, block_ms: int = 40) -> None:
        self.played.append(pcm)
        if on_level:
            on_level(0.8)
            on_level(0.0)

    def stop(self) -> None:
        pass


def gmini_rest(ws_port: int):
    reply_wav = encode_wav(tone(523, 300))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {VALID_TOKEN}"
        if request.url.path == "/api/v1/voice/turn":
            return httpx.Response(200, json={
                "transcript": "cómo estás", "reply": "¡Muy bien! Gracias por preguntar.", "session_id": "ses_1",
                "emotion": "happy", "audio_mime": "audio/wav", "audio_base64": base64.b64encode(reply_wav).decode()})
        return httpx.Response(404, json={"error": {"code": "not_found", "message": "x"}})

    client = GMiniClient(f"http://127.0.0.1:{ws_port}", VALID_TOKEN, transport=httpx.MockTransport(handler))
    return client


def test_bridge_end_to_end_push_to_talk_and_surfaces() -> None:
    async def go():
        server = await FakeGMini().start()
        serial = FakeSerial()
        recorder, player = FakeRecorder(), FakePlayer()
        app = BridgeApp(
            BridgeConfig(port="FAKE", device_name="Cara de prueba"),
            Credentials(base_url=f"http://127.0.0.1:{server.port}", token=VALID_TOKEN),
            serial_factory=lambda device, baud: serial,
            client=gmini_rest(server.port),
            recorder=recorder,
            player=player,
        )
        task = asyncio.create_task(app.run())
        try:
            register = await server.wait_for("node.register")
            assert register["surfaces"] == ["display.face", "display.text", "tts.speak"]
            await eventually(lambda: "T:Conectada a G-Mini" in serial.written, message="saludo en la OLED")

            # Pulsar para hablar: B:1:down ... B:1:up
            serial.feed("B:1:down")
            await eventually(lambda: recorder.active, message="grabando")
            assert "S:listening" in serial.written
            serial.feed("B:1:up")
            await eventually(lambda: player.played and "S:idle" in serial.written[-6:], timeout=5,
                             message="respuesta reproducida")
            seq = serial.written
            assert seq.index("S:listening") < seq.index("S:thinking") < seq.index("S:speaking")
            assert "E:happy" in seq
            assert any(line.startswith("T:¡Muy bien!") for line in seq)
            assert "L:7" in seq and "L:0" in seq  # boca siguiendo el audio
            assert len(player.played) == 2  # tono de aviso + respuesta
            event = await server.wait_for("node.event")
            assert event["data"] == {"button": 1, "action": "down"}

            # El agente usa la cara como superficie.
            await server.push({"type": "node.invoke", "request_id": "f1", "surface": "display.face",
                               "params": {"expression": "love", "text": "Te quiero"}})
            result = await server.wait_for("node.result", request_id="f1")
            assert result["ok"] is True
            await eventually(lambda: "E:love" in serial.written and "T:Te quiero" in serial.written,
                             message="cara cambiada")
            await server.push({"type": "node.invoke", "request_id": "f2", "surface": "display.face",
                               "params": {"expression": "bailar"}})
            bad = await server.wait_for("node.result", request_id="f2")
            assert bad["ok"] is False and bad["error"]["code"] == "bad_request"

            # Estado del agente (fuera de un turno local) y avisos.
            await server.push({"type": "state", "status": "acting", "emotion": "thinking"})
            await server.push({"type": "notify", "title": "Recordatorio", "body": "Comprar pan", "priority": "normal"})
            await eventually(lambda: "S:acting" in serial.written and "N:Recordatorio|Comprar pan" in serial.written,
                             message="estado y aviso")
        finally:
            app.stop()
            await asyncio.wait_for(task, timeout=5)
            await server.close()

    asyncio.run(go())


def test_bridge_exits_with_code_3_when_token_is_rejected() -> None:
    async def go():
        server = await FakeGMini().start()
        app = BridgeApp(
            BridgeConfig(port="FAKE", audio=False),
            Credentials(base_url=f"http://127.0.0.1:{server.port}", token="gm_dev_revocado"),
            serial_factory=lambda device, baud: FakeSerial(),
        )
        try:
            assert await asyncio.wait_for(app.run(), timeout=5) == 3
        finally:
            await server.close()

    asyncio.run(go())
