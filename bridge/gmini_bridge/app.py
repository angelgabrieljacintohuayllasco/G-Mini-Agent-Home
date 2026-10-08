"""Aplicacion del puente: cara USB <-> G-Mini (estado, avisos, superficies y voz)."""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from gmini_link import __version__ as link_version
from gmini_link.api import GMiniClient
from gmini_link.assistant import VoiceAssistant
from gmini_link.audio_io import Player, Recorder
from gmini_link.face import parse_activity, parse_emotion
from gmini_link.session import AuthError, NodeError, RemoteSession, SessionConfig, SessionHandlers
from gmini_link.tokens import Credentials

from . import __version__
from . import protocol as proto
from .ports import find_device

log = logging.getLogger(__name__)


class SerialPort(Protocol):
    """Lo minimo de pyserial que usa el puente (permite simularlo en pruebas)."""

    def readline(self) -> bytes: ...

    def write(self, data: bytes) -> int | None: ...

    def close(self) -> None: ...


SerialFactory = Callable[[str, int], SerialPort]


def open_serial(device: str, baud: int) -> SerialPort:
    import serial

    return serial.Serial(device, baud, timeout=0.2, write_timeout=1.0)


@dataclass
class BridgeConfig:
    port: str | None = None  # None = deteccion automatica
    baud: int = 115200
    device_name: str = "Cara USB"
    audio: bool = True
    mic: str | None = None
    speaker: str | None = None
    volume: int = 80
    wake_word: bool = False


class SerialLink:
    """Puerto serie con lectura en un hilo. Las lineas llegan a una cola de asyncio."""

    def __init__(self, port: SerialPort, loop: asyncio.AbstractEventLoop) -> None:
        self._port = port
        self._loop = loop
        self.lines: asyncio.Queue[str | None] = asyncio.Queue()
        self._lock = threading.Lock()
        self._alive = True
        self._thread = threading.Thread(target=self._reader, name="gmini-serial", daemon=True)
        self._thread.start()

    def _deliver(self, line: str | None) -> None:
        try:
            self._loop.call_soon_threadsafe(self.lines.put_nowait, line)
        except RuntimeError:
            pass  # el bucle ya termino (cierre del programa)

    def _reader(self) -> None:
        try:
            while self._alive:
                raw = self._port.readline()
                if raw:
                    self._deliver(raw.decode("latin-1", "replace").strip())
        except Exception as exc:
            if self._alive:
                log.warning("Lectura serie interrumpida: %s", exc)
        finally:
            self._alive = False
            self._deliver(None)

    @property
    def alive(self) -> bool:
        return self._alive

    def write_line(self, line: str) -> bool:
        if not self._alive:
            return False
        try:
            with self._lock:
                self._port.write((line + "\n").encode("latin-1", "replace"))
        except Exception as exc:
            log.warning("Escritura serie fallida: %s", exc)
            self._alive = False
            return False
        log.debug("-> %s", line)
        return True

    def close(self) -> None:
        self._alive = False
        try:
            self._port.close()
        except Exception:
            pass
        self._thread.join(timeout=1.0)


