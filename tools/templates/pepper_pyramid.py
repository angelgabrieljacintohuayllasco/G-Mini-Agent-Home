#!/usr/bin/env python3
"""Plantillas de corte de la piramide de Pepper (4 caras a 45 grados) por tamano de pantalla.

Genera en hardware/templates/:
  pyramid-<tamano>-net.svg     abanico de una pieza para lamina fina (PET/acetato), escala 1:1 en mm
  pyramid-<tamano>-net.dxf     el mismo abanico para corte laser o plotter de corte
  pyramid-<tamano>-pieces.dxf  cuatro trapecios sueltos para acrilico
  README.md                    tabla de medidas, materiales y caja de Pepper

Geometria (caras a 45 grados de la pantalla):
  b = lado mayor (arriba), a = lado menor (apoya en la pantalla)
  altura de la piramide H = (b - a) / 2
  altura de cada trapecio s = H * sqrt(2)
  angulo de los lados del trapecio = atan(sqrt(2)) = 54,74 grados con la base
  en el abanico cada cara abre 2 * atan(sqrt(2) / 2) = 70,53 grados

Uso:  python tools/templates/pepper_pyramid.py [--check]
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "hardware" / "templates"
TAB = 8.0  # pestana de pegado en mm


@dataclass(frozen=True)
class Screen:
    slug: str
    name: str
    diagonal_in: float
    aspect: tuple[float, float]
    material: str

    @property
    def short_side_mm(self) -> float:
        w, h = self.aspect
        return self.diagonal_in * 25.4 * min(w, h) / math.hypot(w, h)

    @property
    def long_side_mm(self) -> float:
        w, h = self.aspect
        return self.diagonal_in * 25.4 * max(w, h) / math.hypot(w, h)


SCREENS = [
    Screen("phone-6.1", "Teléfono 6,1\"", 6.1, (19.5, 9), "PET o acetato de 0,5 mm (o tapa de CD)"),
    Screen("phone-6.7", "Teléfono 6,7\"", 6.7, (19.5, 9), "PET o acetato de 0,5 mm"),
    Screen("tablet-8", "Tablet 8\"", 8.0, (16, 10), "PET de 0,5-0,75 mm"),
    Screen("tablet-10", "Tablet 10,1\"", 10.1, (16, 10), "PET de 0,75 mm"),
    Screen("tablet-11", "Tablet 11\" (4:3)", 11.0, (4, 3), "PET de 0,75-1 mm"),
    Screen("laptop-15.6", "Portátil 15,6\"", 15.6, (16, 9), "PETG o acrílico de 2 mm"),
    Screen("monitor-24", "Monitor 24\"", 24.0, (16, 9), "Acrílico de 2-3 mm"),
    Screen("monitor-27", "Monitor 27\"", 27.0, (16, 9), "Acrílico de 3 mm"),
    Screen("tv-32", "TV 32\"", 32.0, (16, 9), "Acrílico de 3 mm con marco"),
]


@dataclass(frozen=True)
class Pyramid:
    screen: Screen
    b: float  # lado mayor
    a: float  # lado menor

    @property
    def height(self) -> float:
        return (self.b - self.a) / 2

    @property
    def slant(self) -> float:
        return self.height * math.sqrt(2)

    @property
    def leg(self) -> float:
        return math.hypot(self.slant, self.height)

    @property
    def fan_angle(self) -> float:
        return 2 * math.atan(math.sqrt(2) / 2)

    @property
    def r_small(self) -> float:
        """Distancia del vertice del abanico a las esquinas pequenas."""
        return math.hypot(self.a / math.sqrt(2), self.a / 2)

    @property
    def r_large(self) -> float:
        return math.hypot(self.b / math.sqrt(2), self.b / 2)


def design(screen: Screen) -> Pyramid:
    """b ocupa el 95 % del lado corto (redondeado a mm pares); a = b / 6 deja el centro libre."""
    b = math.floor(screen.short_side_mm * 0.95 / 2) * 2
    a = max(8.0, round(b / 6))
    return Pyramid(screen, float(b), float(a))


# ---------------------------------------------------------------- geometria


Segment = tuple[tuple[float, float], tuple[float, float]]


def fan_net(p: Pyramid) -> tuple[list[Segment], list[Segment], list[tuple[float, float]]]:
    """Abanico de 4 trapecios + pestana. Devuelve (cortes, pliegues, puntos para el marco)."""
    theta = p.fan_angle
    start = -2 * theta  # centrado verticalmente
    corners = []
    for k in range(5):
        ang = start + k * theta
        small = (p.r_small * math.cos(ang), p.r_small * math.sin(ang))
        large = (p.r_large * math.cos(ang), p.r_large * math.sin(ang))
        corners.append((small, large))
    cuts: list[Segment] = []
    folds: list[Segment] = []
    for k in range(4):
        (s0, l0), (s1, l1) = corners[k], corners[k + 1]
        cuts.append((s0, s1))
        cuts.append((l0, l1))
    cuts.append(corners[0])  # primer lado
    for k in range(1, 4):
        folds.append(corners[k])
    # Pestana de pegado sobre el ultimo lado: trapecio corto hacia afuera.
    (s4, l4) = corners[4]
    ang = start + 4 * theta
    nx, ny = -math.sin(ang), math.cos(ang)
    inset = TAB * 0.6
    ux, uy = math.cos(ang), math.sin(ang)
    ts = (s4[0] + nx * TAB + ux * inset, s4[1] + ny * TAB + uy * inset)
    tl = (l4[0] + nx * TAB - ux * inset, l4[1] + ny * TAB - uy * inset)
    cuts += [(s4, ts), (ts, tl), (tl, l4)]
    folds.append((s4, l4))
    points = [pt for seg in cuts for pt in seg]
    return cuts, folds, points


def pieces(p: Pyramid) -> list[Segment]:
    """Cuatro trapecios separados por 6 mm, alternando la orientacion para ahorrar material."""
    segs: list[Segment] = []
    half_diff = (p.b - p.a) / 2
    x = 0.0
    for k in range(4):
        if k % 2 == 0:
            pts = [(x, 0.0), (x + p.b, 0.0), (x + p.b - half_diff, p.slant), (x + half_diff, p.slant)]
        else:
            pts = [(x, p.slant), (x + p.b, p.slant), (x + p.b - half_diff, 0.0), (x + half_diff, 0.0)]
        segs += [(pts[i], pts[(i + 1) % 4]) for i in range(4)]
        # Los lados inclinados de piezas vecinas quedan paralelos a 6 mm (en horizontal).
        x += p.b - half_diff + 6.0
    return segs


# ---------------------------------------------------------------- salidas


def _bounds(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def dxf(cut: list[Segment], fold: list[Segment] | None = None, notes: list[str] | None = None) -> str:
    """DXF R12 minimo en milimetros: capa CORTE, PLIEGUE y NOTAS."""
    out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
           "0", "SECTION", "2", "ENTITIES"]

    def line(seg: Segment, layer: str, color: int) -> None:
        (x1, y1), (x2, y2) = seg
        # DXF tiene el eje Y hacia arriba: se invierte para que coincida con el SVG.
        out.extend(["0", "LINE", "8", layer, "62", str(color), "10", f"{x1:.3f}", "20", f"{-y1:.3f}", "30", "0.0",
                    "11", f"{x2:.3f}", "21", f"{-y2:.3f}", "31", "0.0"])

    for seg in cut:
        line(seg, "CORTE", 1)
    for seg in fold or []:
        line(seg, "PLIEGUE", 5)
    if notes:
        minx, _, _, maxy = _bounds([pt for seg in cut for pt in seg])
        for i, text in enumerate(notes):
            out.extend(["0", "TEXT", "8", "NOTAS", "62", "8", "10", f"{minx:.3f}", "20", f"{-(maxy + 8 + i * 5):.3f}",
                        "30", "0.0", "40", "3.0", "1", text])
    out.extend(["0", "ENDSEC", "0", "EOF"])
    return "\n".join(out) + "\n"


def svg_net(p: Pyramid, cuts: list[Segment], folds: list[Segment]) -> str:
    points = [pt for seg in cuts + folds for pt in seg]
    minx, miny, maxx, maxy = _bounds(points)
    margin = 12.0
    text_h = 40.0
    # Ancho minimo de una hoja A4 para que el encabezado no se corte.
    w = max(maxx - minx + 2 * margin, 186.0)
    h = maxy - miny + 2 * margin + text_h
    ox, oy = (w - (maxx - minx)) / 2 - minx, margin + text_h - miny

    def seg_svg(seg: Segment, color: str, dash: str = "") -> str:
        (x1, y1), (x2, y2) = seg
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'  <line x1="{x1 + ox:.2f}" y1="{y1 + oy:.2f}" x2="{x2 + ox:.2f}" y2="{y2 + oy:.2f}" '
                f'stroke="{color}" stroke-width="0.3"{d}/>')

    s = p.screen
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.1f}mm" height="{h:.1f}mm" '
        f'viewBox="0 0 {w:.2f} {h:.2f}">',
        f"  <title>Pirámide de Pepper - {s.name}</title>",
        f'  <rect x="0" y="0" width="{w:.2f}" height="{h:.2f}" fill="#ffffff"/>',
        f'  <text x="{margin}" y="{margin + 4}" font-family="Arial, sans-serif" font-size="5" font-weight="700" '
        f'fill="#1d2733">Pirámide de Pepper - {s.name}</text>',
        f'  <text x="{margin}" y="{margin + 11}" font-family="Arial, sans-serif" font-size="3.2" fill="#5b6b7b">'
        f"Lado mayor b = {p.b:.0f} mm, lado menor a = {p.a:.0f} mm, alto del trapecio = {p.slant:.1f} mm, "
        f"altura = {p.height:.1f} mm</text>",
        f'  <text x="{margin}" y="{margin + 16.5}" font-family="Arial, sans-serif" font-size="3.2" fill="#5b6b7b">'
        f"Rojo: cortar. Azul punteado: marcar y doblar. Material: {s.material}.</text>",
        f'  <text x="{margin}" y="{margin + 22}" font-family="Arial, sans-serif" font-size="3.2" fill="#5b6b7b">'
        f"Imprime al 100 % (sin ajustar a la página) y mide la regla antes de cortar.</text>",
        f'  <line x1="{margin}" y1="{margin + 27}" x2="{margin + 50}" y2="{margin + 27}" stroke="#1d2733" '
        f'stroke-width="0.4"/>',
        f'  <text x="{margin + 52}" y="{margin + 28}" font-family="Arial, sans-serif" font-size="3" '
        f'fill="#1d2733">50 mm</text>',
    ]
    lines += [seg_svg(seg, "#d64545") for seg in cuts]
    lines += [seg_svg(seg, "#2563eb", "2 1.5") for seg in folds]
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def readme(designs: list[Pyramid]) -> str:
    rows = []
    for p in designs:
        s = p.screen
        rows.append(f"| {s.name} | {s.short_side_mm:.0f} | {p.b:.0f} | {p.a:.0f} | {p.slant:.1f} | {p.height:.1f} | "
                    f"{s.material} | [SVG](pyramid-{s.slug}-net.svg) · [DXF abanico](pyramid-{s.slug}-net.dxf) · "
                    f"[DXF piezas](pyramid-{s.slug}-pieces.dxf) |")
    box_rows = []
    for p in designs:
        s = p.screen
        depth = s.short_side_mm
        box_rows.append(f"| {s.name} | {s.long_side_mm:.0f} x {depth:.0f} | {s.long_side_mm:.0f} x "
                        f"{depth * math.sqrt(2):.0f} | {depth:.0f} |")
    return "\n".join([
        "# Plantillas de corte: pirámide de Pepper",
        "",
        "Generadas por `tools/templates/pepper_pyramid.py` (no editar a mano). Todas las medidas en milímetros.",
        "La guía completa está en [docs/holograms/pyramid.md](../../docs/holograms/pyramid.md).",
        "",
        "| Pantalla | Lado corto útil | b (lado mayor) | a (lado menor) | Alto del trapecio | Altura | Material | Archivos |",
        "|---|---|---|---|---|---|---|---|",
        *rows,
        "",
        "- Las caras quedan a 45° de la pantalla: altura = (b - a) / 2 y alto del trapecio = altura x 1,414.",
        "- Los lados del trapecio forman 54,74° con la base. En el abanico cada cara abre 70,53°.",
        "- La imagen flotante puede medir como máximo la altura de la pirámide.",
        "- Acrílico: las aristas se unen a 120°; bisela 30° los cantos laterales o une por fuera con cinta",
        "  transparente o pegamento UV. Lámina fina: usa el abanico (SVG o DXF) y la pestaña de 8 mm.",
        "",
        "## Caja de Pepper (una placa a 45°)",
        "",
        "Pantalla boca arriba en el piso de una caja y una placa a 45° que cubre su profundidad.",
        "",
        "| Pantalla | Pantalla (largo x ancho) | Placa (largo x ancho) | Alto interior mínimo |",
        "|---|---|---|---|",
        *box_rows,
        "",
    ]) + "\n"


def outputs() -> dict[Path, str]:
    designs = [design(s) for s in SCREENS]
    files: dict[Path, str] = {}
    for p in designs:
        cuts, folds, _ = fan_net(p)
        notes = [f"Piramide de Pepper {p.screen.slug}: b={p.b:.0f} a={p.a:.0f} s={p.slant:.1f} mm",
                 "CORTE = cortar, PLIEGUE = marcar y doblar"]
        files[OUT / f"pyramid-{p.screen.slug}-net.svg"] = svg_net(p, cuts, folds)
        files[OUT / f"pyramid-{p.screen.slug}-net.dxf"] = dxf(cuts, folds, notes)
        files[OUT / f"pyramid-{p.screen.slug}-pieces.dxf"] = dxf(pieces(p), None, notes[:1])
    files[OUT / "README.md"] = readme(designs)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="falla si los archivos estan desactualizados")
    args = parser.parse_args(argv)
    stale = []
    for path, content in outputs().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == content:
            continue
        if args.check:
            stale.append(path.relative_to(ROOT).as_posix())
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"escrito {path.relative_to(ROOT).as_posix()}")
    if stale:
        print("Plantillas desactualizadas:", *stale, sep="\n  ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
