"""Arquitectura del sistema y la imagen principal del README."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from face_sheet import draw_screen
from gmini_link.face import EyesEngine, settle
from svgkit import BRAND, BRAND_SOFT, FONT_MONO, INK, LINE, MUTED, Svg


def _box(svg: Svg, x: float, y: float, w: float, h: float, title: str, lines: list[str], *, accent: str = BRAND,
         fill: str = "#ffffff", tag: str = "", link: str = "") -> None:
    svg.rect(x + 3, y + 4, w, h, rx=12, fill="#000000", opacity=0.06)
    svg.rect(x, y, w, h, rx=12, fill=fill, stroke=LINE, sw=1.2)
    svg.rect(x, y, 5, h, rx=2.5, fill=accent)
    svg.text(x + 18, y + 27, title, size=14.5, weight=700, fill=INK)
    if tag:
        svg.badge(x + w - 14 - (12 + len(tag) * 6.2), y + 27, tag, size=10.5)
    for i, line in enumerate(lines):
        svg.text(x + 18, y + 50 + i * 18, line, size=11.5, fill=MUTED)
    if link:
        svg.text(x + 18, y + h - 14, link, size=10.5, fill=accent, family=FONT_MONO, weight=600)


def build_architecture(path: Path) -> bool:
    w, h = 1200, 800
    svg = Svg(w, h, title="Arquitectura de G-Mini Home",
              desc="Dispositivos de G-Mini Home conectados al nucleo de G-Mini por la Remote API v1.")
    svg.heading("Cómo se conecta todo",
                "La carita escucha y muestra; el trabajo real corre en el núcleo de G-Mini (PC o servidor 24/7)")

    # Nucleo
    cx, cy, cw, ch = 430, 120, 340, 250
    svg.rect(cx + 3, cy + 4, cw, ch, rx=16, fill="#000000", opacity=0.07)
    svg.rect(cx, cy, cw, ch, rx=16, fill="#0f2533")
    svg.text(cx + 24, cy + 36, "Núcleo G-Mini", size=18, weight=700, fill="#ffffff")
    svg.text(cx + 24, cy + 58, "Escritorio (Windows) o servidor 24/7 (Linux)", size=11.5, fill="#a9c2cf")
    items = ["Agente, memoria, tareas y conectores", "STT (Whisper) y TTS (voces neurales)",
             "Remote API v1 en el puerto 8765", "Tokens por dispositivo y aprobaciones"]
    for i, item in enumerate(items):
        svg.circle(cx + 30, cy + 90 + i * 26, 3, fill="#3fe0ff")
        svg.text(cx + 42, cy + 94 + i * 26, item, size=12.5, fill="#e6fbff")
    svg.rect(cx + 24, cy + ch - 56, cw - 48, 34, rx=8, fill="#16384a")
    svg.text(cx + cw / 2, cy + ch - 34, "REST  /api/v1/*      WebSocket  /api/v1/ws", size=11.5, fill="#3fe0ff",
             anchor="middle", family=FONT_MONO)

    # Dispositivos
    devices = [
        (40, 110, "Cara USB", ["Arduino Uno/Nano + OLED", "Protocolo serie a 115200", "Voz con el micrófono de la PC"],
         "#2563eb", "variante 1", "USB serie + puente Python"),
        (40, 290, "Compañero WiFi", ["ESP32-S3 + OLED o TFT", "Micrófono I2S y parlante", "Pulsar para hablar"],
         "#7c3aed", "variante 2", "WiFi: REST + WebSocket"),
        (40, 470, "Parlante con LEDs", ["ESP32 sin pantalla", "La cara es el anillo LED", "'Oye G-Mini' opcional"],
         "#059669", "variante 3", "WiFi: voice/wake + turn"),
        (860, 110, "Raspberry Pi", ["Cara a pantalla completa", "Botón GPIO o teclado", "Servicio systemd"],
         "#c2410c", "variante 4", "LAN: REST + WebSocket"),
        (860, 290, "PC vieja o tablet", ["El mismo cliente de la Pi", "o la página de kiosco", "en el navegador"],
         "#a61e4d", "variante 5", "estado por SSE"),
        (860, 470, "Hologramas", ["Pirámide o caja de Pepper", "Niebla, LCD transparente,", "ventilador POV..."],
         "#0891b2", "pantallas", "usa las caras de 4 y 5"),
    ]
    for x, y, title, lines, accent, tag, link_text in devices:
        _box(svg, x, y, 300, 150, title, lines, accent=accent, tag=tag, link=link_text)

    def link(x1: float, y1: float, x2: float, y2: float, dashed: bool = False) -> None:
        svg.arrow(x1, y1, x2, y2, color="#5b6b7b", sw=1.8, dash="6 5" if dashed else None, both=True,
                  ident="arch-arrow")

    link(344, 185, cx - 4, 170)
    link(344, 365, cx - 4, 250)
    link(344, 545, cx - 4, 330)
    link(856, 185, cx + cw + 4, 170)
    link(856, 365, cx + cw + 4, 280, dashed=True)
    link(1010, 466, 1010, 444, dashed=True)

    # Flujo de un turno de voz
    fy = 700
    svg.text(40, fy - 22, "Un turno de voz", size=14, weight=700, fill=INK)
    steps = ["Botón o 'Oye G-Mini'", "Graba WAV 16 kHz", "POST /voice/turn", "STT -> agente -> TTS",
             "JSON + audio base64", "Habla y anima la boca"]
    sx = 40.0
    for i, step in enumerate(steps):
        bw = 166
        svg.rect(sx, fy - 4, bw, 40, rx=20, fill=BRAND_SOFT if i % 2 == 0 else "#ffffff", stroke=LINE, sw=1)
        svg.text(sx + bw / 2, fy + 20, step, size=11.5, fill=INK, anchor="middle", weight=600)
        if i < len(steps) - 1:
            svg.arrow(sx + bw + 2, fy + 16, sx + bw + 18, fy + 16, color=BRAND, sw=1.8, ident="flow-arrow")
        sx += bw + 20
    svg.footer("Generado por tools/diagrams/architecture.py  |  contrato: docs/protocol/remote-api-v1.md del repo principal")
    return svg.save(path)


def build_hero(path: Path) -> bool:
    w, h = 1280, 520
    svg = Svg(w, h, background=None, title="G-Mini Home",
              desc="Compañero físico de G-Mini Agent: una carita OLED que escucha y habla.")
    svg.define('<linearGradient id="hero-bg" x1="0" y1="0" x2="1" y2="1">'
               '<stop offset="0" stop-color="#071821"/><stop offset="1" stop-color="#0f2f3d"/></linearGradient>')
    svg.define('<radialGradient id="hero-glow" cx="0.5" cy="0.5" r="0.5">'
               '<stop offset="0" stop-color="#3fe0ff" stop-opacity="0.28"/>'
               '<stop offset="1" stop-color="#3fe0ff" stop-opacity="0"/></radialGradient>')
    svg.rect(0, 0, w, h, rx=24, fill="url(#hero-bg)")
    svg.circle(300, 270, 250, fill="url(#hero-glow)")

    # Cuerpo del companero (vista frontal de la carcasa OLED)
    bx, by, bw, bh = 120, 110, 360, 300
    svg.rect(bx + 6, by + 14, bw, bh, rx=64, fill="#000000", opacity=0.35)
    svg.rect(bx, by, bw, bh, rx=64, fill="#e9eef1")
    svg.rect(bx + 10, by + 10, bw - 20, bh - 20, rx=56, fill="#f7f9fa")
    svg.line(bx + 120, by - 26, bx + 104, by + 2, stroke="#c9d3da", sw=8)
    svg.circle(bx + 120, by - 30, 11, fill="#3fe0ff")
    frame = settle(EyesEngine(seed=11), "happy", ms=2200)
    draw_screen(svg, frame, bx + 52, by + 62, 2.0, glow=True, clip_id="hero-screen")
    svg.circle(bx + 140, by + bh - 52, 15, fill="#0f2533")
    svg.circle(bx + 140, by + bh - 52, 9, fill="#3fe0ff", opacity=0.9)
    svg.circle(bx + 220, by + bh - 52, 10, fill="#c9d3da")
    for i in range(5):
        svg.circle(bx + bw - 70 + (i % 3) * 12, by + bh - 60 + (i // 3) * 12, 3, fill="#b8c4cc")

    tx = 600
    svg.text(tx, 190, "G-Mini Home", size=58, weight=800, fill="#ffffff")
    svg.text(tx, 236, "El compañero físico de G-Mini Agent", size=24, weight=600, fill="#3fe0ff")
    lines = ["Una carita que te escucha y te responde mientras el trabajo",
             "pesado corre en tu PC o en tu servidor 24/7."]
    for i, line in enumerate(lines):
        svg.text(tx, 282 + i * 28, line, size=18, fill="#c4d6de")
    chips = ["Arduino USB", "ESP32 WiFi", "Parlante LED", "Raspberry Pi", "Kiosco", "Hologramas"]
    cx = float(tx)
    for chip in chips:
        width = 20 + len(chip) * 7.6
        svg.rect(cx, 356, width, 34, rx=17, fill="#16384a", stroke="#2b6178", sw=1)
        svg.text(cx + width / 2, 378, chip, size=13, fill="#e6fbff", anchor="middle", weight=600)
        cx += width + 10
    svg.text(tx, 440, "Firmware, puente, cliente de Pi, carcasas imprimibles y guías paso a paso.",
             size=14.5, fill="#7aa3ad")
    _ = MUTED
    return svg.save(path)


def targets() -> dict[str, Callable[[Path], bool]]:
    return {"docs/img/architecture.svg": build_architecture, "docs/img/hero.svg": build_hero}


_ = BRAND
