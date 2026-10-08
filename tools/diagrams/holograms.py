"""Esquemas de las tecnicas de "holograma" (vistas laterales con rayos de luz).

Ninguna es un holograma en sentido estricto: son ilusiones de imagen flotante
(reflejos, proyeccion sobre medios casi invisibles o persistencia de la vision).
"""

from __future__ import annotations

import math
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

from face_sheet import draw_screen
from gmini_link.face import EyesEngine, FaceFrame, settle
from svgkit import BRAND, DANGER, INK, LINE, MUTED, Svg

W, H = 1000, 600
RAY = "#0ea5c6"
GLASS = "#cfeef7"
GLASS_EDGE = "#7cc4d6"
DARK = "#16232d"
WOOD = "#d9c7a7"
WOOD_EDGE = "#a8916b"


def _frame(emotion: str = "happy") -> FaceFrame:
    return settle(EyesEngine(seed=21), emotion, ms=2200)


def _label(svg: Svg, x: float, y: float, tx: float, ty: float, text: str, sub: str = "") -> None:
    svg.line(x, y, tx, ty, stroke=MUTED, sw=1)
    svg.circle(x, y, 2.6, fill=INK)
    anchor = "start" if tx >= x else "end"
    off = 6 if tx >= x else -6
    svg.text(tx + off, ty + 4, text, size=13, weight=700, fill=INK, anchor=anchor)
    if sub:
        svg.text(tx + off, ty + 21, sub, size=11, fill=MUTED, anchor=anchor)


def _ray(svg: Svg, points: list[tuple[float, float]], *, arrow: bool = True, color: str = RAY) -> None:
    for (x1, y1), (x2, y2) in pairwise(points):
        last = (x2, y2) == points[-1]
        if last and arrow:
            svg.arrow(x1, y1, x2, y2, color=color, sw=1.6, dash="6 4", ident="ray-arrow")
        else:
            svg.line(x1, y1, x2, y2, stroke=color, sw=1.6, dash="6 4")


def _eye(svg: Svg, x: float, y: float, facing_left: bool = True) -> None:
    """Ojo del observador (icono simple)."""
    d = -1 if facing_left else 1
    svg.ellipse(x, y, 20, 12, fill="#ffffff", stroke=INK, sw=1.6)
    svg.circle(x + d * 6, y, 6.5, fill=BRAND)
    svg.circle(x + d * 6, y, 2.6, fill=INK)
    svg.text(x, y + 32, "observador", size=11, fill=MUTED, anchor="middle")


def _ghost(svg: Svg, x: float, y: float, scale: float, ident: str, emotion: str = "happy") -> None:
    """Imagen virtual: la cara flotando, semitransparente y con borde punteado."""
    with svg.group(opacity="0.55"):
        draw_screen(svg, _frame(emotion), x, y, scale, bezel=False, clip_id=ident,
                    palette={0: "#e8fbff", 1: "#3fe0ff", 2: "#ff4d6d", 3: "#bdeff9", 4: "#3fe0ff"})
    svg.rect(x - 4, y - 4, 128 * scale + 8, 64 * scale + 8, rx=10, stroke=RAY, sw=1.2, dash="4 4")


def _screen(svg: Svg, x: float, y: float, w: float, h: float, *, emotion: str = "happy", angle: float = 0.0,
            ident: str = "") -> None:
    """Pantalla (telefono, tablet o monitor) vista de frente, con la cara."""
    transform = f"rotate({angle:.1f} {x + w / 2:.1f} {y + h / 2:.1f})" if angle else ""
    with svg.group(transform):
        svg.rect(x - 6, y - 6, w + 12, h + 12, rx=10, fill="#1b2631")
        scale = min(w / 128, h / 64)
        draw_screen(svg, _frame(emotion), x + (w - 128 * scale) / 2, y + (h - 64 * scale) / 2, scale,
                    bezel=False, clip_id=ident or f"scr-{int(x)}-{int(y)}")


def _base(svg: Svg, title: str, subtitle: str) -> None:
    svg.heading(title, subtitle)


