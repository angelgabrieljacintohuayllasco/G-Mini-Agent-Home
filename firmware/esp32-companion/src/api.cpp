#include "api.h"

#include <Arduino.h>
#include <ArduinoJson.h>
#include <GMiniLink.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <string.h>

#include "audio.h"
#include "config.h"
#include "ui.h"

namespace api {

namespace {

using gmini::link::Base64Decoder;
using gmini::link::HttpResponseParser;
using gmini::link::JsonScanner;
using gmini::link::WavDecoder;
using gmini::link::WavFormat;

char gHost[64] = "";
uint16_t gPort = GMINI_DEFAULT_PORT;
bool gTls = false;
char gToken[128] = "";

WiFiClient gPlain;
WiFiClientSecure gSecure;

void setError(Error* err, int status, const char* code, const char* message) {
  if (!err) return;
  err->status = status;
  strlcpy(err->code, code, sizeof(err->code));
  strlcpy(err->message, message, sizeof(err->message));
}

// ----------------------------------------------------------------- reproduccion

void (*gAudioHook)(void*) = nullptr;
void* gAudioHookCtx = nullptr;

// Convierte bytes PCM (16 o 8 bits) en muestras y las envia al parlante,
// actualizando el nivel para la boca y los LEDs.
struct Player {
  WavFormat fmt;
  bool started;
  bool haveCarry;
  uint8_t carry;
  int16_t block[512];
  size_t used;
  uint32_t bytes;

  void reset() {
    memset(&fmt, 0, sizeof(fmt));
    started = false;
    haveCarry = false;
    used = 0;
    bytes = 0;
  }

  void flush() {
    if (!used) return;
    ui::setLevel(audio::levelOf(block, used, fmt.channels));
    audio::speakerWrite(block, used);
    used = 0;
  }

  void push(int16_t sample) {
    block[used++] = sample;
    // Bloques con un numero entero de cuadros (mono o estereo).
    if (used >= sizeof(block) / sizeof(block[0]) - 1 && used % fmt.channels == 0) flush();
  }

  void onFormat(const WavFormat& f) {
    fmt = f;
    started = audio::speakerBegin(f.sampleRate, f.channels);
    ui::setActivity(gmini::Activity::Speaking);
    if (gAudioHook) gAudioHook(gAudioHookCtx);
  }

  void onPcm(const uint8_t* data, size_t len) {
    if (!started) return;
    bytes += len;
    if (fmt.bitsPerSample == 8) {
      for (size_t i = 0; i < len; ++i) push((int16_t)((data[i] - 128) << 8));
      return;
    }
    size_t i = 0;
    if (haveCarry && len > 0) {
      push((int16_t)(carry | (data[0] << 8)));
      haveCarry = false;
      i = 1;
    }
    for (; i + 1 < len; i += 2) push((int16_t)(data[i] | (data[i + 1] << 8)));
    if (i < len) {
      carry = data[i];
      haveCarry = true;
    }
  }

