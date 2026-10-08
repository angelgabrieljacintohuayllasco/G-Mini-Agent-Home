// Pruebas en el host del motor de ojos, el rasterizado y el protocolo serie.
// Ejecutar: pio test -e native
#include <GMiniEyes.h>
#include <GMiniRaster.h>
#include <GMiniSerialProto.h>
#include <string.h>
#include <unity.h>

using namespace gmini;

void setUp() {}
void tearDown() {}

namespace {

void advance(EyesEngine& e, uint32_t& t, uint32_t ms, uint32_t step = 10) {
  for (uint32_t i = 0; i < ms; i += step) {
    t += step;
    e.update(t);
  }
}

EyesEngine quietEngine(uint32_t& t) {
  EyesEngine e(42);
  e.setAutoBlink(false);
  e.setSaccades(false);
  e.begin(t);
  advance(e, t, 1500);
  return e;
}

uint8_t gPixels[128 * 64];

}  // namespace

// ------------------------------------------------------------------ nombres

void test_parse_names() {
  Emotion e;
  TEST_ASSERT_TRUE(parseEmotion("happy", &e));
  TEST_ASSERT_EQUAL_UINT8((uint8_t)Emotion::Happy, (uint8_t)e);
  TEST_ASSERT_TRUE(parseEmotion("SURPRISED", &e));
  TEST_ASSERT_EQUAL_UINT8((uint8_t)Emotion::Surprised, (uint8_t)e);
  TEST_ASSERT_TRUE(parseEmotion("curious", &e));  // alias
  TEST_ASSERT_EQUAL_UINT8((uint8_t)Emotion::Surprised, (uint8_t)e);
  TEST_ASSERT_FALSE(parseEmotion("hap", &e));
  TEST_ASSERT_FALSE(parseEmotion("happyx", &e));
  TEST_ASSERT_FALSE(parseEmotion("", &e));

  Activity a;
  TEST_ASSERT_TRUE(parseActivity("speaking", &a));
  TEST_ASSERT_EQUAL_UINT8((uint8_t)Activity::Speaking, (uint8_t)a);
  TEST_ASSERT_FALSE(parseActivity("happy", &a));

  char buf[16];
  TEST_ASSERT_TRUE(copyEmotionName(Emotion::Love, buf, sizeof(buf)));
  TEST_ASSERT_EQUAL_STRING("love", buf);
  TEST_ASSERT_TRUE(copyActivityName(Activity::Acting, buf, sizeof(buf)));
  TEST_ASSERT_EQUAL_STRING("acting", buf);
  TEST_ASSERT_TRUE(copyEmotionName(Emotion::Neutral, buf, 4));
  TEST_ASSERT_EQUAL_STRING("neu", buf);
  TEST_ASSERT_FALSE(copyEmotionName(Emotion::Count, buf, sizeof(buf)));
}

// ------------------------------------------------------------------ motor

void test_begin_opens_eyes() {
  EyesEngine e(7);
  e.setAutoBlink(false);
  e.begin(0);
  TEST_ASSERT_TRUE(e.frame().closure > 0.9f);
  uint32_t t = 0;
  advance(e, t, 1500);
  TEST_ASSERT_TRUE(e.frame().closure < 0.02f);
}

void test_neutral_geometry() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  const FaceFrame& f = e.frame();
  TEST_ASSERT_FLOAT_WITHIN(0.3f, 36.0f, f.eye[0].w);
  TEST_ASSERT_FLOAT_WITHIN(0.5f, 36.0f, f.eye[0].h);
  TEST_ASSERT_FLOAT_WITHIN(0.5f, 41.0f, f.eye[0].cx);
  TEST_ASSERT_FLOAT_WITHIN(0.5f, 87.0f, f.eye[1].cx);
  TEST_ASSERT_FLOAT_WITHIN(0.5f, 32.0f, f.eye[0].cy);
  TEST_ASSERT_FALSE(f.mouth);
}

