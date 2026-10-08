"""Flujos de voz compartidos por el puente USB y el cliente de Raspberry Pi.

- Pulsar para hablar: grabar mientras se mantiene el boton y enviar a /voice/turn.
- Palabra de activacion por el servidor: el detector de voz recorta frases
  cortas y las manda a /voice/wake; si dicen "Oye G-Mini", se atiende el pedido.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Protocol

from .api import GMiniClient, GMiniError
from .audio_io import AudioUnavailable, BlockQueue, Player, Recorder
from .face import parse_emotion
from .vad import EnergyVad, VadEvent
from .wav import SAMPLE_RATE, Pcm, chime, decode_wav, encode_wav

log = logging.getLogger(__name__)


class FaceSink(Protocol):
    """Lo que el asistente necesita de una cara (OLED por USB, pygame, kiosco...)."""

    def set_status(self, status: str) -> None: ...

    def set_emotion(self, emotion: str) -> None: ...

    def set_caption(self, text: str, seconds: float | None = None) -> None: ...

    def set_level(self, level: float) -> None: ...


def caption_seconds(text: str) -> float:
    return min(15.0, 4.0 + 0.055 * len(text))


class VoiceAssistant:
    def __init__(
        self,
        client: GMiniClient,
        face: FaceSink,
        *,
        recorder: Recorder | None,
        player: Player | None,
        min_record_s: float = 0.35,
        max_record_s: float = 15.0,
        play_chimes: bool = True,
    ) -> None:
        self.client = client
        self.face = face
        self.recorder = recorder
        self.player = player
        self.min_record_s = min_record_s
        self.max_record_s = max_record_s
        self.play_chimes = play_chimes
        self.session_id: str | None = None
        self._busy = False
        self._listening = False
        self._listen_started = 0.0
        self._max_timer: asyncio.Task[None] | None = None
        self._wake_active = False

    @property
    def busy(self) -> bool:
        return self._busy or self._listening

    # ------------------------------------------------------------ audio

    async def _play(self, pcm: Pcm) -> None:
        if self.player is None:
            return
        try:
            await asyncio.to_thread(self.player.play, pcm, self.face.set_level)
        except AudioUnavailable as exc:
            log.warning("%s", exc)

    async def _chime(self, rising: bool = True) -> None:
        if self.play_chimes:
            await self._play(Pcm(chime(rising), SAMPLE_RATE, 1))

    def _show_error(self, err: GMiniError) -> None:
        log.warning("G-Mini: %s", err)
        self.face.set_status("idle")
        self.face.set_emotion("error")
        self.face.set_caption(err.describe(), 5.0)

    # ------------------------------------------------------------ pulsar para hablar

    async def start_listening(self) -> None:
        if self.busy or self.recorder is None:
            if self.recorder is None:
                self.face.set_caption("No hay micrófono configurado", 4.0)
            return
        self._listening = True
        self.face.set_emotion("neutral")
        self.face.set_status("listening")
        self.face.set_caption("", 0)
        await self._chime(True)
        try:
            self.recorder.start()
        except AudioUnavailable as exc:
            self._listening = False
            self.face.set_status("idle")
            self.face.set_emotion("error")
            self.face.set_caption("No pude abrir el micrófono", 5.0)
            log.error("%s", exc)
            return
        self.recorder.take()
        self._listen_started = asyncio.get_running_loop().time()
        self._max_timer = asyncio.create_task(self._limit_recording())

    async def _limit_recording(self) -> None:
        await asyncio.sleep(self.max_record_s)
        if self._listening:
            await self.stop_listening()

    async def stop_listening(self) -> None:
        if not self._listening or self.recorder is None:
            return
        self._listening = False
        if self._max_timer is not None and self._max_timer is not asyncio.current_task():
            self._max_timer.cancel()
        # Con la palabra de activacion el microfono sigue abierto para ella.
        pcm = self.recorder.take() if self._wake_active else self.recorder.stop()
        self.face.set_level(0.0)
        if len(pcm) / (2.0 * SAMPLE_RATE) < self.min_record_s:
            self.face.set_status("idle")
            self.face.set_caption("Mantén presionado mientras hablas", 3.0)
            return
        await self.turn(pcm)

    # ------------------------------------------------------------ turnos

    async def turn(self, pcm: bytes) -> None:
        """Envia PCM16 mono de 16 kHz a /voice/turn y reproduce la respuesta."""
        self._busy = True
        try:
            self.face.set_status("thinking")
            try:
                result = await self.client.voice_turn(encode_wav(pcm), session_id=self.session_id)
            except GMiniError as err:
                self._show_error(err)
                return
            if not result.transcript:
                self.face.set_status("idle")
                self.face.set_emotion("thinking")
                self.face.set_caption("No te escuché bien", 3.5)
                return
            if result.session_id:
                self.session_id = result.session_id
            if not result.reply:
                # Te entendio pero el agente no contesto (proveedor de IA caido o sin configurar).
                log.warning("G-Mini no devolvio respuesta para %r", result.transcript)
                self.face.set_status("idle")
                self.face.set_emotion("sad")
                self.face.set_caption("G-Mini no respondió; revisa su proveedor de IA", 5.0)
                return
            if parse_emotion(result.emotion):
                self.face.set_emotion(result.emotion)
            log.info("Tu: %s | %s: %s", result.transcript, "G-Mini", result.reply)
            if result.reply:
                self.face.set_caption(result.reply, None)
            if result.audio:
                await self._speak_wav(result.audio)
            self.face.set_status("idle")
            if result.reply:
                self.face.set_caption(result.reply, caption_seconds(result.reply))
        finally:
            self._busy = False

    async def _speak_wav(self, wav: bytes) -> None:
        try:
            pcm = decode_wav(wav)
        except ValueError as exc:
            log.warning("Audio de respuesta invalido: %s", exc)
            return
        self.face.set_status("speaking")
        await self._play(pcm)

    async def say(self, text: str) -> None:
        """Dice un texto con la voz del servidor (tts.speak, avisos)."""
        if not text or self.busy:
            return
        self._busy = True
        try:
            self.face.set_caption(text, None)
            try:
                wav = await self.client.tts(text)
            except GMiniError as err:
                self._show_error(err)
                return
            await self._speak_wav(wav)
            self.face.set_status("idle")
            self.face.set_caption(text, caption_seconds(text))
        finally:
            self._busy = False

    def cancel(self) -> None:
        if self.player is not None:
            self.player.stop()

    def keep_microphone_open(self) -> None:
        """Un detector de palabra de activacion usa el microfono todo el tiempo:
        al soltar el boton no se cierra el flujo, solo se toma lo grabado."""
        self._wake_active = True

    async def answer_next_utterance(self, blocks: BlockQueue) -> None:
        """Tras la palabra de activacion: escucha la siguiente frase y responde."""
        await self._chime(True)
        self.face.set_status("listening")
        blocks.clear()
        pcm = await self._record_utterance(blocks)
        if pcm:
            await self.turn(pcm)
        else:
            self.face.set_status("idle")
        blocks.clear()

    # ------------------------------------------------------------ palabra de activacion

    async def wake_loop(self, stop: asyncio.Event, *, cooldown_s: float = 1.2) -> None:
        """Escucha siempre y consulta /voice/wake con cada frase corta detectada."""
        if self.recorder is None:
            raise AudioUnavailable("La palabra de activacion necesita microfono")
        blocks = BlockQueue()
        self.recorder.add_listener(blocks.put)
        self.recorder.start()
        self.keep_microphone_open()
        vad = EnergyVad(SAMPLE_RATE, max_speech_ms=3800)
        preroll: deque[bytes] = deque(maxlen=15)  # 15 bloques de 20 ms = 300 ms
        segment: list[bytes] = []
        capturing = False
        blocked_until = 0.0
        loop = asyncio.get_running_loop()
        log.info("Palabra de activacion activa (deteccion en el servidor)")
        while not stop.is_set():
            block = await asyncio.to_thread(blocks.get, 0.25)
            if self.busy:
                # Pulsar para hablar o una respuesta en curso: el detector espera.
                blocks.clear()
                capturing = False
                vad.reset()
                continue
            self.recorder.take()  # fuera de un turno lo grabado no se usa
            if block is None:
                continue
            preroll.append(block)
            if capturing:
                segment.append(block)
            event = vad.feed(block)
            if event is VadEvent.SPEECH_START and not capturing and loop.time() >= blocked_until:
                capturing = True
                segment = list(preroll)
            if capturing and (event is VadEvent.SPEECH_END or len(segment) * 20 >= 3800):
                capturing = False
                pcm = b"".join(segment)
                if len(pcm) >= 2 * SAMPLE_RATE * 0.4:
                    ok = await self._check_wake(pcm, blocks)
                    blocked_until = loop.time() + (cooldown_s if ok else 30.0)
                vad.reset()

    async def _check_wake(self, pcm: bytes, blocks: BlockQueue) -> bool:
        try:
            result = await self.client.voice_wake(encode_wav(pcm))
        except GMiniError as err:
            log.warning("wake: %s", err)
            return False
        if not result.wake:
            return True
        log.info("Activacion: %r comando=%r", result.transcript, result.command)
        if result.command:
            await self._chime(True)
            await self.ask(result.command)
        else:
            await self.answer_next_utterance(blocks)
        blocks.clear()
        return True

    async def ask(self, text: str) -> None:
        """Pedido en texto (lo que siguio a "Oye G-Mini"): chat + voz."""
        self._busy = True
        try:
            self.face.set_status("thinking")
            try:
                chat = await self.client.chat(text, session_id=self.session_id)
            except GMiniError as err:
                self._show_error(err)
                return
            if chat.session_id:
                self.session_id = chat.session_id
            if chat.reply:
                self.face.set_caption(chat.reply, None)
                try:
                    await self._speak_wav(await self.client.tts(chat.reply))
                except GMiniError as err:
                    log.warning("tts: %s", err)
            self.face.set_status("idle")
            if chat.reply:
                self.face.set_caption(chat.reply, caption_seconds(chat.reply))
        finally:
            self._busy = False

    async def _record_utterance(self, blocks: BlockQueue, max_s: float = 8.0) -> bytes:
        vad = EnergyVad(SAMPLE_RATE, min_speech_ms=120, hangover_ms=900, max_speech_ms=int(max_s * 1000))
        out: list[bytes] = []
        heard = False
        waited = 0.0
        while len(out) * 0.02 < max_s:
            block = await asyncio.to_thread(blocks.get, 0.25)
            if block is None:
                waited += 0.25
                if not heard and waited > 5.0:
                    return b""
                continue
            out.append(block)
            self.face.set_level(min(1.0, vad.last_rms / 4000.0))
            event = vad.feed(block)
            if event is VadEvent.SPEECH_START:
                heard = True
            if event is VadEvent.SPEECH_END:
                break
            if not heard and len(out) * 0.02 > 5.0:
                return b""
        self.face.set_level(0.0)
        return b"".join(out) if heard else b""
