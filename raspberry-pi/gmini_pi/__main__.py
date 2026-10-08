"""python -m gmini_pi: cara de G-Mini a pantalla completa con voz.

Ejemplos:
  python -m gmini_pi --demo --windowed                # probar la pantalla sin servidor
  python -m gmini_pi --url http://192.168.1.50:8765 --pair 482913
  python -m gmini_pi                                  # con /etc/gmini-home/config.toml
  python -m gmini_pi --layout pyramid --demo          # para piramide de Pepper
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import platform
import sys
from pathlib import Path

try:
    import gmini_link  # noqa: F401
except ImportError:  # desde una copia del repositorio
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))

from gmini_link.api import GMiniClient, GMiniError
from gmini_link.pairlink import normalize_base_url, parse_pair_input
from gmini_link.tokens import Credentials, TokenStore

from . import __version__
from .config import LAYOUTS, ConfigError, load

log = logging.getLogger("gmini_pi")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gmini_pi", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__.split("Ejemplos:", 1)[1])
    p.add_argument("--config", type=Path, help="archivo TOML (por defecto /etc/gmini-home/config.toml)")
    p.add_argument("--url", help="servidor G-Mini (sobrescribe server.url)")
    p.add_argument("--pair", metavar="CODIGO", help="empareja con un codigo de 6 digitos o un enlace gmini://")
    p.add_argument("--pair-only", action="store_true", help="con --pair: empareja y sale (lo usa install.sh)")
    p.add_argument("--forget", action="store_true", help="borra el emparejamiento guardado y sale")
    p.add_argument("--demo", action="store_true", help="recorre las expresiones sin conectarse a G-Mini")
    p.add_argument("--windowed", action="store_true", help="ventana en vez de pantalla completa")
    p.add_argument("--layout", choices=LAYOUTS, help="normal, mirror (Pepper) o pyramid (piramide de 4 caras)")
    p.add_argument("--list-audio", action="store_true", help="muestra los dispositivos de audio y sale")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


async def pair(store: TokenStore, url: str, code_or_link: str, name: str) -> Credentials:
    info = parse_pair_input(code_or_link)
    base_url = normalize_base_url(info.base_url or url)
    async with GMiniClient(base_url) as client:
        result = await client.claim(info.code, device_name=name, device_type="raspberry-pi",
                                    platform=f"{platform.system().lower()}-{platform.machine()}")
    creds = Credentials(base_url=base_url, token=result.token, device_id=result.device_id,
                        agent_name=result.agent_name, server_name=result.server_name)
    store.save(creds)
    print(f"Emparejado con {result.server_name or base_url} (agente {result.agent_name}).")
    return creds


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S")
    if args.list_audio:
        from gmini_link.audio_io import list_devices

        print(list_devices())
        return 0
    try:
        config = load(args.config)
    except ConfigError as exc:
        print(f"Configuracion invalida: {exc}", file=sys.stderr)
        return 2
    if args.windowed:
        config.display.fullscreen = False
    if args.layout:
        config.display.layout = args.layout
    url = args.url or config.server.url

    store = TokenStore("pi")
    if args.forget:
        if url and store.delete(normalize_base_url(url)):
            print("Emparejamiento borrado. Revoca tambien el dispositivo en G-Mini.")
        else:
            print("No habia un emparejamiento guardado para ese servidor.")
        return 0

    creds: Credentials | None = None
    if args.pair or not args.demo:
        try:
            if args.pair:
                creds = asyncio.run(pair(store, url or "", args.pair, config.server.device_name))
                if args.pair_only:
                    return 0
            elif url:
                creds = store.load(normalize_base_url(url))
            else:
                creds = store.last()
        except (ValueError, OSError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        except GMiniError as exc:
            print(f"No se pudo emparejar: {exc.describe()} ({exc})", file=sys.stderr)
            return 2
        if creds is None:
            print("Esta pantalla no esta emparejada: arranco en modo demostracion.\n"
                  "Para emparejar: python -m gmini_pi --url http://IP:8765 --pair CODIGO", file=sys.stderr)

    from .app import PiApp

    try:
        return asyncio.run(PiApp(config, creds, demo=args.demo).run())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