  void finish() {
    flush();
    if (started) audio::speakerEnd();
    ui::setLevel(0.0f);
    started = false;
  }
};

Player gPlayer;

void onWavFormat(const WavFormat& f, void* ctx) { static_cast<Player*>(ctx)->onFormat(f); }
void onWavPcm(const uint8_t* d, size_t n, void* ctx) { static_cast<Player*>(ctx)->onPcm(d, n); }

// Cadena de decodificacion compartida por todas las peticiones.
WavDecoder gWav(onWavFormat, onWavPcm, &gPlayer);
void onBase64Bytes(const uint8_t* d, size_t n, void* ctx) { static_cast<WavDecoder*>(ctx)->feed(d, n); }
Base64Decoder gB64(onBase64Bytes, &gWav);
void onAudioChars(const char* d, size_t n, void* ctx) { static_cast<Base64Decoder*>(ctx)->feed(d, n); }
JsonScanner gJson;

// ----------------------------------------------------------------- HTTP

enum class BodyMode : uint8_t { Json, Wav };

struct Exchange {
  HttpResponseParser* parser;
  BodyMode mode;
  char errCode[32];
  char errMessage[120];
};

void onBody(const uint8_t* data, size_t len, void* ctx) {
  Exchange* ex = static_cast<Exchange*>(ctx);
  const int status = ex->parser->status();
  if (ex->mode == BodyMode::Wav && status >= 200 && status < 300) {
    gWav.feed(data, len);
  } else {
    gJson.feed((const char*)data, len);
  }
}

typedef bool (*BodyWriter)(Client& client, void* ctx);

struct Request {
  const char* method;
  const char* path;
  const char* host;
  uint16_t port;
  bool tls;
  bool auth;
  const char* contentType;
  size_t contentLength;
  BodyWriter writer;
  void* writerCtx;
  BodyMode mode;
  uint32_t idleMs;
};

// Prepara gJson para leer el error estandar {"error": {"code", "message"}}.
void addErrorFields(Exchange& ex) {
  ex.errCode[0] = ex.errMessage[0] = '\0';
  gJson.addField("code", ex.errCode, sizeof(ex.errCode), "error");
  gJson.addField("message", ex.errMessage, sizeof(ex.errMessage), "error");
}

bool perform(const Request& rq, Exchange& ex, Error* err) {
  if (WiFi.status() != WL_CONNECTED) {
    setError(err, 0, "offline", "Sin WiFi");
    return false;
  }
  Client* client = &gPlain;
  if (rq.tls) {
    // Cifra pero no autentica al servidor: ver docs/safety.md (TLS en el ESP32).
    gSecure.setInsecure();
    client = &gSecure;
  }
  gJson.reset();
  HttpResponseParser parser(onBody, &ex);
  ex.parser = &parser;
  ex.mode = rq.mode;

  if (!client->connect(rq.host, rq.port)) {
    setError(err, 0, "connect_failed", "No se pudo conectar con el servidor");
    return false;
  }
  char head[512];
  int n;
  if ((rq.tls && rq.port == 443) || (!rq.tls && rq.port == 80)) {
    n = snprintf(head, sizeof(head), "%s %s HTTP/1.1\r\nHost: %s\r\n", rq.method, rq.path, rq.host);
  } else {
    n = snprintf(head, sizeof(head), "%s %s HTTP/1.1\r\nHost: %s:%u\r\n", rq.method, rq.path, rq.host, rq.port);
  }
  n += snprintf(head + n, sizeof(head) - n, "User-Agent: %s/%s\r\nConnection: close\r\n", GMINI_FW_NAME,
                GMINI_FW_VERSION);
  if (rq.auth && gToken[0]) n += snprintf(head + n, sizeof(head) - n, "Authorization: Bearer %s\r\n", gToken);
  if (rq.contentType) {
    n += snprintf(head + n, sizeof(head) - n, "Content-Type: %s\r\nContent-Length: %u\r\n", rq.contentType,
                  (unsigned)rq.contentLength);
  }
  n += snprintf(head + n, sizeof(head) - n, "\r\n");
  if (n >= (int)sizeof(head) || client->write((const uint8_t*)head, n) != (size_t)n) {
    client->stop();
    setError(err, 0, "send_failed", "No se pudo enviar la peticion");
    return false;
  }
  if (rq.writer && !rq.writer(*client, rq.writerCtx)) {
    client->stop();
    setError(err, 0, "send_failed", "Se corto el envio del audio");
    return false;
  }

  uint8_t buf[1024];
  uint32_t last = millis();
  while (!parser.done() && !parser.error()) {
    int avail = client->available();
    if (avail > 0) {
      int r = client->read(buf, avail < (int)sizeof(buf) ? avail : (int)sizeof(buf));
      if (r > 0) {
        parser.feed(buf, (size_t)r);
        last = millis();
        continue;
      }
    }
    if (!client->connected() && client->available() <= 0) {
      parser.connectionClosed();
      break;
    }
    if (millis() - last > rq.idleMs) {
      client->stop();
      setError(err, 0, "timeout", "El servidor tardo demasiado");
      return false;
    }
    delay(2);
  }
  client->stop();
  if (parser.error() || !parser.done()) {
    setError(err, parser.status(), "bad_response", "Respuesta invalida del servidor");
    return false;
  }
  if (parser.status() < 200 || parser.status() >= 300) {
    setError(err, parser.status(), ex.errCode[0] ? ex.errCode : "http_error",
             ex.errMessage[0] ? ex.errMessage : "El servidor rechazo la peticion");
    return false;
  }
  if (err) err->status = parser.status();
  return true;
}

Request baseRequest(const char* method, const char* path) {
  Request rq;
  memset(&rq, 0, sizeof(rq));
  rq.method = method;
  rq.path = path;
  rq.host = gHost;
  rq.port = gPort;
  rq.tls = gTls;
  rq.auth = true;
  rq.mode = BodyMode::Json;
  rq.idleMs = GMINI_HTTP_IDLE_MS;
  return rq;
}

// ----------------------------------------------------------------- cuerpos

struct WavBody {
  const int16_t* pcm;
  size_t samples;
};

bool writeWav(Client& client, void* ctx) {
  const WavBody* body = static_cast<const WavBody*>(ctx);
  uint8_t header[44];
  const uint32_t bytes = (uint32_t)(body->samples * sizeof(int16_t));
  gmini::link::buildWavHeader(header, GMINI_SAMPLE_RATE, 1, 16, bytes);
  if (client.write(header, sizeof(header)) != sizeof(header)) return false;
  const uint8_t* data = (const uint8_t*)body->pcm;
  for (uint32_t off = 0; off < bytes;) {
    const size_t chunk = bytes - off > 4096 ? 4096 : bytes - off;
    const size_t sent = client.write(data + off, chunk);
    if (sent == 0) return false;
    off += (uint32_t)sent;
  }
  return true;
}

struct TextBody {
  const char* text;
  size_t len;
};

bool writeText(Client& client, void* ctx) {
  const TextBody* body = static_cast<const TextBody*>(ctx);
  return client.write((const uint8_t*)body->text, body->len) == body->len;
}

}  // namespace

// ----------------------------------------------------------------- API publica

void setAudioStartHook(void (*hook)(void* ctx), void* ctx) {
  gAudioHook = hook;
  gAudioHookCtx = ctx;
}

void configure(const Settings& s) {
  strlcpy(gHost, s.host, sizeof(gHost));
  gPort = s.port;
  gTls = s.tls;
  strlcpy(gToken, s.token, sizeof(gToken));
}

bool claim(const char* host, uint16_t port, bool tls, const char* code, const char* deviceName, ClaimResult* out,
           Error* err) {
  JsonDocument doc;
  doc["code"] = code;
  doc["device_name"] = deviceName;
  doc["device_type"] = "esp32";
#if defined(GMINI_BOARD_S3)
  doc["platform"] = "esp32-s3";
#else
  doc["platform"] = "esp32";
#endif
  char body[256];
  const size_t len = serializeJson(doc, body, sizeof(body));

  memset(out, 0, sizeof(*out));
  gJson.clearFields();
  Exchange ex = {};
  addErrorFields(ex);
  gJson.addField("token", out->token, sizeof(out->token));
  gJson.addField("device_id", out->deviceId, sizeof(out->deviceId));
  gJson.addField("agent_name", out->agentName, sizeof(out->agentName));
  gJson.addField("server_name", out->serverName, sizeof(out->serverName));

  TextBody tb = {body, len};
  Request rq = baseRequest("POST", "/api/v1/pairing/claim");
  rq.host = host;
  rq.port = port;
  rq.tls = tls;
  rq.auth = false;
  rq.contentType = "application/json";
  rq.contentLength = len;
  rq.writer = writeText;
  rq.writerCtx = &tb;
  if (!perform(rq, ex, err)) return false;
  if (!out->token[0] || gJson.truncated("token")) {
    setError(err, 200, "bad_response", "El servidor no devolvio un token valido");
    return false;
  }
  return true;
}

bool me(Error* err) {
  gJson.clearFields();
  Exchange ex = {};
  addErrorFields(ex);
  Request rq = baseRequest("GET", "/api/v1/me");
  rq.idleMs = 10000;
  return perform(rq, ex, err);
}

bool voiceTurn(const int16_t* pcm, size_t samples, const char* sessionId, TurnResult* out, Error* err) {
  memset(out, 0, sizeof(*out));
  gJson.clearFields();
  Exchange ex = {};
  addErrorFields(ex);
  gJson.addField("transcript", out->transcript, sizeof(out->transcript));
  gJson.addField("reply", out->reply, sizeof(out->reply));
  gJson.addField("emotion", out->emotion, sizeof(out->emotion));
  gJson.addField("session_id", out->sessionId, sizeof(out->sessionId));
  gJson.setStreamField("audio_base64", onAudioChars, &gB64);
  gPlayer.reset();
  gWav.reset();
  gB64.reset();

  char path[160];
  snprintf(path, sizeof(path), "/api/v1/voice/turn?reply_format=wav&session_id=%s", sessionId ? sessionId : "");
  WavBody body = {pcm, samples};
  Request rq = baseRequest("POST", path);
  rq.contentType = "audio/wav";
  rq.contentLength = 44 + samples * sizeof(int16_t);
  rq.writer = writeWav;
  rq.writerCtx = &body;
  rq.idleMs = 90000;  // STT + agente + TTS en un servidor modesto
  const bool ok = perform(rq, ex, err);
  gB64.finish();
  gPlayer.finish();
  out->audioBytes = gPlayer.bytes;
  return ok;
}

bool voiceWake(const int16_t* pcm, size_t samples, WakeResult* out, Error* err) {
  memset(out, 0, sizeof(*out));
  char wake[8] = "";
  gJson.clearFields();
  Exchange ex = {};
  addErrorFields(ex);
  gJson.addField("wake", wake, sizeof(wake));
  gJson.addField("phrase", out->phrase, sizeof(out->phrase));
  gJson.addField("command", out->command, sizeof(out->command));
  gJson.addField("transcript", out->transcript, sizeof(out->transcript));
  WavBody body = {pcm, samples};
  Request rq = baseRequest("POST", "/api/v1/voice/wake");
  rq.contentType = "audio/wav";
  rq.contentLength = 44 + samples * sizeof(int16_t);
  rq.writer = writeWav;
  rq.writerCtx = &body;
  rq.idleMs = 30000;
  if (!perform(rq, ex, err)) return false;
  out->wake = strcmp(wake, "true") == 0;
  return true;
}

bool chat(const char* text, const char* sessionId, ChatResult* out, Error* err) {
  JsonDocument doc;
  doc["message"] = text;
  doc["stream"] = false;
  if (sessionId && *sessionId) doc["session_id"] = sessionId;
  char body[512];
  const size_t len = serializeJson(doc, body, sizeof(body));
  memset(out, 0, sizeof(*out));
  gJson.clearFields();
  Exchange ex = {};
  addErrorFields(ex);
  gJson.addField("reply", out->reply, sizeof(out->reply));
  gJson.addField("session_id", out->sessionId, sizeof(out->sessionId));
  TextBody tb = {body, len};
  Request rq = baseRequest("POST", "/api/v1/chat");
  rq.contentType = "application/json";
  rq.contentLength = len;
  rq.writer = writeText;
  rq.writerCtx = &tb;
  rq.idleMs = 90000;
  return perform(rq, ex, err);
}

bool speak(const char* text, Error* err) {
  JsonDocument doc;
  doc["text"] = text;
  doc["format"] = "wav";
  char body[640];
  const size_t len = serializeJson(doc, body, sizeof(body));
  gJson.clearFields();
  Exchange ex = {};
  addErrorFields(ex);
  ex.mode = BodyMode::Wav;
  gPlayer.reset();
  gWav.reset();
  TextBody tb = {body, len};
  Request rq = baseRequest("POST", "/api/v1/voice/tts");
  rq.contentType = "application/json";
  rq.contentLength = len;
  rq.writer = writeText;
  rq.writerCtx = &tb;
  rq.mode = BodyMode::Wav;
  rq.idleMs = 30000;
  const bool ok = perform(rq, ex, err);
  gPlayer.finish();
  return ok;
}

const char* describe(const Error& err) {
  if (strcmp(err.code, "offline") == 0) return "Sin WiFi";
  if (strcmp(err.code, "connect_failed") == 0) return "No encuentro a G-Mini";
  if (strcmp(err.code, "timeout") == 0) return "G-Mini tardó demasiado";
  if (strcmp(err.code, "invalid_code") == 0) return "Código inválido o vencido";
  if (strcmp(err.code, "invalid_token") == 0 || err.status == 401) return "Hay que emparejar de nuevo";
  if (strcmp(err.code, "busy") == 0 || err.status == 409) return "Estoy ocupada, prueba en un momento";
  if (strcmp(err.code, "rate_limited") == 0 || err.status == 429) return "Demasiados intentos, espera un minuto";
  if (strcmp(err.code, "missing_scope") == 0 || err.status == 403) return "Me falta un permiso en G-Mini";
  if (strcmp(err.code, "provider_unavailable") == 0 || err.status == 503) return "La voz del servidor no está lista";
  return err.message[0] ? err.message : "Algo salió mal";
}

}  // namespace api
