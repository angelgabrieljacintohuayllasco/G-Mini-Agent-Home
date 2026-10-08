#include "ui.h"

#include <Arduino.h>
#include <GMiniRaster.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <freertos/task.h>
#include <string.h>

#include "config.h"

#if GMINI_DISPLAY == GMINI_DISPLAY_OLED
#include <U8g2lib.h>
#include <Wire.h>
#elif GMINI_HAS_TFT
#define LGFX_USE_V1
#include <LovyanGFX.hpp>
#include <U8g2lib.h>  // solo por las fuentes con acentos (ISO-8859-1)
#endif

namespace ui {

namespace {

enum class Cmd : uint8_t {
  Emotion,
  Activity,
  Blink,
  Look,
  LookRelease,
  Wake,
  Caption,
  ClearCaption,
  Notify,
  Setup,
  Brightness,
  Online,
  LedOverride,
  LedAuto,
};

struct Msg {
  Cmd cmd;
  uint8_t value;
  uint8_t value2;
  int8_t x;
  int8_t y;
  uint32_t ms;
  uint32_t color;
  char text[96];
  char text2[200];
};

QueueHandle_t gQueue = nullptr;
volatile float gLevel = 0.0f;

// Estado propiedad de la tarea de interfaz.
gmini::EyesEngine gEyes(esp_random());
char gCaption[96] = "";
uint32_t gCaptionUntil = 0;
char gNotifyTitle[96] = "";
char gNotifyBody[200] = "";
uint32_t gNotifyUntil = 0;
char gSetupTitle[96] = "";
char gSetupBody[200] = "";
bool gSetup = false;
bool gWifi = false;
bool gServer = false;

void post(const Msg& m) {
  if (gQueue) xQueueSend(gQueue, &m, pdMS_TO_TICKS(20));
}

Msg make(Cmd c) {
  Msg m;
  memset(&m, 0, sizeof(m));
  m.cmd = c;
  return m;
}

#if GMINI_DISPLAY != GMINI_DISPLAY_NONE
// Corta texto UTF-8 en lineas que entren en maxWidth. Devuelve cuantas lineas escribio.
typedef int (*MeasureFn)(const char* text);
uint8_t wrapText(const char* text, MeasureFn measure, int maxWidth, char lines[][64], uint8_t maxLines) {
  uint8_t count = 0;
  char current[64] = "";
  const char* p = text;
  while (*p && count < maxLines) {
    while (*p == ' ' || *p == '\n') {
      if (*p == '\n' && current[0]) {
        strlcpy(lines[count++], current, 64);
        current[0] = '\0';
        if (count >= maxLines) return count;
      }
      ++p;
    }
    if (!*p) break;
    const char* end = p;
    while (*end && *end != ' ' && *end != '\n') ++end;
    char word[64];
    size_t wlen = (size_t)(end - p);
    if (wlen > 62) wlen = 62;
    // No partir un caracter UTF-8 por la mitad.
    while (wlen > 0 && ((uint8_t)p[wlen] & 0xC0) == 0x80) --wlen;
    memcpy(word, p, wlen);
    word[wlen] = '\0';
    char candidate[128];
    snprintf(candidate, sizeof(candidate), current[0] ? "%s %s" : "%s%s", current, word);
    if (measure(candidate) <= maxWidth && strlen(candidate) < 63) {
      strlcpy(current, candidate, sizeof(current));
      p = end;
    } else if (current[0]) {
      strlcpy(lines[count++], current, 64);
      current[0] = '\0';
    } else {
      strlcpy(lines[count++], word, 64);  // palabra mas larga que la linea
      p = end;
    }
  }
  if (current[0] && count < maxLines) strlcpy(lines[count++], current, 64);
  return count;
}
#endif

// Cada variante de pantalla define estas tres funciones mas abajo.
void displayBegin();
void displayBrightness(uint8_t v);
void render(uint32_t now);

void applyMessage(const Msg& m, uint32_t now) {
  switch (m.cmd) {
    case Cmd::Emotion: gEyes.setEmotion((gmini::Emotion)m.value); break;
    case Cmd::Activity: gEyes.setActivity((gmini::Activity)m.value); break;
    case Cmd::Blink: gEyes.blink(); break;
    case Cmd::Look: gEyes.lookAt(m.x / 100.0f, m.y / 100.0f); break;
    case Cmd::LookRelease: gEyes.releaseLook(); break;
    case Cmd::Wake: gEyes.wake(); break;
    case Cmd::Caption:
      strlcpy(gCaption, m.text, sizeof(gCaption));
      gCaptionUntil = m.ms ? now + m.ms : 0;
      break;
    case Cmd::ClearCaption: gCaption[0] = '\0'; break;
    case Cmd::Notify:
      strlcpy(gNotifyTitle, m.text, sizeof(gNotifyTitle));
      strlcpy(gNotifyBody, m.text2, sizeof(gNotifyBody));
      gNotifyUntil = now + m.ms;
      gEyes.wake();
      leds::notifyPulse();
      break;
    case Cmd::Setup:
      gSetup = m.text[0] != '\0';
      strlcpy(gSetupTitle, m.text, sizeof(gSetupTitle));
      strlcpy(gSetupBody, m.text2, sizeof(gSetupBody));
      break;
    case Cmd::Brightness:
      leds::setBrightness(m.value);
      displayBrightness(m.value);
      break;
    case Cmd::Online:
      gWifi = m.value != 0;
      gServer = m.value2 != 0;
      break;
    case Cmd::LedOverride: leds::override(m.color, (leds::Effect)m.value, m.ms); break;
    case Cmd::LedAuto: leds::autoMode(); break;
  }
}

#if GMINI_DISPLAY != GMINI_DISPLAY_NONE
bool captionActive(uint32_t now) {
  if (gCaption[0] && gCaptionUntil && (int32_t)(now - gCaptionUntil) >= 0) gCaption[0] = '\0';
  return gCaption[0] != '\0';
}

bool notifyActive(uint32_t now) { return gNotifyTitle[0] && (int32_t)(now - gNotifyUntil) < 0; }
#endif

// ================================================================ OLED
#if GMINI_DISPLAY == GMINI_DISPLAY_OLED

#if GMINI_OLED_SH1106
U8G2_SH1106_128X64_NONAME_F_HW_I2C gOled(U8G2_R0, U8X8_PIN_NONE, PIN_I2C_SCL, PIN_I2C_SDA);
#else
U8G2_SSD1306_128X64_NONAME_F_HW_I2C gOled(U8G2_R0, U8X8_PIN_NONE, PIN_I2C_SCL, PIN_I2C_SDA);
#endif

class OledCanvas : public gmini::SpanCanvas {
 public:
  OledCanvas() : SpanCanvas(128, 64) {}

