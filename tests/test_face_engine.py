"""Motor de ojos en Python: mismo comportamiento que la version C++ (test_eyes)."""

from __future__ import annotations

import pytest
from gmini_link import eye_presets
from gmini_link.face import (
    COLOR_ACCENT,
    COLOR_BACKGROUND,
    COLOR_EYE,
    COLOR_GLOW,
    EMOTIONS,
    EyesEngine,
    FaceLayout,
    draw_face,
    parse_activity,
    parse_emotion,
    settle,
)
from gmini_link.raster import BitmapCanvas


def run(engine: EyesEngine, start: int, ms: int, step: int = 10) -> int:
    t = start
    for _ in range(0, ms, step):
        t += step
        engine.update(t)
    return t


def quiet() -> tuple[EyesEngine, int]:
    e = EyesEngine(42)
    e.auto_blink = False
    e.saccades = False
    e.begin(0)
    return e, run(e, 0, 1500)


def test_names_and_aliases() -> None:
    assert parse_emotion("HAPPY") == "happy"
    assert parse_emotion(" curious ") == "surprised"
    assert parse_emotion("hap") is None
    assert parse_activity("speaking") == "speaking"
    assert parse_activity("happy") is None
    assert EMOTIONS[0] == "neutral" and len(EMOTIONS) == 9


def test_begin_opens_eyes_and_neutral_geometry() -> None:
    e = EyesEngine(7)
    e.auto_blink = False
    e.begin(0)
    assert e.frame.closure > 0.9
    e, _ = quiet()
    left, right = e.frame.eyes
    assert left.w == pytest.approx(36, abs=0.3)
    assert left.h == pytest.approx(36, abs=0.5)
    assert left.cx == pytest.approx(41, abs=0.5)
    assert right.cx == pytest.approx(87, abs=0.5)
    assert e.frame.closure < 0.02


@pytest.mark.parametrize("emotion", EMOTIONS)
def test_every_emotion_converges_to_its_preset(emotion: str) -> None:
    e, t = quiet()
    e.set_emotion(emotion)
    run(e, t, 1500)
    preset = eye_presets.EMOTIONS[emotion]
    eye = e.frame.eyes[1]
    assert eye.lid_bottom == pytest.approx(preset["lid_bottom"], abs=0.01)
    assert eye.slant_out == pytest.approx(preset["slant_out"], abs=0.01)
    assert e.frame.shape == preset["shape"]
    assert e.frame.accent is preset["accent"]


def test_blink_timeline_and_shape_change_hidden_by_blink() -> None:
    e, t = quiet()
    e.blink()
    t = run(e, t, 80)
    assert e.blinking and e.frame.closure > 0.9
    t = run(e, t, 250)
    assert not e.blinking and e.frame.closure < 0.01
    e.set_emotion("love")
    e.update(t)
    assert e.frame.shape == "round"  # todavia con los ojos abiertos
    run(e, t, 400)
    assert e.frame.shape == "heart"


def test_speaking_mouth_follows_level_and_stays_on_screen() -> None:
    e, t = quiet()
    e.set_activity("speaking")
    t = run(e, t, 600)
    quiet_width = e.frame.mouth_w
    e.set_level(1.0)
    run(e, t, 200)
    assert e.frame.mouth
    assert e.frame.mouth_w > quiet_width + 15
    assert e.frame.mouth_cy + e.frame.mouth_h / 2 <= 64


def test_sleeps_after_idle_and_wakes_on_activity() -> None:
    e, t = quiet()
    e.sleep_after_ms = 1000
    e.wake()
    t = run(e, t, 1200)
    assert e.asleep
    t = run(e, t, 5000)
    assert e.frame.closure > 0.85
    e.set_activity("listening")
    assert not e.asleep
    run(e, t, 1500)
    assert e.frame.closure < 0.05


def test_acting_scans_and_is_deterministic() -> None:
    a, b = EyesEngine(5), EyesEngine(5)
    a.set_activity("acting")
    b.set_activity("acting")
    xs = []
    for t in range(0, 3000, 10):
        a.update(t)
        b.update(t)
        xs.append(a.frame.eyes[0].cx)
    assert max(xs) - min(xs) > 10
    assert a.frame == b.frame


def test_raster_neutral_symmetric_and_error_uses_accent() -> None:
    e, t = quiet()
    canvas = BitmapCanvas(128, 64)
    draw_face(e.frame, canvas, FaceLayout.fit(128, 64))
    assert 2300 < canvas.count_lit() < 2650
    left = sum(canvas.at(x, y) != COLOR_BACKGROUND for y in range(64) for x in range(64))
    right = sum(canvas.at(x, y) != COLOR_BACKGROUND for y in range(64) for x in range(64, 128))
    assert abs(left - right) <= 40
    e.set_emotion("error")
    run(e, t, 1500)
    canvas.clear()
    draw_face(e.frame, canvas, FaceLayout.fit(128, 64, glow=True))
    assert canvas.count(COLOR_ACCENT) > 200
    assert canvas.count(COLOR_EYE) == 0


def test_glow_and_png_export() -> None:
    frame = settle(EyesEngine(3), "happy")
    canvas = BitmapCanvas(128, 64)
    draw_face(frame, canvas, FaceLayout.fit(128, 64, glow=True))
    assert canvas.count(COLOR_GLOW) > 30
    png = canvas.to_png({COLOR_EYE: (63, 224, 255), COLOR_GLOW: (11, 74, 92)}, scale=2)
    assert png.startswith(b"\x89PNG\r\n\x1a\n") and len(png) > 200
