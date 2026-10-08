"""Utilidades WAV/PCM16 sin dependencias (solo la biblioteca estandar)."""

from __future__ import annotations

import io
import math
import sys
import wave
from array import array
from dataclasses import dataclass

SAMPLE_RATE = 16000


@dataclass(frozen=True)
class Pcm:
    data: bytes  # PCM16 little-endian entrelazado
    rate: int
    channels: int

    @property
    def frames(self) -> int:
        return len(self.data) // (2 * self.channels)

    @property
    def seconds(self) -> float:
        return self.frames / float(self.rate) if self.rate else 0.0


def _samples(data: bytes) -> array:
    samples = array("h")
    samples.frombytes(data[: len(data) - (len(data) % 2)])
    if sys.byteorder == "big":
        samples.byteswap()
    return samples


def _to_bytes(samples: array) -> bytes:
    if sys.byteorder == "big":
        samples = array("h", samples)
        samples.byteswap()
    return samples.tobytes()


def encode_wav(pcm: bytes, rate: int = SAMPLE_RATE, channels: int = 1) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def decode_wav(data: bytes) -> Pcm:
    """Lee un WAV PCM de 8 o 16 bits. Lanza ValueError si no es valido."""
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            width = w.getsampwidth()
            rate = w.getframerate()
            channels = w.getnchannels()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as exc:
        raise ValueError(f"WAV invalido: {exc}") from exc
    if width == 1:
        frames = _to_bytes(array("h", ((b - 128) << 8 for b in frames)))
    elif width != 2:
        raise ValueError(f"Solo se admite PCM de 8 o 16 bits (llego {width * 8})")
    return Pcm(frames, rate, channels)


def to_mono(pcm: Pcm) -> Pcm:
    if pcm.channels == 1:
        return pcm
    s = _samples(pcm.data)
    mono = array("h", ((s[i] + s[i + 1]) // 2 for i in range(0, len(s) - 1, 2)))
    return Pcm(_to_bytes(mono), pcm.rate, 1)


def resample(pcm: Pcm, rate: int) -> Pcm:
    """Remuestreo lineal (suficiente para voz). Convierte a mono."""
    mono = to_mono(pcm)
    if mono.rate == rate or not mono.data:
        return Pcm(mono.data, rate if not mono.data else mono.rate, 1)
    src = _samples(mono.data)
    ratio = mono.rate / rate
    count = int(len(src) / ratio)
    out = array("h", bytes(2 * count))
    last = len(src) - 1
    for i in range(count):
        pos = i * ratio
        j = int(pos)
        frac = pos - j
        a = src[j]
        b = src[j + 1] if j < last else a
        out[i] = int(a + (b - a) * frac)
    return Pcm(_to_bytes(out), rate, 1)


def level(pcm: bytes) -> float:
    """Nivel 0..1 de un bloque PCM16 con la misma curva que el firmware (-50..-10 dBFS)."""
    s = _samples(pcm)
    if not s:
        return 0.0
    rms = math.sqrt(sum(v * v for v in s) / len(s)) / 32768.0
    db = 20.0 * math.log10(rms + 1e-6)
    return min(1.0, max(0.0, (db + 50.0) / 40.0))


def rms(pcm: bytes) -> float:
    s = _samples(pcm)
    if not s:
        return 0.0
    return math.sqrt(sum(v * v for v in s) / len(s))


def tone(freq: float, ms: int, rate: int = SAMPLE_RATE, amp: float = 0.35) -> bytes:
    """Tono con rampas de 5 ms (avisos de "te escucho")."""
    total = rate * ms // 1000
    fade = max(1, rate // 200)
    out = array("h", bytes(2 * total))
    for i in range(total):
        env = min(1.0, i / fade, (total - i) / fade)
        out[i] = int(amp * env * 32767 * math.sin(2 * math.pi * freq * i / rate))
    return _to_bytes(out)


def chime(rising: bool = True, rate: int = SAMPLE_RATE) -> bytes:
    first, second = (880.0, 1320.0) if rising else (1320.0, 880.0)
    return tone(first, 70, rate) + tone(second, 90, rate)


def split_levels(pcm: Pcm, block_ms: int = 40) -> list[float]:
    """Niveles por bloque para animar la boca mientras suena el audio."""
    mono = to_mono(pcm)
    step = max(2, mono.rate * block_ms // 1000 * 2)
    return [level(mono.data[i : i + step]) for i in range(0, len(mono.data), step)]