def _finish(svg: Svg, path: Path, note: str) -> bool:
    svg.footer(note)
    return svg.save(path)


# ---------------------------------------------------------------- 1. piramide


def pyramid(path: Path) -> bool:
    svg = Svg(W, H, title="Pirámide de Pepper", desc="Corte lateral y vista superior de la pirámide de 4 caras.")
    _base(svg, "Pirámide de Pepper (4 caras)",
          "Cuatro trapecios a 45° sobre una pantalla horizontal: cada cara refleja una vista y la imagen flota al centro")
    # Corte lateral
    gx, gy = 70, 430
    svg.text(gx, 120, "Corte lateral", size=13, weight=700, fill=INK)
    svg.rect(gx, gy, 420, 26, rx=6, fill=DARK)
    svg.text(gx + 210, gy + 46, "pantalla horizontal (teléfono, tablet o monitor)", size=11, fill=MUTED,
             anchor="middle")
    cx = gx + 210
    a, b, hgt = 30, 300, 135
    left = [(cx - a / 2, gy), (cx - b / 2, gy - hgt)]
    right = [(cx + a / 2, gy), (cx + b / 2, gy - hgt)]
    svg.polyline(left, stroke=GLASS_EDGE, sw=4)
    svg.polyline(right, stroke=GLASS_EDGE, sw=4)
    svg.rect(cx - b / 2, gy - 6, (b - a) / 2, 6, fill="#3fe0ff", opacity=0.8)
    # El rayo sube desde la pantalla, toca la cara izquierda y sale hacia el observador.
    hit_x = cx - a / 2 - 75 * ((b - a) / 2) / hgt
    _ray(svg, [(hit_x, gy - 6), (hit_x, gy - 75), (gx + 22, gy - 75)])
    _ghost(svg, cx - 48, gy - 128, 0.75, "pyr-ghost")
    _eye(svg, gx - 20 + 0, gy - 75, facing_left=False)
    _label(svg, cx + b / 2 - 40, gy - 95, cx + 230, gy - 210, "Lámina a 45°", "PET, acetato o acrílico")
    _label(svg, cx, gy - 95, cx + 230, gy - 150, "Imagen flotante", "altura máx. = (b - a) / 2")
    # Vista superior
    tx, ty, s = 640, 150, 290
    svg.text(tx, 120, "Vista superior: lo que muestra la pantalla", size=13, weight=700, fill=INK)
    svg.rect(tx, ty, s, s, rx=10, fill=DARK)
    c = (tx + s / 2, ty + s / 2)
    small = 30
    svg.polygon([(c[0] - small / 2, c[1] - small / 2), (c[0] + small / 2, c[1] - small / 2),
                 (c[0] + small / 2, c[1] + small / 2), (c[0] - small / 2, c[1] + small / 2)], stroke=GLASS_EDGE, sw=2)
    for (x0, y0), (x1, y1) in (((tx, ty), (c[0] - small / 2, c[1] - small / 2)),
                               ((tx + s, ty), (c[0] + small / 2, c[1] - small / 2)),
                               ((tx + s, ty + s), (c[0] + small / 2, c[1] + small / 2)),
                               ((tx, ty + s), (c[0] - small / 2, c[1] + small / 2))):
        svg.line(x0, y0, x1, y1, stroke=GLASS_EDGE, sw=1.5, dash="5 4")
    for angle, (dx, dy) in ((0, (0, -1)), (180, (0, 1)), (90, (-1, 0)), (270, (1, 0))):
        px, py = c[0] + dx * 88 - 48, c[1] + dy * 88 - 24
        with svg.group(f"rotate({-angle} {px + 48:.1f} {py + 24:.1f})"):
            draw_screen(svg, _frame(), px, py, 0.75, bezel=False, clip_id=f"pyr-top-{angle}")
    svg.text(tx + s / 2, ty + s + 26, "Cuatro vistas con la parte de arriba hacia afuera",
             size=11.5, fill=MUTED, anchor="middle")
    svg.text(tx + s / 2, ty + s + 44, "(gmini_pi --layout pyramid o kiosk/?layout=pyramid)", size=11, fill=MUTED,
             anchor="middle")
    return _finish(svg, path, "Plantillas de corte en hardware/templates/ (SVG y DXF por tamaño de pantalla)")


