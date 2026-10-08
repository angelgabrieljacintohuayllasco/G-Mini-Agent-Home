// Anillo WS2812: la "cara" de la variante sin pantalla y un apoyo en las demas.
#pragma once

#include <GMiniEyes.h>
#include <stdint.h>

namespace leds {

enum class Effect : uint8_t { Solid, Breathe, Blink, Spin, Rainbow, Off };

bool enabled();
void begin(uint8_t brightness);
void setBrightness(uint8_t brightness);
// Fija color y efecto (superficie led.set). ms = 0 lo mantiene hasta autoMode().
void override(uint32_t rgb, Effect effect, uint32_t ms);
void autoMode();
void notifyPulse();
// Se llama en cada cuadro desde la tarea de interfaz.
void update(uint32_t now, gmini::Activity activity, gmini::Emotion emotion, float level, bool asleep, bool setup,
            bool offline);

bool parseEffect(const char* name, Effect* out);
bool parseColor(const char* text, uint32_t* rgb);

}  // namespace leds
