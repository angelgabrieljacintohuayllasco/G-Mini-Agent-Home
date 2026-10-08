// G-Mini Home - cara USB para Arduino Uno / Nano.
//
// OLED SSD1306 (o SH1106) de 128x64 por I2C con dos ojos animados y dos
// botones. Se conecta por USB a la PC, donde gmini_serial_bridge.py traduce
// entre este protocolo serie y G-Mini (estado del agente, avisos y voz).
//
// Protocolo (115200 baudios, una orden por linea): ver docs/serial-protocol.md
//   PC -> placa: S:<estado> E:<emocion> T:<texto> N:<titulo>|<cuerpo> L:<0-9>
//                G:<x>,<y> K Z:<0|1> C:<0-255> ? V
//   placa -> PC: H:gmini-usb-face;<version>;1  OK  B:<id>:<down|up|long>  ERR:<codigo>
//
// Cableado (Uno/Nano): OLED SDA -> A4, SCL -> A5, VCC -> 5V, GND -> GND.
// Boton 1 (hablar) -> D2 y GND. Boton 2 (cancelar) -> D3 y GND.
//
// Requiere las bibliotecas U8g2 y GMiniEyes (firmware/libraries/GMiniEyes).

#include <Arduino.h>
#include <GMiniEyes.h>
#include <GMiniRaster.h>
#include <GMiniSerialProto.h>
#include <U8g2lib.h>
#include <Wire.h>

// 1 = controlador SH1106 (modulos de 1,3"). 0 = SSD1306 (0,96").
#ifndef GMINI_OLED_SH1106
#define GMINI_OLED_SH1106 0
#endif

// Saludo del protocolo: H:<firmware>;<version>;<protocolo>
#define GMINI_HELLO "H:gmini-usb-face;0.1.0;1"

static const uint8_t kButtonPins[] = {2, 3};
static const uint8_t kButtonCount = sizeof(kButtonPins);
static const uint16_t kLongPressMs = 1500;
static const uint8_t kFrameMs = 33;  // ~30 cuadros/s; el bus I2C a 400 kHz es el limite

// Bufer de 2 paginas (256 bytes): la RAM del Uno no alcanza para el cuadro completo.
#if GMINI_OLED_SH1106
U8G2_SH1106_128X64_NONAME_2_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
#else
U8G2_SSD1306_128X64_NONAME_2_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
#endif

class OledCanvas : public gmini::SpanCanvas {
 public:
  OledCanvas() : SpanCanvas(128, 64) {}

 protected:
  void span(int16_t x0, int16_t x1, int16_t y, uint8_t color) override {
    oled.setDrawColor(color == gmini::kColorBackground ? 0 : 1);
    oled.drawHLine(x0, y, x1 - x0 + 1);
  }
};

OledCanvas canvas;
gmini::EyesEngine eyes;
gmini::SerialLineReader<72> reader;

char caption[44] = "";
char notifyTitle[22] = "";
char notifyBody[66] = "";
uint32_t notifyUntil = 0;
float compact = 0.0f;
uint32_t lastFrame = 0;

struct ButtonState {
  bool stable;
  bool raw;
  bool longSent;
  uint32_t changedAt;
  uint32_t pressedAt;
};
ButtonState buttons[kButtonCount];

void sendLine(const char* line) { Serial.println(line); }

// B:<id>:<accion>. Con dos botones el id es un solo digito.
void sendButton(uint8_t index, const char* action) {
  char buf[12] = "B:1:";
  buf[2] = (char)('1' + index);
  strcat(buf, action);
  sendLine(buf);
}

void sendHello() { Serial.println(F(GMINI_HELLO)); }

void copyText(char* dst, size_t len, const char* src) {
  strncpy(dst, src, len - 1);
  dst[len - 1] = '\0';
}