 protected:
  void span(int16_t x0, int16_t x1, int16_t y, uint8_t color) override {
    gOled.setDrawColor(color == gmini::kColorBackground ? 0 : 1);
    gOled.drawHLine(x0, y, x1 - x0 + 1);
  }
};

OledCanvas gCanvas;
float gCompact = 0.0f;  // 0 = cara completa, 1 = cara reducida con texto debajo

int measureSmall(const char* t) {
  gOled.setFont(u8g2_font_6x10_tf);
  return gOled.getUTF8Width(t);
}

void displayBegin() {
  gOled.setBusClock(GMINI_OLED_I2C_HZ);
  gOled.begin();
  gOled.enableUTF8Print();
  gOled.setFontPosTop();
}

void drawCentered(const char* text, int y, const uint8_t* font) {
  gOled.setFont(font);
  int w = gOled.getUTF8Width(text);
  gOled.drawUTF8((128 - w) / 2, y, text);
}

void drawStatusDot(uint32_t now) {
  if (gWifi && gServer) return;
  // Punto parpadeante arriba a la derecha: sin red (lleno) o sin servidor (hueco).
  if ((now / 600) % 2) return;
  gOled.setDrawColor(1);
  if (!gWifi) {
    gOled.drawDisc(124, 3, 2);
  } else {
    gOled.drawCircle(124, 3, 2);
  }
}

void render(uint32_t now) {
  gOled.clearBuffer();
  if (gSetup) {
    char lines[5][64];
    drawCentered(gSetupTitle, 2, u8g2_font_7x13B_tf);
    uint8_t n = wrapText(gSetupBody, measureSmall, 124, lines, 4);
    gOled.setFont(u8g2_font_6x10_tf);
    for (uint8_t i = 0; i < n; ++i) drawCentered(lines[i], 18 + i * 11, u8g2_font_6x10_tf);
    gOled.sendBuffer();
    return;
  }
  if (notifyActive(now)) {
    char lines[4][64];
    gOled.setDrawColor(1);
    gOled.drawRBox(0, 0, 128, 14, 3);
    gOled.setDrawColor(0);
    gOled.setFont(u8g2_font_7x13B_tf);
    gOled.drawUTF8(4, 1, gNotifyTitle);
    gOled.setDrawColor(1);
    uint8_t n = wrapText(gNotifyBody, measureSmall, 124, lines, 4);
    gOled.setFont(u8g2_font_6x10_tf);
    for (uint8_t i = 0; i < n; ++i) gOled.drawUTF8(2, 17 + i * 11, lines[i]);
    gOled.sendBuffer();
    return;
  }
  const bool text = captionActive(now);
  gCompact += ((text ? 1.0f : 0.0f) - gCompact) * 0.25f;
  gmini::FaceLayout full = gmini::FaceLayout::fit(128, 64);
  gmini::FaceLayout small = gmini::FaceLayout::fit(128, 40, 0.95f);
  gmini::FaceLayout l;
  l.scale = full.scale + (small.scale - full.scale) * gCompact;
  l.originX = full.originX + (small.originX - full.originX) * gCompact;
  l.originY = full.originY + (small.originY - full.originY) * gCompact;
  gmini::drawFace(gEyes.frame(), gCanvas, l);
  if (text && gCompact > 0.6f) {
    char lines[2][64];
    uint8_t n = wrapText(gCaption, measureSmall, 126, lines, 2);
    gOled.setDrawColor(1);
    for (uint8_t i = 0; i < n; ++i) drawCentered(lines[i], 42 + i * 11, u8g2_font_6x10_tf);
  }
  drawStatusDot(now);
  gOled.sendBuffer();
}

void displayBrightness(uint8_t v) { gOled.setContrast(v); }

// ================================================================ TFT
#elif GMINI_HAS_TFT

class Lcd : public lgfx::LGFX_Device {
#if GMINI_DISPLAY == GMINI_DISPLAY_ST7789
  lgfx::Panel_ST7789 panel_;
#else
  lgfx::Panel_GC9A01 panel_;
#endif
  lgfx::Bus_SPI bus_;
  lgfx::Light_PWM light_;

