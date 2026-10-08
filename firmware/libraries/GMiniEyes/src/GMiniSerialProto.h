// Protocolo serie por lineas de la cara USB (version 1).
//
// PC -> dispositivo (una orden por linea, terminada en \n):
//   S:<estado>        idle | listening | thinking | acting | speaking
//   E:<emocion>       neutral | happy | sad | surprised | angry | thinking | sleepy | love | error (y alias)
//   T:<texto>         subtitulo; vacio lo borra (ISO-8859-1)
//   N:<titulo>|<cuerpo>  tarjeta de aviso
//   L:<0-9>           nivel de audio para la boca
//   G:<x>,<y>         mirada manual en -100..100; "G:" vuelve a la automatica
//   K                 parpadear
//   Z:<0|1>           1 = dormir, 0 = despertar
//   C:<0-255>         contraste/brillo
//   ?                 ping, responde "OK"
//   V                 version, responde "H:..."
//
// Dispositivo -> PC:
//   H:<firmware>;<version>;<protocolo>
//   OK
//   B:<id>:<down|up|long>
//   ERR:<codigo>
//   # comentario (se ignora)
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "GMiniEyes.h"

namespace gmini {

static const uint8_t kSerialProtocolVersion = 1;

enum class SerialCmd : uint8_t {
  None,
  Status,
  Emotion,
  Text,
  Notify,
  Level,
  Look,
  LookRelease,
  Blink,
  Sleep,
  Wake,
  Contrast,
  Ping,
  Version,
};

enum class SerialError : uint8_t {
  None,
  Empty,
  Unknown,
  Value,
  Overflow,
};

struct SerialCommand {
  SerialCmd cmd;
  uint8_t value;  // indice de estado/emocion, nivel 0..9 o contraste
  int8_t lookX;  // -100..100
  int8_t lookY;
  const char* text;  // apunta dentro de la linea (Text/Notify)
  const char* text2;  // cuerpo de Notify
};

// Acumula bytes hasta un salto de linea. Los bytes >= 0x80 se conservan
// (texto en ISO-8859-1); los de control se descartan.
template <size_t N>
class SerialLineReader {
 public:
  SerialLineReader() : len_(0), overflow_(false), lastOverflow_(false) { buf_[0] = '\0'; }

  // Devuelve true cuando hay una linea completa disponible en line().
  bool feed(char c) {
    if (c == '\r') return false;
    if (c == '\n') {
      buf_[len_] = '\0';
      lastOverflow_ = overflow_;
      len_ = 0;
      overflow_ = false;
      return true;
    }
    if ((uint8_t)c < 0x20 && c != '\t') return false;
    if (len_ + 1 >= N) {
      overflow_ = true;
      return false;
    }
    buf_[len_++] = c;
    return false;
  }

  char* line() { return buf_; }
  // true si la ultima linea entregada se trunco por ser demasiado larga.
  bool overflowed() const { return lastOverflow_; }

 private:
  char buf_[N];
  size_t len_;
  bool overflow_;
  bool lastOverflow_;
};

// Interpreta una linea completa. Modifica la linea (separa titulo y cuerpo).
SerialError parseSerialLine(char* line, SerialCommand* out);

// Formatea un evento de boton en buf: "B:<id>:<accion>".
size_t formatButtonEvent(char* buf, size_t len, uint8_t id, const char* action);

// Formatea el saludo: "H:<firmware>;<version>;<protocolo>".
size_t formatHello(char* buf, size_t len, const char* firmware, const char* version);

const char* serialErrorCode(SerialError error);

}  // namespace gmini
