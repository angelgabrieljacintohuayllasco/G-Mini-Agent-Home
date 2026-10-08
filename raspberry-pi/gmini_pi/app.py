"""Aplicacion principal del cliente de pantalla."""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import time
from pathlib import Path
from typing import Any

from gmini_link.api import GMiniClient
from gmini_link.assistant import VoiceAssistant
from gmini_link.audio_io import AudioUnavailable, Player, Recorder
from gmini_link.face import EMOTIONS, parse_activity, parse_emotion
from gmini_link.session import AuthError, NodeError, RemoteSession, SessionConfig, SessionHandlers
from gmini_link.tokens import Credentials

from . import __version__
from .config import PiConfig
from .face_model import FaceModel
from .inputs import GpioButtons, KeyboardInput
from .kiosk import KioskServer

log = logging.getLogger(__name__)

DEMO_LABELS = {
    "neutral": "Neutral", "happy": "Alegría", "sad": "Tristeza", "surprised": "Sorpresa", "angry": "Enojo",
    "thinking": "Reflexión", "sleepy": "Sueño", "love": "Cariño", "error": "Error",
}


def kiosk_dir() -> Path:
    here = Path(__file__).resolve()
    for candidate in (here.parents[1] / "kiosk", here.parents[2] / "kiosk"):
        if (candidate / "index.html").is_file():
            return candidate
    raise FileNotFoundError("No encuentro la carpeta kiosk/ (index.html)")