 public:
  Lcd() {
    {
      auto cfg = bus_.config();
      cfg.spi_host = SPI2_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = GMINI_TFT_SPI_HZ;
      cfg.freq_read = 16000000;
      cfg.spi_3wire = true;
      cfg.use_lock = true;
      cfg.dma_channel = SPI_DMA_CH_AUTO;
      cfg.pin_sclk = PIN_TFT_SCLK;
      cfg.pin_mosi = PIN_TFT_MOSI;
      cfg.pin_miso = -1;
      cfg.pin_dc = PIN_TFT_DC;
      bus_.config(cfg);
      panel_.setBus(&bus_);
    }
    {
      auto cfg = panel_.config();
      cfg.pin_cs = PIN_TFT_CS;
      cfg.pin_rst = PIN_TFT_RST;
      cfg.pin_busy = -1;
      cfg.panel_width = GMINI_TFT_WIDTH;
      cfg.panel_height = GMINI_TFT_HEIGHT;
#if GMINI_DISPLAY == GMINI_DISPLAY_ST7789
      cfg.memory_width = 240;
      cfg.memory_height = 320;
#else
      cfg.memory_width = 240;
      cfg.memory_height = 240;
#endif
      cfg.offset_x = GMINI_TFT_OFFSET_X;
      cfg.offset_y = GMINI_TFT_OFFSET_Y;
      cfg.offset_rotation = 0;
      cfg.readable = false;
      cfg.invert = true;
      cfg.rgb_order = false;
      cfg.dlen_16bit = false;
      cfg.bus_shared = false;
      panel_.config(cfg);
    }
    {
      auto cfg = light_.config();
      cfg.pin_bl = PIN_TFT_BL;
      cfg.invert = false;
      cfg.freq = 12000;
      cfg.pwm_channel = 7;
      light_.config(cfg);
      panel_.setLight(&light_);
    }
    setPanel(&panel_);
  }
};

Lcd gLcd;
LGFX_Sprite gFace(&gLcd);
LGFX_Sprite gText(&gLcd);
const int16_t kFaceH = GMINI_TFT_HEIGHT * 5 / 9;
const int16_t kTextH = GMINI_TFT_HEIGHT - kFaceH;
const lgfx::U8g2font kFontBody(u8g2_font_helvR14_tf);
const lgfx::U8g2font kFontTitle(u8g2_font_helvB14_tf);
uint32_t gTextHash = 0;

uint32_t rgbFor(uint8_t color) {
  switch (color) {
    case gmini::kColorEye: return gmini::presets::kColorEye;
    case gmini::kColorAccent: return gmini::presets::kColorAccent;
    case gmini::kColorGlow: return gmini::presets::kColorGlow;
    case gmini::kColorText: return gmini::presets::kColorText;
    default: return gmini::presets::kColorBackground;
  }
}

class SpriteCanvas : public gmini::FaceCanvas {
 public:
  explicit SpriteCanvas(LGFX_Sprite& s) : s_(s) {}
  void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint8_t c) override { s_.fillRect(x, y, w, h, rgbFor(c)); }
  void fillRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint8_t c) override {
    s_.fillRoundRect(x, y, w, h, r, rgbFor(c));
  }
  void fillCircle(int16_t cx, int16_t cy, int16_t r, uint8_t c) override { s_.fillCircle(cx, cy, r, rgbFor(c)); }
  void fillTriangle(int16_t x0, int16_t y0, int16_t x1, int16_t y1, int16_t x2, int16_t y2, uint8_t c) override {
    s_.fillTriangle(x0, y0, x1, y1, x2, y2, rgbFor(c));
  }

