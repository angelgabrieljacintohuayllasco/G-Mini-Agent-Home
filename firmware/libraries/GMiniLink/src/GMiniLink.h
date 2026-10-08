// Utilidades de protocolo de G-Mini Home (sin dependencias de hardware).
//
// Todo trabaja "en flujo": se alimenta con bytes a medida que llegan por la
// red, sin guardar la respuesta completa en RAM. Asi un ESP32 sin PSRAM puede
// recibir varios segundos de audio en base64 dentro de un JSON.
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace gmini {
namespace link {

typedef void (*ByteSink)(const uint8_t* data, size_t len, void* ctx);
typedef void (*CharSink)(const char* data, size_t len, void* ctx);

// ------------------------------------------------------------------ base64

class Base64Decoder {
 public:
  Base64Decoder(ByteSink sink, void* ctx) : sink_(sink), ctx_(ctx) { reset(); }
  void reset();
  void feed(const char* data, size_t len);
  // Emite lo pendiente. Devuelve false si quedo un grupo incompleto invalido.
  bool finish();
  uint32_t decoded() const { return total_; }
  bool error() const { return error_; }

 private:
  void emit(uint8_t b);
  void flush();

  ByteSink sink_;
  void* ctx_;
  uint32_t quad_;
  uint8_t have_;
  uint8_t pad_;
  bool error_;
  uint32_t total_;
  uint8_t out_[192];
  size_t outLen_;
};

// ------------------------------------------------------------------ WAV

struct WavFormat {
  uint16_t audioFormat;  // 1 = PCM
  uint16_t channels;
  uint32_t sampleRate;
  uint16_t bitsPerSample;
  uint32_t dataBytes;  // 0xFFFFFFFF si es desconocido
};

class WavDecoder {
 public:
  typedef void (*FormatSink)(const WavFormat& fmt, void* ctx);

  WavDecoder(FormatSink onFormat, ByteSink onPcm, void* ctx) : onFormat_(onFormat), onPcm_(onPcm), ctx_(ctx) {
    reset();
  }
  void reset();
  // Sin cabecera: trata todo como PCM con este formato (reply_format=pcm16).
  void setRaw(uint32_t sampleRate, uint16_t channels);
  void feed(const uint8_t* data, size_t len);

  // true cuando ya se conoce el formato y empezo el bloque de datos.
  bool ready() const { return dataStarted_; }
  bool error() const { return state_ == kError; }
  const WavFormat& format() const { return fmt_; }
  uint32_t pcmBytes() const { return pcm_; }

 private:
  enum State : uint8_t { kRiff, kChunkHeader, kFmt, kSkip, kData, kError };
  void fail() { state_ = kError; }

  FormatSink onFormat_;
  ByteSink onPcm_;
  void* ctx_;
  State state_;
  uint8_t hdr_[24];
  size_t hdrLen_;
  uint32_t chunkLeft_;
  bool padByte_;
  bool haveFmt_;
  bool dataStarted_;
  WavFormat fmt_;
  uint32_t pcm_;
};

// Cabecera WAV PCM de 44 bytes.
size_t buildWavHeader(uint8_t out[44], uint32_t sampleRate, uint16_t channels, uint16_t bitsPerSample,
                      uint32_t dataBytes);

// ------------------------------------------------------------------ JSON en flujo

// Extrae campos concretos de un JSON sin construir el arbol. Los campos se
// buscan por nombre y, opcionalmente, por el nombre del objeto padre (por
// ejemplo "error" -> "message"). Un campo de flujo envia el contenido de su
// cadena a un CharSink (para audio_base64).
class JsonScanner {
 public:
  static const uint8_t kMaxFields = 10;
  static const uint8_t kMaxDepth = 8;
  static const uint8_t kKeyLen = 24;

  JsonScanner();
  void reset();  // borra el estado del analisis, conserva los campos
  void clearFields();

  // buf recibe la cadena decodificada (UTF-8) o el literal (true, 12.5...).
  bool addField(const char* key, char* buf, size_t len, const char* parent = nullptr);
  bool setStreamField(const char* key, CharSink sink, void* ctx);

  void feed(const char* data, size_t len);

  bool found(const char* key) const;
  bool truncated(const char* key) const;
  bool error() const { return error_; }
  bool complete() const { return complete_; }

 private:
  struct Field {
    const char* key;
    const char* parent;
    char* buf;
    size_t len;
    size_t used;
    bool found;
    bool truncated;
  };
  enum Mode : uint8_t { kValue, kKey, kAfterKey, kString, kLiteral, kAfterValue };
  enum Target : uint8_t { kNone, kCapture, kStream };

  void step(char c);
  void beginValue(char c);
  void endValue();
  void putChar(char c);
  void putCodepoint(uint32_t cp);
  void flushStream();
  int16_t matchField() const;

  Field fields_[kMaxFields];
  uint8_t fieldCount_;
  const char* streamKey_;
  CharSink streamSink_;
  void* streamCtx_;

  Mode mode_;
  bool inArray_[kMaxDepth + 1];
  char keys_[kMaxDepth + 1][kKeyLen];
  uint8_t depth_;
  char keyBuf_[kKeyLen];
  uint8_t keyLen_;
  bool keyOverflow_;
  bool readingKey_;
  bool escape_;
  uint8_t hexLeft_;
  uint32_t hexVal_;
  uint32_t highSurrogate_;
  Target target_;
  int16_t fieldIdx_;
  char streamBuf_[96];
  uint8_t streamLen_;
  bool error_;
  bool complete_;
  bool started_;
};

// ------------------------------------------------------------------ respuesta HTTP

class HttpResponseParser {
 public:
  HttpResponseParser(ByteSink body, void* ctx) : body_(body), ctx_(ctx) { reset(); }
  void reset();
  // Devuelve cuantos bytes consumio (siempre len salvo error).
  size_t feed(const uint8_t* data, size_t len);

  bool headersDone() const { return state_ >= kBody; }
  bool done() const { return state_ == kDone; }
  bool error() const { return state_ == kError; }
  int status() const { return status_; }
  bool chunked() const { return chunked_; }
  int32_t contentLength() const { return contentLength_; }
  const char* contentType() const { return contentType_; }
  uint32_t bodyBytes() const { return bodyBytes_; }
  // Para respuestas sin Content-Length ni chunked: el cierre del socket termina el cuerpo.
  void connectionClosed();

 private:
  enum State : uint8_t { kStatus, kHeader, kBody, kChunkSize, kChunkData, kChunkDataEnd, kTrailer, kDone, kError };
  void headerLine();
  void deliver(const uint8_t* data, size_t len);

  ByteSink body_;
  void* ctx_;
  State state_;
  char line_[160];
  size_t lineLen_;
  int status_;
  bool chunked_;
  int32_t contentLength_;
  uint32_t chunkLeft_;
  uint32_t bodyBytes_;
  char contentType_[40];
};

// ------------------------------------------------------------------ emparejamiento y URL

struct PairInfo {
  char code[8];
  char host[64];
  uint16_t port;  // 0 si el enlace no lo trae
};

// Acepta "482913", "482 913" o "gmini://pair?host=...&port=...&code=...".
bool parsePairInput(const char* input, PairInfo* out);

struct ServerAddr {
  char host[64];
  uint16_t port;
  bool tls;
};

// Acepta "http://host:8765", "https://host", "host:8765" o "host".
bool parseServerUrl(const char* input, ServerAddr* out, uint16_t defaultPort = 8765);

// ------------------------------------------------------------------ detector de voz

// Detector por energia con piso de ruido adaptativo. Pensado para recortar
// frases cortas antes de enviarlas a /api/v1/voice/wake.
class EnergyVad {
 public:
  enum Event : uint8_t { kNone, kSpeechStart, kSpeechEnd };

  explicit EnergyVad(uint32_t sampleRate = 16000);
  void reset();
  // Bloques de ~10-30 ms. Devuelve un evento cuando cambia el estado.
  Event feed(const int16_t* samples, size_t count);

  bool inSpeech() const { return speech_; }
  float noiseFloor() const { return floor_; }
  float lastRms() const { return rms_; }
  uint32_t speechMs() const { return speechMs_; }

  float startRatio;  // energia sobre el piso para empezar
  float stopRatio;  // energia sobre el piso para seguir
  uint16_t minSpeechMs;
  uint16_t hangoverMs;  // silencio necesario para cerrar
  uint16_t maxSpeechMs;
  float minRms;  // por debajo nunca es voz (habitacion silenciosa)

 private:
  uint32_t rate_;
  float floor_;
  float rms_;
  bool speech_;
  uint32_t aboveMs_;
  uint32_t silenceMs_;
  uint32_t speechMs_;
  bool primed_;
};

}  // namespace link
}  // namespace gmini
