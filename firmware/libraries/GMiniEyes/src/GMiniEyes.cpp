#include "GMiniEyes.h"

#include <math.h>
#include <string.h>

namespace gmini {

namespace {

const float kTwoPi = 6.2831853f;
const float kPi = 3.1415927f;
const float kBounceHz = 1.6f;
const float kShakeHz = 9.0f;
const float kBreathHz = 0.25f;
const uint32_t kNeverMs = 0x7FFFFFFFu;

inline float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
inline float maxf(float a, float b) { return a > b ? a : b; }
inline float minf(float a, float b) { return a < b ? a : b; }

// Comparacion robusta ante el desborde de millis() (cada ~49 dias).
inline bool reached(uint32_t now, uint32_t deadline) { return (int32_t)(now - deadline) >= 0; }

// Factor de suavizado exponencial para un paso dt con constante de tiempo tau.
inline float smoothing(float dtMs, float tauMs) {
  return tauMs <= 0.0f ? 1.0f : 1.0f - expf(-dtMs / tauMs);
}

inline char lowerAscii(char c) { return (c >= 'A' && c <= 'Z') ? (char)(c - 'A' + 'a') : c; }

// Busca `name` en un bloque "a\0b\0\0" (en PROGMEM en AVR). Devuelve el indice o -1.
int findName(const char* blob, const char* name) {
  if (name == nullptr || *name == '\0') return -1;
  const char* entry = blob;
  for (int index = 0;; ++index) {
    if (GMINI_PGM_BYTE(entry) == 0) return -1;
    const char* s = entry;
    const char* q = name;
    bool match = true;
    for (;;) {
      char c = (char)GMINI_PGM_BYTE(s);
      if (c != lowerAscii(*q)) match = false;
      if (c == 0) break;
      ++s;
      if (*q) ++q;
    }
    if (match) return index;
    entry = s + 1;
  }
}

bool copyName(const char* blob, uint8_t index, char* buf, size_t len) {
  if (buf == nullptr || len == 0) return false;
  const char* entry = blob;
  for (uint8_t i = 0; i < index; ++i) {
    if (GMINI_PGM_BYTE(entry) == 0) return false;
    while (GMINI_PGM_BYTE(entry) != 0) ++entry;
    ++entry;
  }
  if (GMINI_PGM_BYTE(entry) == 0) return false;
  size_t n = 0;
  for (; n + 1 < len; ++n) {
    char c = (char)GMINI_PGM_BYTE(entry + n);
    if (c == 0) break;
    buf[n] = c;
  }
  buf[n] = '\0';
  return true;
}

inline int16_t roundi(float v) { return (int16_t)floorf(v + 0.5f); }

// Convierte coordenadas de referencia a pixeles segun el layout.
struct Mapper {
  const FaceLayout& l;
  explicit Mapper(const FaceLayout& layout) : l(layout) {}
  float fx(float x) const { return l.originX + (l.mirrorX ? (presets::kRefWidth - x) : x) * l.scale; }
  int16_t x(float v) const { return roundi(fx(v)); }
  int16_t y(float v) const { return roundi(l.originY + v * l.scale); }
  int16_t len(float v) const { return roundi(v * l.scale); }

  void rect(FaceCanvas& c, float x0, float y0, float w, float h, uint8_t color) const {
    if (w <= 0.0f || h <= 0.0f) return;
    int16_t ax = x(x0), bx = x(x0 + w);
    if (ax > bx) { int16_t t = ax; ax = bx; bx = t; }
    int16_t ay = y(y0), by = y(y0 + h);
    if (bx - ax <= 0 || by - ay <= 0) return;
    c.fillRect(ax, ay, bx - ax, by - ay, color);
  }

  void roundRect(FaceCanvas& c, float x0, float y0, float w, float h, float r, uint8_t color) const {
    int16_t ax = x(x0), bx = x(x0 + w);
    if (ax > bx) { int16_t t = ax; ax = bx; bx = t; }
    int16_t ay = y(y0), by = y(y0 + h);
    int16_t pw = bx - ax, ph = by - ay;
    if (pw <= 0 || ph <= 0) return;
    int16_t pr = len(r);
    int16_t maxR = (pw < ph ? pw : ph) / 2 - 1;
    if (pr > maxR) pr = maxR;
    if (pr < 1) {
      c.fillRect(ax, ay, pw, ph, color);
    } else {
      c.fillRoundRect(ax, ay, pw, ph, pr, color);
    }
  }

