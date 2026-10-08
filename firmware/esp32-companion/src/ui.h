// Interfaz: cara animada, textos y LEDs en una tarea propia a ~40 cuadros/s.
//
// Las funciones de este modulo se pueden llamar desde cualquier tarea: solo
// encolan una orden; la tarea de interfaz es la unica que toca la pantalla.
#pragma once

#include <GMiniEyes.h>
#include <stdint.h>

#include "leds.h"

namespace ui {

void begin(uint8_t brightness, uint16_t sleepMinutes);

void setEmotion(gmini::Emotion emotion);
void setActivity(gmini::Activity activity);
void setLevel(float level);  // 0..1, sin cola (se lee en el siguiente cuadro)
void blink();
void lookAt(float x, float y);
void releaseLook();
void wake();

// Subtitulo bajo la cara. ms = 0 lo deja hasta clearCaption().
void caption(const char* text, uint32_t ms);
void clearCaption();
// Tarjeta de aviso (titulo + cuerpo).
void notify(const char* title, const char* body, uint32_t ms);
// Pantalla de configuracion (portal WiFi, emparejamiento). Vacio la quita.
void setup(const char* title, const char* body);

void setBrightness(uint8_t brightness);
void setOnline(bool wifi, bool server);

void ledOverride(uint32_t rgb, leds::Effect effect, uint32_t ms);
void ledAuto();

bool hasDisplay();
const char* displayName();

}  // namespace ui
