"""Cliente REST contra un transporte simulado (httpx.MockTransport)."""

from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest
from gmini_link.api import GMiniClient, GMiniError
from gmini_link.wav import decode_wav, encode_wav, tone


def make_client(handler, token: str | None = "tok") -> GMiniClient:
    return GMiniClient("192.168.1.20", token, transport=httpx.MockTransport(handler))


def test_base_url_and_ws_url() -> None:
    client = make_client(lambda r: httpx.Response(200, json={}))
    assert client.base_url == "http://192.168.1.20:8765"
    assert client.ws_url() == "ws://192.168.1.20:8765/api/v1/ws"
    secure = GMiniClient("https://gmini.example.com", "x")
    assert secure.ws_url() == "wss://gmini.example.com/api/v1/ws"
    asyncio.run(client.aclose())
    asyncio.run(secure.aclose())


def test_claim_sends_device_fields_without_auth() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        seen["path"] = request.url.path
        return httpx.Response(200, json={"token": "gm_dev_1", "device_id": "dev_1", "server_name": "tv-server",
                                         "agent_name": "G-Mini", "scopes": ["chat", "voice", "node"]})

    async def go():
        async with make_client(handler, token=None) as client:
            return await client.claim("482913", device_name="Cara USB", device_type="arduino-usb", platform="win")

    result = asyncio.run(go())
    assert result.token == "gm_dev_1" and result.scopes == ("chat", "voice", "node")
    assert seen["auth"] is None
    assert seen["path"] == "/api/v1/pairing/claim"
    assert seen["body"] == {"code": "482913", "device_name": "Cara USB", "device_type": "arduino-usb",
                            "platform": "win"}


def test_claim_invalid_code_maps_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"code": "invalid_code", "message": "Código inválido o vencido."}})

    async def go():
        async with make_client(handler, token=None) as client:
            await client.claim("000000", device_name="x", device_type="esp32", platform="p")

    with pytest.raises(GMiniError) as info:
        asyncio.run(go())
    assert info.value.status == 401 and info.value.code == "invalid_code"
    assert info.value.describe() == "Código inválido o vencido"


def test_voice_turn_sends_wav_and_decodes_audio() -> None:
    reply_wav = encode_wav(tone(440, 200))
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["Authorization"]
        seen["type"] = request.headers["Content-Type"]
        seen["params"] = dict(request.url.params)
        seen["wav"] = decode_wav(request.content)
        return httpx.Response(200, json={"transcript": "qué hora es", "reply": "Son las 6.", "session_id": "ses_9",
                                         "emotion": "happy", "audio_mime": "audio/wav",
                                         "audio_base64": base64.b64encode(reply_wav).decode()})

    async def go():
        async with make_client(handler) as client:
            return await client.voice_turn(encode_wav(tone(300, 500)), session_id="ses_8")

    turn = asyncio.run(go())
    assert seen["auth"] == "Bearer tok" and seen["type"] == "audio/wav"
    assert seen["params"] == {"reply_format": "wav", "session_id": "ses_8"}
    assert seen["wav"].rate == 16000 and seen["wav"].channels == 1
    assert turn.transcript == "qué hora es" and turn.emotion == "happy" and turn.session_id == "ses_9"
    assert turn.audio == reply_wav


def test_empty_transcript_and_busy_and_network_errors() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.url.path.endswith("/voice/turn"):
            return httpx.Response(200, json={"transcript": "", "reply": "", "session_id": "s"})
        return httpx.Response(409, json={"error": {"code": "busy", "message": "ocupado"}})

    async def go():
        async with make_client(handler) as client:
            turn = await client.voice_turn(encode_wav(b"\x00\x00" * 100))
            assert turn.transcript == "" and turn.audio is None
            with pytest.raises(GMiniError) as info:
                await client.chat("hola")
            assert info.value.describe() == "Estoy ocupada, prueba en un momento"

    asyncio.run(go())

    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    async def offline():
        async with make_client(broken) as client:
            await client.health()

    with pytest.raises(GMiniError) as info:
        asyncio.run(offline())
    assert info.value.code == "connect_failed" and info.value.status == 0


def test_wake_tts_and_chat() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/voice/wake"):
            return httpx.Response(200, json={"wake": True, "phrase": "oye g-mini", "command": "qué hora es",
                                             "transcript": "Oye G-Mini, qué hora es"})
        if path.endswith("/voice/tts"):
            assert json.loads(request.content)["text"] == "Hola"
            return httpx.Response(200, content=encode_wav(tone(500, 50)), headers={"Content-Type": "audio/wav"})
        if path.endswith("/chat"):
            body = json.loads(request.content)
            assert body == {"message": "qué hora es", "stream": False, "session_id": "s1"}
            return httpx.Response(200, json={"session_id": "s1", "reply": "Son las 6.", "actions": []})
        return httpx.Response(404, json={"error": {"code": "not_found", "message": "x"}})

    async def go():
        async with make_client(handler) as client:
            wake = await client.voice_wake(encode_wav(b"\x00\x00" * 160))
            assert wake.wake and wake.command == "qué hora es"
            wav = await client.tts("Hola")
            assert decode_wav(wav).rate == 16000
            chat = await client.chat("qué hora es", session_id="s1")
            assert chat.reply == "Son las 6."

    asyncio.run(go())
