"""Generador de presets: la fuente unica y los archivos generados no se separan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from codegen import gen_expressions as gen

ROOT = Path(__file__).resolve().parents[1]


def test_generated_files_are_up_to_date() -> None:
    assert gen.main(["--check"]) == 0


def test_python_presets_match_the_spec() -> None:
    from gmini_link import eye_presets

    spec = gen.load_spec()
    assert spec["emotions"] == eye_presets.EMOTIONS
    assert spec["activities"] == eye_presets.ACTIVITIES
    assert spec["aliases"] == eye_presets.ALIASES


def test_cpp_header_lists_every_emotion_in_order() -> None:
    header = (ROOT / "firmware/libraries/GMiniEyes/src/GMiniEyesPresets.h").read_text(encoding="utf-8")
    spec = gen.load_spec()
    positions = [header.index(f"/* {name} */") for name in spec["emotions"]]
    assert positions == sorted(positions)
    assert f"kEmotionCount = {len(spec['emotions'])}" in header


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda s: s["emotions"]["happy"].update(lid_bottom=1.5), "fuera de rango"),
        (lambda s: s["emotions"]["happy"].update(shape="star"), "no soportada"),
        (lambda s: s["emotions"]["happy"].update(sparkle=1), "desconocidos"),
        (lambda s: s["aliases"].update(joy="ecstatic"), "no existe"),
        (lambda s: s["timing"].update(blink_close_ms=-1), "timing.blink_close_ms"),
        (lambda s: s["colors"].update(eye="cyan"), "colors.eye"),
    ],
)
def test_spec_validation(tmp_path, mutate, message: str) -> None:
    raw = json.loads((ROOT / "common/expressions.json").read_text(encoding="utf-8"))
    mutate(raw)
    path = tmp_path / "expressions.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(gen.SpecError, match=message):
        gen.load_spec(path)
