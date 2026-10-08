"""Hojas de referencia de la cara: emociones y estados, dibujados con el motor real.

Usa gmini_link.face (el mismo motor que el cliente de Raspberry Pi y que el
firmware en C++), asi que la imagen de la documentacion es exactamente lo que
se ve en la pantalla.
"""

from __future__ import annotations

from pathlib import Path

from gmini_link.face import (
    COLOR_ACCENT,
    COLOR_BACKGROUND,
    COLOR_EYE,
    COLOR_GLOW,
    EMOTIONS,
    REF_H,
    REF_W,
    EyesEngine,
    FaceFrame,
    FaceLayout,
    draw_face,
    settle,
)
from svgkit import FONT_MONO, INK, LINE, MUTED, SCREEN, Svg, fmt

EMOTION_LABELS = {
    "neutral": "Neutral",
    "happy": "Alegría",
    "sad": "Tristeza",
    "surprised": "Sorpresa",
    "angry": "Enojo",
    "thinking": "Reflexión",
    "sleepy": "Sueño",
    "love": "Cariño",
    "error": "Error",
}

STATE_LABELS = {
    "idle": ("Reposo", "idle"),
    "listening": ("Escuchando", "listening"),
    "thinking": ("Pensando", "thinking"),
    "acting": ("Trabajando", "acting"),
    "speaking": ("Hablando", "speaking"),
}

PALETTE = {
    COLOR_BACKGROUND: SCREEN,
    COLOR_EYE: "#3fe0ff",
    COLOR_ACCENT: "#ff4d6d",
    COLOR_GLOW: "#0e3a47",
}


class SvgFaceCanvas:
    """Implementa FaceCanvas emitiendo figuras SVG."""

    def __init__(self, svg: Svg, palette: dict[int, str] | None = None) -> None:
        self.svg = svg
        self.palette = palette or PALETTE

    def _c(self, color: int) -> str:
        return self.palette.get(color, self.palette[COLOR_EYE])

    def fill_rect(self, x: float, y: float, w: float, h: float, color: int) -> None:
        self.svg.rect(x, y, w, h, fill=self._c(color))

    def fill_round_rect(self, x: float, y: float, w: float, h: float, r: float, color: int) -> None:
        self.svg.rect(x, y, w, h, rx=r, fill=self._c(color))

    def fill_circle(self, cx: float, cy: float, r: float, color: int) -> None:
        self.svg.circle(cx, cy, r, fill=self._c(color))

    def fill_triangle(self, x0: float, y0: float, x1: float, y1: float, x2: float, y2: float, color: int) -> None:
        # Trazo del mismo color: tapa las costuras de antialiasing entre triangulos.
        c = self._c(color)
        self.svg.polygon([(x0, y0), (x1, y1), (x2, y2)], fill=c, stroke=c, sw=0.6)


def draw_screen(svg: Svg, frame: FaceFrame, x: float, y: float, scale: float, *, glow: bool = True,
                palette: dict[int, str] | None = None, bezel: bool = True, clip_id: str = "") -> None:
    """Pantalla oscura con la cara; el contenido se recorta al rectangulo."""
    w, h = REF_W * scale, REF_H * scale
    radius = 10 + scale * 2
    if bezel:
        svg.rect(x - 6, y - 6, w + 12, h + 12, rx=radius + 5, fill="#1b2631")
    svg.rect(x, y, w, h, rx=radius, fill=(palette or PALETTE)[COLOR_BACKGROUND])
    if clip_id:
        svg.define(f'<clipPath id="{clip_id}"><rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" '
                   f'height="{fmt(h)}" rx="{fmt(radius)}"/></clipPath>')
    layout = FaceLayout(scale=scale, origin_x=x, origin_y=y, glow=glow, snap=False)
    attrs = {"clip_path": f"url(#{clip_id})"} if clip_id else {}
    with svg.group(**attrs):
        draw_face(frame, SvgFaceCanvas(svg, palette), layout)


def _frame(emotion: str, activity: str = "idle", level: float = 0.0) -> FaceFrame:
    engine = EyesEngine(seed=7)
    engine.begin(0)
    return settle(engine, emotion, activity, level, ms=2000)


def build_expressions(path: Path) -> bool:
    cols, scale, gap = 3, 2.2, 28
    cell_w, cell_h = REF_W * scale, REF_H * scale
    width = 40 * 2 + cols * cell_w + (cols - 1) * gap
    rows = (len(EMOTIONS) + cols - 1) // cols
    top = 104
    row_h = cell_h + 70
    height = top + rows * row_h + 40
    svg = Svg(width, height, title="Expresiones de G-Mini Home",
              desc="Las nueve emociones del protocolo dibujadas con el motor de ojos.")
    svg.heading("Expresiones", "Emociones del protocolo (campo emotion) dibujadas con el motor real, en un lienzo de 128 x 64")
    for i, emotion in enumerate(EMOTIONS):
        col, row = i % cols, i // cols
        x = 40 + col * (cell_w + gap)
        y = top + row * row_h
        draw_screen(svg, _frame(emotion), x, y, scale, clip_id=f"clip-e{i}")
        svg.text(x, y + cell_h + 32, EMOTION_LABELS.get(emotion, emotion), size=15, weight=700, fill=INK)
        svg.text(x + cell_w, y + cell_h + 32, emotion, size=12.5, fill=MUTED, anchor="end", family=FONT_MONO)
    svg.footer("Generado por tools/diagrams/face_sheet.py desde common/expressions.json")
    return svg.save(path)


def build_states(path: Path) -> bool:
    states = list(STATE_LABELS)
    cols, scale, gap = len(states), 1.32, 20
    cell_w, cell_h = REF_W * scale, REF_H * scale
    width = 40 * 2 + cols * cell_w + (cols - 1) * gap
    top = 104
    height = top + cell_h + 100
    svg = Svg(width, height, title="Estados de G-Mini Home",
              desc="Estados del agente (campo status) sobre la emocion neutral.")
    svg.heading("Estados", "Campo status del protocolo: idle, listening, thinking, acting y speaking")
    levels = {"listening": 0.3, "speaking": 0.7}
    for i, state in enumerate(states):
        x = 40 + i * (cell_w + gap)
        frame = _frame("neutral", state, levels.get(state, 0.0))
        draw_screen(svg, frame, x, top, scale, clip_id=f"clip-s{i}")
        label, proto = STATE_LABELS[state]
        svg.text(x, top + cell_h + 30, label, size=14, weight=700, fill=INK)
        svg.text(x, top + cell_h + 48, proto, size=11.5, fill=MUTED, family=FONT_MONO)
    svg.line(40, height - 34, width - 40, height - 34, stroke=LINE, sw=1)
    svg.text(40, height - 14, "En speaking la boca sigue el volumen del audio; en acting la mirada barre de lado a lado.",
             size=11, fill=MUTED)
    return svg.save(path)
