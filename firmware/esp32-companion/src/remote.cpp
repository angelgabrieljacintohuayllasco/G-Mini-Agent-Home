#include "remote.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WebSocketsClient.h>
#include <WiFi.h>
#include <string.h>

#include "config.h"
#include "leds.h"
#include "ui.h"

namespace remote {

namespace {

WebSocketsClient gWs;
Callbacks gCb = {};
bool gActive = false;
bool gOpen = false;
bool gReady = false;
uint32_t gReadySince = 0;
uint32_t gLastPing = 0;
uint8_t gFailed = 0;
char gDeviceName[40] = "";
char gPendingSpeech[200] = "";
bool gHasPendingSpeech = false;

#if GMINI_RELAY_COUNT > 0
const int kRelayPins[] = {PIN_RELAY_1, PIN_RELAY_2};
bool gRelayState[2] = {false, false};

void relayWrite(uint8_t index, bool on) {
  gRelayState[index] = on;
  digitalWrite(kRelayPins[index], (on ^ (GMINI_RELAY_ACTIVE_LOW != 0)) ? HIGH : LOW);
}
#endif

void sendJson(JsonDocument& doc) {
  char buf[768];
  const size_t n = serializeJson(doc, buf, sizeof(buf));
  if (n > 0 && n < sizeof(buf)) gWs.sendTXT((uint8_t*)buf, n);
}

const char* platformName() {
#if defined(GMINI_BOARD_S3)
  return "esp32-s3";
#else
  return "esp32";
#endif
}

void sendHello() {
  JsonDocument doc;
  doc["type"] = "hello";
  doc["client"] = GMINI_FW_NAME;
  doc["version"] = GMINI_FW_VERSION;
  doc["device_name"] = gDeviceName;
  sendJson(doc);
}

void sendRegister() {
  JsonDocument doc;
  doc["type"] = "node.register";
  JsonArray surfaces = doc["surfaces"].to<JsonArray>();
  if (ui::hasDisplay()) {
    surfaces.add("display.face");
    surfaces.add("display.text");
  }
  if (leds::enabled()) surfaces.add("led.set");
#if GMINI_RELAY_COUNT > 0
  surfaces.add("relay.set");
#endif
  surfaces.add("sensor.read");
  surfaces.add("system.info");
  surfaces.add("tts.speak");
  doc["platform"] = platformName();
  JsonObject meta = doc["meta"].to<JsonObject>();
  meta["firmware"] = GMINI_FW_NAME;
  meta["version"] = GMINI_FW_VERSION;
  meta["display"] = ui::displayName();
  meta["led_count"] = leds::enabled() ? GMINI_LED_COUNT : 0;
  meta["relays"] = GMINI_RELAY_COUNT;
  meta["mac"] = WiFi.macAddress();
  JsonArray sensors = meta["sensors"].to<JsonArray>();
  sensors.add("chip_temp");
  sensors.add("wifi_rssi");
  sensors.add("uptime");
  sensors.add("free_heap");
  if (PIN_LIGHT_SENSOR >= 0) sensors.add("light");
  sendJson(doc);
}

void sendResult(const char* requestId, bool ok, JsonDocument& data, const char* errCode, const char* errMessage) {
  JsonDocument doc;
  doc["type"] = "node.result";
  doc["request_id"] = requestId;
  doc["ok"] = ok;
  if (ok) {
    doc["data"] = data;
  } else {
    JsonObject e = doc["error"].to<JsonObject>();
    e["code"] = errCode;
    e["message"] = errMessage;
  }
  sendJson(doc);
}

// Devuelve false y rellena el error si la superficie no aplica.
bool invoke(const char* surface, JsonObjectConst params, JsonDocument& data, const char** errCode,
            const char** errMessage) {
  *errCode = "bad_request";
  if (strcmp(surface, "display.face") == 0 && ui::hasDisplay()) {
    const char* expression = params["expression"] | "";
    gmini::Emotion emotion;
    gmini::Activity activity;
    if (gmini::parseEmotion(expression, &emotion)) {
      ui::setEmotion(emotion);
    } else if (gmini::parseActivity(expression, &activity)) {
      ui::setActivity(activity);
    } else {
      *errMessage = "Expresion desconocida";
      return false;
    }
    const char* text = params["text"] | "";
    if (*text) ui::caption(text, 8000);
    data["ok"] = true;
    return true;
  }
  if (strcmp(surface, "display.text") == 0 && ui::hasDisplay()) {
    const char* text = params["text"] | "";
    uint32_t seconds = params["seconds"] | 8;
    if (seconds == 0 || seconds > 300) seconds = 8;
    ui::caption(text, seconds * 1000UL);
    data["ok"] = true;
    return true;
  }
  if (strcmp(surface, "led.set") == 0 && leds::enabled()) {
    const char* color = params["color"] | "#3fe0ff";
    const char* effectName = params["effect"] | "solid";
    if (strcmp(effectName, "auto") == 0) {
      ui::ledAuto();
      data["ok"] = true;
      return true;
    }
    uint32_t rgb;
    leds::Effect effect;
    if (!leds::parseColor(color, &rgb) || !leds::parseEffect(effectName, &effect)) {
      *errMessage = "Color (#rrggbb) o efecto invalido";
      return false;
    }
    uint32_t seconds = params["seconds"] | 0;
    ui::ledOverride(rgb, effect, seconds * 1000UL);
    data["ok"] = true;
    return true;
  }
#if GMINI_RELAY_COUNT > 0
  if (strcmp(surface, "relay.set") == 0) {
    const int channel = params["channel"] | 0;
    if (channel < 1 || channel > GMINI_RELAY_COUNT || !params["on"].is<bool>()) {
      *errMessage = "Canal o estado invalido";
      return false;
    }
    relayWrite((uint8_t)(channel - 1), params["on"].as<bool>());
    data["ok"] = true;
    data["channel"] = channel;
    data["on"] = gRelayState[channel - 1];
    return true;
  }
#endif
  if (strcmp(surface, "sensor.read") == 0) {
    const char* name = params["name"] | "";
    if (strcmp(name, "chip_temp") == 0) {
      data["value"] = roundf(temperatureRead() * 10.0f) / 10.0f;
      data["unit"] = "C";
    } else if (strcmp(name, "wifi_rssi") == 0) {
      data["value"] = WiFi.RSSI();
      data["unit"] = "dBm";
    } else if (strcmp(name, "uptime") == 0) {
      data["value"] = millis() / 1000UL;
      data["unit"] = "s";
    } else if (strcmp(name, "free_heap") == 0) {
      data["value"] = ESP.getFreeHeap();
      data["unit"] = "bytes";
    } else if (strcmp(name, "light") == 0 && PIN_LIGHT_SENSOR >= 0) {
      data["value"] = roundf(analogRead(PIN_LIGHT_SENSOR) * 1000.0f / 4095.0f) / 10.0f;
      data["unit"] = "%";
    } else {
      *errCode = "not_found";
      *errMessage = "Sensor desconocido";
      return false;
    }
    return true;
  }
  if (strcmp(surface, "system.info") == 0) {
    data["firmware"] = GMINI_FW_NAME " " GMINI_FW_VERSION;
    data["uptime_s"] = millis() / 1000UL;
    data["rssi"] = WiFi.RSSI();
    data["free_heap"] = ESP.getFreeHeap();
    data["psram_free"] = ESP.getFreePsram();
    data["display"] = ui::displayName();
    data["ip"] = WiFi.localIP().toString();
    return true;
  }
  if (strcmp(surface, "tts.speak") == 0) {
    const char* text = params["text"] | "";
    if (!*text) {
      *errMessage = "Falta 'text'";
      return false;
    }
    strlcpy(gPendingSpeech, text, sizeof(gPendingSpeech));
    gHasPendingSpeech = true;
    data["ok"] = true;
    return true;
  }
  *errCode = "not_found";
  *errMessage = "Superficie no disponible en este dispositivo";
  return false;
}

void handleFrame(const uint8_t* payload, size_t length) {
  JsonDocument doc;
  if (deserializeJson(doc, payload, length)) return;
  const char* type = doc["type"] | "";
  if (strcmp(type, "ready") == 0) {
    gReady = true;
    gFailed = 0;
    gReadySince = millis();
    sendRegister();
    if (gCb.onReady) gCb.onReady(doc["agent_name"] | "G-Mini");
  } else if (strcmp(type, "state") == 0) {
    if (gCb.onState) gCb.onState(doc["status"] | "", doc["emotion"] | "");
  } else if (strcmp(type, "notify") == 0) {
    if (gCb.onNotify) gCb.onNotify(doc["title"] | "", doc["body"] | "", doc["priority"] | "normal");
  } else if (strcmp(type, "node.invoke") == 0) {
    const char* requestId = doc["request_id"] | "";
    const char* surface = doc["surface"] | "";
    JsonDocument data;
    const char* errCode = "";
    const char* errMessage = "";
    const bool ok = invoke(surface, doc["params"].as<JsonObjectConst>(), data, &errCode, &errMessage);
    log_i("node.invoke %s -> %s", surface, ok ? "ok" : errCode);
    sendResult(requestId, ok, data, errCode, errMessage);
  } else if (strcmp(type, "node.registered") == 0) {
    log_i("superficies registradas");
  } else if (strcmp(type, "error") == 0) {
    log_w("error del servidor: %s %s", (const char*)(doc["code"] | ""), (const char*)(doc["message"] | ""));
  }
}

void onEvent(WStype_t type, uint8_t* payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      gOpen = true;
      gLastPing = millis();
      sendHello();
      break;
    case WStype_DISCONNECTED:
      if (gOpen && !gReady) ++gFailed;
      if (!gOpen) ++gFailed;
      if (gReady && gCb.onDisconnected) gCb.onDisconnected();
      gOpen = false;
      gReady = false;
      break;
    case WStype_TEXT:
      handleFrame(payload, length);
      break;
    default:
      break;
  }
}

}  // namespace

