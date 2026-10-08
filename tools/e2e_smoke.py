#!/usr/bin/env python3
"""Prueba de punta a punta contra un G-Mini real (emparejamiento, WebSocket y voz).

Hace lo mismo que un dispositivo de G-Mini Home, sin hardware:
  1. health y emparejamiento (con un codigo, o creando uno con un token admin);
  2. GET /me con el token del dispositivo;
  3. WebSocket: hello -> ready, node.register -> node.registered, ping -> pong, node.event;
  4. voz: sintetiza una pregunta con /voice/tts, la envia a /voice/turn y valida
     transcripcion, respuesta y audio; prueba /voice/wake con "Oye G-Mini, ...";
  5. revoca el dispositivo de prueba (si hay token admin).

Uso:
  python tools/e2e_smoke.py --url http://100.64.0.10:8765 --admin-token-file token.txt
  python tools/e2e_smoke.py --url http://192.168.1.50:8765 --pair 482913
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

from gmini_link.api import GMiniClient, GMiniError
from gmini_link.pairlink import normalize_base_url
from gmini_link.wav import Pcm, decode_wav, encode_wav, resample
from websockets.asyncio.client import connect


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def step(self, name: str, ok: bool, detail: str = "") -> None:
        mark = "OK  " if ok else "FALLA"
        print(f"[{mark}] {name}" + (f"  {detail}" if detail else ""), flush=True)
        if not ok:
            self.failed += 1


async def ws_check(url: str, token: str, report: Report) -> None:
    async with connect(url, additional_headers={"Authorization": f"Bearer {token}"}, open_timeout=10) as ws:
        await ws.send(json.dumps({"type": "hello", "client": "gmini-home-e2e", "version": "0.1.0",
                                  "device_name": "Prueba E2E"}))
        ready = json.loads(await asyncio.wait_for(ws.recv(), 10))
        report.step("ws hello -> ready", ready.get("type") == "ready",
                    f"agente={ready.get('agent_name')} protocolo={ready.get('protocol')}")
        surfaces = ["display.face", "display.text", "sensor.read"]
        await ws.send(json.dumps({"type": "node.register", "surfaces": surfaces, "platform": "e2e",
                                  "meta": {"firmware": "gmini-home-e2e"}}))
        await ws.send('{"type": "ping"}')
        seen: dict[str, dict] = {}
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not {"node.registered", "pong"} <= set(seen):
            frame = json.loads(await asyncio.wait_for(ws.recv(), max(0.1, deadline - time.monotonic())))
            seen.setdefault(frame.get("type", ""), frame)
        registered = seen.get("node.registered", {})
        report.step("ws node.register -> node.registered", registered.get("surfaces") == surfaces)
        report.step("ws ping -> pong", "pong" in seen)
        await ws.send(json.dumps({"type": "node.event", "event": "button", "data": {"button": 1, "action": "down"}}))
        report.step("ws node.event enviado", True)


async def main_async(args: argparse.Namespace) -> int:
    report = Report()
    base = normalize_base_url(args.url)
    admin_token = args.admin_token_file.read_text(encoding="utf-8").strip() if args.admin_token_file else None
    async with GMiniClient(base, admin_token, voice_timeout=180) as admin:
        health = await admin.health()
        report.step("health", bool(health.get("ok")), f"modo={health.get('mode')} version={health.get('version')}")
        code = args.pair
        if not code:
            if not admin_token:
                print("Falta --pair o --admin-token-file", file=sys.stderr)
                return 2
            pairing = await admin.create_pairing(label="Prueba E2E G-Mini Home", device_type="esp32",
                                                 scopes=["chat", "voice", "node"])
            code = pairing["code"]
            report.step("pairing (codigo nuevo)", len(code) == 6, f"vence {pairing.get('expires_at')}")
        claimed = await admin.claim(code, device_name="Prueba E2E G-Mini Home", device_type="esp32",
                                    platform="e2e-python")
        report.step("pairing/claim", claimed.token.startswith("gm_"), f"device_id={claimed.device_id}")

    device_id = claimed.device_id
    try:
        async with GMiniClient(base, claimed.token, voice_timeout=180) as dev:
            me = await dev.me()
            report.step("GET /me", me.get("device_id") == device_id, f"scopes={me.get('scopes')}")
            await ws_check(dev.ws_url(), claimed.token, report)

            if not args.skip_voice:
                question = await dev.tts(args.question)
                pcm = resample(decode_wav(question), 16000)
                report.step("voice/tts", pcm.seconds > 0.5, f"{pcm.seconds:.1f} s de audio")
                started = time.monotonic()
                turn = await dev.voice_turn(encode_wav(pcm.data))
                elapsed = time.monotonic() - started
                audio = decode_wav(turn.audio) if turn.audio else Pcm(b"", 16000, 1)
                report.step("voice/turn transcripcion", bool(turn.transcript), repr(turn.transcript))
                hint = "" if turn.reply else " (el agente no contesto: revisa su proveedor de IA)"
                report.step("voice/turn respuesta", bool(turn.reply), repr(turn.reply[:120]) + hint)
                report.step("voice/turn audio", audio.seconds > 0.3,
                            f"{audio.seconds:.1f} s a {audio.rate} Hz, emocion={turn.emotion!r}, {elapsed:.1f} s")
                wake_audio = resample(decode_wav(await dev.tts(args.wake_phrase)), 16000)
                wake = await dev.voice_wake(encode_wav(wake_audio.data))
                report.step("voice/wake", wake.wake, f"frase={wake.phrase!r} comando={wake.command!r} "
                                                     f"transcripcion={wake.transcript!r}")
    except GMiniError as exc:
        report.step("API", False, f"{exc.status} {exc.code}: {exc.message}")
    finally:
        if admin_token and device_id:
            async with GMiniClient(base, admin_token) as admin:
                try:
                    await admin.revoke_device(device_id)
                    report.step("dispositivo de prueba revocado", True, device_id)
                except GMiniError as exc:
                    report.step("revocar dispositivo", False, str(exc))
    print(f"\n{'Todo bien' if not report.failed else f'{report.failed} paso(s) fallaron'}.")
    return 1 if report.failed else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", required=True)
    p.add_argument("--pair", help="codigo de 6 digitos generado en G-Mini")
    p.add_argument("--admin-token-file", type=Path, help="token con scope admin (crea el codigo y revoca al final)")
    p.add_argument("--question", default="¿Cuánto es dos más dos? Responde en una frase corta.")
    p.add_argument("--wake-phrase", default="Oye G-Mini, ¿qué hora es?")
    p.add_argument("--skip-voice", action="store_true")
    return asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
