"""Configuracion del cliente (TOML)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

LAYOUTS = ("normal", "mirror", "pyramid")
WAKE_MODES = ("off", "server", "openwakeword")

SEARCH_PATHS = (
    Path("/etc/gmini-home/config.toml"),
    Path.home() / ".config" / "gmini-home" / "config.toml",
)


class ConfigError(ValueError):
    """Configuracion invalida (el mensaje dice que corregir)."""


@dataclass
class ServerConfig:
    url: str = ""
    device_name: str = "Pantalla G-Mini"


@dataclass
class DisplayConfig:
    fullscreen: bool = True
    width: int = 0
    height: int = 0
    fps: int = 30
    layout: str = "normal"
    rotate: int = 0
    supersample: int = 1
    captions: bool = True
    hide_cursor: bool = True
    invert: bool = False  # LCD transparente: lo negro queda opaco y lo blanco transparente


@dataclass
class AudioConfig:
    enabled: bool = True
    input: str = ""
    output: str = ""
    volume: int = 80
    chimes: bool = True


@dataclass
class ButtonsConfig:
    gpio_talk: int = 0
    gpio_cancel: int = 0
    keyboard: bool = True


@dataclass
class WakeConfig:
    mode: str = "off"
    model: str = ""
    threshold: float = 0.5


@dataclass
class KioskConfig:
    enabled: bool = False
    listen: str = "127.0.0.1:8088"

    @property
    def host_port(self) -> tuple[str, int]:
        host, _, port = self.listen.rpartition(":")
        if not host or not port.isdigit():
            raise ConfigError(f"kiosk.listen debe ser host:puerto (llego {self.listen!r})")
        return host, int(port)


@dataclass
class PiConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    display: DisplayConfig = field(default_factory=DisplayConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    buttons: ButtonsConfig = field(default_factory=ButtonsConfig)
    wake: WakeConfig = field(default_factory=WakeConfig)
    kiosk: KioskConfig = field(default_factory=KioskConfig)
    path: Path | None = None


def _section(cls: type, raw: Any, name: str) -> Any:
    if raw is None:
        return cls()
    if not isinstance(raw, dict):
        raise ConfigError(f"[{name}] debe ser una tabla")
    known = {f.name: f for f in fields(cls)}
    unknown = set(raw) - set(known)
    if unknown:
        raise ConfigError(f"[{name}] tiene claves desconocidas: {', '.join(sorted(unknown))}")
    values = {}
    for key, value in raw.items():
        expected = type(getattr(cls(), key))
        if expected is float and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
            raise ConfigError(f"{name}.{key} debe ser {expected.__name__}")
        values[key] = value
    return cls(**values)


def validate(cfg: PiConfig) -> PiConfig:
    d = cfg.display
    if d.layout not in LAYOUTS:
        raise ConfigError(f"display.layout debe ser uno de {', '.join(LAYOUTS)}")
    if d.rotate not in (0, 90, 180, 270):
        raise ConfigError("display.rotate debe ser 0, 90, 180 o 270")
    if not 5 <= d.fps <= 120:
        raise ConfigError("display.fps debe estar entre 5 y 120")
    if d.supersample not in (1, 2):
        raise ConfigError("display.supersample debe ser 1 o 2")
    if not 0 <= cfg.audio.volume <= 100:
        raise ConfigError("audio.volume debe estar entre 0 y 100")
    if cfg.wake.mode not in WAKE_MODES:
        raise ConfigError(f"wake.mode debe ser uno de {', '.join(WAKE_MODES)}")
    if cfg.wake.mode == "openwakeword" and not cfg.wake.model:
        raise ConfigError("wake.model es obligatorio con mode = \"openwakeword\"")
    if not 0.0 < cfg.wake.threshold < 1.0:
        raise ConfigError("wake.threshold debe estar entre 0 y 1")
    for name in ("gpio_talk", "gpio_cancel"):
        if not 0 <= getattr(cfg.buttons, name) <= 27:
            raise ConfigError(f"buttons.{name} debe ser un GPIO BCM entre 1 y 27 (0 = sin boton)")
    if cfg.kiosk.enabled:
        cfg.kiosk.host_port  # noqa: B018 - valida el formato
    return cfg


def parse(text: str, path: Path | None = None) -> PiConfig:
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"TOML invalido: {exc}") from exc
    unknown = set(raw) - {"server", "display", "audio", "buttons", "wake", "kiosk"}
    if unknown:
        raise ConfigError(f"Secciones desconocidas: {', '.join(sorted(unknown))}")
    cfg = PiConfig(
        server=_section(ServerConfig, raw.get("server"), "server"),
        display=_section(DisplayConfig, raw.get("display"), "display"),
        audio=_section(AudioConfig, raw.get("audio"), "audio"),
        buttons=_section(ButtonsConfig, raw.get("buttons"), "buttons"),
        wake=_section(WakeConfig, raw.get("wake"), "wake"),
        kiosk=_section(KioskConfig, raw.get("kiosk"), "kiosk"),
        path=path,
    )
    return validate(cfg)


def load(path: Path | None = None) -> PiConfig:
    """Lee el archivo indicado, GMINI_PI_CONFIG o el primero que exista en SEARCH_PATHS."""
    candidates = [path] if path else []
    env = os.environ.get("GMINI_PI_CONFIG")
    if env:
        candidates.append(Path(env))
    candidates.extend(SEARCH_PATHS)
    for candidate in candidates:
        if candidate and candidate.is_file():
            return parse(candidate.read_text(encoding="utf-8"), candidate)
    if path:
        raise ConfigError(f"No existe {path}")
    return validate(PiConfig())