class SerialFace:
    """FaceSink que traduce a ordenes del protocolo serie. Seguro entre hilos."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self.link: SerialLink | None = None
        self.status = "idle"
        self.emotion = "neutral"
        self.caption = ""
        self._level = -1
        self._caption_timer: asyncio.TimerHandle | None = None

    def _send(self, line: str) -> None:
        if self.link is not None:
            self.link.write_line(line)

    def attach(self, link: SerialLink | None) -> None:
        self.link = link
        if link is not None:
            # La placa se reinicia al abrir el puerto: se le reenvia el estado.
            self._send(proto.encode_emotion(self.emotion))
            self._send(proto.encode_status(self.status))
            self._send(proto.encode_text(self.caption))

    def set_status(self, status: str) -> None:
        status = parse_activity(status) or "idle"
        if status != self.status:
            self.status = status
            self._send(proto.encode_status(status))

    def set_emotion(self, emotion: str) -> None:
        emotion = parse_emotion(emotion) or "neutral"
        if emotion != self.emotion:
            self.emotion = emotion
            self._send(proto.encode_emotion(emotion))

    def set_caption(self, text: str, seconds: float | None = None) -> None:
        # Puede llamarse desde el hilo de audio: se agenda en el bucle.
        self._loop.call_soon_threadsafe(self._apply_caption, text, seconds)

    def _apply_caption(self, text: str, seconds: float | None) -> None:
        if self._caption_timer is not None:
            self._caption_timer.cancel()
            self._caption_timer = None
        self.caption = text
        self._send(proto.encode_text(text))
        if text and seconds:
            self._caption_timer = self._loop.call_later(seconds, self._apply_caption, "", None)

    def set_level(self, level: float) -> None:
        value = max(0, min(9, round(level * 9)))
        if value != self._level:
            self._level = value
            self._send(f"L:{value}")

    def notify(self, title: str, body: str) -> None:
        self._send(proto.encode_notify(title, body))


class BridgeApp:
    def __init__(
        self,
        config: BridgeConfig,
        creds: Credentials,
        *,
        serial_factory: SerialFactory = open_serial,
        client: GMiniClient | None = None,
        recorder: Recorder | None = None,
        player: Player | None = None,
        port_finder: Callable[[int], tuple[str, str] | None] = find_device,
    ) -> None:
        self.config = config
        self.creds = creds
        self.serial_factory = serial_factory
        self.port_finder = port_finder
        self.client = client or GMiniClient(creds.base_url, creds.token)
        if config.audio:
            recorder = recorder or Recorder(config.mic)
            player = player or Player(config.speaker, volume=config.volume / 100)
        self.assistant: VoiceAssistant | None = None
        self._recorder = recorder
        self._player = player
        self.face: SerialFace | None = None
        self.session: RemoteSession | None = None
        self.stop_event = asyncio.Event()
        self.auth_failed = False
        self._background: set[asyncio.Task[Any]] = set()

    def _spawn(self, coro: Any) -> None:
        task = asyncio.ensure_future(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    # ------------------------------------------------------------ superficies

    def surfaces(self) -> list[str]:
        out = ["display.face", "display.text"]
        if self.config.audio:
            out.append("tts.speak")
        return out

    async def on_invoke(self, surface: str, params: dict[str, Any]) -> dict[str, Any]:
        assert self.face is not None
        if surface == "display.face":
            expression = str(params.get("expression") or "")
            if parse_emotion(expression):
                self.face.set_emotion(expression)
            elif parse_activity(expression):
                self.face.set_status(expression)
            else:
                raise NodeError("bad_request", f"Expresion desconocida: {expression}")
            if params.get("text"):
                self.face.set_caption(str(params["text"]), 8.0)
            return {"ok": True}
        if surface == "display.text":
            seconds = float(params.get("seconds") or 8)
            self.face.set_caption(str(params.get("text") or ""), max(1.0, min(300.0, seconds)))
            return {"ok": True}
        if surface == "tts.speak" and self.assistant is not None:
            text = str(params.get("text") or "")
            if not text:
                raise NodeError("bad_request", "Falta 'text'")
            self._spawn(self.assistant.say(text))
            return {"ok": True}
        raise NodeError("not_found", f"Superficie no disponible: {surface}")

    async def on_state(self, status: str, emotion: str) -> None:
        if self.face is None or (self.assistant is not None and self.assistant.busy):
            return
        if parse_activity(status):
            self.face.set_status(status)
        if parse_emotion(emotion):
            self.face.set_emotion(emotion)

    async def on_notify(self, title: str, body: str, priority: str) -> None:
        if self.face is not None:
            self.face.notify(title, body)

    async def on_connection(self, connected: bool) -> None:
        if self.face is None:
            return
        if connected:
            name = self.session.agent_name if self.session else "G-Mini"
            self.face.set_emotion("happy")
            self.face.set_caption(f"Conectada a {name}", 3.0)
            log.info("Sesion lista con %s", name)
        else:
            self.face.set_emotion("sleepy")
            self.face.set_caption("Sin conexión con G-Mini", 4.0)

    # ------------------------------------------------------------ eventos de la placa

    async def on_device(self, message: proto.DeviceMessage) -> None:
        if isinstance(message, proto.Hello):
            log.info("Cara conectada: %s %s (protocolo %s)", message.firmware, message.version, message.protocol)
            if message.protocol != proto.PROTOCOL_VERSION:
                log.warning("La placa usa el protocolo %s y el puente el %s", message.protocol,
                            proto.PROTOCOL_VERSION)
            return
        if isinstance(message, proto.DeviceError):
            log.warning("La placa rechazo una orden: %s", message.code)
            return
        if not isinstance(message, proto.ButtonEvent):
            return
        if self.session is not None:
            await self.session.send_event("button", {"button": message.button, "action": message.action})
        if self.assistant is None:
            return
        if message.button == 1 and message.action == "down":
            await self.assistant.start_listening()
        elif message.button == 1 and message.action == "up":
            await self.assistant.stop_listening()
        elif message.button == 2 and message.action == "down":
            self.assistant.cancel()
            if self.session is not None:
                await self.session.cancel()

    # ------------------------------------------------------------ bucles

    async def serial_loop(self) -> None:
        loop = asyncio.get_running_loop()
        assert self.face is not None
        while not self.stop_event.is_set():
            device = self.config.port
            if device is None:
                found = await asyncio.to_thread(self.port_finder, self.config.baud)
                if found is None:
                    log.info("No encuentro la cara USB; reintento en 3 s")
                    await self._sleep(3.0)
                    continue
                device = found[0]
            try:
                port = await asyncio.to_thread(self.serial_factory, device, self.config.baud)
            except Exception as exc:
                log.warning("No se pudo abrir %s: %s", device, exc)
                await self._sleep(3.0)
                continue
            log.info("Puerto %s abierto a %d baudios", device, self.config.baud)
            link = SerialLink(port, loop)
            self.face.attach(link)
            try:
                while not self.stop_event.is_set():
                    line = await link.lines.get()
                    if line is None:
                        break
                    log.debug("<- %s", line)
                    message = proto.parse_device_line(line)
                    if message is not None:
                        await self.on_device(message)
            finally:
                self.face.attach(None)
                link.close()
            if not self.stop_event.is_set():
                log.info("Se perdio la cara USB; reconectando")
                await self._sleep(2.0)

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self.stop_event.wait(), timeout=seconds)
        except TimeoutError:
            pass

    async def session_loop(self) -> None:
        assert self.session is not None
        try:
            await self.session.run()
        except AuthError as exc:
            self.auth_failed = True
            log.error("%s. Vuelve a emparejar con --pair.", exc)
            if self.face is not None:
                self.face.set_emotion("error")
                self.face.set_caption("Empareja de nuevo el puente", None)
            self.stop_event.set()

    async def run(self) -> int:
        loop = asyncio.get_running_loop()
        self.face = SerialFace(loop)
        if self.config.audio:
            self.assistant = VoiceAssistant(self.client, self.face, recorder=self._recorder, player=self._player)
        self.session = RemoteSession(
            SessionConfig(
                url=self.client.ws_url(),
                token=self.creds.token,
                device_name=self.config.device_name,
                client="gmini-usb-bridge",
                version=__version__,
                platform=f"usb-serial-{sys.platform}",
                surfaces=self.surfaces(),
                meta={"bridge": __version__, "gmini_link": link_version, "display": "ssd1306-128x64"},
            ),
            SessionHandlers(on_state=self.on_state, on_notify=self.on_notify, on_invoke=self.on_invoke,
                            on_connection=self.on_connection),
        )
        tasks = [asyncio.create_task(self.serial_loop()), asyncio.create_task(self.session_loop())]
        if self.assistant is not None and self.config.wake_word:
            tasks.append(asyncio.create_task(self.assistant.wake_loop(self.stop_event)))
        try:
            await self.stop_event.wait()
        finally:
            self.session.stop()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.client.aclose()
        return 3 if self.auth_failed else 0

    def stop(self) -> None:
        self.stop_event.set()