void test_emotions_converge_to_presets() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  e.setEmotion(Emotion::Happy);
  advance(e, t, 1200);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.46f, e.frame().eye[0].lidBottom);

  e.setEmotion(Emotion::Sad);
  advance(e, t, 1200);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.5f, e.frame().eye[1].slantOut);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, e.frame().eye[1].lidBottom);

  e.setEmotion(Emotion::Angry);
  advance(e, t, 1200);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.55f, e.frame().eye[0].slantIn);

  e.setEmotion(Emotion::Surprised);
  advance(e, t, 1200);
  TEST_ASSERT_FLOAT_WITHIN(0.5f, 40.0f, e.frame().eye[0].w);
  TEST_ASSERT_TRUE(e.frame().eye[0].h > 42.0f);
}

void test_forced_blink_timeline() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  e.blink();
  advance(e, t, 80);
  TEST_ASSERT_TRUE(e.blinking());
  TEST_ASSERT_TRUE(e.frame().closure > 0.9f);
  TEST_ASSERT_TRUE(e.frame().eye[0].h <= 4.0f);
  advance(e, t, 250);
  TEST_ASSERT_FALSE(e.blinking());
  TEST_ASSERT_TRUE(e.frame().closure < 0.01f);
}

void test_auto_blink_happens() {
  EyesEngine e(3);
  e.setSaccades(false);
  uint32_t t = 0;
  e.begin(t);
  bool blinked = false;
  for (uint32_t i = 0; i < 9000 && !blinked; i += 10) {
    t += 10;
    e.update(t);
    if (t > 1500 && e.blinking()) blinked = true;
  }
  TEST_ASSERT_TRUE(blinked);
}

void test_shape_change_waits_for_closed_eyes() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  e.setEmotion(Emotion::Love);
  e.update(t);
  TEST_ASSERT_EQUAL_UINT8(kShapeRound, e.frame().shape);
  advance(e, t, 400);
  TEST_ASSERT_EQUAL_UINT8(kShapeHeart, e.frame().shape);
  TEST_ASSERT_TRUE(e.frame().accent);

  e.setEmotion(Emotion::Error);
  advance(e, t, 400);
  TEST_ASSERT_EQUAL_UINT8(kShapeCross, e.frame().shape);
}

void test_speaking_mouth_follows_level() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  e.setActivity(Activity::Speaking);
  e.setLevel(0.0f);
  advance(e, t, 600);
  TEST_ASSERT_TRUE(e.frame().mouth);
  const float quiet = e.frame().mouthW;
  e.setLevel(1.0f);
  advance(e, t, 200);
  TEST_ASSERT_TRUE(e.frame().mouthW > quiet + 15.0f);
  TEST_ASSERT_TRUE(e.frame().mouthCy + e.frame().mouthH * 0.5f <= 64.0f);
  e.setActivity(Activity::Idle);
  advance(e, t, 100);
  TEST_ASSERT_FALSE(e.frame().mouth);
}

void test_sleeps_when_idle_and_wakes() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  e.setSleepAfter(1000);
  e.wake();
  advance(e, t, 1200);
  TEST_ASSERT_TRUE(e.asleep());
  advance(e, t, 5000);
  TEST_ASSERT_TRUE(e.frame().closure > 0.85f);
  e.setActivity(Activity::Listening);
  TEST_ASSERT_FALSE(e.asleep());
  advance(e, t, 1500);
  TEST_ASSERT_TRUE(e.frame().closure < 0.05f);
}

void test_listening_keeps_gaze_centered() {
  EyesEngine e(11);
  e.setAutoBlink(false);
  uint32_t t = 0;
  e.begin(t);
  e.setActivity(Activity::Listening);
  advance(e, t, 800);
  float minX = 1000, maxX = -1000;
  for (int i = 0; i < 400; ++i) {
    t += 10;
    e.update(t);
    float cx = e.frame().eye[0].cx;
    if (cx < minX) minX = cx;
    if (cx > maxX) maxX = cx;
  }
  TEST_ASSERT_TRUE(maxX - minX < 1.0f);
}