 private:
  LGFX_Sprite& s_;
};

SpriteCanvas gCanvas(gFace);

int measureBody(const char* t) {
  gText.setFont(&kFontBody);
  return gText.textWidth(t);
}

void displayBegin() {
  gLcd.init();
  gLcd.setRotation(0);
  gLcd.fillScreen(TFT_BLACK);
  gFace.setColorDepth(16);
  gFace.setPsram(true);
  gFace.createSprite(GMINI_TFT_WIDTH, kFaceH);
  gText.setColorDepth(16);
  gText.setPsram(true);
  gText.createSprite(GMINI_TFT_WIDTH, kTextH);
}

uint32_t hashText(const char* a, const char* b, uint32_t extra) {
  uint32_t h = 2166136261u ^ extra;
  for (const char* p = a; *p; ++p) h = (h ^ (uint8_t)*p) * 16777619u;
  h = (h ^ 0xFF) * 16777619u;
  for (const char* p = b; *p; ++p) h = (h ^ (uint8_t)*p) * 16777619u;
  return h;
}

void drawTextArea(const char* title, const char* body, uint32_t titleColor) {
  gText.fillScreen(TFT_BLACK);
  // En la pantalla redonda el texto se mete hacia el centro.
  const int margin = GMINI_DISPLAY == GMINI_DISPLAY_GC9A01 ? 34 : 12;
  const int width = GMINI_TFT_WIDTH - 2 * margin;
  int y = 4;
  gText.setTextDatum(lgfx::top_center);
  if (title && *title) {
    gText.setFont(&kFontTitle);
    gText.setTextColor(titleColor);
    gText.drawString(title, GMINI_TFT_WIDTH / 2, y);
    y += 24;
  }
  char lines[4][64];
  uint8_t n = wrapText(body, measureBody, width, lines, (kTextH - y) / 22);
  gText.setFont(&kFontBody);
  gText.setTextColor(gmini::presets::kColorText);
  for (uint8_t i = 0; i < n; ++i) gText.drawString(lines[i], GMINI_TFT_WIDTH / 2, y + i * 22);
  gText.pushSprite(0, kFaceH);
}

void render(uint32_t now) {
  gFace.fillScreen(TFT_BLACK);
  gmini::FaceLayout l = gmini::FaceLayout::fit(GMINI_TFT_WIDTH, kFaceH, 0.92f);
  l.originY += kFaceH * 0.06f;
  l.glow = true;
  gmini::drawFace(gEyes.frame(), gCanvas, l);
  if (!gWifi || !gServer) {
    if ((now / 600) % 2) gFace.fillCircle(GMINI_TFT_WIDTH / 2, 10, 4, gWifi ? 0xFFB020u : 0xFF3B1Fu);
  }
  gFace.pushSprite(0, 0);

  // El area de texto solo se redibuja cuando cambia.
  const char* title = "";
  const char* body = "";
  uint32_t titleColor = gmini::presets::kColorEye;
  if (gSetup) {
    title = gSetupTitle;
    body = gSetupBody;
  } else if (notifyActive(now)) {
    title = gNotifyTitle;
    body = gNotifyBody;
    titleColor = gmini::presets::kColorAccent;
  } else if (captionActive(now)) {
    body = gCaption;
  }
  const uint32_t h = hashText(title, body, titleColor);
  if (h != gTextHash) {
    gTextHash = h;
    drawTextArea(title, body, titleColor);
  }
}

