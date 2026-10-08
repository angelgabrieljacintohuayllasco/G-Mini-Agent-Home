#include "GMiniLink.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

namespace gmini {
namespace link {

namespace {

inline bool isSpace(char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }
inline char lowerAscii(char c) { return (c >= 'A' && c <= 'Z') ? (char)(c - 'A' + 'a') : c; }

bool startsWithNoCase(const char* s, const char* prefix) {
  while (*prefix) {
    if (lowerAscii(*s++) != lowerAscii(*prefix++)) return false;
  }
  return true;
}

bool equalsNoCase(const char* a, const char* b) {
  while (*a && *b) {
    if (lowerAscii(*a++) != lowerAscii(*b++)) return false;
  }
  return *a == *b;
}

void copyBounded(char* dst, size_t cap, const char* src, size_t n) {
  if (cap == 0) return;
  if (n >= cap) n = cap - 1;
  memcpy(dst, src, n);
  dst[n] = '\0';
}

inline uint16_t le16(const uint8_t* p) { return (uint16_t)(p[0] | (p[1] << 8)); }
inline uint32_t le32(const uint8_t* p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
inline void put16(uint8_t* p, uint16_t v) {
  p[0] = (uint8_t)v;
  p[1] = (uint8_t)(v >> 8);
}
inline void put32(uint8_t* p, uint32_t v) {
  p[0] = (uint8_t)v;
  p[1] = (uint8_t)(v >> 8);
  p[2] = (uint8_t)(v >> 16);
  p[3] = (uint8_t)(v >> 24);
}

int8_t base64Value(char c) {
  if (c >= 'A' && c <= 'Z') return (int8_t)(c - 'A');
  if (c >= 'a' && c <= 'z') return (int8_t)(c - 'a' + 26);
  if (c >= '0' && c <= '9') return (int8_t)(c - '0' + 52);
  if (c == '+' || c == '-') return 62;  // tambien base64url
  if (c == '/' || c == '_') return 63;
  return -1;
}

int hexValue(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  c = lowerAscii(c);
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

}  // namespace

// ------------------------------------------------------------------ base64

void Base64Decoder::reset() {
  quad_ = 0;
  have_ = 0;
  pad_ = 0;
  error_ = false;
  total_ = 0;
  outLen_ = 0;
}

void Base64Decoder::emit(uint8_t b) {
  out_[outLen_++] = b;
  ++total_;
  if (outLen_ == sizeof(out_)) flush();
}

void Base64Decoder::flush() {
  if (outLen_ && sink_) sink_(out_, outLen_, ctx_);
  outLen_ = 0;
}

void Base64Decoder::feed(const char* data, size_t len) {
  for (size_t i = 0; i < len; ++i) {
    const char c = data[i];
    if (c == '=') {
      ++pad_;
      continue;
    }
    if (isSpace(c)) continue;
    const int8_t v = base64Value(c);
    if (v < 0 || pad_) {
      error_ = true;
      continue;
    }
    quad_ = (quad_ << 6) | (uint32_t)v;
    if (++have_ == 4) {
      emit((uint8_t)(quad_ >> 16));
      emit((uint8_t)(quad_ >> 8));
      emit((uint8_t)quad_);
      have_ = 0;
      quad_ = 0;
    }
  }
}

bool Base64Decoder::finish() {
  if (have_ == 2) {
    emit((uint8_t)(quad_ >> 4));
  } else if (have_ == 3) {
    emit((uint8_t)(quad_ >> 10));
    emit((uint8_t)(quad_ >> 2));
  } else if (have_ == 1) {
    error_ = true;
  }
  have_ = 0;
  quad_ = 0;
  flush();
  return !error_;
}

// ------------------------------------------------------------------ WAV

void WavDecoder::reset() {
  state_ = kRiff;
  hdrLen_ = 0;
  chunkLeft_ = 0;
  padByte_ = false;
  haveFmt_ = false;
  dataStarted_ = false;
  memset(&fmt_, 0, sizeof(fmt_));
  pcm_ = 0;
}

void WavDecoder::setRaw(uint32_t sampleRate, uint16_t channels) {
  reset();
  fmt_.audioFormat = 1;
  fmt_.channels = channels;
  fmt_.sampleRate = sampleRate;
  fmt_.bitsPerSample = 16;
  fmt_.dataBytes = 0xFFFFFFFFu;
  haveFmt_ = true;
  dataStarted_ = true;
  chunkLeft_ = 0xFFFFFFFFu;
  state_ = kData;
  if (onFormat_) onFormat_(fmt_, ctx_);
}

void WavDecoder::feed(const uint8_t* data, size_t len) {
  size_t i = 0;
  while (i < len && state_ != kError) {
    switch (state_) {
      case kRiff: {
        size_t take = 12 - hdrLen_;
        if (take > len - i) take = len - i;
        memcpy(hdr_ + hdrLen_, data + i, take);
        hdrLen_ += take;
        i += take;
        if (hdrLen_ == 12) {
          if (memcmp(hdr_, "RIFF", 4) != 0 || memcmp(hdr_ + 8, "WAVE", 4) != 0) {
            fail();
            break;
          }
          hdrLen_ = 0;
          state_ = kChunkHeader;
        }
        break;
      }
      case kChunkHeader: {
        if (padByte_) {
          padByte_ = false;
          ++i;
          break;
        }
        size_t take = 8 - hdrLen_;
        if (take > len - i) take = len - i;
        memcpy(hdr_ + hdrLen_, data + i, take);
        hdrLen_ += take;
        i += take;
        if (hdrLen_ < 8) break;
        hdrLen_ = 0;
        const uint32_t size = le32(hdr_ + 4);
        if (memcmp(hdr_, "fmt ", 4) == 0) {
          if (size < 16) {
            fail();
            break;
          }
          chunkLeft_ = size;
          padByte_ = (size & 1) != 0;
          state_ = kFmt;
        } else if (memcmp(hdr_, "data", 4) == 0) {
          if (!haveFmt_) {
            fail();
            break;
          }
          fmt_.dataBytes = size;
          // Algunos codificadores en flujo escriben 0 o 0xFFFFFFFF: se lee hasta el final.
          chunkLeft_ = (size == 0) ? 0xFFFFFFFFu : size;
          padByte_ = (size & 1) != 0;
          dataStarted_ = true;
          state_ = kData;
          if (onFormat_) onFormat_(fmt_, ctx_);
        } else {
          chunkLeft_ = size;
          padByte_ = (size & 1) != 0;
          state_ = chunkLeft_ ? kSkip : kChunkHeader;
        }
        break;
      }
      case kFmt: {
        size_t take = len - i;
        if (take > chunkLeft_) take = chunkLeft_;
        for (size_t k = 0; k < take && hdrLen_ < 16; ++k) hdr_[hdrLen_++] = data[i + k];
        i += take;
        chunkLeft_ -= (uint32_t)take;
        if (chunkLeft_ == 0) {
          fmt_.audioFormat = le16(hdr_);
          fmt_.channels = le16(hdr_ + 2);
          fmt_.sampleRate = le32(hdr_ + 4);
          fmt_.bitsPerSample = le16(hdr_ + 14);
          hdrLen_ = 0;
          const bool pcm = fmt_.audioFormat == 1 || fmt_.audioFormat == 0xFFFE;
          if (!pcm || fmt_.channels == 0 || fmt_.channels > 2 || fmt_.sampleRate < 4000 ||
              fmt_.sampleRate > 96000 || (fmt_.bitsPerSample != 16 && fmt_.bitsPerSample != 8)) {
            fail();
            break;
          }
          fmt_.audioFormat = 1;
          haveFmt_ = true;
          state_ = kChunkHeader;
        }
        break;
      }
      case kSkip: {
        size_t take = len - i;
        if (take > chunkLeft_) take = chunkLeft_;
        i += take;
        chunkLeft_ -= (uint32_t)take;
        if (chunkLeft_ == 0) state_ = kChunkHeader;
        break;
      }
      case kData: {
        size_t take = len - i;
        if (chunkLeft_ != 0xFFFFFFFFu && take > chunkLeft_) take = chunkLeft_;
        if (take && onPcm_) onPcm_(data + i, take, ctx_);
        pcm_ += (uint32_t)take;
        i += take;
        if (chunkLeft_ != 0xFFFFFFFFu) {
          chunkLeft_ -= (uint32_t)take;
          if (chunkLeft_ == 0) state_ = kChunkHeader;  // puede haber chunks LIST al final
        }
        break;
      }
      case kError:
        return;
    }
  }
}

size_t buildWavHeader(uint8_t out[44], uint32_t sampleRate, uint16_t channels, uint16_t bitsPerSample,
                      uint32_t dataBytes) {
  const uint16_t blockAlign = (uint16_t)(channels * bitsPerSample / 8);
  memcpy(out, "RIFF", 4);
  put32(out + 4, 36 + dataBytes);
  memcpy(out + 8, "WAVE", 4);
  memcpy(out + 12, "fmt ", 4);
  put32(out + 16, 16);
  put16(out + 20, 1);
  put16(out + 22, channels);
  put32(out + 24, sampleRate);
  put32(out + 28, sampleRate * blockAlign);
  put16(out + 32, blockAlign);
  put16(out + 34, bitsPerSample);
  memcpy(out + 36, "data", 4);
  put32(out + 40, dataBytes);
  return 44;
}

// ------------------------------------------------------------------ JSON en flujo

JsonScanner::JsonScanner() : fieldCount_(0), streamKey_(nullptr), streamSink_(nullptr), streamCtx_(nullptr) {
  reset();
}

void JsonScanner::clearFields() {
  fieldCount_ = 0;
  streamKey_ = nullptr;
  streamSink_ = nullptr;
  streamCtx_ = nullptr;
}

void JsonScanner::reset() {
  mode_ = kValue;
  depth_ = 0;
  keyLen_ = 0;
  keyOverflow_ = false;
  readingKey_ = false;
  escape_ = false;
  hexLeft_ = 0;
  hexVal_ = 0;
  highSurrogate_ = 0;
  target_ = kNone;
  fieldIdx_ = -1;
  streamLen_ = 0;
  error_ = false;
  complete_ = false;
  started_ = false;
  memset(inArray_, 0, sizeof(inArray_));
  memset(keys_, 0, sizeof(keys_));
  for (uint8_t i = 0; i < fieldCount_; ++i) {
    fields_[i].used = 0;
    fields_[i].found = false;
    fields_[i].truncated = false;
    if (fields_[i].len) fields_[i].buf[0] = '\0';
  }
}

bool JsonScanner::addField(const char* key, char* buf, size_t len, const char* parent) {
  if (fieldCount_ >= kMaxFields || buf == nullptr || len == 0) return false;
  Field& f = fields_[fieldCount_++];
  f.key = key;
  f.parent = parent;
  f.buf = buf;
  f.len = len;
  f.used = 0;
  f.found = false;
  f.truncated = false;
  buf[0] = '\0';
  return true;
}

bool JsonScanner::setStreamField(const char* key, CharSink sink, void* ctx) {
  streamKey_ = key;
  streamSink_ = sink;
  streamCtx_ = ctx;
  return true;
}

bool JsonScanner::found(const char* key) const {
  for (uint8_t i = 0; i < fieldCount_; ++i) {
    if (strcmp(fields_[i].key, key) == 0 && fields_[i].found) return true;
  }
  return false;
}

bool JsonScanner::truncated(const char* key) const {
  for (uint8_t i = 0; i < fieldCount_; ++i) {
    if (strcmp(fields_[i].key, key) == 0) return fields_[i].truncated;
  }
  return false;
}

int16_t JsonScanner::matchField() const {
  if (depth_ < 1 || depth_ > 2 || inArray_[depth_]) return -1;
  const char* key = keys_[depth_];
  if (depth_ == 1 && streamKey_ && strcmp(key, streamKey_) == 0) return -2;
  for (uint8_t i = 0; i < fieldCount_; ++i) {
    const Field& f = fields_[i];
    if (strcmp(f.key, key) != 0) continue;
    if (f.parent == nullptr && depth_ == 1) return (int16_t)i;
    if (f.parent != nullptr && depth_ == 2 && !inArray_[1] && strcmp(keys_[1], f.parent) == 0) return (int16_t)i;
  }
  return -1;
}

void JsonScanner::flushStream() {
  if (streamLen_ && streamSink_) streamSink_(streamBuf_, streamLen_, streamCtx_);
  streamLen_ = 0;
}

void JsonScanner::putChar(char c) {
  if (readingKey_) {
    if (keyLen_ + 1 < kKeyLen) {
      keyBuf_[keyLen_++] = c;
    } else {
      keyOverflow_ = true;
    }
    return;
  }
  if (target_ == kCapture) {
    Field& f = fields_[fieldIdx_];
    if (f.used + 1 < f.len) {
      f.buf[f.used++] = c;
    } else {
      f.truncated = true;
    }
  } else if (target_ == kStream) {
    streamBuf_[streamLen_++] = c;
    if (streamLen_ == sizeof(streamBuf_)) flushStream();
  }
}

void JsonScanner::putCodepoint(uint32_t cp) {
  if (cp < 0x80) {
    putChar((char)cp);
  } else if (cp < 0x800) {
    putChar((char)(0xC0 | (cp >> 6)));
    putChar((char)(0x80 | (cp & 0x3F)));
  } else if (cp < 0x10000) {
    putChar((char)(0xE0 | (cp >> 12)));
    putChar((char)(0x80 | ((cp >> 6) & 0x3F)));
    putChar((char)(0x80 | (cp & 0x3F)));
  } else {
    putChar((char)(0xF0 | (cp >> 18)));
    putChar((char)(0x80 | ((cp >> 12) & 0x3F)));
    putChar((char)(0x80 | ((cp >> 6) & 0x3F)));
    putChar((char)(0x80 | (cp & 0x3F)));
  }
}

void JsonScanner::beginValue(char c) {
  const int16_t idx = matchField();
  if (idx >= 0) {
    target_ = kCapture;
    fieldIdx_ = idx;
    fields_[idx].used = 0;
    fields_[idx].truncated = false;
    fields_[idx].found = false;
  } else if (idx == -2) {
    target_ = kStream;
    streamLen_ = 0;
  } else {
    target_ = kNone;
  }
  if (c == '"') {
    readingKey_ = false;
    mode_ = kString;
  } else {
    mode_ = kLiteral;
    putChar(c);
  }
}

void JsonScanner::endValue() {
  if (target_ == kCapture) {
    Field& f = fields_[fieldIdx_];
    f.buf[f.used] = '\0';
    f.found = true;
  } else if (target_ == kStream) {
    flushStream();
  }
  target_ = kNone;
  fieldIdx_ = -1;
  mode_ = kAfterValue;
}

void JsonScanner::feed(const char* data, size_t len) {
  for (size_t i = 0; i < len && !error_; ++i) step(data[i]);
}

void JsonScanner::step(char c) {
  switch (mode_) {
    case kValue:
      if (isSpace(c)) return;
      if (c == '{' || c == '[') {
        if (depth_ >= kMaxDepth) {
          error_ = true;
          return;
        }
        started_ = true;
        ++depth_;
        inArray_[depth_] = (c == '[');
        keys_[depth_][0] = '\0';
        mode_ = (c == '{') ? kKey : kValue;
        return;
      }
      if (c == ']' && depth_ > 0 && inArray_[depth_]) {
        --depth_;
        mode_ = kAfterValue;
        if (depth_ == 0) complete_ = true;
        return;
      }
      if (c == '}' || c == ']' || c == ',' || c == ':') {
        error_ = true;
        return;
      }
      beginValue(c);
      return;

    case kKey:
      if (isSpace(c)) return;
      if (c == '"') {
        readingKey_ = true;
        keyLen_ = 0;
        keyOverflow_ = false;
        mode_ = kString;
        return;
      }
      if (c == '}') {
        --depth_;
        mode_ = kAfterValue;
        if (depth_ == 0) complete_ = true;
        return;
      }
      error_ = true;
      return;

    case kAfterKey:
      if (isSpace(c)) return;
      if (c == ':') {
        mode_ = kValue;
        return;
      }
      error_ = true;
      return;

    case kString:
      if (hexLeft_ > 0) {
        const int h = hexValue(c);
        if (h < 0) {
          error_ = true;
          return;
        }
        hexVal_ = (hexVal_ << 4) | (uint32_t)h;
        if (--hexLeft_ == 0) {
          const uint32_t v = hexVal_;
          if (v >= 0xD800 && v <= 0xDBFF) {
            if (highSurrogate_) putCodepoint(0xFFFD);
            highSurrogate_ = v;
          } else if (v >= 0xDC00 && v <= 0xDFFF) {
            if (highSurrogate_) {
              putCodepoint(0x10000 + ((highSurrogate_ - 0xD800) << 10) + (v - 0xDC00));
            } else {
              putCodepoint(0xFFFD);
            }
            highSurrogate_ = 0;
          } else {
            if (highSurrogate_) putCodepoint(0xFFFD);
            highSurrogate_ = 0;
            putCodepoint(v);
          }
        }
        return;
      }
      if (escape_) {
        escape_ = false;
        switch (c) {
          case 'u':
            hexLeft_ = 4;
            hexVal_ = 0;
            return;
          case 'b': c = '\b'; break;
          case 'f': c = '\f'; break;
          case 'n': c = '\n'; break;
          case 'r': c = '\r'; break;
          case 't': c = '\t'; break;
          case '"':
          case '\\':
          case '/':
            break;
          default:
            error_ = true;
            return;
        }
        if (highSurrogate_) {
          putCodepoint(0xFFFD);
          highSurrogate_ = 0;
        }
        putChar(c);
        return;
      }
      if (c == '\\') {
        escape_ = true;
        return;
      }
      if (highSurrogate_) {
        putCodepoint(0xFFFD);
        highSurrogate_ = 0;
      }
      if (c == '"') {
        if (readingKey_) {
          readingKey_ = false;
          keyBuf_[keyLen_] = '\0';
          // Una clave demasiado larga no coincide con ningun campo.
          copyBounded(keys_[depth_], kKeyLen, keyOverflow_ ? "" : keyBuf_, keyOverflow_ ? 0 : keyLen_);
          mode_ = kAfterKey;
        } else {
          endValue();
        }
        return;
      }
      putChar(c);
      return;

    case kLiteral:
      if (c == ',' || c == '}' || c == ']' || isSpace(c)) {
        endValue();
        step(c);
        return;
      }
      putChar(c);
      return;

    case kAfterValue:
      if (isSpace(c)) return;
      if (c == ',' && depth_ > 0) {
        mode_ = inArray_[depth_] ? kValue : kKey;
        return;
      }
      if ((c == '}' && depth_ > 0 && !inArray_[depth_]) || (c == ']' && depth_ > 0 && inArray_[depth_])) {
        --depth_;
        if (depth_ == 0) complete_ = true;
        return;
      }
      error_ = true;
      return;
  }
}

// ------------------------------------------------------------------ respuesta HTTP

void HttpResponseParser::reset() {
  state_ = kStatus;
  lineLen_ = 0;
  status_ = 0;
  chunked_ = false;
  contentLength_ = -1;
  chunkLeft_ = 0;
  bodyBytes_ = 0;
  contentType_[0] = '\0';
}

void HttpResponseParser::deliver(const uint8_t* data, size_t len) {
  if (!len) return;
  bodyBytes_ += (uint32_t)len;
  if (body_) body_(data, len, ctx_);
}

void HttpResponseParser::headerLine() {
  char* colon = strchr(line_, ':');
  if (colon == nullptr) return;
  *colon = '\0';
  char* value = colon + 1;
  while (*value == ' ' || *value == '\t') ++value;
  if (equalsNoCase(line_, "content-length")) {
    contentLength_ = (int32_t)strtol(value, nullptr, 10);
  } else if (equalsNoCase(line_, "transfer-encoding")) {
    for (char* p = value; *p; ++p) {
      if (startsWithNoCase(p, "chunked")) chunked_ = true;
    }
  } else if (equalsNoCase(line_, "content-type")) {
    copyBounded(contentType_, sizeof(contentType_), value, strlen(value));
  }
}

size_t HttpResponseParser::feed(const uint8_t* data, size_t len) {
  size_t i = 0;
  while (i < len) {
    switch (state_) {
      case kStatus:
      case kHeader:
      case kChunkSize:
      case kChunkDataEnd:
      case kTrailer: {
        const char c = (char)data[i++];
        if (c != '\n') {
          if (c != '\r' && lineLen_ + 1 < sizeof(line_)) line_[lineLen_++] = c;
          break;
        }
        line_[lineLen_] = '\0';
        lineLen_ = 0;
        if (state_ == kStatus) {
          if (!startsWithNoCase(line_, "HTTP/")) {
            state_ = kError;
            return i;
          }
          const char* sp = strchr(line_, ' ');
          status_ = sp ? (int)strtol(sp + 1, nullptr, 10) : 0;
          state_ = status_ >= 100 ? kHeader : kError;
          if (state_ == kError) return i;
        } else if (state_ == kHeader) {
          if (line_[0] == '\0') {
            if (status_ == 100) {  // 100 Continue: viene otra respuesta detras
              state_ = kStatus;
            } else if (chunked_) {
              state_ = kChunkSize;
            } else if (contentLength_ == 0 || status_ == 204 || status_ == 304) {
              state_ = kDone;
            } else {
              state_ = kBody;
            }
          } else {
            headerLine();
          }
        } else if (state_ == kChunkSize) {
          char* end = nullptr;
          const unsigned long size = strtoul(line_, &end, 16);
          if (end == line_) {
            state_ = kError;
            return i;
          }
          chunkLeft_ = (uint32_t)size;
          state_ = size == 0 ? kTrailer : kChunkData;
        } else if (state_ == kChunkDataEnd) {
          state_ = kChunkSize;
        } else if (state_ == kTrailer) {
          if (line_[0] == '\0') state_ = kDone;
        }
        break;
      }
      case kBody: {
        size_t take = len - i;
        if (contentLength_ >= 0) {
          const uint32_t left = (uint32_t)contentLength_ - bodyBytes_;
          if (take > left) take = left;
        }
        deliver(data + i, take);
        i += take;
        if (contentLength_ >= 0 && bodyBytes_ >= (uint32_t)contentLength_) state_ = kDone;
        break;
      }
      case kChunkData: {
        size_t take = len - i;
        if (take > chunkLeft_) take = chunkLeft_;
        deliver(data + i, take);
        i += take;
        chunkLeft_ -= (uint32_t)take;
        if (chunkLeft_ == 0) state_ = kChunkDataEnd;
        break;
      }
      case kDone:
        return len;
      case kError:
        return i;
    }
  }
  return i;
}

void HttpResponseParser::connectionClosed() {
  if (state_ == kBody && contentLength_ < 0) {
    state_ = kDone;
  } else if (state_ != kDone) {
    state_ = kError;
  }
}

// ------------------------------------------------------------------ emparejamiento y URL

namespace {

// Decodifica %XX y '+' en un valor de consulta.
void urlDecode(const char* src, size_t n, char* dst, size_t cap) {
  size_t o = 0;
  for (size_t i = 0; i < n && o + 1 < cap; ++i) {
    char c = src[i];
    if (c == '+') {
      c = ' ';
    } else if (c == '%' && i + 2 < n + 0 && hexValue(src[i + 1]) >= 0 && hexValue(src[i + 2]) >= 0) {
      c = (char)(hexValue(src[i + 1]) * 16 + hexValue(src[i + 2]));
      i += 2;
    }
    dst[o++] = c;
  }
  dst[o] = '\0';
}

bool normalizeCode(const char* s, char out[8]) {
  size_t n = 0;
  for (; *s; ++s) {
    if (*s >= '0' && *s <= '9') {
      if (n >= 6) return false;
      out[n++] = *s;
    } else if (*s != ' ' && *s != '-' && *s != '\t') {
      return false;
    }
  }
  out[n] = '\0';
  return n == 6;
}

}  // namespace

bool parsePairInput(const char* input, PairInfo* out) {
  if (input == nullptr || out == nullptr) return false;
  memset(out, 0, sizeof(*out));
  while (isSpace(*input)) ++input;
  size_t len = strlen(input);
  while (len > 0 && isSpace(input[len - 1])) --len;

  const char* prefix = "gmini://pair";
  if (len >= strlen(prefix) && startsWithNoCase(input, prefix)) {
    const char* q = strchr(input, '?');
    if (q == nullptr || (size_t)(q - input) >= len) return false;
    const char* p = q + 1;
    const char* end = input + len;
    char code[16] = {0};
    while (p < end) {
      const char* amp = p;
      while (amp < end && *amp != '&') ++amp;
      const char* eq = p;
      while (eq < amp && *eq != '=') ++eq;
      if (eq < amp) {
        const size_t klen = (size_t)(eq - p);
        char value[72];
        urlDecode(eq + 1, (size_t)(amp - eq - 1), value, sizeof(value));
        if (klen == 4 && startsWithNoCase(p, "host")) {
          copyBounded(out->host, sizeof(out->host), value, strlen(value));
        } else if (klen == 4 && startsWithNoCase(p, "port")) {
          char* e = nullptr;
          const long port = strtol(value, &e, 10);
          if (e == value || *e != '\0' || port < 1 || port > 65535) return false;
          out->port = (uint16_t)port;
        } else if (klen == 4 && startsWithNoCase(p, "code")) {
          copyBounded(code, sizeof(code), value, strlen(value));
        }
      }
      p = amp < end ? amp + 1 : end;
    }
    return normalizeCode(code, out->code);
  }
  char buf[24];
  if (len >= sizeof(buf)) return false;
  memcpy(buf, input, len);
  buf[len] = '\0';
  return normalizeCode(buf, out->code);
}

bool parseServerUrl(const char* input, ServerAddr* out, uint16_t defaultPort) {
  if (input == nullptr || out == nullptr) return false;
  memset(out, 0, sizeof(*out));
  while (isSpace(*input)) ++input;
  const char* p = input;
  bool explicitScheme = false;
  if (startsWithNoCase(p, "https://")) {
    out->tls = true;
    p += 8;
    explicitScheme = true;
  } else if (startsWithNoCase(p, "http://")) {
    p += 7;
    explicitScheme = true;
  }
  (void)explicitScheme;
  const char* hostEnd = p;
  while (*hostEnd && *hostEnd != ':' && *hostEnd != '/' && !isSpace(*hostEnd)) ++hostEnd;
  const size_t hostLen = (size_t)(hostEnd - p);
  if (hostLen == 0 || hostLen >= sizeof(out->host)) return false;
  for (const char* c = p; c < hostEnd; ++c) {
    const bool ok = (*c >= 'a' && *c <= 'z') || (*c >= 'A' && *c <= 'Z') || (*c >= '0' && *c <= '9') ||
                    *c == '.' || *c == '-' || *c == '_';
    if (!ok) return false;
  }
  copyBounded(out->host, sizeof(out->host), p, hostLen);
  out->port = out->tls ? 443 : defaultPort;
  const char* rest = hostEnd;
  if (*rest == ':') {
    char* e = nullptr;
    const long port = strtol(rest + 1, &e, 10);
    if (e == rest + 1 || port < 1 || port > 65535) return false;
    out->port = (uint16_t)port;
    rest = e;
  }
  // Solo se admite una ruta ("/...") o espacios finales despues del puerto.
  if (*rest == '/') return true;
  while (isSpace(*rest)) ++rest;
  return *rest == '\0';
}

// ------------------------------------------------------------------ detector de voz

EnergyVad::EnergyVad(uint32_t sampleRate)
    : startRatio(3.0f),
      stopRatio(1.8f),
      minSpeechMs(160),
      hangoverMs(650),
      maxSpeechMs(3800),
      minRms(150.0f),
      rate_(sampleRate ? sampleRate : 16000) {
  reset();
}

void EnergyVad::reset() {
  floor_ = 0.0f;
  rms_ = 0.0f;
  speech_ = false;
  aboveMs_ = 0;
  silenceMs_ = 0;
  speechMs_ = 0;
  primed_ = false;
}

EnergyVad::Event EnergyVad::feed(const int16_t* samples, size_t count) {
  if (count == 0) return kNone;
  double acc = 0.0;
  for (size_t i = 0; i < count; ++i) acc += (double)samples[i] * (double)samples[i];
  rms_ = (float)sqrt(acc / (double)count);
  const uint32_t blockMs = (uint32_t)((count * 1000u) / rate_);
  if (!primed_) {
    floor_ = rms_ > minRms * 0.5f ? rms_ : minRms * 0.5f;
    primed_ = true;
  }
  if (!speech_) {
    const float threshold = floor_ * startRatio > minRms ? floor_ * startRatio : minRms;
    if (rms_ > threshold) {
      aboveMs_ += blockMs;
      if (aboveMs_ >= minSpeechMs) {
        speech_ = true;
        speechMs_ = aboveMs_;
        silenceMs_ = 0;
        return kSpeechStart;
      }
    } else {
      aboveMs_ = 0;
      // El piso baja rapido y sube despacio: un portazo no lo dispara.
      const float k = rms_ < floor_ ? 0.2f : 0.03f;
      floor_ += (rms_ - floor_) * k;
      if (floor_ < 1.0f) floor_ = 1.0f;
    }
    return kNone;
  }
  speechMs_ += blockMs;
  const float keep = floor_ * stopRatio > minRms * 0.8f ? floor_ * stopRatio : minRms * 0.8f;
  if (rms_ > keep) {
    silenceMs_ = 0;
  } else {
    silenceMs_ += blockMs;
  }
  if (silenceMs_ >= hangoverMs || speechMs_ >= maxSpeechMs) {
    speech_ = false;
    aboveMs_ = 0;
    return kSpeechEnd;
  }
  return kNone;
}

}  // namespace link
}  // namespace gmini