void test_acting_scans_side_to_side() {
  EyesEngine e(5);
  e.setAutoBlink(false);
  uint32_t t = 0;
  e.begin(t);
  e.setActivity(Activity::Acting);
  float minX = 1000, maxX = -1000;
  for (int i = 0; i < 300; ++i) {
    t += 10;
    e.update(t);
    float cx = e.frame().eye[0].cx;
    if (cx < minX) minX = cx;
    if (cx > maxX) maxX = cx;
  }
  TEST_ASSERT_TRUE(maxX - minX > 10.0f);
}

void test_manual_look() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  e.lookAt(1.0f, 0.0f);
  advance(e, t, 500);
  TEST_ASSERT_TRUE(e.frame().eye[0].cx > 41.0f + 15.0f);
  e.releaseLook();
  advance(e, t, 500);
  TEST_ASSERT_FLOAT_WITHIN(0.5f, 41.0f, e.frame().eye[0].cx);
}

void test_deterministic_with_same_seed() {
  EyesEngine a(1234), b(1234);
  uint32_t t = 0;
  a.begin(t);
  b.begin(t);
  for (int i = 0; i < 1000; ++i) {
    t += 16;
    a.update(t);
    b.update(t);
  }
  TEST_ASSERT_EQUAL_MEMORY(&a.frame(), &b.frame(), sizeof(FaceFrame));
}

void test_survives_millis_wraparound() {
  EyesEngine e(9);
  e.setSaccades(false);
  uint32_t t = 0xFFFFF000u;
  e.begin(t);
  int blinks = 0;
  bool was = false;
  for (int i = 0; i < 2000; ++i) {
    t += 10;  // cruza 0xFFFFFFFF -> 0
    e.update(t);
    if (e.blinking() && !was) ++blinks;
    was = e.blinking();
  }
  TEST_ASSERT_TRUE(blinks >= 2);
  TEST_ASSERT_TRUE(e.frame().eye[0].h > 30.0f || e.blinking());
}

// ------------------------------------------------------------------ dibujo

void test_draw_neutral_is_symmetric() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  RasterCanvas canvas(gPixels, 128, 64);
  canvas.clear();
  drawFace(e.frame(), canvas, FaceLayout::fit(128, 64));
  uint32_t lit = canvas.countLit();
  TEST_ASSERT_UINT32_WITHIN(150, 2480, lit);
  uint32_t left = 0, right = 0;
  for (int16_t y = 0; y < 64; ++y) {
    for (int16_t x = 0; x < 64; ++x) left += canvas.at(x, y) != kColorBackground;
    for (int16_t x = 64; x < 128; ++x) right += canvas.at(x, y) != kColorBackground;
  }
  TEST_ASSERT_UINT32_WITHIN(40, left, right);
}

void test_draw_sleeping_is_mostly_dark() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  e.sleep();
  advance(e, t, 6000);
  RasterCanvas canvas(gPixels, 128, 64);
  canvas.clear();
  drawFace(e.frame(), canvas, FaceLayout::fit(128, 64));
  TEST_ASSERT_TRUE(canvas.countLit() < 300);
  TEST_ASSERT_TRUE(canvas.countLit() > 20);
}

void test_draw_error_uses_accent_and_glow() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  e.setEmotion(Emotion::Error);
  advance(e, t, 1500);
  RasterCanvas canvas(gPixels, 128, 64);
  canvas.clear();
  drawFace(e.frame(), canvas, FaceLayout::fit(128, 64));
  TEST_ASSERT_TRUE(canvas.count(kColorAccent) > 200);
  TEST_ASSERT_EQUAL_UINT32(0, canvas.count(kColorEye));

  e.setEmotion(Emotion::Neutral);
  advance(e, t, 1500);
  FaceLayout glow = FaceLayout::fit(128, 64);
  glow.glow = true;
  canvas.clear();
  drawFace(e.frame(), canvas, glow);
  TEST_ASSERT_TRUE(canvas.count(kColorGlow) > 50);
}

void test_draw_happy_cuts_bottom() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  RasterCanvas canvas(gPixels, 128, 64);
  canvas.clear();
  drawFace(e.frame(), canvas, FaceLayout::fit(128, 64));
  const uint32_t neutral = canvas.countLit();
  e.setEmotion(Emotion::Happy);
  advance(e, t, 1500);
  canvas.clear();
  drawFace(e.frame(), canvas, FaceLayout::fit(128, 64));
  TEST_ASSERT_TRUE(canvas.countLit() < neutral * 3 / 4);
}

