"""Enlaces de emparejamiento (gmini://pair?...) y direcciones de servidor."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

DEFAULT_PORT = 8765
_HOST_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class PairInfo:
    code: str
    host: str = ""
    port: int = 0

    @property
    def base_url(self) -> str:
        if not self.host:
            return ""
        return f"http://{self.host}:{self.port or DEFAULT_PORT}"


def _normalize_code(text: str) -> str | None:
    digits = re.sub(r"[\s-]", "", text)
    return digits if re.fullmatch(r"\d{6}", digits) else None


def parse_pair_input(text: str) -> PairInfo:
    """Acepta "482913", "482 913" o "gmini://pair?host=...&port=...&code=...".

    Lanza ValueError con un mensaje en espanol si no es valido.
    """
    raw = (text or "").strip()
    if raw.lower().startswith("gmini://"):
        parts = urlsplit(raw)
        if parts.netloc.lower() != "pair":
            raise ValueError("El enlace debe empezar con gmini://pair")
        query = parse_qs(parts.query)
        code = _normalize_code((query.get("code") or [""])[0])
        if code is None:
            raise ValueError("El enlace no trae un código de 6 dígitos")
        host = (query.get("host") or [""])[0].strip()
        if host and not _HOST_RE.match(host):
            raise ValueError("El enlace trae un host inválido")
        port_text = (query.get("port") or [""])[0].strip()
        port = 0
        if port_text:
            if not port_text.isdigit() or not 0 < int(port_text) < 65536:
                raise ValueError("El enlace trae un puerto inválido")
            port = int(port_text)
        return PairInfo(code=code, host=host, port=port)
    code = _normalize_code(raw)
    if code is None:
        raise ValueError("El código debe tener 6 dígitos")
    return PairInfo(code=code)


def normalize_base_url(value: str, default_port: int = DEFAULT_PORT) -> str:
    """Convierte "192.168.1.20", "tv-server:8765" o "https://x" en una URL base sin barra final."""
    raw = (value or "").strip().rstrip("/")
    if not raw:
        raise ValueError("Falta la dirección del servidor")
    if "://" not in raw:
        raw = "http://" + raw
    parts = urlsplit(raw)
    if parts.scheme not in ("http", "https"):
        raise ValueError("La dirección debe ser http:// o https://")
    host = parts.hostname or ""
    if not host or not _HOST_RE.match(host):
        raise ValueError(f"Host inválido: {value!r}")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError(f"Puerto inválido: {value!r}") from exc
    if port is None:
        port = 443 if parts.scheme == "https" else default_port
    default_for_scheme = 443 if parts.scheme == "https" else 80
    netloc = host if port == default_for_scheme else f"{host}:{port}"
    return f"{parts.scheme}://{netloc}"
