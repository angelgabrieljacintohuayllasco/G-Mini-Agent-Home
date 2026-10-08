// G-Mini Home: companero WiFi de G-Mini Agent para ESP32 / ESP32-S3.
//
// Bucle principal (nucleo 1): red, botones, consola y voz.
// Tarea de interfaz (nucleo 1, prioridad mayor): cara y LEDs a ~40 cuadros/s.
#include <Arduino.h>
#include <GMiniEyes.h>
#include <WiFi.h>

#include "api.h"
#include "audio.h"
#include "buttons.h"
#include "config.h"
#include "console.h"
#include "provision.h"
#include "remote.h"
#include "settings.h"
#include "ui.h"
#include "voice.h"

namespace {

Settings gSettings;
Button gTalk;
Button gMode;
uint32_t gLastNetCheck = 0;
uint32_t gLastTokenCheck = 0;
bool gWifiUp = false;
bool gNeedsPairing = false;
char gPendingSpeech[200] = "";

void showPairingHelp() {
  gNeedsPairing = true;
  ui::setEmotion(gmini::Emotion::Thinking);
  if (ui::hasDisplay()) {
    ui::setup("Falta emparejar",
              "Mantén MODO 3 s y escribe el código de G-Mini, o usa la consola: emparejar 123456");
  }
}

void onReady(const char* agentName) {
  if (strcmp(agentName, gSettings.agentName) != 0) {
    strlcpy(gSettings.agentName, agentName, sizeof(gSettings.agentName));
    settingsSave(gSettings);
  }
  ui::setOnline(true, true);
  ui::setEmotion(gmini::Emotion::Happy);
  char text[64];
  snprintf(text, sizeof(text), "Conectada a %s", agentName);
  ui::caption(text, 3000);
  log_i("sesion lista con %s", agentName);
}

void onState(const char* status, const char* emotion) {
  // Durante un turno local la cara la maneja el flujo de voz.
  if (voice::busy()) return;
  gmini::Activity activity;
  gmini::Emotion mood;
  if (gmini::parseActivity(status, &activity)) ui::setActivity(activity);
  if (gmini::parseEmotion(emotion, &mood)) ui::setEmotion(mood);
}

void onNotify(const char* title, const char* body, const char* priority) {
  const bool high = strcmp(priority, "high") == 0 || strcmp(priority, "urgent") == 0;
  const uint32_t ms = high ? 15000 : 8000;
  ui::notify(title, body, ms);
  if (gSettings.speakNotifications && !voice::busy()) {
    snprintf(gPendingSpeech, sizeof(gPendingSpeech), "%s. %s", title, body);
  }
}

void onDisconnected() { ui::setOnline(gWifiUp, false); }

void startSession() {
  remote::stop();
  api::configure(gSettings);
  if (!gSettings.paired()) {
    showPairingHelp();
    return;
  }
  gNeedsPairing = false;
  ui::setup("", "");
  remote::Callbacks cb = {onReady, onState, onNotify, onDisconnected};
  remote::begin(gSettings, cb);
}

void openPortal() {
  remote::stop();
  provision::connect(gSettings, true);
  gWifiUp = WiFi.status() == WL_CONNECTED;
  startSession();
}

void factoryReset() {
  ui::setup("Restableciendo", "Se borran WiFi, servidor y token");
  settingsErase();
  provision::forgetWifi();
  delay(1500);
  ESP.restart();
}

void handleButtons(uint32_t now) {
  switch (gTalk.poll(now)) {
    case Button::kPress:
      remote::sendButton("talk", "down");
      voice::talkPressed();
      break;
    case Button::kRelease:
      remote::sendButton("talk", "up");
      voice::talkReleased();
      break;
    default:
      break;
  }
  static bool longHeld = false;
  switch (gMode.poll(now)) {
    case Button::kRelease:
      if (longHeld) {
        // Soltar despues de 3 s (y antes de 10 s) abre el portal.
        longHeld = false;
        openPortal();
      } else if (!voice::busy()) {
        // Pulsacion corta: corta la respuesta en curso y muestra el estado.
        remote::sendCancel();
        char text[96];
        snprintf(text, sizeof(text), "%s  %s", WiFi.localIP().toString().c_str(),
                 remote::connected() ? gSettings.agentName : "sin servidor");
        ui::caption(text, 4000);
      }
      break;
    case Button::kLong:
      longHeld = true;
      ui::caption("Suelta para abrir el portal; 10 s borra todo", 4000);
      break;
    case Button::kVeryLong:
      factoryReset();
      break;
    default:
      break;
  }
}

void checkNetwork(uint32_t now) {
  if (now - gLastNetCheck < 2000) return;
  gLastNetCheck = now;
  const bool up = WiFi.status() == WL_CONNECTED;
  if (up != gWifiUp) {
    gWifiUp = up;
    log_i("wifi %s", up ? "conectado" : "perdido");
    if (!up) WiFi.reconnect();
  }
  ui::setOnline(gWifiUp, remote::connected());
  // Varias conexiones rechazadas seguidas: se comprueba si el token fue revocado.
  if (gWifiUp && gSettings.paired() && remote::failedAttempts() >= 3 && now - gLastTokenCheck > 60000) {
    gLastTokenCheck = now;
    api::Error err = {};
    if (!api::me(&err) && err.status == 401) {
      log_w("token revocado: hay que emparejar de nuevo");
      settingsForgetPairing(gSettings);
      remote::stop();
      ui::setEmotion(gmini::Emotion::Sad);
      showPairingHelp();
    }
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(50);
  settingsLoad(gSettings);
  ui::begin(gSettings.brightness, gSettings.sleepMinutes);
  if (!audio::begin()) log_w("audio no disponible: revisa el cableado I2S");
  audio::setVolume(gSettings.volume);
  gTalk.begin(PIN_BTN_TALK, GMINI_LONG_PRESS_MS, GMINI_FACTORY_PRESS_MS);
  gMode.begin(PIN_BTN_MODE, GMINI_LONG_PRESS_MS, GMINI_FACTORY_PRESS_MS);
  console::Hooks hooks = {startSession, openPortal, factoryReset};
  console::begin(&gSettings, hooks);
  voice::begin(&gSettings);

  Serial.printf("\n%s %s - escribe 'ayuda' para ver los comandos\n", GMINI_FW_NAME, GMINI_FW_VERSION);
  // MODO presionado al encender: portal de configuracion aunque haya WiFi guardado.
  const bool force = gMode.enabled() && digitalRead(PIN_BTN_MODE) == LOW;
  gWifiUp = provision::connect(gSettings, force);
  if (!gWifiUp) {
    ui::setEmotion(gmini::Emotion::Sad);
    ui::caption("Sin WiFi: mantén MODO 3 s para configurar", 0);
  }
  startSession();
}

void loop() {
  const uint32_t now = millis();
  handleButtons(now);
  console::loop();
  checkNetwork(now);
  remote::loop();
  voice::loop();
  char speech[200];
  if (remote::takePendingSpeech(speech, sizeof(speech))) voice::say(speech);
  if (gPendingSpeech[0] && !voice::busy()) {
    strlcpy(speech, gPendingSpeech, sizeof(speech));
    gPendingSpeech[0] = '\0';
    voice::say(speech);
  }
  delay(1);
}