void test_mirror_preserves_area() {
  uint32_t t = 0;
  EyesEngine e = quietEngine(t);
  e.setEmotion(Emotion::Thinking);
  advance(e, t, 1500);
  RasterCanvas canvas(gPixels, 128, 64);
  canvas.clear();
  FaceLayout l = FaceLayout::fit(128, 64);
  drawFace(e.frame(), canvas, l);
  const uint32_t normal = canvas.countLit();
  l.mirrorX = true;
  canvas.clear();
  drawFace(e.frame(), canvas, l);
  TEST_ASSERT_UINT32_WITHIN(30, normal, canvas.countLit());
}

void test_layout_fit() {
  FaceLayout l = FaceLayout::fit(240, 280);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.875f, l.scale);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, l.originX);
  TEST_ASSERT_FLOAT_WITHIN(0.01f, 80.0f, l.originY);
}

void test_raster_primitives() {
  RasterCanvas canvas(gPixels, 128, 64);
  canvas.clear();
  canvas.fillCircle(64, 32, 10, kColorEye);
  // pi * 10.5^2 ~ 346
  TEST_ASSERT_UINT32_WITHIN(25, 346, canvas.countLit());
  canvas.clear();
  canvas.fillTriangle(0, 0, 40, 0, 0, 40, kColorEye);
  TEST_ASSERT_UINT32_WITHIN(60, 820, canvas.countLit());
  canvas.clear();
  canvas.fillRect(-10, -10, 20, 20, kColorEye);  // recorte en la esquina
  TEST_ASSERT_EQUAL_UINT32(100, canvas.countLit());
  canvas.clear();
  canvas.fillRoundRect(10, 10, 30, 20, 6, kColorEye);
  TEST_ASSERT_TRUE(canvas.countLit() < 600 && canvas.countLit() > 560);
  TEST_ASSERT_EQUAL_UINT8(kColorBackground, canvas.at(10, 10));
  TEST_ASSERT_EQUAL_UINT8(kColorEye, canvas.at(25, 20));
}

// ------------------------------------------------------------------ protocolo serie

void test_serial_commands() {
  SerialCommand c;
  char l1[] = "S:thinking";
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialError::None, (uint8_t)parseSerialLine(l1, &c));
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialCmd::Status, (uint8_t)c.cmd);
  TEST_ASSERT_EQUAL_UINT8((uint8_t)Activity::Thinking, c.value);

  char l2[] = " E:Happy ";
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialError::None, (uint8_t)parseSerialLine(l2, &c));
  TEST_ASSERT_EQUAL_UINT8((uint8_t)Emotion::Happy, c.value);

  char l3[] = "T:Hola mundo";
  parseSerialLine(l3, &c);
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialCmd::Text, (uint8_t)c.cmd);
  TEST_ASSERT_EQUAL_STRING("Hola mundo", c.text);

  char l4[] = "N:Correo|Tienes 3 mensajes";
  parseSerialLine(l4, &c);
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialCmd::Notify, (uint8_t)c.cmd);
  TEST_ASSERT_EQUAL_STRING("Correo", c.text);
  TEST_ASSERT_EQUAL_STRING("Tienes 3 mensajes", c.text2);

  char l5[] = "G:-50,25";
  parseSerialLine(l5, &c);
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialCmd::Look, (uint8_t)c.cmd);
  TEST_ASSERT_EQUAL_INT8(-50, c.lookX);
  TEST_ASSERT_EQUAL_INT8(25, c.lookY);

  char l6[] = "G:";
  parseSerialLine(l6, &c);
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialCmd::LookRelease, (uint8_t)c.cmd);

  char l7[] = "?";
  parseSerialLine(l7, &c);
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialCmd::Ping, (uint8_t)c.cmd);

  char l8[] = "Z:1";
  parseSerialLine(l8, &c);
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialCmd::Sleep, (uint8_t)c.cmd);

  char l9[] = "C:200";
  parseSerialLine(l9, &c);
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialCmd::Contrast, (uint8_t)c.cmd);
  TEST_ASSERT_EQUAL_UINT8(200, c.value);
}

