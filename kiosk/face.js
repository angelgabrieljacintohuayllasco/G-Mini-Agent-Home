// Motor de ojos de G-Mini Home para el navegador (port de common/gmini_link/face.py).
// Lee los presets de presets.js (generado desde common/expressions.json).
"use strict";

(function (global) {
  const P = global.GMINI_PRESETS;
  const REF_W = P.reference.width;
  const REF_H = P.reference.height;
  const T = P.timing;
  const SHAPE_KEYS = ["w", "h", "r", "gap", "dy", "lid_top", "slant_in", "slant_out", "lid_bottom",
    "look_x", "look_y", "scale_l", "scale_r"];
  const BOUNCE_HZ = 1.6;
  const SHAKE_HZ = 9.0;
  const BREATH_HZ = 0.25;

  const clamp = (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v);
  const smoothing = (dt, tau) => (tau <= 0 ? 1 : dt / (tau + dt));
  function fastSin(x) {
    x -= 2 * Math.PI * Math.floor((x + Math.PI) / (2 * Math.PI));
    const y = 1.27323954 * x - 0.405284735 * x * Math.abs(x);
    return 0.225 * (y * Math.abs(y) - y) + y;
  }

  function parseEmotion(name) {
    const key = String(name || "").trim().toLowerCase();
    if (P.emotions[key]) return key;
    return P.aliases[key] || null;
  }

  function parseActivity(name) {
    const key = String(name || "").trim().toLowerCase();
    return P.activities[key] ? key : null;
  }

  class Eyes {
    constructor(seed) {
      this.rng = (seed >>> 0) || 0x2545f491;
      this.emotion = "neutral";
      this.activity = "idle";
      this.sleepAfterMs = T.sleep_after_ms;
      this.started = false;
      this.blinking = false;
      this.forceBlink = false;
      this.asleep = false;
      this.gaze = [0, 0];
      this.sac = [0, 0];
      this.level = 0;
      this.levelTarget = 0;
      this.sleepClosure = 0;
      this.phase = 0;
      this.lastMs = 0;
      this.nextBlinkMs = 0;
      this.nextSaccadeMs = 0;
      this.blinkStartMs = 0;
      this.emotionSinceMs = 0;
      this.lastWakeMs = 0;
      this.scanSign = 1;
      this.shape = "round";
      this.pendingShape = null;
      this.frame = null;
      this.applyPresets(true);
      this.cur = Object.assign({}, this.target);
    }

    rand(lo, hi) {
      let x = this.rng;
      x ^= x << 13; x >>>= 0;
      x ^= x >>> 17;
      x ^= x << 5; x >>>= 0;
      this.rng = x;
      return hi <= lo ? lo : lo + (x % (hi - lo + 1));
    }

    randSigned() { return this.rand(0, 2000) / 1000 - 1; }

    applyPresets(immediate) {
      const e = P.emotions[this.emotion];
      const a = P.activities[this.activity];
      const t = {};
      for (const k of SHAPE_KEYS) t[k] = e[k];
      t.w *= a.mul_w;
      t.h *= a.mul_h;
      t.dy += a.add_dy;
      t.lid_top = Math.max(t.lid_top, a.lid_top_min);
      this.target = t;
      this.bounce = e.bounce;
      this.shake = e.shake;
      this.pulse = e.pulse;
      this.pulseHz = e.pulse_hz;
      this.levelH = a.level_h;
      this.mouth = a.mouth;
      this.accent = e.accent;
      [this.blinkMin, this.blinkMax] = a.blink || e.blink;
      [this.sacMin, this.sacMax] = a.saccade || e.saccade;
      this.actLook = a.look;
      this.scan = a.scan;
      if (immediate) {
        this.shape = e.shape;
        this.pendingShape = null;
      } else if (e.shape !== this.shape) {
        this.pendingShape = e.shape;
        this.forceBlink = true;
      } else {
        this.pendingShape = null;
      }
    }

    begin(now) {
      this.started = true;
      this.lastMs = now;
      this.lastWakeMs = now;
      this.emotionSinceMs = now;
      this.sleepClosure = 1;
      this.scheduleBlink(now);
      this.nextSaccadeMs = now + 600;
    }

    setEmotion(name) {
      const e = parseEmotion(name);
      if (!e) return false;
      this.wake();
      if (e === this.emotion) return true;
      this.emotion = e;
      this.emotionSinceMs = this.lastMs;
      this.sac = [0, 0];
      this.applyPresets(false);
      this.nextSaccadeMs = this.lastMs + this.sacMin;
      return true;
    }

    setActivity(name) {
      const a = parseActivity(name);
      if (!a) return false;
      this.wake();
      if (a === this.activity) return true;
      this.activity = a;
      this.applyPresets(false);
      this.nextSaccadeMs = this.lastMs;
      if (a !== "speaking" && a !== "listening") this.levelTarget = 0;
      return true;
    }

    setLevel(v) { this.levelTarget = clamp(+v || 0, 0, 1); }
    wake() { this.lastWakeMs = this.lastMs; this.asleep = false; }

    scheduleBlink(now) {
      if (this.blinkMax === 0) { this.nextBlinkMs = now + 0x7fffffff; return; }
      this.nextBlinkMs = now + (this.rand(0, 99) < 12 ? 170 : this.rand(this.blinkMin, this.blinkMax));
    }

    blinkClosure(now) {
      const t = now - this.blinkStartMs;
      if (t < T.blink_close_ms) { const p = t / T.blink_close_ms; return p * p; }
      if (t < T.blink_close_ms + T.blink_hold_ms) return 1;
      if (t < T.blink_close_ms + T.blink_hold_ms + T.blink_open_ms) {
        const q = 1 - (t - T.blink_close_ms - T.blink_hold_ms) / T.blink_open_ms;
        return q * q;
      }
      this.blinking = false;
      this.scheduleBlink(now);
      return 0;
    }

    updateGaze(now, k) {
      let tx;
      let ty;
      if (this.scan) {
        if (now >= this.nextSaccadeMs) {
          this.scanSign = -this.scanSign;
          this.nextSaccadeMs = now + this.rand(this.scan.ms[0], this.scan.ms[1]);
        }
        tx = this.scan.x * this.scanSign;
        ty = this.scan.y;
      } else if (this.actLook) {
        [tx, ty] = this.actLook;
      } else {
        if (this.sacMax === 0 || this.asleep) {
          this.sac = [0, 0];
        } else if (now >= this.nextSaccadeMs) {
          this.sac = this.rand(0, 99) < 35 ? [0, 0] : [this.randSigned() * 0.6, this.randSigned() * 0.35];
          this.nextSaccadeMs = now + this.rand(this.sacMin, this.sacMax);
        }
        tx = clamp(this.cur.look_x + this.sac[0], -1, 1);
        ty = clamp(this.cur.look_y + this.sac[1], -1, 1);
      }
      this.gaze[0] += (tx - this.gaze[0]) * k;
      this.gaze[1] += (ty - this.gaze[1]) * k;
    }

    update(now) {
      if (!this.started) this.begin(now);
      const dt = clamp(now - this.lastMs, 0, 100);
      this.lastMs = now;
      if (!this.asleep && this.sleepAfterMs > 0 && this.activity === "idle" &&
          now - this.lastWakeMs >= this.sleepAfterMs) this.asleep = true;
      const ks = smoothing(dt, T.shape_tau_ms);
      for (const key of SHAPE_KEYS) this.cur[key] += (this.target[key] - this.cur[key]) * ks;
      const tau = this.levelTarget > this.level ? T.level_attack_ms : T.level_release_ms;
      this.level += (this.levelTarget - this.level) * smoothing(dt, tau);
      const sleepTarget = this.asleep ? 1 : 0;
      this.sleepClosure += (sleepTarget - this.sleepClosure) * smoothing(dt, this.asleep ? 900 : 220);
      this.updateGaze(now, smoothing(dt, T.gaze_tau_ms));
      if (!this.blinking && (this.forceBlink ||
          (this.blinkMax > 0 && !this.asleep && now >= this.nextBlinkMs))) {
        this.blinking = true;
        this.forceBlink = false;
        this.blinkStartMs = now;
      }
      const blink = this.blinking ? this.blinkClosure(now) : 0;
      if (this.pendingShape && (!this.blinking || blink > 0.9)) {
        this.shape = this.pendingShape;
        this.pendingShape = null;
      }
      this.phase = (this.phase + dt * 0.001) % 1000;
      this.frame = this.buildFrame(now, blink);
      return this.frame;
    }

    buildFrame(now, blink) {
      const c = this.cur;
      const bounceOff = -this.bounce * Math.abs(fastSin(Math.PI * BOUNCE_HZ * this.phase));
      const since = now - this.emotionSinceMs;
      const shakeEnv = this.shake > 0 && since < T.shake_ms ? 1 - since / T.shake_ms : 0;
      const shakeOff = this.shake * shakeEnv * fastSin(2 * Math.PI * SHAKE_HZ * this.phase);
      const pulseMul = 1 + this.pulse * fastSin(2 * Math.PI * this.pulseHz * this.phase);
      const breath = this.sleepClosure * 0.8 * fastSin(2 * Math.PI * BREATH_HZ * this.phase);
      const w = c.w * pulseMul;
      const h = c.h * pulseMul * (1 + this.levelH * this.level);
      const maxDx = Math.max(0, (REF_W - (2 * w + c.gap)) * 0.5 - 2);
      const maxDy = Math.max(0, (REF_H - h) * 0.5 - 2);
      const cx = REF_W * 0.5 + this.gaze[0] * maxDx + shakeOff;
      const cy = REF_H * 0.5 + this.gaze[1] * maxDy + c.dy + bounceOff + breath;
      const curious = 0.08 * this.gaze[0];
      const closure = Math.max(blink, this.sleepClosure * 0.93);
      const eyes = [[-1, c.scale_l * (1 - curious)], [1, c.scale_r * (1 + curious)]].map(([side, scale]) => {
        const vis = Math.max(2, h * scale * (1 - closure));
        return {
          cx: cx + side * (w + c.gap) * 0.5, cy, w, h: vis, r: Math.min(c.r, Math.min(w, vis) * 0.5),
          lidTop: c.lid_top, slantIn: c.slant_in, slantOut: c.slant_out, lidBottom: c.lid_bottom,
        };
      });
      const frame = { eyes, shape: this.shape, accent: this.accent, closure, mouth: this.mouth };
      if (this.mouth) {
        frame.mouthW = 12 + 22 * this.level;
        frame.mouthH = 3 + 8 * this.level;
        frame.mouthCx = REF_W * 0.5 + this.gaze[0] * maxDx * 0.5;
        frame.mouthCy = Math.min(cy + h * 0.5 + 5 + frame.mouthH * 0.5, REF_H - frame.mouthH * 0.5 - 1);
      }
      return frame;
    }
  }

  // ---------------------------------------------------------------- dibujo en canvas

  function roundRect(ctx, x, y, w, h, r) {
    r = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function poly(ctx, points) {
    ctx.beginPath();
    ctx.moveTo(points[0], points[1]);
    for (let i = 2; i < points.length; i += 2) ctx.lineTo(points[i], points[i + 1]);
    ctx.closePath();
    ctx.fill();
  }

  // Dibuja el cuadro en coordenadas de referencia (128x64); el llamador fija la escala.
  function drawFace(ctx, frame, opts) {
    const colors = P.colors;
    const eyeColor = frame.accent ? colors.accent : colors.eye;
    const bg = colors.background;
    frame.eyes.forEach((g, index) => {
      const innerOnRight = index === 0;
      const x = g.cx - g.w / 2;
      const y = g.cy - g.h / 2;
      ctx.save();
      ctx.fillStyle = eyeColor;
      ctx.shadowColor = eyeColor;
      ctx.shadowBlur = opts.glow ? opts.glow : 0;
      if (frame.shape === "heart" && frame.closure < 0.6) {
        const s = Math.min(g.w, g.h * 1.05);
        const lr = 0.27 * s;
        const ldx = 0.23 * g.w;
        const ly = g.cy - 0.17 * g.h;
        ctx.beginPath();
        ctx.arc(g.cx - ldx, ly, lr, 0, Math.PI * 2);
        ctx.arc(g.cx + ldx, ly, lr, 0, Math.PI * 2);
        ctx.fill();
        poly(ctx, [g.cx - ldx - lr * 0.97, ly + lr * 0.25, g.cx + ldx + lr * 0.97, ly + lr * 0.25, g.cx, g.cy + 0.5 * g.h]);
        ctx.restore();
        return;
      }
      if (frame.shape === "cross" && frame.closure < 0.6) {
        const s = Math.min(g.w, g.h);
        ctx.strokeStyle = eyeColor;
        ctx.lineWidth = 0.24 * s * 0.7071 * 2;
        ctx.lineCap = "butt";
        ctx.beginPath();
        ctx.moveTo(g.cx - 0.46 * s, g.cy - 0.46 * s);
        ctx.lineTo(g.cx + 0.46 * s, g.cy + 0.46 * s);
        ctx.moveTo(g.cx - 0.46 * s, g.cy + 0.46 * s);
        ctx.lineTo(g.cx + 0.46 * s, g.cy - 0.46 * s);
        ctx.stroke();
        ctx.restore();
        return;
      }
      roundRect(ctx, x, y, g.w, g.h, g.r);
      ctx.fill();
      ctx.restore();
      // Parpados: se pinta fondo encima, igual que en el firmware.
      ctx.fillStyle = bg;
      const pad = 1.5;
      const top = g.lidTop * g.h;
      if (g.lidTop > 0.001) ctx.fillRect(x - pad, y - pad, g.w + 2 * pad, top + pad);
      const inner = innerOnRight ? x + g.w + pad : x - pad;
      const outer = innerOnRight ? x - pad : x + g.w + pad;
      if (g.slantIn > 0.001) {
        poly(ctx, [inner, y - pad, outer, y - pad, outer, y + top, inner, y + top + g.slantIn * g.h]);
      }
      if (g.slantOut > 0.001) {
        poly(ctx, [outer, y - pad, inner, y - pad, inner, y + top, outer, y + top + g.slantOut * g.h]);
      }
      if (g.lidBottom > 0.001) {
        const radius = 0.62 * g.w + pad;
        ctx.beginPath();
        ctx.arc(g.cx, y + g.h - g.lidBottom * g.h + radius, radius, 0, Math.PI * 2);
        ctx.fill();
      }
    });
    if (frame.mouth) {
      ctx.save();
      ctx.fillStyle = eyeColor;
      ctx.shadowColor = eyeColor;
      ctx.shadowBlur = opts.glow ? opts.glow : 0;
      roundRect(ctx, frame.mouthCx - frame.mouthW / 2, frame.mouthCy - frame.mouthH / 2, frame.mouthW,
        frame.mouthH, frame.mouthH / 2);
      ctx.fill();
      ctx.restore();
    }
  }

  global.GMiniFace = { Eyes, drawFace, parseEmotion, parseActivity, REF_W, REF_H };
})(window);