def read_cpu_temp() -> float | None:
    try:
        return int(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000.0
    except (OSError, ValueError):
        return None


class PiApp:
    def __init__(self, config: PiConfig, creds: Credentials | None, *, demo: bool = False) -> None:
        self.config = config
        self.creds = creds
        self.demo = demo or creds is None
        self.stop_event = asyncio.Event()
        self.model = FaceModel(seed=int(time.time()) & 0xFFFFFFFF)
        self.assistant: VoiceAssistant | None = None
        self.session: RemoteSession | None = None
        self.client: GMiniClient | None = None
        self.kiosk: KioskServer | None = None
        self.started = time.monotonic()
        self.exit_code = 0
        self._background: set[asyncio.Task[Any]] = set()

    def _spawn(self, coro: Any) -> None:
        task = asyncio.ensure_future(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    # ------------------------------------------------------------ G-Mini

    def surfaces(self) -> list[str]:
        out = ["display.face", "display.text", "system.info", "sensor.read"]
        if self.assistant is not None and self.assistant.player is not None:
            out.append("tts.speak")
        return out

    async def on_invoke(self, surface: str, params: dict[str, Any]) -> dict[str, Any]:
        if surface == "display.face":
            expression = str(params.get("expression") or "")
            if parse_emotion(expression):
                self.model.set_emotion(expression)
            elif parse_activity(expression):
                self.model.set_status(expression)
            else:
                raise NodeError("bad_request", f"Expresion desconocida: {expression}")
            if params.get("text"):
                self.model.set_caption(str(params["text"]), 8.0)
            return {"ok": True}
        if surface == "display.text":
            seconds = float(params.get("seconds") or 8)
            self.model.set_caption(str(params.get("text") or ""), max(1.0, min(300.0, seconds)))
            return {"ok": True}
        if surface == "tts.speak" and self.assistant is not None:
            text = str(params.get("text") or "")
            if not text:
                raise NodeError("bad_request", "Falta 'text'")
            self._spawn(self.assistant.say(text))
            return {"ok": True}
        if surface == "system.info":
            return {"firmware": f"gmini-pi {__version__}", "uptime_s": int(time.monotonic() - self.started),
                    "os": platform.platform(terse=True), "python": platform.python_version(),
                    "cpu_temp": read_cpu_temp(), "display": f"pygame/{self.config.display.layout}"}
        if surface == "sensor.read":
            name = str(params.get("name") or "")
            if name == "cpu_temp" and read_cpu_temp() is not None:
                return {"value": read_cpu_temp(), "unit": "C"}
            if name == "load" and hasattr(os, "getloadavg"):
                return {"value": round(os.getloadavg()[0], 2), "unit": "load1"}
            if name == "uptime":
                return {"value": int(time.monotonic() - self.started), "unit": "s"}
            raise NodeError("not_found", f"Sensor desconocido: {name}")
        raise NodeError("not_found", f"Superficie no disponible: {surface}")

    async def on_state(self, status: str, emotion: str) -> None:
        if self.assistant is not None and self.assistant.busy:
            return
        if parse_activity(status):
            self.model.set_status(status)
        if parse_emotion(emotion):
            self.model.set_emotion(emotion)

    async def on_notify(self, title: str, body: str, priority: str) -> None:
        self.model.notify(title, body, 15.0 if priority in ("high", "urgent") else 8.0)

    async def on_connection(self, connected: bool) -> None:
        if connected:
            name = self.session.agent_name if self.session else "G-Mini"
            self.model.set_emotion("happy")
            self.model.set_caption(f"Conectada a {name}", 3.0)
        else:
            self.model.set_emotion("sleepy")
            self.model.set_caption("Sin conexión con G-Mini", 5.0)

    async def session_loop(self) -> None:
        assert self.session is not None
        try:
            await self.session.run()
        except AuthError as exc:
            log.error("%s. Empareja de nuevo: python -m gmini_pi --pair CODIGO", exc)
            self.model.set_emotion("error")
            self.model.set_caption("Hay que emparejar de nuevo esta pantalla", None)
            self.exit_code = 3

    # ------------------------------------------------------------ demostracion

    async def demo_loop(self) -> None:
        """Recorre emociones y estados: sirve para probar pantallas y hologramas."""
        states = ["idle", "listening", "thinking", "acting", "speaking"]
        while not self.stop_event.is_set():
            for emotion in EMOTIONS:
                self.model.set_status("idle")
                self.model.set_emotion(emotion)
                self.model.set_caption(f"Demostración: {DEMO_LABELS.get(emotion, emotion)}", 2.4)
                await asyncio.sleep(2.5)
            for status in states:
                self.model.set_emotion("neutral")
                self.model.set_status(status)
                self.model.set_caption(f"Estado: {status}", 2.4)
                for step in range(25):
                    if status == "speaking":
                        self.model.set_level(abs(((step * 7) % 10) - 5) / 5)
                    await asyncio.sleep(0.1)
                self.model.set_level(0.0)

    # ------------------------------------------------------------ arranque

    def _audio(self) -> tuple[Recorder | None, Player | None]:
        if not self.config.audio.enabled:
            return None, None
        try:
            recorder = Recorder(self.config.audio.input or None)
            player = Player(self.config.audio.output or None, volume=self.config.audio.volume / 100)
            from gmini_link.audio_io import list_devices

            list_devices()  # comprueba que PortAudio cargue
            return recorder, player
        except AudioUnavailable as exc:
            log.warning("%s: sigo sin voz", exc)
            return None, None

    async def _talk_down(self) -> None:
        self.model.engine.wake()
        if self.assistant is not None:
            await self.assistant.start_listening()

    async def _talk_up(self) -> None:
        if self.assistant is not None:
            await self.assistant.stop_listening()

    async def _cancel(self) -> None:
        if self.assistant is not None:
            self.assistant.cancel()
        if self.session is not None:
            await self.session.cancel()

    async def run(self) -> int:
        from .renderer import FaceRenderer

        loop = asyncio.get_running_loop()
        renderer = FaceRenderer(self.config.display, self.model)
        tasks: list[asyncio.Task[Any]] = []
        if self.config.kiosk.enabled:
            host, port = self.config.kiosk.host_port
            self.kiosk = KioskServer(host, port, kiosk_dir())
            await self.kiosk.start()
            self.model.add_listener(self.kiosk.publish)
            self.kiosk.publish(self.model.snapshot())

        if self.demo:
            tasks.append(asyncio.create_task(self.demo_loop()))
        else:
            assert self.creds is not None
            self.client = GMiniClient(self.creds.base_url, self.creds.token)
            recorder, player = self._audio()
            if recorder is not None or player is not None:
                self.assistant = VoiceAssistant(self.client, self.model, recorder=recorder, player=player,
                                                play_chimes=self.config.audio.chimes)
            self.session = RemoteSession(
                SessionConfig(url=self.client.ws_url(), token=self.creds.token,
                              device_name=self.config.server.device_name, client="gmini-pi", version=__version__,
                              platform="raspberry-pi" if Path("/proc/device-tree/model").exists() else "linux-pc",
                              surfaces=self.surfaces(),
                              meta={"layout": self.config.display.layout, "kiosk": self.config.kiosk.enabled}),
                SessionHandlers(on_state=self.on_state, on_notify=self.on_notify, on_invoke=self.on_invoke,
                                on_connection=self.on_connection),
            )
            tasks.append(asyncio.create_task(self.session_loop()))
            wake = self.config.wake
            if self.assistant is not None and recorder is not None and wake.mode == "server":
                tasks.append(asyncio.create_task(self.assistant.wake_loop(self.stop_event)))
            elif self.assistant is not None and recorder is not None and wake.mode == "openwakeword":
                from .wakeword import openwakeword_loop

                tasks.append(asyncio.create_task(
                    openwakeword_loop(self.assistant, recorder, wake.model, wake.threshold, self.stop_event)))

        gpio = GpioButtons(loop, self.config.buttons.gpio_talk, self.config.buttons.gpio_cancel,
                           on_talk_down=self._talk_down, on_talk_up=self._talk_up, on_cancel=self._cancel)
        keyboard = KeyboardInput(renderer.pg, on_talk_down=self._talk_down, on_talk_up=self._talk_up,
                                 on_cancel=self._cancel, on_quit=self.stop_event.set,
                                 on_fullscreen=renderer.toggle_fullscreen) if self.config.buttons.keyboard else None
        period = 1.0 / self.config.display.fps
        try:
            while not self.stop_event.is_set():
                started = time.perf_counter()
                if keyboard is not None:
                    for coro in keyboard.poll():
                        self._spawn(coro)
                else:
                    renderer.pg.event.pump()
                renderer.render(int(time.monotonic() * 1000))
                if self.kiosk is not None and self.model.level > 0.01:
                    self.kiosk.publish_level(self.model.level, time.monotonic())
                if self.exit_code and not self.demo:
                    await asyncio.sleep(5)  # deja ver el aviso antes de salir
                    break
                await asyncio.sleep(max(0.0, period - (time.perf_counter() - started)))
        finally:
            if self.session is not None:
                self.session.stop()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            gpio.close()
            if self.kiosk is not None:
                await self.kiosk.close()
            if self.client is not None:
                await self.client.aclose()
            renderer.close()
        return self.exit_code