# ---------------------------------------------------------------- 2. caja de Pepper


def pepper_box(path: Path) -> bool:
    svg = Svg(W, H, title="Caja de Pepper", desc="Placa unica a 45 grados dentro de una caja oscura.")
    _base(svg, "Caja de Pepper (una placa a 45°)",
          "La técnica de los teatros del siglo XIX: la pantalla queda oculta y su reflejo aparece dentro de la caja")
    bx, by, bw, bh = 260, 150, 420, 330
    svg.rect(bx, by, bw, bh, rx=8, fill="#2a3640", stroke="#11181e", sw=2)
    svg.rect(bx + 10, by + 10, bw - 20, bh - 20, rx=4, fill="#0c1318")
    svg.rect(bx + 30, by + bh - 34, bw - 60, 16, rx=4, fill=DARK)
    svg.rect(bx + 50, by + bh - 40, bw - 100, 6, fill="#3fe0ff", opacity=0.85)
    svg.text(bx + bw / 2, by + bh + 24, "pantalla boca arriba en el piso de la caja", size=11, fill=MUTED,
             anchor="middle")
    # Placa "\": la luz que sube desde la pantalla sale hacia la izquierda (observador).
    svg.line(bx + 40, by + 40, bx + bw - 40, by + bh - 50, stroke=GLASS_EDGE, sw=5)
    _ghost(svg, bx + bw - 200, by + 60, 0.95, "box-ghost")
    hit_y = by + 40 + (bh - 90) * (150 - 40) / (bw - 80)
    _ray(svg, [(bx + 150, by + bh - 42), (bx + 150, hit_y), (bx - 70, hit_y)])
    _eye(svg, bx - 110, hit_y, facing_left=False)
    _label(svg, bx + 300, by + 40 + (bh - 90) * 260 / (bw - 80), bx + bw + 40, by + 250, "Placa a 45°",
           "vidrio fino, acrílico o PET")
    _label(svg, bx + bw - 110, by + 100, bx + bw + 40, by + 100, "Imagen virtual", "detrás de la placa")
    _label(svg, bx + bw - 24, by + 180, bx + bw + 40, by + 175, "Interior negro mate", "más contraste")
    svg.text(bx + bw + 40, by + 330, "Placa: ancho de pantalla x (profundidad x 1,41)", size=11.5, fill=INK)
    return _finish(svg, path, "Con gmini_pi --layout mirror la imagen sale espejada para que el reflejo se lea bien")


# ---------------------------------------------------------------- 3. pantalla de niebla


def fog_screen(path: Path) -> bool:
    svg = Svg(W, H, title="Pantalla de niebla", desc="Cortina laminar de niebla ultrasonica con proyector trasero.")
    _base(svg, "Pantalla de niebla",
          "Un nebulizador ultrasónico llena un depósito; ventiladores y una rejilla de pajillas forman una cortina fina")
    tx, ty = 330, 420
    svg.rect(tx, ty, 320, 70, rx=8, fill="#e7eef2", stroke=LINE, sw=1.5)
    svg.rect(tx + 10, ty + 40, 300, 22, rx=4, fill="#9fd9ef", opacity=0.8)
    svg.text(tx + 160, ty + 30, "depósito con nebulizador", size=11.5, fill=INK, anchor="middle")
    for i in range(10):
        svg.rect(tx + 20 + i * 29, ty - 26, 10, 26, fill="#ffffff", stroke=LINE, sw=1)
    svg.text(tx + 330, ty - 8, "rejilla de pajillas (flujo laminar)", size=11, fill=MUTED)
    svg.rect(tx + 220, ty + 70, 60, 26, rx=4, fill="#b8c4cc")
    svg.text(tx + 250, ty + 112, "ventilador 12 V", size=11, fill=MUTED, anchor="middle")
    svg.define('<linearGradient id="fog" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#e9f6fb" '
               'stop-opacity="0.95"/><stop offset="1" stop-color="#e9f6fb" stop-opacity="0"/></linearGradient>')
    svg.rect(tx + 15, 150, 290, ty - 176, fill="url(#fog)")
    _ghost(svg, tx + 64, 220, 1.5, "fog-ghost")
    px, py = 820, 300
    svg.rect(px - 40, py - 26, 90, 52, rx=8, fill="#2f3b44")
    svg.circle(px - 40, py, 14, fill="#9fe7f7")
    svg.text(px + 5, py + 48, "proyector", size=11.5, fill=MUTED, anchor="middle")
    _ray(svg, [(px - 54, py), (tx + 300, 270)])
    _ray(svg, [(px - 54, py), (tx + 300, 330)])
    _eye(svg, 160, 300, facing_left=False)
    svg.callout(40, 470, 250, ["Nunca acerques agua o niebla a", "la fuente de 220 V ni al proyector.",
                               "Usa agua destilada (sin minerales)."], title="Agua y electricidad", tone="danger",
                size=11)
    return _finish(svg, path, "Proyección trasera: el observador ve la imagen en la niebla con el proyector al otro lado")