void test_serial_errors() {
  SerialCommand c;
  char a[] = "E:bored";
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialError::Value, (uint8_t)parseSerialLine(a, &c));
  char b[] = "L:12";
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialError::Value, (uint8_t)parseSerialLine(b, &c));
  char d[] = "X:1";
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialError::Unknown, (uint8_t)parseSerialLine(d, &c));
  char f[] = "   ";
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialError::Empty, (uint8_t)parseSerialLine(f, &c));
  char g[] = "G:10";
  TEST_ASSERT_EQUAL_UINT8((uint8_t)SerialError::Value, (uint8_t)parseSerialLine(g, &c));
  TEST_ASSERT_EQUAL_STRING("value", serialErrorCode(SerialError::Value));
}

void test_line_reader() {
  SerialLineReader<8> r;
  const char* input = "S:idle\r\nTOOLONGLINE\nK\n";
  int lines = 0;
  for (const char* p = input; *p; ++p) {
    if (!r.feed(*p)) continue;
    ++lines;
    if (lines == 1) {
      TEST_ASSERT_EQUAL_STRING("S:idle", r.line());
      TEST_ASSERT_FALSE(r.overflowed());
    } else if (lines == 2) {
      TEST_ASSERT_TRUE(r.overflowed());
    } else {
      TEST_ASSERT_EQUAL_STRING("K", r.line());
      TEST_ASSERT_FALSE(r.overflowed());
    }
  }
  TEST_ASSERT_EQUAL_INT(3, lines);
  // Los bytes ISO-8859-1 se conservan.
  SerialLineReader<16> latin;
  const char text[] = {'T', ':', (char)0xE1, 'r', 'b', 'o', 'l', '\n', 0};
  for (const char* p = text; *p; ++p) latin.feed(*p);
  TEST_ASSERT_EQUAL_UINT8(0xE1, (uint8_t)latin.line()[2]);
}

void test_serial_formatting() {
  char buf[32];
  formatButtonEvent(buf, sizeof(buf), 1, "down");
  TEST_ASSERT_EQUAL_STRING("B:1:down", buf);
  formatHello(buf, sizeof(buf), "gmini-usb-face", "0.1.0");
  TEST_ASSERT_EQUAL_STRING("H:gmini-usb-face;0.1.0;1", buf);
  char tiny[6];
  formatButtonEvent(tiny, sizeof(tiny), 12, "long");
  TEST_ASSERT_EQUAL_STRING("B:12:", tiny);
}

int main(int, char**) {
  UNITY_BEGIN();
  RUN_TEST(test_parse_names);
  RUN_TEST(test_begin_opens_eyes);
  RUN_TEST(test_neutral_geometry);
  RUN_TEST(test_emotions_converge_to_presets);
  RUN_TEST(test_forced_blink_timeline);
  RUN_TEST(test_auto_blink_happens);
  RUN_TEST(test_shape_change_waits_for_closed_eyes);
  RUN_TEST(test_speaking_mouth_follows_level);
  RUN_TEST(test_sleeps_when_idle_and_wakes);
  RUN_TEST(test_listening_keeps_gaze_centered);
  RUN_TEST(test_acting_scans_side_to_side);
  RUN_TEST(test_manual_look);
  RUN_TEST(test_deterministic_with_same_seed);
  RUN_TEST(test_survives_millis_wraparound);
  RUN_TEST(test_draw_neutral_is_symmetric);
  RUN_TEST(test_draw_sleeping_is_mostly_dark);
  RUN_TEST(test_draw_error_uses_accent_and_glow);
  RUN_TEST(test_draw_happy_cuts_bottom);
  RUN_TEST(test_mirror_preserves_area);
  RUN_TEST(test_layout_fit);
  RUN_TEST(test_raster_primitives);
  RUN_TEST(test_serial_commands);
  RUN_TEST(test_serial_errors);
  RUN_TEST(test_line_reader);
  RUN_TEST(test_serial_formatting);
  return UNITY_END();
}
