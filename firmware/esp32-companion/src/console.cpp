#include "console.h"

#include <Arduino.h>
#include <GMiniEyes.h>
#include <GMiniLink.h>
#include <GMiniSerialProto.h>
#include <WiFi.h>
#include <string.h>

#include "audio.h"
#include "config.h"
#include "provision.h"
#include "remote.h"
#include "ui.h"
#include "voice.h"

namespace console {

namespace {

Settings* gSettings = nullptr;
Hooks gHooks = {};
gmini::SerialLineReader<200> gReader;

void printHelp() {
  Serial.println(F("Comandos de G-Mini Home:"));
  Serial.println(F("  estado                    estado de WiFi, servidor y emparejamiento"));
  Serial.println(F("  emparejar <codigo|enlace> empareja con un codigo de 6 digitos o gmini://pair?..."));
  Serial.println(F("  servidor <host[:puerto]>  cambia el servidor (http://, https:// o IP)"));
  Serial.println(F("  olvidar                   borra el token de este dispositivo"));
  Serial.println(F("  wifi                      abre el portal de configuracion"));
  Serial.println(F("  activacion si|no          palabra de activacion 'Oye G-Mini'"));
  Serial.println(F("  avisos-voz si|no          leer en voz alta los avisos"));
  Serial.println(F("  volumen <0-100>           volumen del parlante"));
  Serial.println(F("  brillo <0-255>            brillo de pantalla y LEDs"));
  Serial.println(F("  cara <emocion>            prueba una expresion (happy, sad, love...)"));
  Serial.println(F("  decir <texto>             lo dice con la voz del servidor"));
  Serial.println(F("  reiniciar                 reinicia la placa"));
  Serial.println(F("  fabrica                   borra WiFi, servidor y token"));
}

void printStatus() {
  Serial.printf("Firmware: %s %s (pantalla %s)\n", GMINI_FW_NAME, GMINI_FW_VERSION, ui::displayName());
  Serial.printf("WiFi: %s  IP %s  RSSI %d dBm\n", WiFi.status() == WL_CONNECTED ? "conectado" : "desconectado",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
  Serial.printf("Servidor: %s://%s:%u\n", gSettings->tls ? "https" : "http",
                gSettings->host[0] ? gSettings->host : "(sin configurar)", gSettings->port);
  Serial.printf("Emparejado: %s  dispositivo %s  agente %s\n", gSettings->paired() ? "si" : "no",
                gSettings->deviceId[0] ? gSettings->deviceId : "-", gSettings->agentName);
  Serial.printf("Sesion WebSocket: %s\n", remote::connected() ? "lista" : "sin conexion");
  Serial.printf("Volumen %u  brillo %u  activacion por voz %s  avisos hablados %s\n", gSettings->volume,
                gSettings->brightness, gSettings->wakeWord ? "si" : "no",
                gSettings->speakNotifications ? "si" : "no");
  Serial.printf("Memoria libre %u B  PSRAM libre %u B\n", (unsigned)ESP.getFreeHeap(),
                (unsigned)ESP.getFreePsram());
}

bool parseYesNo(const char* arg, bool* out) {
  if (strcasecmp(arg, "si") == 0 || strcasecmp(arg, "on") == 0 || strcmp(arg, "1") == 0) {
    *out = true;
    return true;
  }
  if (strcasecmp(arg, "no") == 0 || strcasecmp(arg, "off") == 0 || strcmp(arg, "0") == 0) {
    *out = false;
    return true;
  }
  return false;
}

void run(char* line) {
  while (*line == ' ') ++line;
  if (!*line) return;
  char* arg = strchr(line, ' ');
  if (arg) {
    *arg++ = '\0';
    while (*arg == ' ') ++arg;
  } else {
    arg = line + strlen(line);
  }
  const char* cmd = line;

  if (!strcasecmp(cmd, "ayuda") || !strcasecmp(cmd, "help") || !strcmp(cmd, "?")) {
    printHelp();
  } else if (!strcasecmp(cmd, "estado") || !strcasecmp(cmd, "status")) {
    printStatus();
  } else if (!strcasecmp(cmd, "emparejar") || !strcasecmp(cmd, "pair")) {
    char message[96];
    const bool ok = provision::pair(*gSettings, arg, message, sizeof(message));
    Serial.println(message);
    ui::caption(message, 5000);
    if (ok && gHooks.restartSession) gHooks.restartSession();
  } else if (!strcasecmp(cmd, "servidor") || !strcasecmp(cmd, "server")) {
    gmini::link::ServerAddr addr;
    if (!gmini::link::parseServerUrl(arg, &addr, GMINI_DEFAULT_PORT)) {
      Serial.println(F("Direccion invalida. Ejemplos: 192.168.1.20  tv-server:8765  https://gmini.midominio.com"));
      return;
    }
    strlcpy(gSettings->host, addr.host, sizeof(gSettings->host));
    gSettings->port = addr.port;
    gSettings->tls = addr.tls;
    settingsSave(*gSettings);
    Serial.printf("Servidor: %s://%s:%u\n", addr.tls ? "https" : "http", addr.host, addr.port);
    if (gHooks.restartSession) gHooks.restartSession();
  } else if (!strcasecmp(cmd, "olvidar") || !strcasecmp(cmd, "unpair")) {
    settingsForgetPairing(*gSettings);
    Serial.println(F("Token borrado. Revoca tambien el dispositivo en G-Mini (Ajustes > Dispositivos)."));
    if (gHooks.restartSession) gHooks.restartSession();
  } else if (!strcasecmp(cmd, "wifi")) {
    if (gHooks.openPortal) gHooks.openPortal();
  } else if (!strcasecmp(cmd, "activacion") || !strcasecmp(cmd, "wake")) {
    bool on;
    if (!parseYesNo(arg, &on)) {
      Serial.println(F("Uso: activacion si|no"));
      return;
    }
    gSettings->wakeWord = on;
    settingsSave(*gSettings);
    Serial.println(on ? F("Activacion por voz encendida: se envian frases cortas a tu G-Mini para detectar 'Oye G-Mini'.")
                      : F("Activacion por voz apagada."));
  } else if (!strcasecmp(cmd, "avisos-voz")) {
    bool on;
    if (!parseYesNo(arg, &on)) {
      Serial.println(F("Uso: avisos-voz si|no"));
      return;
    }
    gSettings->speakNotifications = on;
    settingsSave(*gSettings);
  } else if (!strcasecmp(cmd, "volumen") || !strcasecmp(cmd, "volume")) {
    const int v = atoi(arg);
    if (v < 0 || v > 100 || !*arg) {
      Serial.println(F("Uso: volumen 0-100"));
      return;
    }
    gSettings->volume = (uint8_t)v;
    settingsSave(*gSettings);
    audio::setVolume(gSettings->volume);
    audio::chime(true);
  } else if (!strcasecmp(cmd, "brillo")) {
    const int v = atoi(arg);
    if (v < 0 || v > 255 || !*arg) {
      Serial.println(F("Uso: brillo 0-255"));
      return;
    }
    gSettings->brightness = (uint8_t)v;
    settingsSave(*gSettings);
    ui::setBrightness(gSettings->brightness);
  } else if (!strcasecmp(cmd, "cara") || !strcasecmp(cmd, "face")) {
    gmini::Emotion e;
    gmini::Activity a;
    if (gmini::parseEmotion(arg, &e)) {
      ui::setEmotion(e);
    } else if (gmini::parseActivity(arg, &a)) {
      ui::setActivity(a);
    } else {
      Serial.println(F("Emociones: neutral happy sad surprised angry thinking sleepy love error"));
      Serial.println(F("Estados: idle listening thinking acting speaking"));
    }
  } else if (!strcasecmp(cmd, "decir") || !strcasecmp(cmd, "say")) {
    voice::say(arg);
  } else if (!strcasecmp(cmd, "reiniciar") || !strcasecmp(cmd, "reboot")) {
    Serial.println(F("Reiniciando..."));
    delay(200);
    ESP.restart();
  } else if (!strcasecmp(cmd, "fabrica")) {
    if (gHooks.factoryReset) gHooks.factoryReset();
  } else {
    Serial.printf("Comando desconocido: %s (escribe 'ayuda')\n", cmd);
  }
}

}  // namespace

void begin(Settings* settings, const Hooks& hooks) {
  gSettings = settings;
  gHooks = hooks;
}

void loop() {
  while (Serial.available() > 0) {
    if (gReader.feed((char)Serial.read())) {
      if (gReader.overflowed()) {
        Serial.println(F("Linea demasiado larga"));
        continue;
      }
      run(gReader.line());
    }
  }
}

}  // namespace console
