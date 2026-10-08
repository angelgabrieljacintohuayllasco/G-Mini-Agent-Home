// Sesion WebSocket con G-Mini (/api/v1/ws): estado del agente, avisos y
// superficies de nodo (display.face, display.text, led.set, relay.set,
// sensor.read, system.info, tts.speak).
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "settings.h"

namespace remote {

struct Callbacks {
  void (*onReady)(const char* agentName);
  void (*onState)(const char* status, const char* emotion);
  void (*onNotify)(const char* title, const char* body, const char* priority);
  void (*onDisconnected)();
};

void begin(const Settings& s, const Callbacks& callbacks);
void stop();
void loop();

bool connected();  // socket abierto y "ready" recibido
uint32_t connectedSince();
// Intentos de conexion sin llegar a "ready" (token revocado, servidor ajeno...).
uint8_t failedAttempts();

void sendButton(const char* button, const char* action);
void sendCancel();

// tts.speak llega por el socket pero se ejecuta en el bucle principal.
bool takePendingSpeech(char* out, size_t len);

}  // namespace remote