void handleCommand(char* line) {
  gmini::SerialCommand c;
  const gmini::SerialError err = gmini::parseSerialLine(line, &c);
  if (err == gmini::SerialError::Empty) return;
  if (err != gmini::SerialError::None) {
    Serial.print(F("ERR:"));
    Serial.println(gmini::serialErrorCode(err));
    return;
  }
  switch (c.cmd) {
    case gmini::SerialCmd::Status: eyes.setActivity((gmini::Activity)c.value); break;
    case gmini::SerialCmd::Emotion: eyes.setEmotion((gmini::Emotion)c.value); break;
    case gmini::SerialCmd::Text: copyText(caption, sizeof(caption), c.text); break;
    case gmini::SerialCmd::Notify:
      copyText(notifyTitle, sizeof(notifyTitle), c.text);
      copyText(notifyBody, sizeof(notifyBody), c.text2);
      notifyUntil = millis() + 6000;
      eyes.wake();
      break;
    case gmini::SerialCmd::Level: eyes.setLevel(c.value / 9.0f); break;
    case gmini::SerialCmd::Look: eyes.lookAt(c.lookX / 100.0f, c.lookY / 100.0f); break;
    case gmini::SerialCmd::LookRelease: eyes.releaseLook(); break;
    case gmini::SerialCmd::Blink: eyes.blink(); break;
    case gmini::SerialCmd::Sleep: eyes.sleep(); break;
    case gmini::SerialCmd::Wake: eyes.wake(); break;
    case gmini::SerialCmd::Contrast: oled.setContrast(c.value); break;
    case gmini::SerialCmd::Ping: sendLine("OK"); break;
    case gmini::SerialCmd::Version: sendHello(); break;
    case gmini::SerialCmd::None: break;
  }
}

void pollSerial() {
  while (Serial.available() > 0) {
    if (!reader.feed((char)Serial.read())) continue;
    if (reader.overflowed()) {
      sendLine("ERR:overflow");
      continue;
    }
    handleCommand(reader.line());
  }
}

void pollButtons(uint32_t now) {
  for (uint8_t i = 0; i < kButtonCount; ++i) {
    ButtonState& b = buttons[i];
    const bool level = digitalRead(kButtonPins[i]) == LOW;
    if (level != b.raw) {
      b.raw = level;
      b.changedAt = now;
    }
    if (b.raw != b.stable && now - b.changedAt >= 25) {
      b.stable = b.raw;
      if (b.stable) {
        b.pressedAt = now;
        b.longSent = false;
        sendButton(i, "down");
        eyes.wake();
      } else {
        sendButton(i, "up");
      }
    }
    if (b.stable && !b.longSent && now - b.pressedAt >= kLongPressMs) {
      b.longSent = true;
      sendButton(i, "long");
    }
  }
}

// ------------------------------------------------------------------ texto
// La fuente _tr (solo ASCII) ocupa la mitad de flash que la _tf. Las vocales
// con tilde, la enie y la dieresis se dibujan como la letra base mas su marca.
// El texto llega en ISO-8859-1 (el puente convierte desde UTF-8).
enum Mark : uint8_t { kAcute = 1, kTilde = 2, kDiaeresis = 3 };
struct Latin1Glyph {
  uint8_t code;
  char base;
  uint8_t mark;
};
const Latin1Glyph kLatin1[] PROGMEM = {
    {0xE1, 'a', kAcute}, {0xE9, 'e', kAcute}, {0xED, 'i', kAcute},     {0xF3, 'o', kAcute},
    {0xFA, 'u', kAcute}, {0xF1, 'n', kTilde}, {0xFC, 'u', kDiaeresis}, {0xC1, 'A', kAcute},
    {0xC9, 'E', kAcute}, {0xCD, 'I', kAcute}, {0xD3, 'O', kAcute},     {0xDA, 'U', kAcute},
    {0xD1, 'N', kTilde}, {0xDC, 'U', kDiaeresis},
};
const uint8_t kCharW = 6;

// Los signos de apertura (inverted) no tienen glifo: se omiten.
bool skipChar(uint8_t c) { return c == 0xBF || c == 0xA1; }

void drawMark(int x, int y, uint8_t mark, bool upper) {
  const int top = upper ? y - 1 : y + 1;
  switch (mark) {
    case kAcute:
      oled.drawPixel(x + 3, top);
      oled.drawPixel(x + 2, top + 1);
      break;
    case kTilde:
      oled.drawPixel(x + 1, top + 1);
      oled.drawPixel(x + 2, top);
      oled.drawPixel(x + 3, top + 1);
      oled.drawPixel(x + 4, top);
      break;
    default:
      oled.drawPixel(x + 1, top + 1);
      oled.drawPixel(x + 3, top + 1);
      break;
  }
}