# ---------------------------------------------------------------- 4. cortina de humo


def smoke_curtain(path: Path) -> bool:
    svg = Svg(W, H, title="Cortina de humo y viento", desc="Humo de maquina de niebla guiado por un tunel de viento.")
    _base(svg, "Cortina de humo y viento",
          "Una máquina de humo alimenta un túnel con ventiladores; la lámina de humo recibe la proyección desde abajo")
    svg.rect(150, 440, 700, 60, rx=10, fill="#e7eef2", stroke=LINE, sw=1.5)
    for i in range(6):
        cx = 220 + i * 110
        svg.circle(cx, 470, 22, fill="#ffffff", stroke=LINE, sw=1.2)
        svg.line(cx - 14, 456, cx + 14, 484, stroke=MUTED, sw=1.2)
        svg.line(cx + 14, 456, cx - 14, 484, stroke=MUTED, sw=1.2)
    svg.text(500, 525, "túnel de viento: ventiladores de PC + difusor de panal", size=11.5, fill=MUTED, anchor="middle")
    svg.rect(40, 452, 90, 40, rx=6, fill="#3d4a54")
    svg.text(85, 512, "máquina de humo", size=11, fill=MUTED, anchor="middle")
    svg.line(130, 472, 150, 472, stroke="#9aa8b2", sw=6)
    svg.define('<linearGradient id="smoke" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#dfe7ec" '
               'stop-opacity="0.95"/><stop offset="1" stop-color="#dfe7ec" stop-opacity="0"/></linearGradient>')
    svg.rect(170, 150, 660, 290, fill="url(#smoke)")
    _ghost(svg, 380, 210, 1.9, "smoke-ghost", "surprised")
    _ray(svg, [(500, 560), (470, 340)])
    _ray(svg, [(500, 560), (560, 340)])
    svg.rect(470, 545, 60, 30, rx=6, fill="#2f3b44")
    svg.callout(640, 120, 330, ["Ventila el ambiente: el humo de glicol", "irrita y activa detectores de humo.",
                                "Hielo seco: nunca en espacios cerrados."], title="Humo y CO2", tone="warn", size=11)
    return _finish(svg, path, "Funciona mejor a oscuras y sin corrientes de aire en la sala")


# ---------------------------------------------------------------- 5. LCD transparente


