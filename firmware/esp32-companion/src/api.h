// Cliente HTTP de la G-Mini Remote API v1.
//
// Las respuestas se procesan en flujo: el audio de /voice/turn (base64 dentro
// del JSON) y de /voice/tts se decodifica y se reproduce mientras llega.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "settings.h"

namespace api {

struct Error {
  int status;  // HTTP; 0 si no hubo respuesta
  char code[32];
  char message[120];
};

struct ClaimResult {
  char token[128];
  char deviceId[48];
  char agentName[32];
  char serverName[48];
};

struct TurnResult {
  char transcript[160];
  char reply[240];
  char emotion[16];
  char sessionId[64];
  uint32_t audioBytes;
};

struct WakeResult {
  bool wake;
  char phrase[32];
  char command[160];
  char transcript[160];
};

struct ChatResult {
  char reply[240];
  char sessionId[64];
};

void configure(const Settings& s);

bool claim(const char* host, uint16_t port, bool tls, const char* code, const char* deviceName, ClaimResult* out,
           Error* err);
// true si el token sigue valido. Con 401 el dispositivo debe volver a emparejarse.
bool me(Error* err);
// Sube la grabacion (PCM16 mono 16 kHz) y reproduce la respuesta mientras llega.
bool voiceTurn(const int16_t* pcm, size_t samples, const char* sessionId, TurnResult* out, Error* err);
bool voiceWake(const int16_t* pcm, size_t samples, WakeResult* out, Error* err);
bool chat(const char* text, const char* sessionId, ChatResult* out, Error* err);
// Sintetiza y reproduce texto.
bool speak(const char* text, Error* err);

// Funcion que se llama cuando empieza a sonar la respuesta (la emocion y el
// texto ya llegaron en el JSON, antes que el audio).
void setAudioStartHook(void (*hook)(void* ctx), void* ctx);

// Mensaje corto en espanol para mostrar en pantalla.
const char* describe(const Error& err);

}  // namespace api
