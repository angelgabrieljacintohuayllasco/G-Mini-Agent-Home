#!/usr/bin/env python3
"""Exporta las carcasas de OpenSCAD a STL (binario) y PNG.

  python tools/render_enclosures.py                 # todo
  python tools/render_enclosures.py --only puck     # solo las que contienen "puck"
  python tools/render_enclosures.py --stl-only      # sin imagenes (CI sin GPU)

Busca OpenSCAD en $OPENSCAD, en el PATH o en E:/tools/openscad (Windows).
En Linux sin pantalla usa xvfb-run si esta instalado.
"""

from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAD_DIR = ROOT / "hardware" / "enclosures"
STL_DIR = ROOT / "hardware" / "stl"
PNG_DIR = ROOT / "hardware" / "renders"
MAX_STL_BYTES = 5 * 1024 * 1024


@dataclass
class Model:
    name: str
    parts: list[str]
    camera: str  # tx,ty,tz,rx,ry,rz,dist (dist se ajusta con --viewall)
    part_camera: str = "0,0,0,55,0,30,0"
    defines: dict[str, str] = field(default_factory=dict)


MODELS = [
    Model("oled_companion", ["shell", "back"], camera="0,0,0,72,0,28,0"),
    Model("speaker_puck", ["base", "top", "diffuser", "bottom"], camera="0,0,0,62,0,30,0"),
    Model("pepper_pyramid", ["frame"], camera="0,0,0,58,0,35,0"),
]


def find_openscad() -> list[str]:
    env = os.environ.get("OPENSCAD")
    candidates = [env] if env else []
    candidates += [shutil.which("openscad") or "", r"E:\tools\openscad\openscad-2021.01\openscad.com"]
    for c in candidates:
        if c and Path(c).exists():
            exe = [c]
            break
    else:
        raise SystemExit("No encuentro OpenSCAD (define OPENSCAD=/ruta/al/openscad)")
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and shutil.which("xvfb-run"):
        exe = ["xvfb-run", "-a", "-s", "-screen 0 1600x1200x24", *exe]
    return exe


def run(cmd: list[str]) -> float:
    started = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stdout + result.stderr)
        raise SystemExit(f"Fallo: {' '.join(cmd)}")
    for line in (result.stdout + result.stderr).splitlines():
        if "WARNING" in line or "ERROR" in line:
            print("   ", line)
    return time.monotonic() - started


def ascii_to_binary_stl(path: Path) -> int:
    """OpenSCAD 2021.01 exporta STL ASCII; en binario pesa ~5 veces menos."""
    text = path.read_text(encoding="ascii", errors="replace")
    if not text.lstrip().startswith("solid"):
        return path.stat().st_size  # ya es binario
    triangles: list[tuple[float, ...]] = []
    normal: list[float] = []
    verts: list[float] = []
    for raw in text.splitlines():
        parts = raw.split()
        if not parts:
            continue
        if parts[0] == "facet":
            normal = [float(v) for v in parts[2:5]]
            verts = []
        elif parts[0] == "vertex":
            verts.extend(float(v) for v in parts[1:4])
        elif parts[0] == "endfacet":
            triangles.append((*normal, *verts))
    header = b"G-Mini Home - exportado con OpenSCAD".ljust(80, b" ")
    body = b"".join(struct.pack("<12fH", *t, 0) for t in triangles)
    path.write_bytes(header + struct.pack("<I", len(triangles)) + body)
    return path.stat().st_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="solo los modelos que contengan este texto")
    parser.add_argument("--stl-only", action="store_true")
    parser.add_argument("--png-only", action="store_true")
    parser.add_argument("--size", default="1200,900")
    args = parser.parse_args(argv)
    openscad = find_openscad()
    STL_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    for model in MODELS:
        if args.only and args.only not in model.name:
            continue
        scad = SCAD_DIR / f"{model.name}.scad"
        defines = [f"-D{k}={v}" for k, v in model.defines.items()]
        for part in model.parts:
            if not args.png_only:
                stl = STL_DIR / f"{model.name}-{part}.stl"
                seconds = run([*openscad, *defines, f'-Dpart="{part}"', "-o", str(stl), str(scad)])
                size = ascii_to_binary_stl(stl)
                if size > MAX_STL_BYTES:
                    raise SystemExit(f"{stl.name} pesa {size / 1e6:.1f} MB (limite 5 MB): baja $fn")
                print(f"STL {stl.relative_to(ROOT).as_posix():48} {size / 1024:8.0f} KB  {seconds:5.1f} s")
            if not args.stl_only:
                png = PNG_DIR / f"{model.name}-{part}.png"
                seconds = run([*openscad, *defines, f'-Dpart="{part}"', "--render", "--colorscheme=Tomorrow",
                               f"--imgsize={args.size}", f"--camera={model.part_camera}", "--viewall",
                               "--autocenter", "-o", str(png), str(scad)])
                print(f"PNG {png.relative_to(ROOT).as_posix():48} {png.stat().st_size / 1024:8.0f} KB  {seconds:5.1f} s")
        if not args.stl_only:
            png = PNG_DIR / f"{model.name}.png"
            seconds = run([*openscad, *defines, '-Dpart="assembly"', "--colorscheme=Tomorrow",
                           f"--imgsize={args.size}", f"--camera={model.camera}", "--viewall", "--autocenter",
                           "-o", str(png), str(scad)])
            print(f"PNG {png.relative_to(ROOT).as_posix():48} {png.stat().st_size / 1024:8.0f} KB  {seconds:5.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
