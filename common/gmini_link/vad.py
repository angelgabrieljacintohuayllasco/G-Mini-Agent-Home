"""Detector de voz por energia (mismo algoritmo que GMiniLink::EnergyVad)."""

from __future__ import annotations

import math
from array import array
from enum import Enum


class VadEvent(Enum):
    NONE = 0
    SPEECH_START = 1
    SPEECH_END = 2


class EnergyVad:
    def __init__(self, sample_rate: int = 16000, *, start_ratio: float = 3.0, stop_ratio: float = 1.8,
                 min_speech_ms: int = 160, hangover_ms: int = 650, max_speech_ms: int = 3800,
                 min_rms: float = 150.0) -> None:
        self.rate = sample_rate
        self.start_ratio = start_ratio
        self.stop_ratio = stop_ratio
        self.min_speech_ms = min_speech_ms
        self.hangover_ms = hangover_ms
        self.max_speech_ms = max_speech_ms
        self.min_rms = min_rms
        self.reset()

    def reset(self) -> None:
        self.floor = 0.0
        self.last_rms = 0.0
        self.in_speech = False
        self.speech_ms = 0
        self._above_ms = 0
        self._silence_ms = 0
        self._primed = False

    def feed(self, pcm: bytes) -> VadEvent:
        samples = array("h")
        samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        if not samples:
            return VadEvent.NONE
        self.last_rms = math.sqrt(sum(v * v for v in samples) / len(samples))
        block_ms = len(samples) * 1000 // self.rate
        if not self._primed:
            self.floor = max(self.last_rms, self.min_rms * 0.5)
            self._primed = True
        if not self.in_speech:
            if self.last_rms > max(self.floor * self.start_ratio, self.min_rms):
                self._above_ms += block_ms
                if self._above_ms >= self.min_speech_ms:
                    self.in_speech = True
                    self.speech_ms = self._above_ms
                    self._silence_ms = 0
                    return VadEvent.SPEECH_START
            else:
                self._above_ms = 0
                k = 0.2 if self.last_rms < self.floor else 0.03
                self.floor = max(1.0, self.floor + (self.last_rms - self.floor) * k)
            return VadEvent.NONE
        self.speech_ms += block_ms
        if self.last_rms > max(self.floor * self.stop_ratio, self.min_rms * 0.8):
            self._silence_ms = 0
        else:
            self._silence_ms += block_ms
        if self._silence_ms >= self.hangover_ms or self.speech_ms >= self.max_speech_ms:
            self.in_speech = False
            self._above_ms = 0
            return VadEvent.SPEECH_END
        return VadEvent.NONE
