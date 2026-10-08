#include "leds.h"

#include <Arduino.h>
#include <math.h>
#include <string.h>

#include "config.h"

#if GMINI_LED_RING
#include <Adafruit_NeoPixel.h>
#endif

namespace leds {

namespace {

uint32_t gOverrideRgb = 0;
Effect gOverrideEffect = Effect::Solid;
bool gOverride = false;
uint32_t gOverrideUntil = 0;
uint32_t gNotifyAt = 0;
uint8_t gBrightness = 200;

#if GMINI_LED_RING
Adafruit_NeoPixel gStrip(GMINI_LED_COUNT, PIN_LED_RING, NEO_GRB + NEO_KHZ800);
#endif

struct Rgb {
  float r, g, b;
};

Rgb fromHex(uint32_t c) { return {(float)((c >> 16) & 0xFF), (float)((c >> 8) & 0xFF), (float)(c & 0xFF)}; }

Rgb scale(Rgb c, float k) { return {c.r * k, c.g * k, c.b * k}; }

Rgb emotionColor(gmini::Emotion e) {
  switch (e) {
    case gmini::Emotion::Happy: return fromHex(0x7CFFB2);
    case gmini::Emotion::Sad: return fromHex(0x2F5BFF);
    case gmini::Emotion::Surprised: return fromHex(0xFFFFFF);
    case gmini::Emotion::Angry: return fromHex(0xFF3B1F);
    case gmini::Emotion::Thinking: return fromHex(0x9B6BFF);
    case gmini::Emotion::Sleepy: return fromHex(0x3A2A7A);
    case gmini::Emotion::Love: return fromHex(0xFF4D9A);
    case gmini::Emotion::Error: return fromHex(0xFF1A1A);
    default: return fromHex(gmini::presets::kColorEye);
  }
}

#if GMINI_LED_RING
void put(uint16_t i, Rgb c) {
  auto ch = [](float v) -> uint8_t { return v <= 0 ? 0 : (v >= 255 ? 255 : (uint8_t)v); };
  gStrip.setPixelColor(i, gStrip.gamma32(gStrip.Color(ch(c.r), ch(c.g), ch(c.b))));
}

void fill(Rgb c) {
  for (uint16_t i = 0; i < GMINI_LED_COUNT; ++i) put(i, c);
}

void spin(uint32_t now, Rgb c, float revPerSec, uint8_t heads) {
  const float pos = fmodf(now * 0.001f * revPerSec, 1.0f) * GMINI_LED_COUNT;
  for (uint16_t i = 0; i < GMINI_LED_COUNT; ++i) {
    float best = 0.0f;
    for (uint8_t h = 0; h < heads; ++h) {
      float head = fmodf(pos + (float)h * GMINI_LED_COUNT / heads, (float)GMINI_LED_COUNT);
      float d = head - (float)i;
      if (d < 0) d += GMINI_LED_COUNT;
      float k = d < 4.0f ? 1.0f - d / 4.0f : 0.0f;  // cola de 4 LEDs
      if (k > best) best = k;
    }
    put(i, scale(c, 0.04f + 0.96f * best * best));
  }
}

void renderEffect(uint32_t now, Effect e, Rgb c) {
  switch (e) {
    case Effect::Solid: fill(c); break;
    case Effect::Breathe: fill(scale(c, 0.15f + 0.85f * (0.5f - 0.5f * cosf(now * 0.0021f)))); break;
    case Effect::Blink: fill((now / 400) % 2 ? c : Rgb{0, 0, 0}); break;
    case Effect::Spin: spin(now, c, 1.0f, 1); break;
    case Effect::Rainbow:
      for (uint16_t i = 0; i < GMINI_LED_COUNT; ++i) {
        uint16_t hue = (uint16_t)(now * 20 + i * 65536UL / GMINI_LED_COUNT);
        gStrip.setPixelColor(i, gStrip.gamma32(gStrip.ColorHSV(hue)));
      }
      break;
    case Effect::Off: fill({0, 0, 0}); break;
  }
}
#endif

}  // namespace

bool enabled() { return GMINI_LED_RING != 0; }

void begin(uint8_t brightness) {
  gBrightness = brightness;
#if GMINI_LED_RING
  gStrip.begin();
  gStrip.setBrightness(brightness / 2);  // el anillo a pleno brillo deslumbra y consume ~0,7 A
  gStrip.clear();
  gStrip.show();
#endif
}

void setBrightness(uint8_t brightness) {
  gBrightness = brightness;
#if GMINI_LED_RING
  gStrip.setBrightness(brightness / 2);
#endif
}

void override(uint32_t rgb, Effect effect, uint32_t ms) {
  gOverrideRgb = rgb;
  gOverrideEffect = effect;
  gOverride = true;
  gOverrideUntil = ms ? millis() + ms : 0;
}

void autoMode() { gOverride = false; }

void notifyPulse() { gNotifyAt = millis(); }

void update(uint32_t now, gmini::Activity activity, gmini::Emotion emotion, float level, bool asleep, bool setup,
            bool offline) {
#if GMINI_LED_RING
  if (gOverride && gOverrideUntil && (int32_t)(now - gOverrideUntil) >= 0) gOverride = false;
  const Rgb eye = fromHex(gmini::presets::kColorEye);
  if (gOverride) {
    renderEffect(now, gOverrideEffect, fromHex(gOverrideRgb));
  } else if (setup) {
    spin(now, fromHex(0x2F6BFF), 0.5f, 2);
  } else if (gNotifyAt && now - gNotifyAt < 1800) {
    // Tres pulsos azules para un aviso.
    const float t = (now - gNotifyAt) / 600.0f;
    fill(scale(fromHex(0x3D8BFF), 0.5f - 0.5f * cosf(t * 2.0f * PI)));
  } else if (emotion == gmini::Emotion::Error) {
    fill(scale(emotionColor(emotion), (now / 250) % 2 ? 0.9f : 0.15f));
  } else {
    switch (activity) {
      case gmini::Activity::Listening: fill(scale(eye, 0.35f + 0.65f * level)); break;
      case gmini::Activity::Thinking: spin(now, fromHex(0x9B6BFF), 1.2f, 1); break;
      case gmini::Activity::Acting: spin(now, fromHex(0xFFB020), 2.0f, 2); break;
      case gmini::Activity::Speaking: fill(scale(emotionColor(emotion), 0.25f + 0.75f * level)); break;
      default: {
        float base = asleep ? 0.0f : 0.06f + 0.10f * (0.5f - 0.5f * cosf(now * 0.0016f));
        if (offline) base = (now / 1000) % 4 == 0 ? 0.3f : 0.0f;
        fill(scale(offline ? fromHex(0xFF8A00) : emotionColor(emotion), base));
      }
    }
  }
  gStrip.show();
#else
  (void)now;
  (void)activity;
  (void)emotion;
  (void)level;
  (void)asleep;
  (void)setup;
  (void)offline;
#endif
}

bool parseEffect(const char* name, Effect* out) {
  struct Entry {
    const char* name;
    Effect effect;
  };
  static const Entry kEffects[] = {{"solid", Effect::Solid},     {"breathe", Effect::Breathe},
                                   {"blink", Effect::Blink},     {"spin", Effect::Spin},
                                   {"rainbow", Effect::Rainbow}, {"off", Effect::Off}};
  if (name == nullptr || *name == '\0') {
    *out = Effect::Solid;
    return true;
  }
  for (const Entry& e : kEffects) {
    if (strcasecmp(name, e.name) == 0) {
      *out = e.effect;
      return true;
    }
  }
  return false;
}

bool parseColor(const char* text, uint32_t* rgb) {
  if (text == nullptr || text[0] != '#' || strlen(text) != 7) return false;
  char* end = nullptr;
  unsigned long v = strtoul(text + 1, &end, 16);
  if (end == nullptr || *end != '\0') return false;
  *rgb = (uint32_t)v;
  return true;
}

}  // namespace leds
