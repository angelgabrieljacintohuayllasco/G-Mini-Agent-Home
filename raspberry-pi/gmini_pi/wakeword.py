"""Palabra de activacion local con openWakeWord (opcional).

Necesita un modelo propio de "Oye G-Mini" (.onnx o .tflite) entrenado con las
herramientas de openWakeWord; ver docs/guides/raspberry-pi.md. Sin modelo,
usa wake.mode = "server" (la deteccion la hace G-Mini con /voice/wake).
"""

from __future__ import annotations

import asyncio
import logging

from gmini_link.assistant import VoiceAssistant
from gmini_link.audio_io import BlockQueue, Recorder

log = logging.getLogger(__name__)

FRAME_BYTES = 1280 * 2  # openWakeWord procesa cuadros de 80 ms a 16 kHz


async def openwakeword_loop(assistant: VoiceAssistant, recorder: Recorder, model_path: str, threshold: float,
                            stop: asyncio.Event) -> None:
    try:
        import numpy as np
        from openwakeword.model import Model
    except ImportError as exc:
        raise RuntimeError("Falta openwakeword: /opt/gmini-home/venv/bin/pip install openwakeword") from exc

    framework = "onnx" if model_path.endswith(".onnx") else "tflite"
    model = Model(wakeword_models=[model_path], inference_framework=framework)
    blocks = BlockQueue()
    recorder.add_listener(blocks.put)
    recorder.start()
    assistant.keep_microphone_open()
    loop = asyncio.get_running_loop()
    pending = bytearray()
    cooldown_until = 0.0
    log.info("Palabra de activacion local con %s (umbral %.2f)", model_path, threshold)
    while not stop.is_set():
        block = await asyncio.to_thread(blocks.get, 0.25)
        if assistant.busy:
            pending.clear()
            blocks.clear()
            continue
        recorder.take()
        if block is None:
            continue
        pending += block
        while len(pending) >= FRAME_BYTES:
            frame = np.frombuffer(bytes(pending[:FRAME_BYTES]), dtype=np.int16)
            del pending[:FRAME_BYTES]
            scores = model.predict(frame)
            if scores and max(scores.values()) >= threshold and loop.time() >= cooldown_until:
                log.info("Palabra detectada (%.2f)", max(scores.values()))
                model.reset()
                cooldown_until = loop.time() + 2.0
                await assistant.answer_next_utterance(blocks)
                pending.clear()
                break
