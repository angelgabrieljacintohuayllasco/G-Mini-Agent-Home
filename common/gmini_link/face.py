"""Motor de ojos de G-Mini Home (port de firmware/libraries/GMiniEyes).

Mismo comportamiento que la version C++: presets generados desde
common/expressions.json, suavizado exponencial, parpadeo con curvas de
aceleracion, movimientos de mirada y sueno automatico. El dibujo se hace sobre
cualquier objeto que cumpla FaceCanvas (pygame, SVG o un mapa de bits).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

from . import eye_presets as presets

REF_W = float(presets.REFERENCE["width"])
REF_H = float(presets.REFERENCE["height"])

EMOTIONS: tuple[str, ...] = presets.EMOTION_ORDER
ACTIVITIES: tuple[str, ...] = presets.ACTIVITY_ORDER
SHAPES = ("round", "heart", "cross")

COLOR_BACKGROUND = 0
COLOR_EYE = 1
COLOR_ACCENT = 2
COLOR_GLOW = 3
COLOR_TEXT = 4

_BOUNCE_HZ = 1.6
_SHAKE_HZ = 9.0
_BREATH_HZ = 0.25
_NEVER_MS = 0x7FFFFFFF


def parse_emotion(name: str | None) -> str | None:
    """Devuelve el nombre canonico de la emocion (acepta alias) o None."""
    if not name:
        return None
    key = name.strip().lower()
    if key in presets.EMOTIONS:
        return key
    return presets.ALIASES.get(key)


def parse_activity(name: str | None) -> str | None:
    if not name:
        return None
    key = name.strip().lower()
    return key if key in presets.ACTIVITIES else None


def _smoothing(dt_ms: float, tau_ms: float) -> float:
    # Aproximacion racional de 1 - exp(-dt/tau), igual que el firmware.
    return 1.0 if tau_ms <= 0 else dt_ms / (tau_ms + dt_ms)


def _fast_sin(x: float) -> float:
    """Seno aproximado identico al del firmware (error maximo ~0,1 %)."""
    x -= 2 * math.pi * math.floor((x + math.pi) / (2 * math.pi))
    y = 1.27323954 * x - 0.405284735 * x * abs(x)
    return 0.225 * (y * abs(y) - y) + y


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


@dataclass
class EyeGeom:
    cx: float = 0.0
    cy: float = 0.0
    w: float = 0.0
    h: float = 0.0
    r: float = 0.0
    lid_top: float = 0.0
    slant_in: float = 0.0
    slant_out: float = 0.0
    lid_bottom: float = 0.0


@dataclass
class FaceFrame:
    eyes: tuple[EyeGeom, EyeGeom] = field(default_factory=lambda: (EyeGeom(), EyeGeom()))
    shape: str = "round"
    accent: bool = False
    mouth: bool = False
    mouth_cx: float = 0.0
    mouth_cy: float = 0.0
    mouth_w: float = 0.0
    mouth_h: float = 0.0
    closure: float = 0.0


@dataclass
class _Shape:
    w: float
    h: float
    r: float
    gap: float
    dy: float
    lid_top: float
    slant_in: float
    slant_out: float
    lid_bottom: float
    look_x: float
    look_y: float
    scale_l: float
    scale_r: float

    def approach(self, target: _Shape, k: float) -> None:
        for name in self.__dataclass_fields__:
            cur = getattr(self, name)
            setattr(self, name, cur + (getattr(target, name) - cur) * k)


class EyesEngine:
    """Maquina de estados de la cara. update() se llama en cada cuadro."""

    def __init__(self, seed: int = 0x2545F491) -> None:
        self._rng = (seed or 0x2545F491) & 0xFFFFFFFF
        self.emotion = "neutral"
        self.activity = "idle"
        self.sleep_after_ms = presets.TIMING["sleep_after_ms"]
        self.auto_blink = True
        self.saccades = True
        self._started = False
        self._blinking = False
        self._force_blink = False
        self._manual_look = False
        self._asleep = False
        self._manual = (0.0, 0.0)
        self._gaze = [0.0, 0.0]
        self._sac = [0.0, 0.0]
        self._level = 0.0
        self._level_target = 0.0
        self._sleep_closure = 0.0
        self._phase = 0.0
        self._last_ms = 0
        self._next_blink_ms = 0
        self._next_saccade_ms = 0
        self._blink_start_ms = 0
        self._emotion_since_ms = 0
        self._last_wake_ms = 0
        self._scan_sign = 1
        self._shape = "round"
        self._pending_shape: str | None = None
        self.frame = FaceFrame()
        self._apply_presets(immediate=True)
        self._cur = _Shape(**vars(self._target))

    # ------------------------------------------------------------ propiedades

    @property
    def asleep(self) -> bool:
        return self._asleep

    @property
    def blinking(self) -> bool:
        return self._blinking

    @property
    def level(self) -> float:
        return self._level

    # ------------------------------------------------------------ azar

    def _rand_range(self, lo: int, hi: int) -> int:
        x = self._rng
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self._rng = x & 0xFFFFFFFF
        if hi <= lo:
            return lo
        return lo + self._rng % (hi - lo + 1)

    def _rand_signed(self) -> float:
        return self._rand_range(0, 2000) / 1000.0 - 1.0

    # ------------------------------------------------------------ control

    def begin(self, now_ms: int) -> None:
        self._started = True
        self._last_ms = now_ms
        self._last_wake_ms = now_ms
        self._emotion_since_ms = now_ms
        self._sleep_closure = 1.0
        self._schedule_blink(now_ms)
        self._next_saccade_ms = now_ms + 600
        self._build_frame(now_ms, 0.0)

    def set_emotion(self, name: str) -> bool:
        emotion = parse_emotion(name)
        if emotion is None:
            return False
        self.wake()
        if emotion == self.emotion:
            return True
        self.emotion = emotion
        self._emotion_since_ms = self._last_ms
        self._sac = [0.0, 0.0]
        self._apply_presets(immediate=False)
        self._next_saccade_ms = self._last_ms + self._sac_min
        return True

    def set_activity(self, name: str) -> bool:
        activity = parse_activity(name)
        if activity is None:
            return False
        self.wake()
        if activity == self.activity:
            return True
        self.activity = activity
        self._apply_presets(immediate=False)
        self._next_saccade_ms = self._last_ms
        if activity not in ("speaking", "listening"):
            self._level_target = 0.0
        return True

    def set_level(self, level: float) -> None:
        self._level_target = _clamp(float(level), 0.0, 1.0)

    def look_at(self, x: float, y: float) -> None:
        self._manual_look = True
        self._manual = (_clamp(x, -1.0, 1.0), _clamp(y, -1.0, 1.0))

    def release_look(self) -> None:
        self._manual_look = False

    def blink(self) -> None:
        self._force_blink = True

    def wake(self) -> None:
        self._last_wake_ms = self._last_ms
        self._asleep = False

    def sleep(self) -> None:
        self._asleep = True

    # ------------------------------------------------------------ presets

    def _apply_presets(self, immediate: bool) -> None:
        e = presets.EMOTIONS[self.emotion]
        a = presets.ACTIVITIES[self.activity]
        self._target = _Shape(
            w=e["w"] * a["mul_w"],
            h=e["h"] * a["mul_h"],
            r=e["r"],
            gap=e["gap"],
            dy=e["dy"] + a["add_dy"],
            lid_top=max(e["lid_top"], a["lid_top_min"]),
            slant_in=e["slant_in"],
            slant_out=e["slant_out"],
            lid_bottom=e["lid_bottom"],
            look_x=e["look_x"],
            look_y=e["look_y"],
            scale_l=e["scale_l"],
            scale_r=e["scale_r"],
        )
        self._bounce = e["bounce"]
        self._shake = e["shake"]
        self._pulse = e["pulse"]
        self._pulse_hz = e["pulse_hz"]
        self._level_h = a["level_h"]
        self._mouth = a["mouth"]
        self._accent = e["accent"]
        blink = a["blink"] if a["blink"] is not None else e["blink"]
        sac = a["saccade"] if a["saccade"] is not None else e["saccade"]
        self._blink_min, self._blink_max = blink
        self._sac_min, self._sac_max = sac
        self._has_look = a["look"] is not None
        self._act_look = tuple(a["look"]) if a["look"] is not None else (0.0, 0.0)
        scan = a["scan"]
        if scan is not None:
            self._scan_min, self._scan_max = scan["ms"]
            self._scan_x, self._scan_y = scan["x"], scan["y"]
        else:
            self._scan_min = self._scan_max = 0
            self._scan_x = self._scan_y = 0.0
        if immediate:
            self._shape = e["shape"]
            self._pending_shape = None
        elif e["shape"] != self._shape:
            # El cambio de forma ocurre con los ojos cerrados.
            self._pending_shape = e["shape"]
            self._force_blink = True
        else:
            self._pending_shape = None

    # ------------------------------------------------------------ parpadeo

    def _start_blink(self, now: int) -> None:
        self._blinking = True
        self._force_blink = False
        self._blink_start_ms = now

    def _schedule_blink(self, now: int) -> None:
        if self._blink_max == 0:
            self._next_blink_ms = now + _NEVER_MS
            return
        if self._rand_range(0, 99) < 12:
            self._next_blink_ms = now + 170
        else:
            self._next_blink_ms = now + self._rand_range(self._blink_min, self._blink_max)

    def _blink_closure(self, now: int) -> float:
        close = presets.TIMING["blink_close_ms"]
        hold = presets.TIMING["blink_hold_ms"]
        opening = presets.TIMING["blink_open_ms"]
        t = now - self._blink_start_ms
        if t < close:
            p = t / close
            return p * p
        if t < close + hold:
            return 1.0
        if t < close + hold + opening:
            q = 1.0 - (t - close - hold) / opening
            return q * q
        self._blinking = False
        self._schedule_blink(now)
        return 0.0

    # ------------------------------------------------------------ mirada

    def _update_gaze(self, now: int, k: float) -> None:
        if self._manual_look:
            tx, ty = self._manual
        elif self._scan_max > 0:
            if now >= self._next_saccade_ms:
                self._scan_sign = -self._scan_sign
                self._next_saccade_ms = now + self._rand_range(self._scan_min, self._scan_max)
            tx, ty = self._scan_x * self._scan_sign, self._scan_y
        elif self._has_look:
            tx, ty = self._act_look
        else:
            if not self.saccades or self._sac_max == 0 or self._asleep:
                self._sac = [0.0, 0.0]
            elif now >= self._next_saccade_ms:
                if self._rand_range(0, 99) < 35:
                    self._sac = [0.0, 0.0]
                else:
                    self._sac = [self._rand_signed() * 0.6, self._rand_signed() * 0.35]
                self._next_saccade_ms = now + self._rand_range(self._sac_min, self._sac_max)
            tx = _clamp(self._cur.look_x + self._sac[0], -1.0, 1.0)
            ty = _clamp(self._cur.look_y + self._sac[1], -1.0, 1.0)
        self._gaze[0] += (tx - self._gaze[0]) * k
        self._gaze[1] += (ty - self._gaze[1]) * k

    # ------------------------------------------------------------ cuadro

    def update(self, now_ms: int) -> FaceFrame:
        if not self._started:
            self.begin(now_ms)
        dt = float(min(max(now_ms - self._last_ms, 0), 100))
        self._last_ms = now_ms

        if (
            not self._asleep
            and self.sleep_after_ms > 0
            and self.activity == "idle"
            and now_ms - self._last_wake_ms >= self.sleep_after_ms
        ):
            self._asleep = True

        timing = presets.TIMING
        self._cur.approach(self._target, _smoothing(dt, timing["shape_tau_ms"]))

        tau_level = timing["level_attack_ms"] if self._level_target > self._level else timing["level_release_ms"]
        self._level += (self._level_target - self._level) * _smoothing(dt, tau_level)

        sleep_target = 1.0 if self._asleep else 0.0
        self._sleep_closure += (sleep_target - self._sleep_closure) * _smoothing(
            dt, 900.0 if self._asleep else 220.0
        )

        self._update_gaze(now_ms, _smoothing(dt, timing["gaze_tau_ms"]))

        if not self._blinking and (
            self._force_blink
            or (self.auto_blink and self._blink_max > 0 and not self._asleep and now_ms >= self._next_blink_ms)
        ):
            self._start_blink(now_ms)
        blink = self._blink_closure(now_ms) if self._blinking else 0.0
        if self._pending_shape is not None and (not self._blinking or blink > 0.9):
            self._shape = self._pending_shape
            self._pending_shape = None

        self._phase += dt * 0.001
        if self._phase >= 1000.0:
            self._phase -= 1000.0
        self._build_frame(now_ms, blink)
        return self.frame

    def _build_frame(self, now: int, blink: float) -> None:
        cur = self._cur
        bounce_off = -self._bounce * abs(_fast_sin(math.pi * _BOUNCE_HZ * self._phase))
        shake_env = 0.0
        since = now - self._emotion_since_ms
        if self._shake > 0 and since < presets.TIMING["shake_ms"]:
            shake_env = 1.0 - since / presets.TIMING["shake_ms"]
        shake_off = self._shake * shake_env * _fast_sin(2 * math.pi * _SHAKE_HZ * self._phase)
        pulse_mul = 1.0 + self._pulse * _fast_sin(2 * math.pi * self._pulse_hz * self._phase)
        breath = self._sleep_closure * 0.8 * _fast_sin(2 * math.pi * _BREATH_HZ * self._phase)

        w = cur.w * pulse_mul
        h = cur.h * pulse_mul * (1.0 + self._level_h * self._level)
        gap = cur.gap
        max_dx = max(0.0, (REF_W - (2.0 * w + gap)) * 0.5 - 2.0)
        max_dy = max(0.0, (REF_H - h) * 0.5 - 2.0)
        cx = REF_W * 0.5 + self._gaze[0] * max_dx + shake_off
        cy = REF_H * 0.5 + self._gaze[1] * max_dy + cur.dy + bounce_off + breath
        curious = 0.08 * self._gaze[0]
        closure = max(blink, self._sleep_closure * 0.93)

        eyes = []
        for side, scale in ((-1.0, cur.scale_l * (1.0 - curious)), (1.0, cur.scale_r * (1.0 + curious))):
            eye_h = h * scale
            vis = max(2.0, eye_h * (1.0 - closure))
            eyes.append(
                EyeGeom(
                    cx=cx + side * (w + gap) * 0.5,
                    cy=cy,
                    w=w,
                    h=vis,
                    r=min(cur.r, min(w, vis) * 0.5),
                    lid_top=cur.lid_top,
                    slant_in=cur.slant_in,
                    slant_out=cur.slant_out,
                    lid_bottom=cur.lid_bottom,
                )
            )
        frame = FaceFrame(eyes=(eyes[0], eyes[1]), shape=self._shape, accent=self._accent, closure=closure)
        if self._mouth:
            frame.mouth = True
            frame.mouth_w = 12.0 + 22.0 * self._level
            frame.mouth_h = 3.0 + 8.0 * self._level
            frame.mouth_cx = REF_W * 0.5 + self._gaze[0] * max_dx * 0.5
            my = cy + h * 0.5 + 5.0 + frame.mouth_h * 0.5
            frame.mouth_cy = min(my, REF_H - frame.mouth_h * 0.5 - 1.0)
        self.frame = frame


# ---------------------------------------------------------------- dibujo


class FaceCanvas(Protocol):
    def fill_rect(self, x: float, y: float, w: float, h: float, color: int) -> None: ...

    def fill_round_rect(self, x: float, y: float, w: float, h: float, r: float, color: int) -> None: ...

    def fill_circle(self, cx: float, cy: float, r: float, color: int) -> None: ...

    def fill_triangle(
        self, x0: float, y0: float, x1: float, y1: float, x2: float, y2: float, color: int
    ) -> None: ...


@dataclass
class FaceLayout:
    scale: float = 1.0
    origin_x: float = 0.0
    origin_y: float = 0.0
    mirror_x: bool = False
    glow: bool = False
    snap: bool = True  # redondear a pixeles enteros (como el firmware)

    @classmethod
    def fit(cls, width: float, height: float, fill: float = 1.0, **kwargs: object) -> FaceLayout:
        scale = min(width / REF_W, height / REF_H) * fill
        return cls(
            scale=scale,
            origin_x=(width - REF_W * scale) * 0.5,
            origin_y=(height - REF_H * scale) * 0.5,
            **kwargs,  # type: ignore[arg-type]
        )


class _Mapper:
    def __init__(self, layout: FaceLayout) -> None:
        self.l = layout

    def _snap(self, v: float) -> float:
        return float(math.floor(v + 0.5)) if self.l.snap else v

    def x(self, v: float) -> float:
        m = (REF_W - v) if self.l.mirror_x else v
        return self._snap(self.l.origin_x + m * self.l.scale)

    def y(self, v: float) -> float:
        return self._snap(self.l.origin_y + v * self.l.scale)

    def length(self, v: float) -> float:
        return self._snap(v * self.l.scale)

    def rect(self, c: FaceCanvas, x0: float, y0: float, w: float, h: float, color: int) -> None:
        if w <= 0 or h <= 0:
            return
        ax, bx = sorted((self.x(x0), self.x(x0 + w)))
        ay, by = self.y(y0), self.y(y0 + h)
        if bx - ax <= 0 or by - ay <= 0:
            return
        c.fill_rect(ax, ay, bx - ax, by - ay, color)

    def round_rect(self, c: FaceCanvas, x0: float, y0: float, w: float, h: float, r: float, color: int) -> None:
        ax, bx = sorted((self.x(x0), self.x(x0 + w)))
        ay, by = self.y(y0), self.y(y0 + h)
        pw, ph = bx - ax, by - ay
        if pw <= 0 or ph <= 0:
            return
        pr = self.length(r)
        max_r = (min(pw, ph) // 2 - 1) if self.l.snap else min(pw, ph) / 2
        pr = min(pr, max_r)
        if pr < 1:
            c.fill_rect(ax, ay, pw, ph, color)
        else:
            c.fill_round_rect(ax, ay, pw, ph, pr, color)

    def circle(self, c: FaceCanvas, cx: float, cy: float, r: float, color: int) -> None:
        pr = self.length(r)
        if pr < 1:
            return
        c.fill_circle(self.x(cx), self.y(cy), pr, color)

    def triangle(self, c: FaceCanvas, pts: tuple[float, ...], color: int) -> None:
        x0, y0, x1, y1, x2, y2 = pts
        c.fill_triangle(self.x(x0), self.y(y0), self.x(x1), self.y(y1), self.x(x2), self.y(y2), color)


def _draw_round_eye(g: EyeGeom, inner_on_right: bool, color: int, c: FaceCanvas, m: _Mapper, glow: bool) -> None:
    x = g.cx - g.w * 0.5
    y = g.cy - g.h * 0.5
    glow_pad = 1.6 if glow else 0.0
    if glow:
        m.round_rect(c, x - glow_pad, y - glow_pad, g.w + 2 * glow_pad, g.h + 2 * glow_pad, g.r + glow_pad, COLOR_GLOW)
    m.round_rect(c, x, y, g.w, g.h, g.r, color)

    pad = glow_pad + 1.0 / max(m.l.scale, 0.25)
    top_px = g.lid_top * g.h
    if g.lid_top > 0.001:
        m.rect(c, x - pad, y - pad, g.w + 2 * pad, top_px + pad, COLOR_BACKGROUND)
    inner_x = x + g.w + pad if inner_on_right else x - pad
    outer_x = x - pad if inner_on_right else x + g.w + pad
    # Parpado inclinado: cuadrilatero desde el borde superior hasta la diagonal.
    if g.slant_in > 0.001:
        low = y + top_px + g.slant_in * g.h
        m.triangle(c, (inner_x, y - pad, outer_x, y - pad, outer_x, y + top_px), COLOR_BACKGROUND)
        m.triangle(c, (inner_x, y - pad, outer_x, y + top_px, inner_x, low), COLOR_BACKGROUND)
    if g.slant_out > 0.001:
        low = y + top_px + g.slant_out * g.h
        m.triangle(c, (outer_x, y - pad, inner_x, y - pad, inner_x, y + top_px), COLOR_BACKGROUND)
        m.triangle(c, (outer_x, y - pad, inner_x, y + top_px, outer_x, low), COLOR_BACKGROUND)
    if g.lid_bottom > 0.001:
        radius = 0.62 * g.w + glow_pad
        m.circle(c, g.cx, y + g.h - g.lid_bottom * g.h + radius, radius, COLOR_BACKGROUND)


def _draw_heart(g: EyeGeom, color: int, c: FaceCanvas, m: _Mapper) -> None:
    s = min(g.w, g.h * 1.05)
    lobe_r = 0.27 * s
    lobe_dx = 0.23 * g.w
    lobe_y = g.cy - 0.17 * g.h
    m.circle(c, g.cx - lobe_dx, lobe_y, lobe_r, color)
    m.circle(c, g.cx + lobe_dx, lobe_y, lobe_r, color)
    m.triangle(
        c,
        (g.cx - lobe_dx - lobe_r * 0.97, lobe_y + lobe_r * 0.25,
         g.cx + lobe_dx + lobe_r * 0.97, lobe_y + lobe_r * 0.25,
         g.cx, g.cy + 0.5 * g.h),
        color,
    )


def _draw_cross(g: EyeGeom, color: int, c: FaceCanvas, m: _Mapper) -> None:
    s = min(g.w, g.h)
    half = 0.46 * s
    t = 0.12 * s
    for dy in (1.0, -1.0):
        x1, y1 = g.cx - half, g.cy - half * dy
        x2, y2 = g.cx + half, g.cy + half * dy
        nx, ny = -dy * t * 0.7071, t * 0.7071
        m.triangle(c, (x1 + nx, y1 + ny, x2 + nx, y2 + ny, x2 - nx, y2 - ny), color)
        m.triangle(c, (x1 + nx, y1 + ny, x2 - nx, y2 - ny, x1 - nx, y1 - ny), color)


def draw_face(frame: FaceFrame, canvas: FaceCanvas, layout: FaceLayout) -> None:
    m = _Mapper(layout)
    color = COLOR_ACCENT if frame.accent else COLOR_EYE
    for index, g in enumerate(frame.eyes):
        inner_on_right = index == 0
        if frame.shape == "heart" and frame.closure < 0.6:
            _draw_heart(g, color, canvas, m)
        elif frame.shape == "cross" and frame.closure < 0.6:
            _draw_cross(g, color, canvas, m)
        else:
            _draw_round_eye(g, inner_on_right, color, canvas, m, layout.glow)
    if frame.mouth:
        m.round_rect(
            canvas,
            frame.mouth_cx - frame.mouth_w * 0.5,
            frame.mouth_cy - frame.mouth_h * 0.5,
            frame.mouth_w,
            frame.mouth_h,
            frame.mouth_h * 0.5,
            color,
        )


def settle(engine: EyesEngine, emotion: str = "neutral", activity: str = "idle", level: float = 0.0,
           ms: int = 1500) -> FaceFrame:
    """Lleva el motor a un estado estable (para vistas previas y pruebas)."""
    engine.auto_blink = False
    engine.saccades = False
    engine.set_emotion(emotion)
    engine.set_activity(activity)
    engine.set_level(level)
    now = engine._last_ms  # noqa: SLF001 - continuidad temporal del motor
    for _ in range(0, ms, 10):
        now += 10
        engine.update(now)
    return engine.frame
