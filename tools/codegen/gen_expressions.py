#!/usr/bin/env python3
"""Genera los presets de la cara a partir de common/expressions.json.

Salidas (no se editan a mano):
  - firmware/libraries/GMiniEyes/src/GMiniEyesPresets.h  (C++ para ESP32 y AVR)
  - common/gmini_link/eye_presets.py                      (cliente Raspberry Pi y puente)
  - kiosk/presets.js                                      (pagina de kiosko)

Uso:
  python tools/codegen/gen_expressions.py          # escribe los archivos
  python tools/codegen/gen_expressions.py --check  # falla si algo esta desactualizado
"""

from __future__ import annotations

import argparse
import json
import pprint
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "common" / "expressions.json"
OUT_CPP = ROOT / "firmware" / "libraries" / "GMiniEyes" / "src" / "GMiniEyesPresets.h"
OUT_PY = ROOT / "common" / "gmini_link" / "eye_presets.py"
OUT_JS = ROOT / "kiosk" / "presets.js"

SHAPES = ("round", "heart", "cross")

EMOTION_FIELDS: dict[str, type] = {
    "w": float, "h": float, "r": float, "gap": float, "dy": float,
    "lid_top": float, "slant_in": float, "slant_out": float, "lid_bottom": float,
    "look_x": float, "look_y": float, "scale_l": float, "scale_r": float,
    "bounce": float, "shake": float, "pulse": float, "pulse_hz": float,
    "blink": list, "saccade": list, "shape": str, "accent": bool,
}
ACTIVITY_DEFAULTS: dict[str, Any] = {
    "mul_w": 1.0, "mul_h": 1.0, "add_dy": 0.0, "lid_top_min": 0.0, "level_h": 0.0,
    "look": None, "scan": None, "saccade": None, "blink": None, "mouth": False,
}
TIMING_FIELDS = (
    "shape_tau_ms", "gaze_tau_ms", "level_attack_ms", "level_release_ms",
    "blink_close_ms", "blink_hold_ms", "blink_open_ms", "sleep_after_ms", "shake_ms",
)
COLOR_FIELDS = ("background", "eye", "glow", "accent", "text")

HEADER_NOTE = "Generado por tools/codegen/gen_expressions.py desde common/expressions.json. No editar a mano."


class SpecError(ValueError):
    """La especificacion de expresiones no es valida."""


def _check_range(name: str, value: float, low: float, high: float) -> None:
    if not low <= value <= high:
        raise SpecError(f"{name}={value} fuera de rango [{low}, {high}]")


def _check_pair(name: str, value: Any) -> tuple[int, int]:
    if not (isinstance(value, list) and len(value) == 2 and all(isinstance(v, int) for v in value)):
        raise SpecError(f"{name} debe ser [min_ms, max_ms] con enteros")
    low, high = value
    if low < 0 or high < low or high > 60000:
        raise SpecError(f"{name}={value} invalido")
    return low, high