  void circle(FaceCanvas& c, float cx, float cy, float r, uint8_t color) const {
    int16_t pr = len(r);
    if (pr < 1) return;
    c.fillCircle(x(cx), y(cy), pr, color);
  }

  void triangle(FaceCanvas& c, float x0, float y0, float x1, float y1, float x2, float y2, uint8_t color) const {
    c.fillTriangle(x(x0), y(y0), x(x1), y(y1), x(x2), y(y2), color);
  }
};

void drawRoundEye(const EyeGeom& g, bool innerOnRight, uint8_t color, FaceCanvas& c, const Mapper& m,
                  bool glow) {
  const float x = g.cx - g.w * 0.5f;
  const float y = g.cy - g.h * 0.5f;
  const float glowPad = glow ? 1.6f : 0.0f;
  if (glow) m.roundRect(c, x - glowPad, y - glowPad, g.w + 2 * glowPad, g.h + 2 * glowPad, g.r + glowPad, kColorGlow);
  m.roundRect(c, x, y, g.w, g.h, g.r, color);

  // Los parpados se "recortan" pintando fondo encima del ojo.
  const float pad = glowPad + 1.0f / maxf(m.l.scale, 0.25f);
  const float topPx = g.lidTop * g.h;
  if (g.lidTop > 0.001f) m.rect(c, x - pad, y - pad, g.w + 2 * pad, topPx + pad, kColorBackground);

  const float innerX = innerOnRight ? x + g.w + pad : x - pad;
  const float outerX = innerOnRight ? x - pad : x + g.w + pad;
  // Parpado inclinado: cuadrilatero desde el borde superior hasta la diagonal,
  // asi no quedan restos del halo por encima del ojo.
  if (g.slantIn > 0.001f) {
    const float low = y + topPx + g.slantIn * g.h;
    m.triangle(c, innerX, y - pad, outerX, y - pad, outerX, y + topPx, kColorBackground);
    m.triangle(c, innerX, y - pad, outerX, y + topPx, innerX, low, kColorBackground);
  }
  if (g.slantOut > 0.001f) {
    const float low = y + topPx + g.slantOut * g.h;
    m.triangle(c, outerX, y - pad, innerX, y - pad, innerX, y + topPx, kColorBackground);
    m.triangle(c, outerX, y - pad, innerX, y + topPx, outerX, low, kColorBackground);
  }
  if (g.lidBottom > 0.001f) {
    // Parpado inferior en arco: ojos "sonrientes".
    const float radius = 0.62f * g.w + glowPad;
    m.circle(c, g.cx, y + g.h - g.lidBottom * g.h + radius, radius, kColorBackground);
  }
}

void drawHeart(const EyeGeom& g, uint8_t color, FaceCanvas& c, const Mapper& m) {
  const float s = minf(g.w, g.h * 1.05f);
  const float lobeR = 0.27f * s;
  const float lobeDx = 0.23f * g.w;
  const float lobeY = g.cy - 0.17f * g.h;
  m.circle(c, g.cx - lobeDx, lobeY, lobeR, color);
  m.circle(c, g.cx + lobeDx, lobeY, lobeR, color);
  m.triangle(c, g.cx - lobeDx - lobeR * 0.97f, lobeY + lobeR * 0.25f, g.cx + lobeDx + lobeR * 0.97f,
             lobeY + lobeR * 0.25f, g.cx, g.cy + 0.5f * g.h, color);
}

void drawCross(const EyeGeom& g, uint8_t color, FaceCanvas& c, const Mapper& m) {
  const float s = minf(g.w, g.h);
  const float half = 0.46f * s;
  const float t = 0.12f * s;
  for (int d = 0; d < 2; ++d) {
    const float dy = d == 0 ? 1.0f : -1.0f;
    const float x1 = g.cx - half, y1 = g.cy - half * dy;
    const float x2 = g.cx + half, y2 = g.cy + half * dy;
    // normal unitaria (-dy, 1)/sqrt(2) escalada por t
    const float nx = -dy * t * 0.7071f, ny = t * 0.7071f;
    m.triangle(c, x1 + nx, y1 + ny, x2 + nx, y2 + ny, x2 - nx, y2 - ny, color);
    m.triangle(c, x1 + nx, y1 + ny, x2 - nx, y2 - ny, x1 - nx, y1 - ny, color);
  }
}

}  // namespace

// ------------------------------------------------------------------ nombres

bool parseEmotion(const char* name, Emotion* out) {
  int idx = findName(presets::kEmotionNames, name);
  if (idx < 0) {
    int alias = findName(presets::kAliasNames, name);
    if (alias < 0) return false;
    idx = GMINI_PGM_BYTE(&presets::kAliasTargets[alias]);
  }
  if (out) *out = (Emotion)idx;
  return true;
}

bool parseActivity(const char* name, Activity* out) {
  int idx = findName(presets::kActivityNames, name);
  if (idx < 0) return false;
  if (out) *out = (Activity)idx;
  return true;
}

bool copyEmotionName(Emotion emotion, char* buf, size_t len) {
  return copyName(presets::kEmotionNames, (uint8_t)emotion, buf, len);
}

bool copyActivityName(Activity activity, char* buf, size_t len) {
  return copyName(presets::kActivityNames, (uint8_t)activity, buf, len);
}

// ------------------------------------------------------------------ layout

FaceLayout FaceLayout::fit(int16_t width, int16_t height, float fill) {
  FaceLayout l;
  float sx = (float)width / presets::kRefWidth;
  float sy = (float)height / presets::kRefHeight;
  l.scale = minf(sx, sy) * fill;
  l.originX = ((float)width - presets::kRefWidth * l.scale) * 0.5f;
  l.originY = ((float)height - presets::kRefHeight * l.scale) * 0.5f;
  return l;
}

void drawFace(const FaceFrame& f, FaceCanvas& c, const FaceLayout& layout) {
  Mapper m(layout);
  const uint8_t color = f.accent ? kColorAccent : kColorEye;
  for (uint8_t i = 0; i < 2; ++i) {
    const EyeGeom& g = f.eye[i];
    // El lado interno del ojo izquierdo queda a la derecha (hacia la nariz).
    const bool innerOnRight = (i == 0);
    if (f.shape == kShapeHeart && f.closure < 0.6f) {
      drawHeart(g, color, c, m);
    } else if (f.shape == kShapeCross && f.closure < 0.6f) {
      drawCross(g, color, c, m);
    } else {
      drawRoundEye(g, innerOnRight, color, c, m, layout.glow);
    }
  }
  if (f.mouth) {
    m.roundRect(c, f.mouthCx - f.mouthW * 0.5f, f.mouthCy - f.mouthH * 0.5f, f.mouthW, f.mouthH, f.mouthH * 0.5f,
                color);
  }
}

// ------------------------------------------------------------------ motor

EyesEngine::EyesEngine(uint32_t seed)
    : bounce_(0), shake_(0), pulse_(0), pulseHz_(1), levelH_(0),
      actLookX_(0), actLookY_(0), scanX_(0), scanY_(0),
      blinkMin_(0), blinkMax_(0), sacMin_(0), sacMax_(0), scanMin_(0), scanMax_(0),
      shape_(kShapeRound), pendingShape_(kShapeRound),
      hasLook_(false), mouth_(false), accent_(false), hasPendingShape_(false),
      gazeX_(0), gazeY_(0), sacX_(0), sacY_(0), manualX_(0), manualY_(0),
      level_(0), levelTarget_(0), sleepClosure_(0), phase_(0),
      lastMs_(0), nextBlinkMs_(0), nextSaccadeMs_(0), blinkStartMs_(0), emotionSinceMs_(0), lastWakeMs_(0),
      sleepAfterMs_(presets::kSleepAfterMs), rng_(seed ? seed : 0x2545F491u), scanSign_(1),
      started_(false), blinking_(false), forceBlink_(false), manualLook_(false), asleep_(false),
      autoBlink_(true), saccades_(true),
      emotion_(Emotion::Neutral), activity_(Activity::Idle) {
  memset(&frame_, 0, sizeof(frame_));
  applyPresets(true);
  cur_ = target_;
}

uint32_t EyesEngine::randRange(uint32_t lo, uint32_t hi) {
  // xorshift32: determinista y barato tambien en AVR.
  rng_ ^= rng_ << 13;
  rng_ ^= rng_ >> 17;
  rng_ ^= rng_ << 5;
  if (hi <= lo) return lo;
  return lo + rng_ % (hi - lo + 1);
}

float EyesEngine::randSigned() { return (float)randRange(0, 2000) / 1000.0f - 1.0f; }

void EyesEngine::begin(uint32_t nowMs) {
  started_ = true;
  lastMs_ = nowMs;
  lastWakeMs_ = nowMs;
  emotionSinceMs_ = nowMs;
  sleepClosure_ = 1.0f;  // abre los ojos al arrancar
  scheduleBlink(nowMs);
  nextSaccadeMs_ = nowMs + 600;
  buildFrame(nowMs, 0.0f);
}

void EyesEngine::applyPresets(bool immediate) {
  EmotionPreset e;
  ActivityPreset a;
  GMINI_MEMCPY_P(&e, &presets::kEmotions[(uint8_t)emotion_], sizeof(e));
  GMINI_MEMCPY_P(&a, &presets::kActivities[(uint8_t)activity_], sizeof(a));

  target_.w = e.w * a.mulW;
  target_.h = e.h * a.mulH;
  target_.r = e.r;
  target_.gap = e.gap;
  target_.dy = e.dy + a.addDy;
  target_.lidTop = maxf(e.lidTop, a.lidTopMin);
  target_.slantIn = e.slantIn;
  target_.slantOut = e.slantOut;
  target_.lidBottom = e.lidBottom;
  target_.lookX = e.lookX;
  target_.lookY = e.lookY;
  target_.scaleL = e.scaleL;
  target_.scaleR = e.scaleR;

  bounce_ = e.bounce;
  shake_ = e.shake;
  pulse_ = e.pulse;
  pulseHz_ = e.pulseHz;
  levelH_ = a.levelH;
  mouth_ = a.mouth != 0;
  accent_ = e.accent != 0;
  blinkMin_ = a.hasBlink ? a.blinkMin : e.blinkMin;
  blinkMax_ = a.hasBlink ? a.blinkMax : e.blinkMax;
  sacMin_ = a.hasSaccade ? a.saccadeMin : e.saccadeMin;
  sacMax_ = a.hasSaccade ? a.saccadeMax : e.saccadeMax;
  hasLook_ = a.hasLook != 0;
  actLookX_ = a.lookX;
  actLookY_ = a.lookY;
  scanMin_ = a.hasScan ? a.scanMin : 0;
  scanMax_ = a.hasScan ? a.scanMax : 0;
  scanX_ = a.scanX;
  scanY_ = a.scanY;

  if (immediate) {
    shape_ = e.shape;
    hasPendingShape_ = false;
  } else if (e.shape != shape_) {
    // El cambio de forma se hace con los ojos cerrados para que no "salte".
    pendingShape_ = e.shape;
    hasPendingShape_ = true;
    forceBlink_ = true;
  } else {
    hasPendingShape_ = false;
  }
}

void EyesEngine::setEmotion(Emotion emotion) {
  if ((uint8_t)emotion >= presets::kEmotionCount) return;
  wake();
  if (emotion == emotion_) return;
  emotion_ = emotion;
  emotionSinceMs_ = lastMs_;
  sacX_ = 0;
  sacY_ = 0;
  applyPresets(false);
  nextSaccadeMs_ = lastMs_ + sacMin_;
}

void EyesEngine::setActivity(Activity activity) {
  if ((uint8_t)activity >= presets::kActivityCount) return;
  wake();
  if (activity == activity_) return;
  activity_ = activity;
  applyPresets(false);
  nextSaccadeMs_ = lastMs_;
  if (activity_ != Activity::Speaking && activity_ != Activity::Listening) levelTarget_ = 0.0f;
}

void EyesEngine::setLevel(float level) { levelTarget_ = clampf(level, 0.0f, 1.0f); }

void EyesEngine::lookAt(float x, float y) {
  manualLook_ = true;
  manualX_ = clampf(x, -1.0f, 1.0f);
  manualY_ = clampf(y, -1.0f, 1.0f);
}

void EyesEngine::releaseLook() { manualLook_ = false; }

void EyesEngine::blink() { forceBlink_ = true; }

void EyesEngine::wake() {
  lastWakeMs_ = lastMs_;
  asleep_ = false;
}

void EyesEngine::sleep() { asleep_ = true; }

void EyesEngine::startBlink(uint32_t now) {
  blinking_ = true;
  forceBlink_ = false;
  blinkStartMs_ = now;
}

void EyesEngine::scheduleBlink(uint32_t now) {
  if (blinkMax_ == 0) {
    nextBlinkMs_ = now + kNeverMs;
    return;
  }
  // De vez en cuando un doble parpadeo, como hacemos las personas.
  if (randRange(0, 99) < 12) {
    nextBlinkMs_ = now + 170;
  } else {
    nextBlinkMs_ = now + randRange(blinkMin_, blinkMax_);
  }
}

float EyesEngine::blinkClosure(uint32_t now) {
  const uint32_t close = presets::kBlinkCloseMs;
  const uint32_t hold = presets::kBlinkHoldMs;
  const uint32_t open = presets::kBlinkOpenMs;
  const uint32_t t = now - blinkStartMs_;
  if (t < close) {
    float p = (float)t / (float)close;
    return p * p;
  }
  if (t < close + hold) return 1.0f;
  if (t < close + hold + open) {
    float q = 1.0f - (float)(t - close - hold) / (float)open;
    return q * q;
  }
  blinking_ = false;
  scheduleBlink(now);
  return 0.0f;
}

void EyesEngine::updateGaze(uint32_t now, float k) {
  float tx, ty;
  if (manualLook_) {
    tx = manualX_;
    ty = manualY_;
  } else if (scanMax_ > 0) {
    if (reached(now, nextSaccadeMs_)) {
      scanSign_ = (int8_t)-scanSign_;
      nextSaccadeMs_ = now + randRange(scanMin_, scanMax_);
    }
    tx = scanX_ * scanSign_;
    ty = scanY_;
  } else if (hasLook_) {
    tx = actLookX_;
    ty = actLookY_;
  } else {
    if (!saccades_ || sacMax_ == 0 || asleep_) {
      sacX_ = 0;
      sacY_ = 0;
    } else if (reached(now, nextSaccadeMs_)) {
      if (randRange(0, 99) < 35) {
        sacX_ = 0;
        sacY_ = 0;
      } else {
        sacX_ = randSigned() * 0.6f;
        sacY_ = randSigned() * 0.35f;
      }
      nextSaccadeMs_ = now + randRange(sacMin_, sacMax_);
    }
    tx = clampf(cur_.lookX + sacX_, -1.0f, 1.0f);
    ty = clampf(cur_.lookY + sacY_, -1.0f, 1.0f);
  }
  gazeX_ += (tx - gazeX_) * k;
  gazeY_ += (ty - gazeY_) * k;
}

void EyesEngine::update(uint32_t nowMs) {
  if (!started_) begin(nowMs);
  uint32_t elapsed = nowMs - lastMs_;
  const float dt = elapsed > 100 ? 100.0f : (float)elapsed;
  lastMs_ = nowMs;

  if (!asleep_ && sleepAfterMs_ > 0 && activity_ == Activity::Idle && (nowMs - lastWakeMs_) >= sleepAfterMs_) {
    asleep_ = true;
  }

  const float ks = smoothing(dt, (float)presets::kShapeTauMs);
  cur_.w += (target_.w - cur_.w) * ks;
  cur_.h += (target_.h - cur_.h) * ks;
  cur_.r += (target_.r - cur_.r) * ks;
  cur_.gap += (target_.gap - cur_.gap) * ks;
  cur_.dy += (target_.dy - cur_.dy) * ks;
  cur_.lidTop += (target_.lidTop - cur_.lidTop) * ks;
  cur_.slantIn += (target_.slantIn - cur_.slantIn) * ks;
  cur_.slantOut += (target_.slantOut - cur_.slantOut) * ks;
  cur_.lidBottom += (target_.lidBottom - cur_.lidBottom) * ks;
  cur_.lookX += (target_.lookX - cur_.lookX) * ks;
  cur_.lookY += (target_.lookY - cur_.lookY) * ks;
  cur_.scaleL += (target_.scaleL - cur_.scaleL) * ks;
  cur_.scaleR += (target_.scaleR - cur_.scaleR) * ks;

  const float tauLevel = levelTarget_ > level_ ? (float)presets::kLevelAttackMs : (float)presets::kLevelReleaseMs;
  level_ += (levelTarget_ - level_) * smoothing(dt, tauLevel);

  const float sleepTarget = asleep_ ? 1.0f : 0.0f;
  sleepClosure_ += (sleepTarget - sleepClosure_) * smoothing(dt, asleep_ ? 900.0f : 220.0f);

  updateGaze(nowMs, smoothing(dt, (float)presets::kGazeTauMs));

  if (!blinking_ && (forceBlink_ || (autoBlink_ && blinkMax_ > 0 && !asleep_ && reached(nowMs, nextBlinkMs_)))) {
    startBlink(nowMs);
  }
  float blink = blinking_ ? blinkClosure(nowMs) : 0.0f;
  if (hasPendingShape_ && (!blinking_ || blink > 0.9f)) {
    shape_ = pendingShape_;
    hasPendingShape_ = false;
  }

  phase_ += dt * 0.001f;
  if (phase_ >= 1000.0f) phase_ -= 1000.0f;
  buildFrame(nowMs, blink);
}

void EyesEngine::buildFrame(uint32_t now, float blink) {
  const float bounceOff = -bounce_ * fabsf(sinf(kPi * kBounceHz * phase_));
  float shakeEnv = 0.0f;
  const uint32_t sinceEmotion = now - emotionSinceMs_;
  if (shake_ > 0.0f && sinceEmotion < presets::kShakeMs) {
    shakeEnv = 1.0f - (float)sinceEmotion / (float)presets::kShakeMs;
  }
  const float shakeOff = shake_ * shakeEnv * sinf(kTwoPi * kShakeHz * phase_);
  const float pulseMul = 1.0f + pulse_ * sinf(kTwoPi * pulseHz_ * phase_);
  const float breath = sleepClosure_ * 0.8f * sinf(kTwoPi * kBreathHz * phase_);

  const float w = cur_.w * pulseMul;
  const float h = cur_.h * pulseMul * (1.0f + levelH_ * level_);
  const float gap = cur_.gap;
  const float maxDx = maxf(0.0f, (presets::kRefWidth - (2.0f * w + gap)) * 0.5f - 2.0f);
  const float maxDy = maxf(0.0f, (presets::kRefHeight - h) * 0.5f - 2.0f);
  const float cx = presets::kRefWidth * 0.5f + gazeX_ * maxDx + shakeOff;
  const float cy = presets::kRefHeight * 0.5f + gazeY_ * maxDy + cur_.dy + bounceOff + breath;
  // El ojo hacia el que se mira crece un poco: da sensacion de profundidad.
  const float curious = 0.08f * gazeX_;
  const float closure = maxf(blink, sleepClosure_ * 0.93f);

  for (uint8_t i = 0; i < 2; ++i) {
    const float side = i == 0 ? -1.0f : 1.0f;
    const float scale = i == 0 ? cur_.scaleL * (1.0f - curious) : cur_.scaleR * (1.0f + curious);
    const float eyeH = h * scale;
    const float vis = maxf(2.0f, eyeH * (1.0f - closure));
    EyeGeom& g = frame_.eye[i];
    g.cx = cx + side * (w + gap) * 0.5f;
    g.cy = cy;
    g.w = w;
    g.h = vis;
    g.r = minf(cur_.r, minf(w, vis) * 0.5f);
    g.lidTop = cur_.lidTop;
    g.slantIn = cur_.slantIn;
    g.slantOut = cur_.slantOut;
    g.lidBottom = cur_.lidBottom;
  }
  frame_.shape = shape_;
  frame_.accent = accent_;
  frame_.closure = closure;
  frame_.mouth = mouth_;
  if (mouth_) {
    frame_.mouthW = 12.0f + 22.0f * level_;
    frame_.mouthH = 3.0f + 8.0f * level_;
    frame_.mouthCx = presets::kRefWidth * 0.5f + gazeX_ * maxDx * 0.5f;
    float my = cy + h * 0.5f + 5.0f + frame_.mouthH * 0.5f;
    frame_.mouthCy = minf(my, presets::kRefHeight - frame_.mouthH * 0.5f - 1.0f);
  }
}

}  // namespace gmini
