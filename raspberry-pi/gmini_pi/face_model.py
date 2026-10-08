"""Estado de la cara: motor de ojos + textos. Lo dibuja pygame y lo replica el kiosco."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from gmini_link.face import EyesEngine, FaceFrame, parse_activity, parse_emotion

Listener = Callable[[dict[str, Any]], None]


class FaceModel:
    """Implementa FaceSink. Seguro entre hilos (el audio actualiza el nivel)."""

    def __init__(self, seed: int = 0x2545F491, *, sleep_after_s: float | None = None) -> None:
        self.engine = EyesEngine(seed)
        if sleep_after_s is not None:
            self.engine.sleep_after_ms = int(sleep_after_s * 1000)
        self._lock = threading.Lock()
        self.status = "idle"
        self.emotion = "neutral"
        self.caption = ""
        self._caption_until: float | None = None
        self.notify_title = ""
        self.notify_body = ""
        self._notify_until = 0.0
        self.level = 0.0
        self._listeners: list[Listener] = []
        self._started = False

    # ------------------------------------------------------------ oyentes (kiosco)

    def add_listener(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def _changed(self) -> None:
        snap = self.snapshot()
        for listener in list(self._listeners):
            listener(snap)

    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            notify = None
            if self.notify_title and now < self._notify_until:
                notify = {"title": self.notify_title, "body": self.notify_body,
                          "seconds": round(self._notify_until - now, 1)}
            return {"status": self.status, "emotion": self.emotion, "caption": self.current_caption(now),
                    "level": round(self.level, 2), "notify": notify}

    # ------------------------------------------------------------ FaceSink

    def set_status(self, status: str) -> None:
        status = parse_activity(status) or "idle"
        with self._lock:
            if status == self.status:
                return
            self.status = status
        self._changed()

    def set_emotion(self, emotion: str) -> None:
        emotion = parse_emotion(emotion) or "neutral"
        with self._lock:
            if emotion == self.emotion:
                return
            self.emotion = emotion
        self._changed()

    def set_caption(self, text: str, seconds: float | None = None) -> None:
        with self._lock:
            self.caption = text or ""
            self._caption_until = time.monotonic() + seconds if (text and seconds) else None
        self._changed()

    def set_level(self, level: float) -> None:
        self.level = max(0.0, min(1.0, float(level)))

    def notify(self, title: str, body: str, seconds: float = 8.0) -> None:
        with self._lock:
            self.notify_title = title
            self.notify_body = body
            self._notify_until = time.monotonic() + seconds
        self.engine.wake()
        self._changed()

    # ------------------------------------------------------------ cuadro

    def current_caption(self, now: float | None = None) -> str:
        now = time.monotonic() if now is None else now
        if self._caption_until is not None and now >= self._caption_until:
            self.caption = ""
            self._caption_until = None
        return self.caption

    def current_notify(self) -> tuple[str, str] | None:
        if self.notify_title and time.monotonic() < self._notify_until:
            return self.notify_title, self.notify_body
        return None

    def update(self, now_ms: int) -> FaceFrame:
        if not self._started:
            self.engine.begin(now_ms)
            self._started = True
        self.engine.set_emotion(self.emotion)
        self.engine.set_activity(self.status)
        self.engine.set_level(self.level)
        return self.engine.update(now_ms)