void begin(const Settings& s, const Callbacks& callbacks) {
  gCb = callbacks;
  strlcpy(gDeviceName, s.deviceName, sizeof(gDeviceName));
#if GMINI_RELAY_COUNT > 0
  for (uint8_t i = 0; i < GMINI_RELAY_COUNT; ++i) {
    pinMode(kRelayPins[i], OUTPUT);
    relayWrite(i, false);
  }
#endif
  char header[160];
  snprintf(header, sizeof(header), "Authorization: Bearer %s", s.token);
  gWs.setExtraHeaders(header);
  // Sin subprotocolo: el servidor no negocia ninguno.
  if (s.tls) {
    gWs.beginSSL(s.host, s.port, "/api/v1/ws", "", "");
  } else {
    gWs.begin(s.host, s.port, "/api/v1/ws", "");
  }
  gWs.onEvent(onEvent);
  gWs.setReconnectInterval(5000);
  gActive = true;
  gFailed = 0;
}

void stop() {
  if (!gActive) return;
  gWs.disconnect();
  gActive = false;
  gOpen = false;
  gReady = false;
}

void loop() {
  if (!gActive) return;
  gWs.loop();
  if (gOpen && millis() - gLastPing >= GMINI_WS_PING_MS) {
    gLastPing = millis();
    gWs.sendTXT("{\"type\":\"ping\"}");
  }
}

bool connected() { return gActive && gReady; }
uint32_t connectedSince() { return gReadySince; }
uint8_t failedAttempts() { return gFailed; }

void sendButton(const char* button, const char* action) {
  if (!connected()) return;
  JsonDocument doc;
  doc["type"] = "node.event";
  doc["event"] = "button";
  JsonObject data = doc["data"].to<JsonObject>();
  data["button"] = button;
  data["action"] = action;
  sendJson(doc);
}

void sendCancel() {
  if (connected()) gWs.sendTXT("{\"type\":\"cancel\"}");
}

bool takePendingSpeech(char* out, size_t len) {
  if (!gHasPendingSpeech) return false;
  strlcpy(out, gPendingSpeech, len);
  gHasPendingSpeech = false;
  return true;
}

}  // namespace remote
