#include "provision.h"

#include <Arduino.h>
#include <GMiniLink.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <string.h>

#include "api.h"
#include "config.h"
#include "ui.h"

namespace provision {

namespace {

char gApName[32] = "";
bool gSaved = false;

void onSaved() { gSaved = true; }

void buildApName() {
  if (gApName[0]) return;
  uint8_t mac[6];
  WiFi.macAddress(mac);
  snprintf(gApName, sizeof(gApName), GMINI_AP_PREFIX "%02X%02X", mac[4], mac[5]);
}

const char kPortalHead[] PROGMEM =
    "<style>"
    ":root{--primarycolor:#0b7285}"
    "body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif}"
    "h1{letter-spacing:.02em}"
    ".gm{color:#5b6b7b;font-size:.9em;margin:.4em 0 1em}"
    "</style>";

// Aplica lo que el usuario escribio en el portal.
void applyPortal(Settings& s, const char* host, const char* port, const char* name, const char* code) {
  if (host && *host) {
    gmini::link::ServerAddr addr;
    const uint16_t fallbackPort = (port && *port) ? (uint16_t)atoi(port) : GMINI_DEFAULT_PORT;
    if (gmini::link::parseServerUrl(host, &addr, fallbackPort ? fallbackPort : GMINI_DEFAULT_PORT)) {
      strlcpy(s.host, addr.host, sizeof(s.host));
      s.port = addr.port;
      s.tls = addr.tls;
    }
  } else if (port && *port && atoi(port) > 0) {
    s.port = (uint16_t)atoi(port);
  }
  if (name && *name) strlcpy(s.deviceName, name, sizeof(s.deviceName));
  settingsSave(s);
  if (code && *code) {
    char message[96];
    const bool ok = pair(s, code, message, sizeof(message));
    ui::setup("", "");
    ui::caption(message, 6000);
    ui::setEmotion(ok ? gmini::Emotion::Happy : gmini::Emotion::Sad);
  }
}

}  // namespace

const char* apName() {
  buildApName();
  return gApName;
}

bool connect(Settings& s, bool force) {
  buildApName();
  WiFi.mode(WIFI_STA);
  WiFiManager wm;
  char portText[8];
  snprintf(portText, sizeof(portText), "%u", s.port);
  WiFiManagerParameter intro(
      "<p class='gm'>Datos de tu G-Mini: en la app abre Ajustes &gt; Dispositivos &gt; Este equipo "
      "y copia la direcci&oacute;n y el c&oacute;digo de emparejamiento (o el enlace gmini://).</p>");
  WiFiManagerParameter host("gm_host", "Servidor G-Mini (IP, nombre o URL)", s.host, 63);
  WiFiManagerParameter port("gm_port", "Puerto", portText, 6);
  WiFiManagerParameter code("gm_code", "C&oacute;digo de 6 d&iacute;gitos o enlace gmini://", "", 120);
  WiFiManagerParameter name("gm_name", "Nombre de este dispositivo", s.deviceName, 39);
  wm.addParameter(&intro);
  wm.addParameter(&host);
  wm.addParameter(&port);
  wm.addParameter(&code);
  wm.addParameter(&name);
  gSaved = false;
  wm.setSaveConfigCallback(onSaved);
  wm.setSaveParamsCallback(onSaved);
  wm.setTitle("G-Mini Home");
  wm.setCustomHeadElement(kPortalHead);
  wm.setClass("invert");
  wm.setConfigPortalTimeout(GMINI_PORTAL_TIMEOUT_S);
  wm.setConnectTimeout(20);
  wm.setBreakAfterConfig(true);
  wm.setHostname("gmini-home");
  std::vector<const char*> menu = {"wifi", "info", "restart", "exit"};
  wm.setMenu(menu);

  char body[160];
  snprintf(body, sizeof(body), "Red: %s\nClave: %s\nAbre 192.168.4.1", gApName, GMINI_AP_PASSWORD);
  bool connected;
  if (force) {
    ui::setup("Configura tu G-Mini", body);
    connected = wm.startConfigPortal(gApName, GMINI_AP_PASSWORD);
  } else {
    // autoConnect solo abre el portal si no hay WiFi guardado o si falla.
    if (!wm.getWiFiIsSaved()) ui::setup("Configura tu G-Mini", body);
    connected = wm.autoConnect(gApName, GMINI_AP_PASSWORD);
  }
  ui::setup("", "");
  if (gSaved) applyPortal(s, host.getValue(), port.getValue(), name.getValue(), code.getValue());
  if (!connected) connected = WiFi.status() == WL_CONNECTED;
  log_i("wifi: %s (%s)", connected ? "conectado" : "sin conexion", WiFi.localIP().toString().c_str());
  return connected;
}

bool pair(Settings& s, const char* input, char* message, size_t len) {
  gmini::link::PairInfo info;
  if (!gmini::link::parsePairInput(input, &info)) {
    strlcpy(message, "El código debe tener 6 dígitos", len);
    return false;
  }
  if (info.host[0]) {
    strlcpy(s.host, info.host, sizeof(s.host));
    s.port = info.port ? info.port : GMINI_DEFAULT_PORT;
    s.tls = false;
  }
  if (!s.host[0]) {
    strlcpy(message, "Falta la dirección del servidor", len);
    return false;
  }
  ui::setup("Emparejando", s.host);
  api::ClaimResult result;
  api::Error err = {};
  const bool ok = api::claim(s.host, s.port, s.tls, info.code, s.deviceName, &result, &err);
  ui::setup("", "");
  if (!ok) {
    strlcpy(message, api::describe(err), len);
    return false;
  }
  strlcpy(s.token, result.token, sizeof(s.token));
  strlcpy(s.deviceId, result.deviceId, sizeof(s.deviceId));
  if (result.agentName[0]) strlcpy(s.agentName, result.agentName, sizeof(s.agentName));
  settingsSave(s);
  snprintf(message, len, "Emparejado con %s", result.serverName[0] ? result.serverName : s.host);
  return true;
}

void forgetWifi() {
  WiFiManager wm;
  wm.resetSettings();
}

}  // namespace provision
