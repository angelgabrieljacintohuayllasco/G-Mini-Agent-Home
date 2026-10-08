"""Constructor minimo de SVG con el estilo visual del proyecto.

Sin dependencias externas y con salida determinista (mismos datos, mismos
bytes), para que los diagramas se puedan regenerar y revisar en git.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence
from xml.sax.saxutils import escape

FONT_SANS = "'Inter', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
FONT_MONO = "'JetBrains Mono', 'Cascadia Mono', Consolas, 'DejaVu Sans Mono', monospace"

# Paleta base (fondo claro: se lee igual en el tema claro y oscuro de GitHub).
PAPER = "#ffffff"
PANEL = "#f4f6f8"
PANEL_DARK = "#e6eaee"
INK = "#1d2733"
MUTED = "#5b6b7b"
LINE = "#c9d1d9"
BRAND = "#0b7285"
BRAND_SOFT = "#e3f6f9"
SCREEN = "#06121a"
EYE = "#3fe0ff"
EYE_GLOW = "#0b4a5c"
WARN = "#c2410c"
WARN_SOFT = "#fff4e6"
DANGER = "#c92a2a"
DANGER_SOFT = "#fff0f0"
OK = "#2b8a3e"

# Colores de cable por funcion (se repiten en todos los diagramas y en la leyenda).
WIRE = {
    "5v": ("#d64545", "5 V"),
    "3v3": ("#e8890c", "3,3 V"),
    "gnd": ("#1d2733", "GND"),
    "sda": ("#2563eb", "I2C SDA"),
    "scl": ("#b7791f", "I2C SCL"),
    "bclk": ("#7c3aed", "I2S BCLK / SCK"),
    "ws": ("#db2777", "I2S WS / LRC"),
    "i2s_data": ("#059669", "I2S datos"),
    "spi": ("#0891b2", "SPI (SCK/MOSI)"),
    "ctrl": ("#4c6ef5", "Control (CS/DC/RST/BL)"),
    "data": ("#0ca678", "Datos LED"),
    "button": ("#64748b", "Botones"),
    "relay": ("#a61e4d", "Relés"),
    "analog": ("#9c36b5", "Analógico"),
    "audio": ("#495057", "Audio (altavoz)"),
    "usb": ("#343a40", "USB"),
}


def fmt(value: float) -> str:
    """Numero corto y estable para atributos SVG."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


