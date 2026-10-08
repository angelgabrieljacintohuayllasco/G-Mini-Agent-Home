#!/usr/bin/env python3
"""Regenera todos los diagramas SVG del repositorio.

Uso:
  python tools/diagrams/build_all.py            # escribe los SVG que cambiaron
  python tools/diagrams/build_all.py --check    # falla si alguno esta desactualizado
  python tools/diagrams/build_all.py --png DIR  # ademas exporta PNG con resvg (vista previa)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "common"))

import face_sheet  # noqa: E402

Builder = Callable[[Path], bool]


def targets() -> dict[str, Builder]:
    """Ruta relativa al repo -> funcion que la construye."""
    import architecture
    import holograms
    import wiring

    out: dict[str, Builder] = {
        "docs/img/expressions.svg": face_sheet.build_expressions,
        "docs/img/states.svg": face_sheet.build_states,
    }
    out.update(architecture.targets())
    out.update(wiring.targets())
    out.update(holograms.targets())
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="no escribe; falla si hay diferencias")
    parser.add_argument("--png", type=Path, help="carpeta donde exportar PNG con resvg")
    parser.add_argument("--only", help="construye solo las rutas que contienen este texto")
    args = parser.parse_args(argv)

    stale: list[str] = []
    built: list[Path] = []
    for rel, build in targets().items():
        if args.only and args.only not in rel:
            continue
        dest = ROOT / rel
        if args.check:
            with tempfile.TemporaryDirectory() as tmp:
                probe = Path(tmp) / dest.name
                build(probe)
                current = dest.read_text(encoding="utf-8") if dest.exists() else None
                if current != probe.read_text(encoding="utf-8"):
                    stale.append(rel)
            continue
        if build(dest):
            print(f"actualizado {rel}")
        built.append(dest)

    if stale:
        print("Diagramas desactualizados (ejecuta build_all.py):", *stale, sep="\n  ", file=sys.stderr)
        return 1
    if args.png:
        resvg = shutil.which("resvg")
        if not resvg:
            print("resvg no esta en el PATH; omito la exportacion PNG", file=sys.stderr)
            return 0
        args.png.mkdir(parents=True, exist_ok=True)
        for svg in built:
            png = args.png / (svg.stem + ".png")
            subprocess.run([resvg, "--zoom", "1.5", str(svg), str(png)], check=True)
        print(f"PNG en {args.png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