void displayBrightness(uint8_t v) { gLcd.setBrightness(v); }

// ================================================================ sin pantalla
#else

void displayBegin() {}
void displayBrightness(uint8_t) {}
void render(uint32_t) {}

#endif

void uiTask(void*) {
  displayBegin();
  gEyes.begin(millis());
  TickType_t last = xTaskGetTickCount();
  const TickType_t period = pdMS_TO_TICKS(1000 / GMINI_FACE_FPS);
  Msg m;
  for (;;) {
    const uint32_t now = millis();
    while (xQueueReceive(gQueue, &m, 0) == pdTRUE) applyMessage(m, now);
    gEyes.setLevel(gLevel);
    gEyes.update(now);
    render(now);
    leds::update(now, gEyes.activity(), gEyes.emotion(), gEyes.level(), gEyes.asleep(), gSetup, !gWifi || !gServer);
    vTaskDelayUntil(&last, period);
  }
}

}  // namespace

void begin(uint8_t brightness, uint16_t sleepMinutes) {
  gQueue = xQueueCreate(10, sizeof(Msg));
  gEyes.setSleepAfter((uint32_t)sleepMinutes * 60000UL);
  leds::begin(brightness);
  // Nucleo 1 junto al bucle de Arduino; prioridad mayor para que la animacion
  // siga fluida mientras el bucle espera respuestas de red.
  xTaskCreatePinnedToCore(uiTask, "gmini-ui", 8192, nullptr, 3, nullptr, 1);
  setBrightness(brightness);
}

void setEmotion(gmini::Emotion emotion) {
  Msg m = make(Cmd::Emotion);
  m.value = (uint8_t)emotion;
  post(m);
}

void setActivity(gmini::Activity activity) {
  Msg m = make(Cmd::Activity);
  m.value = (uint8_t)activity;
  post(m);
}

void setLevel(float level) { gLevel = level; }
void blink() { post(make(Cmd::Blink)); }

void lookAt(float x, float y) {
  Msg m = make(Cmd::Look);
  m.x = (int8_t)(x * 100);
  m.y = (int8_t)(y * 100);
  post(m);
}

void releaseLook() { post(make(Cmd::LookRelease)); }
void wake() { post(make(Cmd::Wake)); }

void caption(const char* text, uint32_t ms) {
  Msg m = make(Cmd::Caption);
  strlcpy(m.text, text ? text : "", sizeof(m.text));
  m.ms = ms;
  post(m);
}

void clearCaption() { post(make(Cmd::ClearCaption)); }

void notify(const char* title, const char* body, uint32_t ms) {
  Msg m = make(Cmd::Notify);
  strlcpy(m.text, title ? title : "", sizeof(m.text));
  strlcpy(m.text2, body ? body : "", sizeof(m.text2));
  m.ms = ms;
  post(m);
}

void setup(const char* title, const char* body) {
  Msg m = make(Cmd::Setup);
  strlcpy(m.text, title ? title : "", sizeof(m.text));
  strlcpy(m.text2, body ? body : "", sizeof(m.text2));
  post(m);
}

void setBrightness(uint8_t brightness) {
  Msg m = make(Cmd::Brightness);
  m.value = brightness;
  post(m);
}

void setOnline(bool wifi, bool server) {
  Msg m = make(Cmd::Online);
  m.value = wifi;
  m.value2 = server;
  post(m);
}

void ledOverride(uint32_t rgb, leds::Effect effect, uint32_t ms) {
  Msg m = make(Cmd::LedOverride);
  m.color = rgb;
  m.value = (uint8_t)effect;
  m.ms = ms;
  post(m);
}

void ledAuto() { post(make(Cmd::LedAuto)); }

bool hasDisplay() { return GMINI_DISPLAY != GMINI_DISPLAY_NONE; }

const char* displayName() {
#if GMINI_DISPLAY == GMINI_DISPLAY_OLED
  return GMINI_OLED_SH1106 ? "sh1106" : "ssd1306";
#elif GMINI_DISPLAY == GMINI_DISPLAY_ST7789
  return "st7789";
#elif GMINI_DISPLAY == GMINI_DISPLAY_GC9A01
  return "gc9a01";
#else
  return "none";
#endif
}

}  // namespace ui
