"""Almacen de credenciales de dispositivo.

Usa el llavero del sistema (keyring) si esta instalado y disponible; si no,
un JSON en la carpeta de configuracion del usuario con permisos 600.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

log = logging.getLogger(__name__)
SERVICE = "gmini-home"


@dataclass(frozen=True)
class Credentials:
    base_url: str
    token: str
    device_id: str = ""
    agent_name: str = "G-Mini"
    server_name: str = ""


def config_dir() -> Path:
    override = os.environ.get("GMINI_HOME_CONFIG")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "gmini-home"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return (Path(xdg) if xdg else Path.home() / ".config") / "gmini-home"


class TokenStore:
    """Guarda una credencial por (aplicacion, servidor)."""

    def __init__(self, app: str, *, path: Path | None = None, use_keyring: bool | None = None) -> None:
        self.app = app
        self.path = path or config_dir() / "credentials.json"
        self._keyring = self._load_keyring() if use_keyring in (None, True) else None

    @staticmethod
    def _load_keyring():
        try:
            import keyring
            from keyring.backends import fail
        except ImportError:
            return None
        if isinstance(keyring.get_keyring(), fail.Keyring):
            return None
        return keyring

    def _key(self, base_url: str) -> str:
        return f"{self.app}@{base_url}"

    # ------------------------------------------------------------ archivo

    def _read_file(self) -> dict[str, dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            log.warning("No se pudo leer %s: %s", self.path, exc)
            return {}
        return data if isinstance(data, dict) else {}

    def _write_file(self, data: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if os.name == "posix":
            os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------ API

    def load(self, base_url: str) -> Credentials | None:
        record = self._read_file().get(self._key(base_url))
        if not record:
            return None
        token = record.get("token", "")
        if self._keyring is not None and not token:
            token = self._keyring.get_password(SERVICE, self._key(base_url)) or ""
        if not token:
            return None
        return Credentials(base_url=base_url, token=token, device_id=record.get("device_id", ""),
                           agent_name=record.get("agent_name", "G-Mini"),
                           server_name=record.get("server_name", ""))

    def save(self, creds: Credentials) -> None:
        data = self._read_file()
        record = asdict(creds)
        if self._keyring is not None:
            self._keyring.set_password(SERVICE, self._key(creds.base_url), creds.token)
            record["token"] = ""  # el token queda solo en el llavero
        data[self._key(creds.base_url)] = record
        self._write_file(data)

    def delete(self, base_url: str) -> bool:
        data = self._read_file()
        existed = data.pop(self._key(base_url), None) is not None
        if self._keyring is not None:
            try:
                self._keyring.delete_password(SERVICE, self._key(base_url))
            except Exception:
                pass
        self._write_file(data)
        return existed

    def last(self) -> Credentials | None:
        """La credencial mas reciente de esta aplicacion (para no pedir --url cada vez)."""
        prefix = f"{self.app}@"
        keys = [k for k in self._read_file() if k.startswith(prefix)]
        return self.load(keys[-1][len(prefix):]) if keys else None
