// Generado por tools/codegen/gen_expressions.py desde common/expressions.json. No editar a mano.
#pragma once

#include <stdint.h>
#include <string.h>

#if defined(__AVR__)
#include <avr/pgmspace.h>
#define GMINI_PROGMEM PROGMEM
#define GMINI_MEMCPY_P(dst, src, n) memcpy_P((dst), (src), (n))
#define GMINI_PGM_BYTE(p) pgm_read_byte(p)
#else
#define GMINI_PROGMEM
#define GMINI_MEMCPY_P(dst, src, n) memcpy((dst), (src), (n))
#define GMINI_PGM_BYTE(p) (*(const uint8_t*)(p))
#endif

namespace gmini {

enum class Emotion : uint8_t {
  Neutral,
  Happy,
  Sad,
  Surprised,
  Angry,
  Thinking,
  Sleepy,
  Love,
  Error,
  Count
};

enum class Activity : uint8_t {
  Idle,
  Listening,
  Thinking,
  Acting,
  Speaking,
  Count
};

enum EyeShapeKind : uint8_t { kShapeRound = 0, kShapeHeart = 1, kShapeCross = 2 };

struct EmotionPreset {
  float w, h, r, gap, dy;
  float lidTop, slantIn, slantOut, lidBottom;
  float lookX, lookY, scaleL, scaleR;
  float bounce, shake, pulse, pulseHz;
  uint16_t blinkMin, blinkMax, saccadeMin, saccadeMax;
  uint8_t shape;
  uint8_t accent;
};

struct ActivityPreset {
  float mulW, mulH, addDy, lidTopMin, levelH;
  float lookX, lookY;
  float scanX, scanY;
  uint16_t scanMin, scanMax;
  uint16_t saccadeMin, saccadeMax;
  uint16_t blinkMin, blinkMax;
  uint8_t hasLook, hasScan, hasSaccade, hasBlink, mouth;
};

namespace presets {

static const float kRefWidth = 128.0f;
static const float kRefHeight = 64.0f;

static const uint32_t kShapeTauMs = 70u;
static const uint32_t kGazeTauMs = 45u;
static const uint32_t kLevelAttackMs = 25u;
static const uint32_t kLevelReleaseMs = 140u;
static const uint32_t kBlinkCloseMs = 70u;
static const uint32_t kBlinkHoldMs = 35u;
static const uint32_t kBlinkOpenMs = 110u;
static const uint32_t kSleepAfterMs = 600000u;
static const uint32_t kShakeMs = 900u;

static const uint32_t kColorBackground = 0x000000u;
static const uint32_t kColorEye = 0x3FE0FFu;
static const uint32_t kColorGlow = 0x0B4A5Cu;
static const uint32_t kColorAccent = 0xFF4D6Du;
static const uint32_t kColorText = 0xE6FBFFu;

static const uint8_t kEmotionCount = 9;
static const uint8_t kActivityCount = 5;
static const uint8_t kAliasCount = 8;

static const EmotionPreset kEmotions[kEmotionCount] GMINI_PROGMEM = {
  /* neutral */ {36.0f, 36.0f, 8.0f, 10.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.2f, 2200, 6000, 900, 3200, 0, 0},
  /* happy */ {36.0f, 38.0f, 8.0f, 10.0f, -1.0f, 0.0f, 0.0f, 0.0f, 0.46f, 0.0f, 0.0f, 1.0f, 1.0f, 0.8f, 0.0f, 0.0f, 1.2f, 2200, 6000, 1400, 3600, 0, 0},
  /* sad */ {36.0f, 30.0f, 8.0f, 10.0f, 5.0f, 0.0f, 0.0f, 0.5f, 0.0f, 0.0f, 0.35f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.2f, 3000, 7000, 2600, 6000, 0, 0},
  /* surprised */ {40.0f, 44.0f, 16.0f, 8.0f, -2.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.2f, 3500, 8000, 1600, 4000, 0, 0},
  /* angry */ {36.0f, 31.0f, 8.0f, 10.0f, 2.0f, 0.04f, 0.55f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.2f, 2200, 6000, 1200, 3000, 0, 0},
  /* thinking */ {36.0f, 36.0f, 8.0f, 10.0f, 0.0f, 0.12f, 0.0f, 0.0f, 0.0f, 0.55f, -0.45f, 1.0f, 0.84f, 0.0f, 0.0f, 0.0f, 1.2f, 2200, 6000, 1800, 4200, 0, 0},
  /* sleepy */ {36.0f, 36.0f, 8.0f, 10.0f, 3.0f, 0.55f, 0.0f, 0.12f, 0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.2f, 1500, 3600, 4000, 9000, 0, 0},
  /* love */ {36.0f, 34.0f, 8.0f, 10.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.09f, 1.3f, 2200, 6000, 2000, 5000, 1, 1},
  /* error */ {30.0f, 30.0f, 8.0f, 10.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 1.0f, 0.0f, 2.2f, 0.0f, 1.2f, 0, 0, 0, 0, 2, 1},
};

static const ActivityPreset kActivities[kActivityCount] GMINI_PROGMEM = {
  /* idle */ {1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
  /* listening */ {1.05f, 1.1f, 0.0f, 0.0f, 0.12f, 0.0f, 0.0f, 0.0f, 0.0f, 0, 0, 0, 0, 4000, 9000, 1, 0, 1, 1, 0},
  /* thinking */ {1.0f, 1.0f, 0.0f, 0.14f, 0.0f, 0.0f, 0.0f, 0.5f, -0.45f, 1100, 1900, 0, 0, 2600, 6000, 0, 1, 0, 1, 0},
  /* acting */ {1.0f, 1.0f, 0.0f, 0.22f, 0.0f, 0.0f, 0.0f, 0.65f, 0.1f, 320, 650, 0, 0, 2000, 5000, 0, 1, 0, 1, 0},
  /* speaking */ {1.0f, 1.0f, -6.0f, 0.0f, -0.14f, 0.0f, 0.0f, 0.0f, 0.0f, 0, 0, 1500, 3500, 0, 0, 0, 0, 1, 0, 1},
};

static const char kEmotionNames[] GMINI_PROGMEM = "neutral\0happy\0sad\0surprised\0angry\0thinking\0sleepy\0love\0error\0";
static const char kActivityNames[] GMINI_PROGMEM = "idle\0listening\0thinking\0acting\0speaking\0";
static const char kAliasNames[] GMINI_PROGMEM = "calm\0curious\0tired\0confused\0sorry\0joy\0excited\0fear\0";
static const uint8_t kAliasTargets[kAliasCount] GMINI_PROGMEM = {0, 3, 6, 5, 2, 1, 1, 3};

}  // namespace presets
}  // namespace gmini
