"""Cliente de pantalla: configuracion, modelo de cara, kiosco y prueba de humo con pygame."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import pytest
from gmini_link.session import NodeError
from gmini_pi.app import PiApp, kiosk_dir
from gmini_pi.config import ConfigError, parse
from gmini_pi.face_model import FaceModel
from gmini_pi.kiosk import KioskServer

ROOT = Path(__file__).resolve().parents[1]


def test_example_config_is_valid() -> None:
    cfg = parse((ROOT / "raspberry-pi" / "config.example.toml").read_text(encoding="utf-8"))
    assert cfg.display.layout == "normal" and cfg.buttons.gpio_talk == 17
    assert cfg.kiosk.host_port == ("127.0.0.1", 8088)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('[display]\nlayout = "cubo"', "display.layout"),
        ("[display]\nfps = 500", "display.fps"),
        ('[wake]\nmode = "openwakeword"', "wake.model"),
        ("[audio]\nvolume = 150", "audio.volume"),
        ("[audio]\nvolumen = 10", "claves desconocidas"),
        ('[server]\nurl = 5', "server.url"),
        ("[extra]\na = 1", "Secciones desconocidas"),
        ('[kiosk]\nenabled = true\nlisten = "8088"', "host:puerto"),
    ],
)
def test_invalid_configs(text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        parse(text)


def test_face_model_caption_expiry_and_listeners() -> None:
    model = FaceModel(seed=1)
    seen: list[dict] = []
    model.add_listener(seen.append)
    model.set_emotion("love")
    model.set_emotion("love")  # sin cambios no notifica
    model.set_status("speaking")
    model.set_caption("Hola", 0.05)
    model.notify("Aviso", "Cuerpo", 5)
    assert [s["emotion"] for s in seen] == ["love", "love", "love", "love"]
    assert seen[-1]["notify"]["title"] == "Aviso"
    frame = model.update(0)
    assert frame is not None and model.current_caption() == "Hola"
    time.sleep(0.08)
    assert model.current_caption() == ""
    model.set_emotion("no-existe")
    assert model.emotion == "neutral"


def test_pi_surfaces_without_display() -> None:
    from gmini_pi.config import PiConfig

    app = PiApp(PiConfig(), creds=None, demo=True)

    async def go():
        assert await app.on_invoke("display.face", {"expression": "surprised", "text": "¡Hola!"}) == {"ok": True}
        assert app.model.emotion == "surprised" and app.model.caption == "¡Hola!"
        await app.on_invoke("display.face", {"expression": "thinking"})
        info = await app.on_invoke("system.info", {})
        assert info["firmware"].startswith("gmini-pi")
        uptime = await app.on_invoke("sensor.read", {"name": "uptime"})
        assert uptime["unit"] == "s"
        with pytest.raises(NodeError):
            await app.on_invoke("display.face", {"expression": "bailar"})
        with pytest.raises(NodeError):
            await app.on_invoke("relay.set", {"channel": 1, "on": True})

    asyncio.run(go())


def test_kiosk_serves_page_and_streams_state() -> None:
    async def go():
        server = KioskServer("127.0.0.1", 0, kiosk_dir())
        await server.start()
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            writer.write(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
            page = await reader.read()
            assert b"200 OK" in page and b"face.js" in page
            writer.close()

            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            writer.write(b"GET /../secreto HTTP/1.1\r\n\r\n")
            assert b"404" in await reader.read()
            writer.close()

            reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
            writer.write(b"GET /events HTTP/1.1\r\nAccept: text/event-stream\r\n\r\n")
            await asyncio.wait_for(reader.readuntil(b"retry: 2000\n\n"), timeout=3)
            first = await asyncio.wait_for(reader.readuntil(b"\n\n"), timeout=3)
            assert first.startswith(b"data: ")
            server.publish({"status": "speaking", "emotion": "happy", "caption": "Hola", "level": 0.5})
            line = await asyncio.wait_for(reader.readuntil(b"\n\n"), timeout=3)
            assert json.loads(line[len(b"data: "):].decode()) ["emotion"] == "happy"
            assert server.clients == 1
            writer.close()
        finally:
            await server.close()

    asyncio.run(go())


def test_pygame_renderer_smoke(tmp_path) -> None:
    pygame = pytest.importorskip("pygame")
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    from gmini_pi.config import DisplayConfig
    from gmini_pi.renderer import FaceRenderer

    for layout, invert in (("normal", False), ("mirror", False), ("pyramid", False), ("normal", True)):
        model = FaceModel(seed=4)
        model.set_emotion("happy")
        model.set_caption("Prueba de subtítulos con tildes: ñandú", None)
        renderer = FaceRenderer(DisplayConfig(fullscreen=False, width=480, height=320, layout=layout,
                                              supersample=2, invert=invert), model)
        for t in range(0, 1600, 40):
            renderer.render(t)
        surface = renderer.screen
        lit = sum(1 for x in range(0, 480, 4) for y in range(0, 320, 4) if surface.get_at((x, y))[1] > 120)
        if invert:
            assert surface.get_at((2, 2))[:3] == (255, 255, 255)  # el fondo negro pasa a blanco
        else:
            assert lit > 50, layout
        pygame.image.save(surface, str(tmp_path / f"face-{layout}-{invert}.png"))
        renderer.close()