def transparent_lcd(path: Path) -> bool:
    svg = Svg(W, H, title="LCD transparente", desc="Vista explotada de un LCD sin retroiluminacion delante de una caja de luz.")
    _base(svg, "LCD transparente",
          "Un LCD sin luz trasera ni difusor deja ver lo que hay detrás: los píxeles oscuros \"flotan\" sobre el fondo")
    layers = [
        ("Polarizador", "frontal", "#9fb3c0", 0.9),
        ("Vidrio LCD", "(píxeles)", "#cfeef7", 0.95),
        ("Polarizador", "trasero", "#9fb3c0", 0.9),
        ("Difusor", "(se retira)", "#f1f3f5", 0.6),
        ("Retroiluminación", "(se retira)", "#fff3c4", 0.6),
    ]
    x0, y0 = 330, 130
    for i, (name, sub, color, op) in enumerate(layers):
        x = x0 + i * 95
        removed = "retira" in sub
        svg.polygon([(x, y0 + 30), (x + 34, y0), (x + 34, y0 + 280), (x, y0 + 310)], fill=color, opacity=op,
                    stroke="#7a8a95", sw=1.2, dash="5 4" if removed else None)
        svg.text(x + 17, y0 + 336, name, size=11, fill=DANGER if removed else INK, anchor="middle", weight=600)
        svg.text(x + 17, y0 + 352, sub, size=10.5, fill=DANGER if removed else MUTED, anchor="middle")
    svg.rect(x0 + 490, y0 + 20, 110, 270, rx=10, fill="#fffbe6", stroke="#e2c86a", sw=1.5)
    svg.text(x0 + 545, y0 + 150, "caja de luz", size=12, fill="#8a6d10", anchor="middle")
    svg.text(x0 + 545, y0 + 168, "o tira LED", size=11, fill="#8a6d10", anchor="middle")
    svg.text(x0 + 545, y0 + 184, "+ difusor", size=11, fill="#8a6d10", anchor="middle")
    _eye(svg, 200, y0 + 150, facing_left=False)
    svg.callout(40, 410, 260, ["Bordes de vidrio filosos: guantes", "anticorte y lentes.",
                               "Alcohol isopropílico o calor suave para", "despegar; nunca acetona en el vidrio.",
                               "Ventila: los adhesivos y solventes", "desprenden vapores."],
                title="Seguridad al desarmar", tone="danger", size=11)
    return _finish(svg, path, "Los polarizadores se quedan: sin ellos el LCD no muestra imagen")


# ---------------------------------------------------------------- 6. ventilador POV


def pov_fan(path: Path) -> bool:
    svg = Svg(W, H, title="Ventilador holográfico POV", desc="Aspas con LEDs que giran y dibujan la imagen por persistencia.")
    _base(svg, "Ventilador holográfico (POV)",
          "Aspas con tiras de LEDs giran a ~700 RPM; el controlador enciende cada LED en el momento justo")
    cx, cy, r = 420, 330, 190
    svg.circle(cx, cy, r + 18, stroke="#9aa8b2", sw=2, dash="3 6")
    for k in range(4):
        ang = math.radians(k * 90 + 20)
        x2, y2 = cx + r * math.cos(ang), cy + r * math.sin(ang)
        svg.line(cx, cy, x2, y2, stroke="#2f3b44", sw=12)
        for j in range(1, 9):
            px, py = cx + r * j / 9 * math.cos(ang), cy + r * j / 9 * math.sin(ang)
            svg.circle(px, py, 3.2, fill="#3fe0ff")
    svg.circle(cx, cy, 26, fill="#1b2631")
    _ghost(svg, cx - 96, cy - 48, 1.5, "pov-ghost", "love")
    svg.callout(680, 160, 290, ["Las aspas giran rápido: usa la carcasa", "o cúpula protectora y fíjalo firme",
                                "a la pared o a un soporte pesado."], title="Aspas en movimiento", tone="danger",
                size=11)
    blade = math.radians(290)
    _label(svg, cx + 0.72 * r * math.cos(blade), cy + 0.72 * r * math.sin(blade), 700, 330,
           "Tiras de LEDs en las aspas", "controlador con WiFi propio")
    _label(svg, cx, cy, 700, 400, "Eje y sensor de posición", "sincroniza cada vuelta")
    return _finish(svg, path, "Se compra hecho (20-50 cm); G-Mini Home le envía caras como video o GIF desde su app")


# ---------------------------------------------------------------- 7. volumetrico


