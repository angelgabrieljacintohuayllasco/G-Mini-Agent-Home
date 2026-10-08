// Ajustes persistentes en NVS (Preferences, espacio "gmini").
#pragma once

#include <stddef.h>
#include <stdint.h>

struct Settings {
  char host[64];
  uint16_t port;
  bool tls;
  char token[128];
  char deviceId[48];
  char deviceName[40];
  char agentName[32];
  uint8_t volume;  // 0..100
  uint8_t brightness;  // 0..255 (pantalla y LEDs)
  bool wakeWord;  // "Oye G-Mini" detectado por el servidor
  bool speakNotifications;
  uint16_t sleepMinutes;  // 0 = nunca

  bool paired() const { return token[0] != '\0' && host[0] != '\0'; }
};

void settingsDefaults(Settings& s);
void settingsLoad(Settings& s);
void settingsSave(const Settings& s);
// Borra token e id de dispositivo (mantiene WiFi y servidor).
void settingsForgetPairing(Settings& s);
// Borra todo el espacio "gmini" de NVS.
void settingsErase();
