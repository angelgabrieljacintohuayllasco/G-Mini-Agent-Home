// Motor de ojos de G-Mini Home.
//
// Calcula la geometria de dos ojos (y una boca opcional) en un lienzo de
// referencia de 128x64 a partir de una emocion y una actividad. No depende de
// ninguna pantalla: cada driver implementa FaceCanvas y llama a drawFace().
//
// Compila en AVR (Uno/Nano), ESP32 y en el host (pruebas nativas): solo usa
// C++11, <math.h> y <stdint.h>.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "GMiniEyesPresets.h"

namespace gmini {

// Indices de color que recibe FaceCanvas. Las pantallas monocromo tratan todo
// lo que no sea kColorBackground como pixel encendido.
enum FaceColor : uint8_t {
  kColorBackground = 0,
  kColorEye = 1,
  kColorAccent = 2,
  kColorGlow = 3,
  kColorText = 4,
};

struct EyeGeom {
  float cx, cy;  // centro, en pixeles de referencia
  float w, h, r;  // h ya incluye parpadeo y sueno
  float lidTop, slantIn, slantOut, lidBottom;  // fracciones de h
};

struct FaceFrame {
  EyeGeom eye[2];  // [0] = ojo izquierdo, [1] = derecho, vistos de frente
  uint8_t shape;  // EyeShapeKind
  bool accent;
  bool mouth;
  float mouthCx, mouthCy, mouthW, mouthH;
  float closure;  // 0 = abiertos, 1 = cerrados
};

// Superficie de dibujo minima que necesita el motor.
class FaceCanvas {
 public:
  virtual void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint8_t color) = 0;
  virtual void fillRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint8_t color) = 0;
  virtual void fillCircle(int16_t cx, int16_t cy, int16_t r, uint8_t color) = 0;
  virtual void fillTriangle(int16_t x0, int16_t y0, int16_t x1, int16_t y1, int16_t x2, int16_t y2,
                            uint8_t color) = 0;

 protected:
  ~FaceCanvas() {}
};

// Transformacion del lienzo de referencia a pixeles reales.
struct FaceLayout {
  float scale;
  float originX;
  float originY;
  bool mirrorX;  // para reflejos tipo Pepper
  bool glow;  // halo alrededor de los ojos (pantallas a color)

  FaceLayout() : scale(1.0f), originX(0.0f), originY(0.0f), mirrorX(false), glow(false) {}

  // Centra la cara en una pantalla de width x height; fill < 1 deja margen.
  static FaceLayout fit(int16_t width, int16_t height, float fill = 1.0f);
};

void drawFace(const FaceFrame& frame, FaceCanvas& canvas, const FaceLayout& layout);

// Nombres del protocolo (sin distinguir mayusculas). parseEmotion acepta alias.
bool parseEmotion(const char* name, Emotion* out);
bool parseActivity(const char* name, Activity* out);
bool copyEmotionName(Emotion emotion, char* buf, size_t len);
bool copyActivityName(Activity activity, char* buf, size_t len);

class EyesEngine {
 public:
  explicit EyesEngine(uint32_t seed = 0x2545F491u);

  // Opcional: fija el instante inicial y arranca con los ojos cerrados.
  void begin(uint32_t nowMs);

  void setEmotion(Emotion emotion);
  void setActivity(Activity activity);
  // Nivel de audio 0..1 (boca y pulso al hablar, ojos atentos al escuchar).
  void setLevel(float level);
  // Mirada manual en -1..1; desactiva los movimientos automaticos.
  void lookAt(float x, float y);
  void releaseLook();
  void blink();
  // Registra actividad del usuario: despierta y reinicia el temporizador de sueno.
  void wake();
  void sleep();
  void setSleepAfter(uint32_t ms) { sleepAfterMs_ = ms; }
  void setAutoBlink(bool on) { autoBlink_ = on; }
  void setSaccades(bool on) { saccades_ = on; }

  void update(uint32_t nowMs);

  const FaceFrame& frame() const { return frame_; }
  Emotion emotion() const { return emotion_; }
  Activity activity() const { return activity_; }
  bool asleep() const { return asleep_; }
  bool blinking() const { return blinking_; }
  float level() const { return level_; }

 private:
  // Geometria animable. El orden coincide con los primeros 13 campos de
  // EmotionPreset, asi los presets se copian de un bloque (menos flash en AVR).
  enum ShapeField : uint8_t {
    kW, kH, kR, kGap, kDy, kLidTop, kSlantIn, kSlantOut, kLidBottom, kLookX, kLookY, kScaleL, kScaleR, kShapeFields
  };

  void applyPresets(bool immediate);
  void startBlink(uint32_t now);
  void scheduleBlink(uint32_t now);
  float blinkClosure(uint32_t now);
  void updateGaze(uint32_t now, float k);
  void buildFrame(uint32_t now, float blink);
  uint32_t randRange(uint32_t lo, uint32_t hi);
  float randSigned();

  float target_[kShapeFields];
  float cur_[kShapeFields];

  // Comportamiento derivado de los presets activos.
  float bounce_, shake_, pulse_, pulseHz_, levelH_;
  float actLookX_, actLookY_, scanX_, scanY_;
  uint16_t blinkMin_, blinkMax_, sacMin_, sacMax_, scanMin_, scanMax_;
  uint8_t shape_, pendingShape_;
  bool hasLook_, mouth_, accent_, hasPendingShape_;

  // Estado dinamico.
  float gazeX_, gazeY_, sacX_, sacY_, manualX_, manualY_;
  float level_, levelTarget_, sleepClosure_, phase_;
  uint32_t lastMs_, nextBlinkMs_, nextSaccadeMs_, blinkStartMs_, emotionSinceMs_, lastWakeMs_;
  uint32_t sleepAfterMs_;
  uint32_t rng_;
  int8_t scanSign_;
  bool started_, blinking_, forceBlink_, manualLook_, asleep_, autoBlink_, saccades_;

  Emotion emotion_;
  Activity activity_;
  FaceFrame frame_;
};

}  // namespace gmini
