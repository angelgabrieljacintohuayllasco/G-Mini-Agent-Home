#!/usr/bin/env python3
"""Puente entre la cara USB de G-Mini Home (Arduino) y G-Mini Agent.

Ejemplos:
  python gmini_serial_bridge.py --url http://127.0.0.1:8765 --pair 482913
  python gmini_serial_bridge.py                       # usa el emparejamiento guardado
  python gmini_serial_bridge.py --session-token-file "C:/G-Mini-Agent/data/runtime/session_token"
  python gmini_serial_bridge.py --list-ports
  python gmini_serial_bridge.py --list-audio
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import platform
import signal
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:
    import gmini_link  # noqa: F401
except ImportError:  # desde una copia del repositorio: la biblioteca vive en common/
    sys.path.insert(0, str(HERE.parent / "common"))

from gmini_link.api import GMiniClient, GMiniError
from gmini_link.pairlink import DEFAULT_PORT, normalize_base_url, parse_pair_input
from gmini_link.tokens import Credentials, TokenStore

from gmini_bridge import __version__
from gmini_bridge.app import BridgeApp, BridgeConfig
from gmini_bridge.ports import candidates, list_ports

log = logging.getLogger("gmini_bridge")
DEFAULT_URL = f"http://127.0.0.1:{DEFAULT_PORT}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="gmini_serial_bridge",
        description="Conecta la cara USB (Arduino + OLED) con G-Mini: estado, avisos y voz.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Ejemplos:", 1)[1],
    )
    p.add_argument("--url", help=f"servidor G-Mini (por defecto el guardado o {DEFAULT_URL})")
    p.add_argument("--pair", metavar="CODIGO", help="empareja con un codigo de 6 digitos o un enlace gmini://pair?...")
    p.add_argument("--token", help="usa este token (no se guarda)")
    p.add_argument("--session-token-file", type=Path, help="lee el token de sesion del escritorio (misma PC)")
    p.add_argument("--forget", action="store_true", help="borra el emparejamiento guardado y sale")
    p.add_argument("--name", default="Cara USB", help="nombre del dispositivo en G-Mini")
    p.add_argument("--port", help="puerto serie (COM5, /dev/ttyUSB0); por defecto se detecta")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--no-audio", action="store_true", help="solo cara: sin microfono ni parlante")
    p.add_argument("--mic", help="microfono (indice o nombre de --list-audio)")
    p.add_argument("--speaker", help="parlante (indice o nombre de --list-audio)")
    p.add_argument("--volume", type=int, default=80, help="volumen 0-100")
    p.add_argument("--wake", action="store_true", help="activa 'Oye G-Mini' (deteccion en el servidor)")
    p.add_argument("--list-ports", action="store_true", help="muestra los puertos serie y sale")
    p.add_argument("--list-audio", action="store_true", help="muestra los dispositivos de audio y sale")
    p.add_argument("-v", "--verbose", action="store_true", help="registro detallado (incluye el trafico serie)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


async def pair(store: TokenStore, url: str | None, code_or_link: str, name: str) -> Credentials:
    info = parse_pair_input(code_or_link)
    base_url = normalize_base_url(info.base_url or url or DEFAULT_URL)
    async with GMiniClient(base_url) as client:
        result = await client.claim(info.code, device_name=name, device_type="arduino-usb",
                                    platform=f"{platform.system().lower()}-python{platform.python_version()}")
    creds = Credentials(base_url=base_url, token=result.token, device_id=result.device_id,
                        agent_name=result.agent_name, server_name=result.server_name)
    store.save(creds)
    print(f"Emparejado con {result.server_name or base_url} (agente {result.agent_name}).")
    return creds


def resolve_credentials(args: argparse.Namespace, store: TokenStore) -> Credentials | None:
    if args.session_token_file:
        token = args.session_token_file.read_text(encoding="utf-8").strip()
        return Credentials(base_url=normalize_base_url(args.url or DEFAULT_URL), token=token)
    if args.token:
        return Credentials(base_url=normalize_base_url(args.url or DEFAULT_URL), token=args.token)
    if args.url:
        return store.load(normalize_base_url(args.url))
    return store.last()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")
    if args.list_ports:
        ports = list_ports()
        good = {p.device for p in candidates(ports)}
        for p in ports:
            mark = "*" if p.device in good else " "
            print(f"{mark} {p.device:12} {p.label or '-':16} {p.description}")
        return 0
    if args.list_audio:
        from gmini_link.audio_io import list_devices

        print(list_devices())
        return 0

    store = TokenStore("bridge")
    if args.forget:
        url = normalize_base_url(args.url) if args.url else (store.last().base_url if store.last() else None)
        if url and store.delete(url):
            print(f"Emparejamiento con {url} borrado. Revoca tambien el dispositivo en G-Mini.")
        else:
            print("No habia un emparejamiento guardado.")
        return 0

    try:
        creds = asyncio.run(pair(store, args.url, args.pair, args.name)) if args.pair else resolve_credentials(
            args, store)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except GMiniError as exc:
        print(f"No se pudo emparejar: {exc.describe()} ({exc})", file=sys.stderr)
        return 2
    if creds is None:
        print("Falta emparejar el puente. En G-Mini abre Ajustes > Dispositivos > Este equipo, genera un\n"
              "codigo y ejecuta:  python gmini_serial_bridge.py --url http://IP:8765 --pair CODIGO", file=sys.stderr)
        return 2

    config = BridgeConfig(port=args.port, baud=args.baud, device_name=args.name, audio=not args.no_audio,
                          mic=args.mic, speaker=args.speaker, volume=max(0, min(100, args.volume)),
                          wake_word=args.wake)
    app = BridgeApp(config, creds)

    async def runner() -> int:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, app.stop)
            except (NotImplementedError, RuntimeError):
                pass  # Windows: Ctrl+C llega como KeyboardInterrupt
        return await app.run()

    try:
        return asyncio.run(runner())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
