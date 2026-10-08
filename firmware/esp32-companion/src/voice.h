// Flujos de voz: pulsar para hablar y palabra de activacion ("Oye G-Mini")
// detectada por el servidor con /api/v1/voice/wake.
#pragma once

#include <stdint.h>

#include "settings.h"

namespace voice {

void begin(Settings* settings);
void loop();

void talkPressed();
void talkReleased();
bool busy();

// Sintetiza y reproduce un texto (tts.speak, avisos hablados, consola).
void say(const char* text);

}  // namespace voice
