"""Cliente asincrono de la G-Mini Remote API v1 (REST)."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import __version__
from .pairlink import normalize_base_url

USER_AGENT = f"gmini-home/{__version__}"


class GMiniError(Exception):
    """Error de la API (o de red, con status 0)."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}" if code else message)
        self.status = status
        self.code = code
        self.message = message

    @property
    def auth_failed(self) -> bool:
        return self.status == 401 or self.code in ("invalid_token", "invalid_code")

    def describe(self) -> str:
        """Mensaje corto en espanol para mostrar en una pantalla."""
        known = {
            "connect_failed": "No encuentro a G-Mini",
            "timeout": "G-Mini tardó demasiado",
            "invalid_code": "Código inválido o vencido",
            "invalid_token": "Hay que emparejar de nuevo",
            "busy": "Estoy ocupada, prueba en un momento",
            "rate_limited": "Demasiados intentos, espera un minuto",
            "missing_scope": "Me falta un permiso en G-Mini",
            "provider_unavailable": "La voz del servidor no está lista",
        }
        if self.code in known:
            return known[self.code]
        if self.status == 401:
            return known["invalid_token"]
        if self.status == 409:
            return known["busy"]
        return self.message or "Algo salió mal"


@dataclass(frozen=True)
class PairingResult:
    token: str
    device_id: str
    server_name: str = ""
    agent_name: str = "G-Mini"
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class VoiceTurn:
    transcript: str
    reply: str
    session_id: str = ""
    emotion: str = ""
    audio: bytes | None = None
    audio_mime: str = ""


@dataclass(frozen=True)
class WakeResult:
    wake: bool
    phrase: str = ""
    command: str = ""
    transcript: str = ""


@dataclass(frozen=True)
class ChatResult:
    reply: str
    session_id: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)


def _error_from_response(response: httpx.Response) -> GMiniError:
    code, message = "http_error", f"HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        err = payload["error"]
        code = str(err.get("code") or code)
        message = str(err.get("message") or message)
    return GMiniError(response.status_code, code, message)


class GMiniClient:
    """Cliente REST. Se usa como contexto asincrono o llamando a aclose()."""

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        timeout: float = 30.0,
        voice_timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
        verify: bool | str = True,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.token = token
        self.voice_timeout = voice_timeout
        self._http = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
            verify=verify,
            headers={"User-Agent": USER_AGENT},
        )

    async def __aenter__(self) -> GMiniClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------ base

    def _headers(self, auth: bool = True, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = dict(extra or {})
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _request(self, method: str, path: str, *, auth: bool = True, timeout: float | None = None,
                       **kwargs: Any) -> httpx.Response:
        headers = self._headers(auth, kwargs.pop("headers", None))
        try:
            response = await self._http.request(method, path, headers=headers,
                                                timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
                                                **kwargs)
        except httpx.TimeoutException as exc:
            raise GMiniError(0, "timeout", f"Tiempo de espera agotado ({exc.__class__.__name__})") from exc
        except httpx.TransportError as exc:
            raise GMiniError(0, "connect_failed", f"No se pudo conectar con {self.base_url}: {exc}") from exc
        if response.status_code >= 400:
            raise _error_from_response(response)
        return response

    async def _json(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = await self._request(method, path, **kwargs)
        try:
            data = response.json()
        except ValueError as exc:
            raise GMiniError(response.status_code, "bad_response", "La respuesta no es JSON") from exc
        if not isinstance(data, dict):
            raise GMiniError(response.status_code, "bad_response", "Se esperaba un objeto JSON")
        return data

    def ws_url(self) -> str:
        if self.base_url.startswith("https://"):
            return "wss://" + self.base_url[len("https://"):] + "/api/v1/ws"
        return "ws://" + self.base_url[len("http://"):] + "/api/v1/ws"

    # ------------------------------------------------------------ rutas

    async def health(self) -> dict[str, Any]:
        return await self._json("GET", "/api/v1/health", auth=False)

    async def me(self) -> dict[str, Any]:
        return await self._json("GET", "/api/v1/me")

    async def claim(self, code: str, *, device_name: str, device_type: str, platform: str) -> PairingResult:
        data = await self._json(
            "POST",
            "/api/v1/pairing/claim",
            auth=False,
            json={"code": code, "device_name": device_name, "device_type": device_type, "platform": platform},
        )
        token = str(data.get("token") or "")
        if not token:
            raise GMiniError(200, "bad_response", "El servidor no devolvió un token")
        return PairingResult(
            token=token,
            device_id=str(data.get("device_id") or ""),
            server_name=str(data.get("server_name") or ""),
            agent_name=str(data.get("agent_name") or "G-Mini"),
            scopes=tuple(str(s) for s in data.get("scopes") or ()),
        )

    async def create_pairing(self, *, label: str, device_type: str, scopes: list[str]) -> dict[str, Any]:
        """Pide un codigo de emparejamiento (requiere un token con scope admin)."""
        return await self._json("POST", "/api/v1/pairing",
                                json={"label": label, "device_type": device_type, "scopes": scopes})

    async def revoke_device(self, device_id: str) -> None:
        await self._request("DELETE", f"/api/v1/devices/{device_id}")

    async def voice_turn(self, wav: bytes, *, session_id: str | None = None) -> VoiceTurn:
        params = {"reply_format": "wav", "session_id": session_id or ""}
        data = await self._json("POST", "/api/v1/voice/turn", params=params, content=wav,
                                headers={"Content-Type": "audio/wav"}, timeout=self.voice_timeout)
        audio = None
        if data.get("audio_base64"):
            try:
                audio = base64.b64decode(str(data["audio_base64"]), validate=False)
            except (binascii.Error, ValueError) as exc:
                raise GMiniError(200, "bad_response", "Audio en base64 invalido") from exc
        return VoiceTurn(
            transcript=str(data.get("transcript") or ""),
            reply=str(data.get("reply") or ""),
            session_id=str(data.get("session_id") or ""),
            emotion=str(data.get("emotion") or ""),
            audio=audio,
            audio_mime=str(data.get("audio_mime") or ""),
        )

    async def voice_wake(self, wav: bytes) -> WakeResult:
        data = await self._json("POST", "/api/v1/voice/wake", content=wav,
                                headers={"Content-Type": "audio/wav"}, timeout=self.voice_timeout)
        return WakeResult(
            wake=bool(data.get("wake")),
            phrase=str(data.get("phrase") or ""),
            command=str(data.get("command") or ""),
            transcript=str(data.get("transcript") or ""),
        )

    async def tts(self, text: str, *, voice: str | None = None) -> bytes:
        response = await self._request("POST", "/api/v1/voice/tts",
                                       json={"text": text, "voice": voice, "format": "wav"},
                                       timeout=self.voice_timeout)
        return response.content

    async def stt(self, wav: bytes) -> str:
        data = await self._json("POST", "/api/v1/voice/stt", content=wav, headers={"Content-Type": "audio/wav"},
                                timeout=self.voice_timeout)
        return str(data.get("text") or "")

    async def chat(self, message: str, *, session_id: str | None = None) -> ChatResult:
        body: dict[str, Any] = {"message": message, "stream": False}
        if session_id:
            body["session_id"] = session_id
        data = await self._json("POST", "/api/v1/chat", json=body, timeout=self.voice_timeout)
        actions = data.get("actions") if isinstance(data.get("actions"), list) else []
        return ChatResult(reply=str(data.get("reply") or ""), session_id=str(data.get("session_id") or ""),
                          actions=actions)