void drawText(int x, int y, const char* s) {
  for (; *s; ++s) {
    const uint8_t c = (uint8_t)*s;
    if (skipChar(c)) continue;
    if (c < 0x80) {
      if (c >= 32) oled.drawGlyph(x, y, c);
    } else {
      char base = '?';
      uint8_t mark = 0;
      for (uint8_t i = 0; i < sizeof(kLatin1) / sizeof(kLatin1[0]); ++i) {
        if (pgm_read_byte(&kLatin1[i].code) == c) {
          base = (char)pgm_read_byte(&kLatin1[i].base);
          mark = pgm_read_byte(&kLatin1[i].mark);
          break;
        }
      }
      oled.drawGlyph(x, y, base);
      if (mark) drawMark(x, y, mark, base < 'a');
    }
    x += kCharW;
  }
}

int textWidth(const char* s) {
  int n = 0;
  for (; *s; ++s) n += skipChar((uint8_t)*s) ? 0 : 1;
  return n * kCharW;
}

void drawCentered(const char* text, int y) { drawText((128 - textWidth(text)) / 2, y, text); }

// Corta el texto en lineas de hasta 21 caracteres (128 px / 6 px) por palabras.
void drawWrapped(const char* p, int y, uint8_t maxLines, bool centered) {
  char line[22];
  for (uint8_t row = 0; row < maxLines && *p; ++row) {
    size_t n = strlen(p);
    if (n > 21) {
      n = 21;
      while (n > 0 && p[n] != ' ') --n;
      if (n == 0) n = 21;
    }
    copyText(line, n + 1, p);
    if (centered) {
      drawCentered(line, y);
    } else {
      drawText(1, y, line);
    }
    y += 11;
    p += n;
    while (*p == ' ') ++p;
  }
}

void drawNotify() {
  oled.setDrawColor(1);
  oled.drawBox(0, 0, 128, 13);
  oled.setDrawColor(0);
  drawText(3, 1, notifyTitle);
  oled.setDrawColor(1);
  drawWrapped(notifyBody, 16, 4, false);
}

void renderFrame(uint32_t now) {
  const bool showNotify = notifyTitle[0] && (int32_t)(now - notifyUntil) < 0;
  const bool showCaption = caption[0] != '\0';
  compact += ((showCaption ? 1.0f : 0.0f) - compact) * 0.25f;
  const gmini::FaceLayout full = gmini::FaceLayout::fit(128, 64);
  const gmini::FaceLayout small = gmini::FaceLayout::fit(128, 40, 0.95f);
  gmini::FaceLayout layout;
  layout.scale = full.scale + (small.scale - full.scale) * compact;
  layout.originX = full.originX + (small.originX - full.originX) * compact;
  layout.originY = full.originY + (small.originY - full.originY) * compact;

  oled.firstPage();
  do {
    // Solo se rasterizan las filas de la pagina actual.
    const int16_t top = oled.getBufferCurrTileRow() * 8;
    canvas.setClipRows(top, top + oled.getBufferTileHeight() * 8 - 1);
    if (showNotify) {
      drawNotify();
    } else {
      gmini::drawFace(eyes.frame(), canvas, layout);
      if (showCaption && compact > 0.6f) {
        oled.setDrawColor(1);
        drawWrapped(caption, 42, 2, true);
      }
    }
  } while (oled.nextPage());
}

void setup() {
  Serial.begin(115200);
  for (uint8_t i = 0; i < kButtonCount; ++i) {
    pinMode(kButtonPins[i], INPUT_PULLUP);
    buttons[i].raw = buttons[i].stable = digitalRead(kButtonPins[i]) == LOW;
    buttons[i].longSent = true;
  }
  oled.setBusClock(400000);
  oled.begin();
  oled.setFont(u8g2_font_6x10_tr);
  oled.setFontPosTop();
  eyes.begin(millis());
  sendHello();
}

void loop() {
  const uint32_t now = millis();
  pollSerial();
  pollButtons(now);
  if (now - lastFrame >= kFrameMs) {
    lastFrame = now;
    eyes.update(now);
    renderFrame(now);
  }
}