def volumetric(path: Path) -> bool:
    svg = Svg(W, H, title="Pantalla volumétrica de barrido",
              desc="Superficie giratoria iluminada por un proyector rapido.")
    _base(svg, "Volumétrica de barrido (espejo o pantalla giratoria)",
          "Una superficie gira a alta velocidad y un proyector rápido dibuja en cada ángulo una rebanada de la imagen")
    cx, cy = 430, 290
    svg.ellipse(cx, cy + 150, 170, 26, fill="#e7eef2", stroke=LINE, sw=1.5)
    svg.rect(cx - 6, cy - 20, 12, 170, fill="#9aa8b2")
    svg.polygon([(cx - 110, cy - 130), (cx + 110, cy - 70), (cx + 110, cy + 90), (cx - 110, cy + 30)],
                fill=GLASS, opacity=0.8, stroke=GLASS_EDGE, sw=2)
    svg.path(f"M{cx - 150},{cy - 170} A160,40 0 0 1 {cx + 150},{cy - 170}", stroke=MUTED, sw=1.4, dash="5 4",
             extra='marker-end="url(#ray-arrow-m)"')
    svg.define('<marker id="ray-arrow-m" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
               'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#5b6b7b"/></marker>')
    svg.rect(cx - 30, cy + 190, 60, 34, rx=6, fill="#2f3b44")
    svg.text(cx, cy + 244, "proyector DLP de alta frecuencia", size=11, fill=MUTED, anchor="middle")
    _ray(svg, [(cx, cy + 190), (cx - 60, cy + 40)])
    _ray(svg, [(cx, cy + 190), (cx + 60, cy + 60)])
    svg.text(cx + 200, cy - 150, "giro de 600-1200 RPM", size=12, fill=INK)
    svg.callout(660, 300, 300, ["Prototipo de investigación: exige", "equilibrado fino, eje robusto y",
                                "una cubierta transparente cerrada."], title="Proyecto avanzado", tone="warn",
                size=11)
    return _finish(svg, path, "Única técnica de la lista con volumen real: se ve en 3D desde cualquier lado")


# ---------------------------------------------------------------- 8. tul / film holografico


def holo_gauze(path: Path) -> bool:
    svg = Svg(W, H, title="Retroproyección en film o tul holográfico",
              desc="Lamina casi transparente que recibe la proyeccion en una caja oscura.")
    _base(svg, "Film holográfico o tul (holo-gauze)",
          "Una lámina casi invisible capta la luz del proyector; con fondo negro la imagen parece suspendida")
    svg.rect(120, 140, 760, 360, rx=10, fill="#0c1318")
    svg.rect(430, 160, 10, 320, fill="#bfe9f5", opacity=0.55)
    svg.text(435, 520, "film o tul tensado", size=11.5, fill=MUTED, anchor="middle")
    _ghost(svg, 300, 260, 1.4, "gauze-ghost", "neutral")
    svg.rect(700, 330, 90, 50, rx=8, fill="#2f3b44")
    svg.circle(700, 355, 14, fill="#9fe7f7")
    _ray(svg, [(686, 355), (446, 300)])
    _ray(svg, [(686, 355), (446, 400)])
    svg.text(745, 400, "proyector (de frente o trasero)", size=11, fill=MUTED, anchor="middle")
    _eye(svg, 70, 330, facing_left=False)
    svg.text(140, 560, "Fondo y paredes en negro mate; ilumina al presentador por los lados para que la luz no toque el film.",
             size=11.5, fill=INK)
    return _finish(svg, path, "El efecto de escenario de los conciertos con 'hologramas' (tul o lámina tipo Musion)")


# ---------------------------------------------------------------- 9. imagen aerea