class Svg:
    def __init__(self, width: float, height: float, *, background: str | None = PAPER, title: str = "",
                 desc: str = "") -> None:
        self.width = width
        self.height = height
        self._parts: list[str] = []
        self._defs: list[str] = []
        self._indent = 1
        self.title = title
        self.desc = desc
        if background:
            self.rect(0, 0, width, height, fill=background)

    # ------------------------------------------------------------ base

    def raw(self, text: str) -> None:
        self._parts.append("  " * self._indent + text)

    def define(self, text: str) -> None:
        if text not in self._defs:
            self._defs.append(text)

    @contextmanager
    def group(self, transform: str = "", **attrs: str) -> Iterator[None]:
        extra = "".join(f' {k.replace("_", "-")}="{v}"' for k, v in attrs.items())
        tr = f' transform="{transform}"' if transform else ""
        self.raw(f"<g{tr}{extra}>")
        self._indent += 1
        try:
            yield
        finally:
            self._indent -= 1
            self.raw("</g>")

    @staticmethod
    def _style(fill: str | None, stroke: str | None, sw: float | None, opacity: float | None,
               dash: str | None, extra: str) -> str:
        out = f' fill="{fill or "none"}"'
        if stroke:
            out += f' stroke="{stroke}"'
            if sw is not None:
                out += f' stroke-width="{fmt(sw)}"'
        if opacity is not None:
            out += f' opacity="{fmt(opacity)}"'
        if dash:
            out += f' stroke-dasharray="{dash}"'
        if extra:
            out += " " + extra
        return out

    # ------------------------------------------------------------ figuras

    def rect(self, x: float, y: float, w: float, h: float, *, rx: float = 0, fill: str | None = None,
             stroke: str | None = None, sw: float | None = None, opacity: float | None = None,
             dash: str | None = None, extra: str = "") -> None:
        r = f' rx="{fmt(rx)}"' if rx else ""
        self.raw(f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{fmt(w)}" height="{fmt(h)}"{r}'
                 f'{self._style(fill, stroke, sw, opacity, dash, extra)}/>')

    def circle(self, cx: float, cy: float, r: float, *, fill: str | None = None, stroke: str | None = None,
               sw: float | None = None, opacity: float | None = None, dash: str | None = None,
               extra: str = "") -> None:
        self.raw(f'<circle cx="{fmt(cx)}" cy="{fmt(cy)}" r="{fmt(r)}"'
                 f'{self._style(fill, stroke, sw, opacity, dash, extra)}/>')

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, *, fill: str | None = None,
                stroke: str | None = None, sw: float | None = None, opacity: float | None = None,
                extra: str = "") -> None:
        self.raw(f'<ellipse cx="{fmt(cx)}" cy="{fmt(cy)}" rx="{fmt(rx)}" ry="{fmt(ry)}"'
                 f'{self._style(fill, stroke, sw, opacity, None, extra)}/>')

    def line(self, x1: float, y1: float, x2: float, y2: float, *, stroke: str = INK, sw: float = 1.5,
             dash: str | None = None, opacity: float | None = None, cap: str = "round", extra: str = "") -> None:
        style = self._style(None, stroke, sw, opacity, dash, f'stroke-linecap="{cap}" ' + extra)
        self.raw(f'<line x1="{fmt(x1)}" y1="{fmt(y1)}" x2="{fmt(x2)}" y2="{fmt(y2)}"{style}/>')

    def polyline(self, points: Sequence[tuple[float, float]], *, stroke: str = INK, sw: float = 1.5,
                 dash: str | None = None, opacity: float | None = None, extra: str = "") -> None:
        pts = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in points)
        style = self._style(None, stroke, sw, opacity, dash,
                            'stroke-linecap="round" stroke-linejoin="round" ' + extra)
        self.raw(f'<polyline points="{pts}"{style}/>')

    def polygon(self, points: Sequence[tuple[float, float]], *, fill: str | None = None, stroke: str | None = None,
                sw: float | None = None, opacity: float | None = None, dash: str | None = None,
                extra: str = "") -> None:
        pts = " ".join(f"{fmt(x)},{fmt(y)}" for x, y in points)
        style = self._style(fill, stroke, sw, opacity, dash, 'stroke-linejoin="round" ' + extra)
        self.raw(f'<polygon points="{pts}"{style}/>')

    def path(self, d: str, *, fill: str | None = None, stroke: str | None = None, sw: float | None = None,
             opacity: float | None = None, dash: str | None = None, extra: str = "") -> None:
        self.raw(f'<path d="{d}"{self._style(fill, stroke, sw, opacity, dash, extra)}/>')

    def text(self, x: float, y: float, content: str, *, size: float = 13, weight: int = 400, fill: str = INK,
             anchor: str = "start", family: str = FONT_SANS, italic: bool = False, extra: str = "",
             baseline: str | None = None) -> None:
        style = ' font-style="italic"' if italic else ""
        base = f' dominant-baseline="{baseline}"' if baseline else ""
        self.raw(f'<text x="{fmt(x)}" y="{fmt(y)}" font-family="{family}" font-size="{fmt(size)}" '
                 f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{style}{base}'
                 f'{(" " + extra) if extra else ""}>{escape(content)}</text>')

    def arrow_marker(self, ident: str, color: str) -> str:
        self.define(
            f'<marker id="{ident}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
        return f'marker-end="url(#{ident})"'

    def arrow(self, x1: float, y1: float, x2: float, y2: float, *, color: str = INK, sw: float = 1.6,
              dash: str | None = None, both: bool = False, ident: str | None = None) -> None:
        mid = ident or f"arrow-{color.lstrip('#')}"
        marker = self.arrow_marker(mid, color)
        if both:
            marker += f' marker-start="url(#{mid})"'
        self.line(x1, y1, x2, y2, stroke=color, sw=sw, dash=dash, cap="butt", extra=marker)

    # ------------------------------------------------------------ componentes de estilo

    def heading(self, title: str, subtitle: str = "", *, x: float = 32, y: float = 44) -> None:
        self.text(x, y, title, size=22, weight=700, fill=INK)
        if subtitle:
            self.text(x, y + 24, subtitle, size=13.5, fill=MUTED)

    def footer(self, note: str) -> None:
        self.line(32, self.height - 34, self.width - 32, self.height - 34, stroke=LINE, sw=1)
        self.text(32, self.height - 14, note, size=11, fill=MUTED)
        self.text(self.width - 32, self.height - 14, "G-Mini Home  |  CC BY-SA 4.0", size=11, fill=MUTED,
                  anchor="end")

    def badge(self, x: float, y: float, label: str, *, fill: str = BRAND_SOFT, color: str = BRAND,
              size: float = 11.5) -> float:
        width = 12 + len(label) * size * 0.58
        self.rect(x, y - size - 3, width, size + 9, rx=(size + 9) / 2, fill=fill)
        self.text(x + width / 2, y + 0.5, label, size=size, weight=600, fill=color, anchor="middle")
        return width

    def callout(self, x: float, y: float, w: float, lines: Sequence[str], *, title: str = "", tone: str = "warn",
                size: float = 12) -> float:
        bg, fg = {"warn": (WARN_SOFT, WARN), "danger": (DANGER_SOFT, DANGER), "info": (BRAND_SOFT, BRAND)}[tone]
        line_h = size * 1.45
        h = 16 + (line_h if title else 0) + line_h * len(lines)
        self.rect(x, y, w, h, rx=8, fill=bg, stroke=fg, sw=1)
        self.rect(x, y, 4, h, rx=2, fill=fg)
        cy = y + 8 + size
        if title:
            self.text(x + 14, cy, title, size=size, weight=700, fill=fg)
            cy += line_h
        for line in lines:
            self.text(x + 14, cy, line, size=size, fill=INK)
            cy += line_h
        return h

    # ------------------------------------------------------------ salida

    def render(self) -> str:
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(self.width)}" height="{fmt(self.height)}" '
                f'viewBox="0 0 {fmt(self.width)} {fmt(self.height)}" role="img"'
                f'{(" aria-label=" + chr(34) + escape(self.title) + chr(34)) if self.title else ""}>')
        out = [head]
        if self.title:
            out.append(f"  <title>{escape(self.title)}</title>")
        if self.desc:
            out.append(f"  <desc>{escape(self.desc)}</desc>")
        if self._defs:
            out.append("  <defs>")
            out.extend("    " + d for d in self._defs)
            out.append("  </defs>")
        out.extend(self._parts)
        out.append("</svg>")
        return "\n".join(out) + "\n"

    def save(self, path: Path) -> bool:
        """Escribe el archivo si cambio. Devuelve True si hubo cambios."""
        content = self.render()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return False
        path.write_text(content, encoding="utf-8", newline="\n")
        return True