def resolve_emotion(name: str, base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    unknown = set(override) - set(EMOTION_FIELDS)
    if unknown:
        raise SpecError(f"emocion '{name}': campos desconocidos {sorted(unknown)}")
    merged = {**base, **override}
    for field, kind in EMOTION_FIELDS.items():
        if field not in merged:
            raise SpecError(f"emocion '{name}': falta '{field}'")
        value = merged[field]
        if kind is float:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise SpecError(f"emocion '{name}': '{field}' debe ser numerico")
            merged[field] = float(value)
    for field in ("lid_top", "slant_in", "slant_out", "lid_bottom"):
        _check_range(f"{name}.{field}", merged[field], 0.0, 1.0)
    for field in ("look_x", "look_y"):
        _check_range(f"{name}.{field}", merged[field], -1.0, 1.0)
    for field in ("w", "h", "gap"):
        _check_range(f"{name}.{field}", merged[field], 4.0, 64.0)
    _check_range(f"{name}.r", merged["r"], 0.0, 32.0)
    merged["blink"] = list(_check_pair(f"{name}.blink", merged["blink"]))
    merged["saccade"] = list(_check_pair(f"{name}.saccade", merged["saccade"]))
    if merged["shape"] not in SHAPES:
        raise SpecError(f"emocion '{name}': forma '{merged['shape']}' no soportada")
    if not isinstance(merged["accent"], bool):
        raise SpecError(f"emocion '{name}': 'accent' debe ser booleano")
    return merged


def resolve_activity(name: str, override: dict[str, Any]) -> dict[str, Any]:
    unknown = set(override) - set(ACTIVITY_DEFAULTS)
    if unknown:
        raise SpecError(f"actividad '{name}': campos desconocidos {sorted(unknown)}")
    merged = {**ACTIVITY_DEFAULTS, **override}
    for field in ("mul_w", "mul_h", "add_dy", "lid_top_min", "level_h"):
        merged[field] = float(merged[field])
    _check_range(f"{name}.lid_top_min", merged["lid_top_min"], 0.0, 1.0)
    if merged["look"] is not None:
        look = merged["look"]
        if not (isinstance(look, list) and len(look) == 2):
            raise SpecError(f"actividad '{name}': 'look' debe ser [x, y]")
        merged["look"] = [float(look[0]), float(look[1])]
    if merged["scan"] is not None:
        scan = merged["scan"]
        if set(scan) != {"x", "y", "ms"}:
            raise SpecError(f"actividad '{name}': 'scan' requiere x, y, ms")
        low, high = _check_pair(f"{name}.scan.ms", scan["ms"])
        merged["scan"] = {"x": float(scan["x"]), "y": float(scan["y"]), "ms": [low, high]}
    for field in ("saccade", "blink"):
        if merged[field] is not None:
            merged[field] = list(_check_pair(f"{name}.{field}", merged[field]))
    if not isinstance(merged["mouth"], bool):
        raise SpecError(f"actividad '{name}': 'mouth' debe ser booleano")
    return merged


def load_spec(path: Path = SOURCE) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("version") != 1:
        raise SpecError("version de especificacion no soportada")
    base = raw["base"]
    emotions = {name: resolve_emotion(name, base, ov) for name, ov in raw["emotions"].items()}
    activities = {name: resolve_activity(name, ov) for name, ov in raw["activities"].items()}
    if next(iter(emotions)) != "neutral" or next(iter(activities)) != "idle":
        raise SpecError("la primera emocion debe ser 'neutral' y la primera actividad 'idle'")
    aliases = raw.get("aliases", {})
    for alias, target in aliases.items():
        if target not in emotions:
            raise SpecError(f"alias '{alias}' apunta a '{target}', que no existe")
        if alias in emotions or alias in activities:
            raise SpecError(f"alias '{alias}' choca con un nombre existente")
    timing = raw["timing"]
    for field in TIMING_FIELDS:
        if not isinstance(timing.get(field), int) or timing[field] < 0:
            raise SpecError(f"timing.{field} debe ser entero >= 0")
    colors = raw["colors"]
    for field in COLOR_FIELDS:
        value = colors.get(field, "")
        if not (isinstance(value, str) and len(value) == 7 and value.startswith("#")):
            raise SpecError(f"colors.{field} debe tener formato #RRGGBB")
        int(value[1:], 16)
    return {
        "reference": raw["reference"],
        "colors": colors,
        "timing": timing,
        "emotions": emotions,
        "activities": activities,
        "aliases": aliases,
    }


# ---------------------------------------------------------------- C++


def _f(value: float) -> str:
    text = f"{value:.4f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text + "f"


def _camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def _names_blob(names: list[str]) -> str:
    return "".join(f"{n}\\0" for n in names)


def render_cpp(spec: dict[str, Any]) -> str:
    emotions = spec["emotions"]
    activities = spec["activities"]
    aliases = spec["aliases"]
    timing = spec["timing"]
    colors = spec["colors"]
    ref = spec["reference"]
    out: list[str] = []
    out.append(f"// {HEADER_NOTE}")
    out.append("#pragma once")
    out.append("")
    out.append("#include <stdint.h>")
    out.append("#include <string.h>")
    out.append("")
    out.append("#if defined(__AVR__)")
    out.append("#include <avr/pgmspace.h>")
    out.append("#define GMINI_PROGMEM PROGMEM")
    out.append("#define GMINI_MEMCPY_P(dst, src, n) memcpy_P((dst), (src), (n))")
    out.append("#define GMINI_PGM_BYTE(p) pgm_read_byte(p)")
    out.append("#else")
    out.append("#define GMINI_PROGMEM")
    out.append("#define GMINI_MEMCPY_P(dst, src, n) memcpy((dst), (src), (n))")
    out.append("#define GMINI_PGM_BYTE(p) (*(const uint8_t*)(p))")
    out.append("#endif")
    out.append("")
    out.append("namespace gmini {")
    out.append("")
    out.append("enum class Emotion : uint8_t {")
    for name in emotions:
        out.append(f"  {_camel(name)},")
    out.append("  Count")
    out.append("};")
    out.append("")
    out.append("enum class Activity : uint8_t {")
    for name in activities:
        out.append(f"  {_camel(name)},")
    out.append("  Count")
    out.append("};")
    out.append("")
    out.append("enum EyeShapeKind : uint8_t { kShapeRound = 0, kShapeHeart = 1, kShapeCross = 2 };")
    out.append("")
    out.append("struct EmotionPreset {")
    out.append("  float w, h, r, gap, dy;")
    out.append("  float lidTop, slantIn, slantOut, lidBottom;")
    out.append("  float lookX, lookY, scaleL, scaleR;")
    out.append("  float bounce, shake, pulse, pulseHz;")
    out.append("  uint16_t blinkMin, blinkMax, saccadeMin, saccadeMax;")
    out.append("  uint8_t shape;")
    out.append("  uint8_t accent;")
    out.append("};")
    out.append("")
    out.append("struct ActivityPreset {")
    out.append("  float mulW, mulH, addDy, lidTopMin, levelH;")
    out.append("  float lookX, lookY;")
    out.append("  float scanX, scanY;")
    out.append("  uint16_t scanMin, scanMax;")
    out.append("  uint16_t saccadeMin, saccadeMax;")
    out.append("  uint16_t blinkMin, blinkMax;")
    out.append("  uint8_t hasLook, hasScan, hasSaccade, hasBlink, mouth;")
    out.append("};")
    out.append("")
    out.append("namespace presets {")
    out.append("")
    out.append(f"static const float kRefWidth = {_f(ref['width'])};")
    out.append(f"static const float kRefHeight = {_f(ref['height'])};")
    out.append("")
    for field in TIMING_FIELDS:
        out.append(f"static const uint32_t k{_camel(field)} = {timing[field]}u;")
    out.append("")
    for field in COLOR_FIELDS:
        out.append(f"static const uint32_t kColor{_camel(field)} = 0x{colors[field][1:].upper()}u;")
    out.append("")
    out.append(f"static const uint8_t kEmotionCount = {len(emotions)};")
    out.append(f"static const uint8_t kActivityCount = {len(activities)};")
    out.append(f"static const uint8_t kAliasCount = {len(aliases)};")
    out.append("")
    out.append("static const EmotionPreset kEmotions[kEmotionCount] GMINI_PROGMEM = {")
    for name, e in emotions.items():
        floats = ", ".join(_f(e[k]) for k in (
            "w", "h", "r", "gap", "dy", "lid_top", "slant_in", "slant_out", "lid_bottom",
            "look_x", "look_y", "scale_l", "scale_r", "bounce", "shake", "pulse", "pulse_hz"))
        ints = f"{e['blink'][0]}, {e['blink'][1]}, {e['saccade'][0]}, {e['saccade'][1]}"
        out.append(f"  /* {name} */ {{{floats}, {ints}, {SHAPES.index(e['shape'])}, {int(e['accent'])}}},")
    out.append("};")
    out.append("")
    out.append("static const ActivityPreset kActivities[kActivityCount] GMINI_PROGMEM = {")
    for name, a in activities.items():
        look = a["look"] or [0.0, 0.0]
        scan = a["scan"] or {"x": 0.0, "y": 0.0, "ms": [0, 0]}
        sac = a["saccade"] or [0, 0]
        blink = a["blink"] or [0, 0]
        parts = [
            _f(a["mul_w"]), _f(a["mul_h"]), _f(a["add_dy"]), _f(a["lid_top_min"]), _f(a["level_h"]),
            _f(look[0]), _f(look[1]), _f(scan["x"]), _f(scan["y"]),
            str(scan["ms"][0]), str(scan["ms"][1]), str(sac[0]), str(sac[1]), str(blink[0]), str(blink[1]),
            str(int(a["look"] is not None)), str(int(a["scan"] is not None)),
            str(int(a["saccade"] is not None)), str(int(a["blink"] is not None)), str(int(a["mouth"])),
        ]
        out.append(f"  /* {name} */ {{{', '.join(parts)}}},")
    out.append("};")
    out.append("")
    out.append(f'static const char kEmotionNames[] GMINI_PROGMEM = "{_names_blob(list(emotions))}";')
    out.append(f'static const char kActivityNames[] GMINI_PROGMEM = "{_names_blob(list(activities))}";')
    out.append(f'static const char kAliasNames[] GMINI_PROGMEM = "{_names_blob(list(aliases))}";')
    targets = ", ".join(str(list(emotions).index(t)) for t in aliases.values())
    out.append(f"static const uint8_t kAliasTargets[kAliasCount] GMINI_PROGMEM = {{{targets}}};")
    out.append("")
    out.append("}  // namespace presets")
    out.append("}  // namespace gmini")
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- Python


def render_py(spec: dict[str, Any]) -> str:
    def dump(value: Any) -> str:
        return pprint.pformat(value, indent=1, width=110, sort_dicts=False)

    out = [
        f'"""{HEADER_NOTE}"""',
        "",
        "# ruff: noqa: E501",
        "",
        f"REFERENCE = {dump(spec['reference'])}",
        "",
        f"COLORS = {dump(spec['colors'])}",
        "",
        f"TIMING = {dump(spec['timing'])}",
        "",
        f"EMOTIONS = {dump(spec['emotions'])}",
        "",
        f"ACTIVITIES = {dump(spec['activities'])}",
        "",
        f"ALIASES = {dump(spec['aliases'])}",
        "",
        "EMOTION_ORDER = tuple(EMOTIONS)",
        "ACTIVITY_ORDER = tuple(ACTIVITIES)",
        "",
    ]
    return "\n".join(out)


# ---------------------------------------------------------------- JavaScript


def render_js(spec: dict[str, Any]) -> str:
    body = json.dumps(spec, ensure_ascii=False, indent=2)
    return f"// {HEADER_NOTE}\n\"use strict\";\nwindow.GMINI_PRESETS = Object.freeze({body});\n"


def outputs(spec: dict[str, Any]) -> dict[Path, str]:
    return {OUT_CPP: render_cpp(spec), OUT_PY: render_py(spec), OUT_JS: render_js(spec)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="no escribe; falla si hay diferencias")
    args = parser.parse_args(argv)
    try:
        spec = load_spec()
    except (SpecError, KeyError, json.JSONDecodeError) as exc:
        print(f"expressions.json invalido: {exc}", file=sys.stderr)
        return 2
    stale = []
    for path, content in outputs(spec).items():
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
        print("Archivos desactualizados (ejecuta gen_expressions.py):", *stale, sep="\n  ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
