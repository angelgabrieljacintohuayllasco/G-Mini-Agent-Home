#include "GMiniSerialProto.h"

#include <stdlib.h>
#include <string.h>

namespace gmini {

namespace {

char* trim(char* s) {
  while (*s == ' ' || *s == '\t') ++s;
  size_t n = strlen(s);
  while (n > 0 && (s[n - 1] == ' ' || s[n - 1] == '\t')) s[--n] = '\0';
  return s;
}

// Entero con signo en [lo, hi]; false si no es un numero completo.
bool parseInt(const char* s, long lo, long hi, long* out) {
  if (s == nullptr || *s == '\0') return false;
  char* end = nullptr;
  long v = strtol(s, &end, 10);
  if (end == s || *end != '\0' || v < lo || v > hi) return false;
  *out = v;
  return true;
}

size_t appendStr(char* buf, size_t len, size_t pos, const char* s) {
  while (*s && pos + 1 < len) buf[pos++] = *s++;
  if (pos < len) buf[pos] = '\0';
  return pos;
}

size_t appendUint(char* buf, size_t len, size_t pos, unsigned v) {
  char tmp[6];
  int n = 0;
  do {
    tmp[n++] = (char)('0' + v % 10);
    v /= 10;
  } while (v && n < 5);
  while (n > 0 && pos + 1 < len) buf[pos++] = tmp[--n];
  if (pos < len) buf[pos] = '\0';
  return pos;
}

}  // namespace

SerialError parseSerialLine(char* line, SerialCommand* out) {
  out->cmd = SerialCmd::None;
  out->value = 0;
  out->lookX = 0;
  out->lookY = 0;
  out->text = nullptr;
  out->text2 = nullptr;

  char* s = trim(line);
  if (*s == '\0') return SerialError::Empty;

  if (s[1] == '\0') {
    switch (s[0]) {
      case '?': out->cmd = SerialCmd::Ping; return SerialError::None;
      case 'V': out->cmd = SerialCmd::Version; return SerialError::None;
      case 'K': out->cmd = SerialCmd::Blink; return SerialError::None;
      default: return SerialError::Unknown;
    }
  }
  if (s[1] != ':') return SerialError::Unknown;
  const char tag = s[0];
  char* arg = s + 2;

  switch (tag) {
    case 'S': {
      Activity a;
      if (!parseActivity(trim(arg), &a)) return SerialError::Value;
      out->cmd = SerialCmd::Status;
      out->value = (uint8_t)a;
      return SerialError::None;
    }
    case 'E': {
      Emotion e;
      if (!parseEmotion(trim(arg), &e)) return SerialError::Value;
      out->cmd = SerialCmd::Emotion;
      out->value = (uint8_t)e;
      return SerialError::None;
    }
    case 'T':
      out->cmd = SerialCmd::Text;
      out->text = arg;
      return SerialError::None;
    case 'N': {
      char* bar = strchr(arg, '|');
      if (bar != nullptr) {
        *bar = '\0';
        out->text2 = bar + 1;
      } else {
        out->text2 = arg + strlen(arg);
      }
      out->cmd = SerialCmd::Notify;
      out->text = arg;
      return SerialError::None;
    }
    case 'L': {
      long v;
      if (!parseInt(trim(arg), 0, 9, &v)) return SerialError::Value;
      out->cmd = SerialCmd::Level;
      out->value = (uint8_t)v;
      return SerialError::None;
    }
    case 'G': {
      char* a = trim(arg);
      if (*a == '\0') {
        out->cmd = SerialCmd::LookRelease;
        return SerialError::None;
      }
      char* comma = strchr(a, ',');
      if (comma == nullptr) return SerialError::Value;
      *comma = '\0';
      long x, y;
      if (!parseInt(trim(a), -100, 100, &x) || !parseInt(trim(comma + 1), -100, 100, &y)) return SerialError::Value;
      out->cmd = SerialCmd::Look;
      out->lookX = (int8_t)x;
      out->lookY = (int8_t)y;
      return SerialError::None;
    }
    case 'Z': {
      long v;
      if (!parseInt(trim(arg), 0, 1, &v)) return SerialError::Value;
      out->cmd = v ? SerialCmd::Sleep : SerialCmd::Wake;
      return SerialError::None;
    }
    case 'C': {
      long v;
      if (!parseInt(trim(arg), 0, 255, &v)) return SerialError::Value;
      out->cmd = SerialCmd::Contrast;
      out->value = (uint8_t)v;
      return SerialError::None;
    }
    default:
      return SerialError::Unknown;
  }
}

size_t formatButtonEvent(char* buf, size_t len, uint8_t id, const char* action) {
  size_t pos = appendStr(buf, len, 0, "B:");
  pos = appendUint(buf, len, pos, id);
  pos = appendStr(buf, len, pos, ":");
  return appendStr(buf, len, pos, action);
}

size_t formatHello(char* buf, size_t len, const char* firmware, const char* version) {
  size_t pos = appendStr(buf, len, 0, "H:");
  pos = appendStr(buf, len, pos, firmware);
  pos = appendStr(buf, len, pos, ";");
  pos = appendStr(buf, len, pos, version);
  pos = appendStr(buf, len, pos, ";");
  return appendUint(buf, len, pos, kSerialProtocolVersion);
}

const char* serialErrorCode(SerialError error) {
  switch (error) {
    case SerialError::None: return "none";
    case SerialError::Empty: return "empty";
    case SerialError::Unknown: return "unknown";
    case SerialError::Value: return "value";
    case SerialError::Overflow: return "overflow";
  }
  return "unknown";
}

}  // namespace gmini
