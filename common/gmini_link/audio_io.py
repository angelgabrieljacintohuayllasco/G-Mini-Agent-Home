"""Microfono y parlante de la PC o la Raspberry Pi (sounddevice / PortAudio).

sounddevice se importa al usarse: el resto del paquete funciona sin audio
(por ejemplo en las pruebas o en una cara solo de pantalla).
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

from .wav import SAMPLE_RATE, Pcm, level, resample

log = logging.getLogger(__name__)


class AudioUnavailable(RuntimeError):
    """No hay sounddevice/PortAudio o el dispositivo no existe."""


def _sd() -> Any:
    try:
        import sounddevice
    except (ImportError, OSError) as exc:
        raise AudioUnavailable(
            "Falta sounddevice o PortAudio (pip install sounddevice; en Linux: sudo apt install libportaudio2)"
        ) from exc
    return sounddevice


def list_devices() -> str:
    return str(_sd().query_devices())


def _parse_device(device: str | int | None) -> str | int | None:
    if device is None or device == "":
        return None
    if isinstance(device, int):
        return device
    return int(device) if str(device).isdigit() else str(device)


class Recorder:
    """Graba mono PCM16. Usa la frecuencia del dispositivo y remuestrea a 16 kHz."""

    def __init__(self, device: str | int | None = None, *, rate: int = SAMPLE_RATE,
                 on_level: Callable[[float], None] | None = None, block_ms: int = 20) -> None:
        self.device = _parse_device(device)
        self.rate = rate
        self.on_level = on_level
        self.block_ms = block_ms
        self._chunks: list[bytes] = []
        self._stream: Any = None
        self._device_rate = rate
        self._lock = threading.Lock()
        self._listeners: list[Callable[[bytes], None]] = []

    def add_listener(self, listener: Callable[[bytes], None]) -> None:
        """Recibe cada bloque ya convertido a 16 kHz mono (para el detector de voz)."""
        self._listeners.append(listener)

    def _callback(self, indata: Any, frames: int, time: Any, status: Any) -> None:
        if status:
            log.debug("audio: %s", status)
        raw = bytes(indata)
        if self._device_rate != self.rate:
            raw = resample(Pcm(raw, self._device_rate, 1), self.rate).data
        with self._lock:
            self._chunks.append(raw)
        if self.on_level:
            self.on_level(level(raw))
        for listener in self._listeners:
            listener(raw)

    def start(self) -> None:
        sd = _sd()
        if self._stream is not None:
            return
        self._chunks = []
        try:
            info = sd.query_devices(self.device, "input")
            supported = True
            try:
                sd.check_input_settings(device=self.device, samplerate=self.rate, channels=1, dtype="int16")
            except Exception:
                supported = False
            self._device_rate = self.rate if supported else int(info["default_samplerate"])
            self._stream = sd.RawInputStream(
                samplerate=self._device_rate,
                blocksize=self._device_rate * self.block_ms // 1000,
                device=self.device,
                channels=1,
                dtype="int16",
                callback=self._callback,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise AudioUnavailable(f"No se pudo abrir el microfono: {exc}") from exc

    def take(self) -> bytes:
        """Devuelve y vacia lo grabado hasta ahora (sin detener)."""
        with self._lock:
            data = b"".join(self._chunks)
            self._chunks = []
        return data

    def stop(self) -> bytes:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        return self.take()

    @property
    def active(self) -> bool:
        return self._stream is not None


class Player:
    """Reproduce PCM en un hilo y avisa el nivel de cada bloque (para la boca)."""

    def __init__(self, device: str | int | None = None, *, volume: float = 1.0) -> None:
        self.device = _parse_device(device)
        self.volume = max(0.0, min(1.0, volume))
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def play(self, pcm: Pcm, on_level: Callable[[float], None] | None = None, block_ms: int = 40) -> None:
        """Bloquea hasta terminar o hasta stop(). Llamar desde un hilo (asyncio.to_thread)."""
        sd = _sd()
        self._stop.clear()
        data = pcm.data
        if self.volume < 0.999:
            from array import array

            samples = array("h")
            samples.frombytes(data)
            gain = self.volume * self.volume
            data = array("h", (int(s * gain) for s in samples)).tobytes()
        frame_bytes = 2 * pcm.channels
        step = max(frame_bytes, pcm.rate * block_ms // 1000 * frame_bytes)
        try:
            with sd.RawOutputStream(samplerate=pcm.rate, channels=pcm.channels, dtype="int16",
                                    device=self.device) as stream:
                for i in range(0, len(data), step):
                    if self._stop.is_set():
                        break
                    block = data[i : i + step]
                    if on_level:
                        on_level(level(block))
                    stream.write(block)
        except Exception as exc:
            raise AudioUnavailable(f"No se pudo reproducir: {exc}") from exc
        finally:
            if on_level:
                on_level(0.0)


class BlockQueue:
    """Puente hilo de audio -> asyncio para el detector de palabra de activacion."""

    def __init__(self, maxsize: int = 200) -> None:
        self._q: queue.Queue[bytes] = queue.Queue(maxsize=maxsize)

    def put(self, block: bytes) -> None:
        try:
            self._q.put_nowait(block)
        except queue.Full:
            pass  # si el consumidor se atrasa se descartan bloques viejos

    def get(self, timeout: float) -> bytes | None:
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear(self) -> None:
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                return