def aerial(path: Path) -> bool:
    svg = Svg(W, H, title="Imagen aérea con retrorreflector",
              desc="Divisor de haz y lamina retrorreflectante forman una imagen real en el aire.")
    _base(svg, "Imagen aérea (retrorreflector + divisor de haz)",
          "La luz rebota en una lámina retrorreflectante, vuelve por el divisor y se enfoca en el aire: imagen real")
    # Pantalla boca arriba bajo un divisor "/": la luz va al retrorreflector de la derecha,
    # vuelve por el mismo camino, atraviesa el divisor y se enfoca a la izquierda.
    svg.rect(380, 470, 150, 16, rx=4, fill=DARK)
    svg.rect(395, 466, 120, 5, fill="#3fe0ff", opacity=0.9)
    svg.text(455, 510, "pantalla boca arriba", size=11.5, fill=MUTED, anchor="middle")
    svg.line(330, 420, 560, 190, stroke=GLASS_EDGE, sw=5)
    svg.text(570, 182, "divisor de haz (vidrio 50/50)", size=11.5, fill=INK)
    svg.rect(690, 190, 12, 240, fill="#d6d9dc", stroke="#9aa1a7", sw=1)
    svg.text(712, 320, "lámina", size=11.5, fill=INK)
    svg.text(712, 336, "retrorreflectante", size=11.5, fill=INK)
    _ray(svg, [(445, 466), (445, 305)], arrow=False)
    _ray(svg, [(445, 305), (688, 305)])
    _ray(svg, [(688, 312), (452, 312), (300, 312)])
    _ghost(svg, 170, 276, 0.9, "aer-ghost")
    svg.text(228, 380, "imagen real en el aire", size=12, fill=BRAND, anchor="middle")
    _eye(svg, 70, 312, facing_left=False)
    return _finish(svg, path, "Más tenue que Pepper pero se puede 'tocar': la imagen queda delante del vidrio")


# ---------------------------------------------------------------- 10. mirascopio


def mirascope(path: Path) -> bool:
    svg = Svg(W, H, title="Mirascopio con pantalla",
              desc="Dos espejos parabolicos enfrentados forman una imagen real en la abertura superior.")
    _base(svg, "Mirascopio con pantalla redonda",
          "Dos espejos parabólicos enfrentados: lo que está en el fondo aparece flotando sobre la abertura")
    # Corte: espejo superior (con agujero) y espejo inferior, unidos por el borde.
    cx, top, mid, bottom = 470, 230, 340, 450
    svg.path(f"M{cx - 230},{mid} Q{cx},{2 * top - mid} {cx + 230},{mid}", stroke="#7a8a95", sw=6)
    svg.path(f"M{cx - 230},{mid} Q{cx},{2 * bottom - mid} {cx + 230},{mid}", stroke="#7a8a95", sw=6)
    svg.rect(cx - 36, top - 6, 72, 14, fill="#ffffff")
    svg.rect(cx - 24, bottom - 26, 48, 12, rx=3, fill=DARK)
    svg.rect(cx - 18, bottom - 30, 36, 5, fill="#3fe0ff", opacity=0.9)
    svg.text(cx + 120, bottom + 30, "pantalla redonda GC9A01 en el fondo", size=11.5, fill=INK)

    def curve_y(x: float, apex: float) -> float:
        t = (x - cx + 230) / 460
        return mid + 2 * t * (1 - t) * (2 * apex - 2 * mid)

    for side in (-1, 1):
        rx = cx + side * 140
        _ray(svg, [(cx, bottom - 30), (rx, curve_y(rx, top)), (rx, curve_y(rx, bottom)), (cx, top - 34)],
             arrow=side == -1)
    _ghost(svg, cx - 40, top - 78, 0.62, "mira-ghost")
    svg.text(cx + 70, top - 50, "imagen real sobre la abertura", size=12, fill=BRAND)
    _eye(svg, cx + 330, top - 46)
    return _finish(svg, path, "Imagen pequeña y brillante; conviene una pantalla con mucho brillo y fondo negro")


def targets() -> dict[str, Callable[[Path], bool]]:
    base = "docs/holograms/img/"
    return {
        base + "pyramid.svg": pyramid,
        base + "pepper-box.svg": pepper_box,
        base + "fog-screen.svg": fog_screen,
        base + "smoke-curtain.svg": smoke_curtain,
        base + "transparent-lcd.svg": transparent_lcd,
        base + "pov-fan.svg": pov_fan,
        base + "volumetric.svg": volumetric,
        base + "holo-gauze.svg": holo_gauze,
        base + "aerial-image.svg": aerial,
        base + "mirascope.svg": mirascope,
    }
