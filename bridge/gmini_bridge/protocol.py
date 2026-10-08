"""Protocolo serie de la cara USB (version 1). Ver docs/serial-protocol.md."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

PROTOCOL_VERSION = 1
MAX_TEXT = 43  # caben dos lineas de 21 caracteres en la OLED
MAX_TITLE = 21
MAX_BODY = 65

STATUSES = ("idle", "listening", "thinking", "acting", "speaking")

# Equivalencias para caracteres fuera de ISO-8859-1 (comillas tipograficas, guiones...).
_REPLACEMENTS = {
    "‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"',
    "–": "-", "—": "-", "…": "...", " ": " ", "€": "EUR", "•": "-",
}
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def to_latin1(text: str, max_len: int = MAX_TEXT) -> str:
    """Texto apto para la OLED: ISO-8859-1, una sola linea y recortado.

    Conserva tildes y enies; los caracteres sin equivalente (emojis, simbolos)
    se descartan en vez de mostrarse como basura.
    """
    text = unicodedata.normalize("NFC", text or "")
    text = "".join(_REPLACEMENTS.get(ch, ch) for ch in text)
    text = _CONTROL.sub(" ", text.replace("\r", " ").replace("\n", " ").replace("\t", " "))
    out = []
    for ch in text:
        try:
            ch.encode("latin-1")
            out.append(ch)
            continue
        except UnicodeEncodeError:
            pass
        base = unicodedata.normalize("NFKD", ch).encode("latin-1", "ignore").decode("latin-1")
        out.append(base)
    clean = re.sub(r"\s+", " ", "".join(out)).strip()
    if len(clean) > max_len:
        clean = clean[: max_len - 3].rstrip() + "..."
    return clean


def encode_status(status: str) -> str:
    if status not in STATUSES:
        raise ValueError(f"Estado desconocido: {status}")
    return f"S:{status}"


def encode_emotion(emotion: str) -> str:
    return f"E:{emotion}"


def encode_text(text: str) -> str:
    return "T:" + to_latin1(text, MAX_TEXT)


def encode_notify(title: str, body: str) -> str:
    return "N:" + to_latin1(title, MAX_TITLE).replace("|", "/") + "|" + to_latin1(body, MAX_BODY)


def encode_level(level: float) -> str:
    return f"L:{max(0, min(9, round(level * 9)))}"


def encode_look(x: float | None, y: float | None = None) -> str:
    if x is None or y is None:
        return "G:"
    return f"G:{round(max(-1.0, min(1.0, x)) * 100)},{round(max(-1.0, min(1.0, y)) * 100)}"


def encode_sleep(asleep: bool) -> str:
    return "Z:1" if asleep else "Z:0"


def encode_contrast(value: int) -> str:
    return f"C:{max(0, min(255, int(value)))}"


# ---------------------------------------------------------------- dispositivo -> PC


@dataclass(frozen=True)
class Hello:
    firmware: str
    version: str
    protocol: int


@dataclass(frozen=True)
class Ok:
    pass


@dataclass(frozen=True)
class ButtonEvent:
    button: int
    action: str  # down | up | long


@dataclass(frozen=True)
class DeviceError:
    code: str


DeviceMessage = Hello | Ok | ButtonEvent | DeviceError


def parse_device_line(line: str) -> DeviceMessage | None:
    """Interpreta una linea de la placa. Devuelve None para comentarios o basura."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line == "OK":
        return Ok()
    if line.startswith("H:"):
        parts = line[2:].split(";")
        if len(parts) != 3 or not parts[2].isdigit():
            return None
        return Hello(parts[0], parts[1], int(parts[2]))
    if line.startswith("B:"):
        parts = line[2:].split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1] in ("down", "up", "long"):
            return ButtonEvent(int(parts[0]), parts[1])
        return None
    if line.startswith("ERR:"):
        return DeviceError(line[4:])
    return None
