#include "settings.h"

#include <Arduino.h>
#include <Preferences.h>
#include <WiFi.h>
#include <string.h>

#include "config.h"

namespace {

const char* kNamespace = "gmini";

void readString(Preferences& p, const char* key, char* out, size_t len, const char* fallback) {
  if (p.isKey(key)) {
    size_t n = p.getString(key, out, len);
    if (n > 0) return;
  }
  strlcpy(out, fallback, len);
}

}  // namespace

void settingsDefaults(Settings& s) {
  memset(&s, 0, sizeof(s));
  s.port = GMINI_DEFAULT_PORT;
  s.volume = 60;
  s.brightness = 200;
  s.wakeWord = false;
  s.speakNotifications = false;
  s.sleepMinutes = 10;
  uint8_t mac[6];
  WiFi.macAddress(mac);
  snprintf(s.deviceName, sizeof(s.deviceName), "G-Mini Home %02X%02X", mac[4], mac[5]);
  strlcpy(s.agentName, "G-Mini", sizeof(s.agentName));
}

void settingsLoad(Settings& s) {
  Settings defaults;
  settingsDefaults(defaults);
  Preferences p;
  if (!p.begin(kNamespace, true)) {
    s = defaults;
    return;
  }
  readString(p, "host", s.host, sizeof(s.host), defaults.host);
  s.port = p.getUShort("port", defaults.port);
  s.tls = p.getBool("tls", defaults.tls);
  readString(p, "token", s.token, sizeof(s.token), "");
  readString(p, "dev_id", s.deviceId, sizeof(s.deviceId), "");
  readString(p, "dev_name", s.deviceName, sizeof(s.deviceName), defaults.deviceName);
  readString(p, "agent", s.agentName, sizeof(s.agentName), defaults.agentName);
  s.volume = p.getUChar("volume", defaults.volume);
  s.brightness = p.getUChar("bright", defaults.brightness);
  s.wakeWord = p.getBool("wake", defaults.wakeWord);
  s.speakNotifications = p.getBool("speak_ntf", defaults.speakNotifications);
  s.sleepMinutes = p.getUShort("sleep_min", defaults.sleepMinutes);
  p.end();
  if (s.volume > 100) s.volume = 100;
}

void settingsSave(const Settings& s) {
  Preferences p;
  if (!p.begin(kNamespace, false)) return;
  p.putString("host", s.host);
  p.putUShort("port", s.port);
  p.putBool("tls", s.tls);
  p.putString("token", s.token);
  p.putString("dev_id", s.deviceId);
  p.putString("dev_name", s.deviceName);
  p.putString("agent", s.agentName);
  p.putUChar("volume", s.volume);
  p.putUChar("bright", s.brightness);
  p.putBool("wake", s.wakeWord);
  p.putBool("speak_ntf", s.speakNotifications);
  p.putUShort("sleep_min", s.sleepMinutes);
  p.end();
}

void settingsForgetPairing(Settings& s) {
  s.token[0] = '\0';
  s.deviceId[0] = '\0';
  settingsSave(s);
}

void settingsErase() {
  Preferences p;
  if (p.begin(kNamespace, false)) {
    p.clear();
    p.end();
  }
}
