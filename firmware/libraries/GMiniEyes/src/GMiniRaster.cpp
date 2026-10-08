#include "GMiniRaster.h"

#include <math.h>
#include <string.h>

namespace gmini {

namespace {
inline int16_t min16(int16_t a, int16_t b) { return a < b ? a : b; }
inline int16_t max16(int16_t a, int16_t b) { return a > b ? a : b; }
inline void swap16(int16_t& a, int16_t& b) {
  int16_t t = a;
  a = b;
  b = t;
}
}  // namespace

void SpanCanvas::setClipRows(int16_t top, int16_t bottom) {
  clipTop_ = max16(top, 0);
  clipBottom_ = min16(bottom, (int16_t)(height_ - 1));
}

void SpanCanvas::clippedSpan(int16_t x0, int16_t x1, int16_t y, uint8_t color) {
  if (y < clipTop_ || y > clipBottom_) return;
  if (x0 > x1) swap16(x0, x1);
  x0 = max16(x0, 0);
  x1 = min16(x1, (int16_t)(width_ - 1));
  if (x0 > x1) return;
  span(x0, x1, y, color);
}

void SpanCanvas::fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint8_t color) {
  if (w <= 0 || h <= 0) return;
  int16_t y0 = max16(y, clipTop_);
  int16_t y1 = min16((int16_t)(y + h - 1), clipBottom_);
  for (int16_t row = y0; row <= y1; ++row) clippedSpan(x, (int16_t)(x + w - 1), row, color);
}

void SpanCanvas::fillRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint8_t color) {
  if (w <= 0 || h <= 0) return;
  int16_t maxR = min16(w, h) / 2;
  if (r > maxR) r = maxR;
  if (r <= 0) {
    fillRect(x, y, w, h, color);
    return;
  }
  const float rf = (float)r;
  const int16_t jStart = max16(0, (int16_t)(clipTop_ - y));
  const int16_t jEnd = min16(h, (int16_t)(clipBottom_ - y + 1));
  for (int16_t j = jStart; j < jEnd; ++j) {
    int16_t row = (int16_t)(y + j);
    float dy = -1.0f;
    if (j < r) {
      dy = rf - (float)j - 0.5f;
    } else if (j >= h - r) {
      dy = (float)(j - (h - r)) + 0.5f;
    }
    int16_t inset = 0;
    if (dy >= 0.0f) {
      float inside = rf * rf - dy * dy;
      float dx = inside > 0.0f ? sqrtf(inside) : 0.0f;
      inset = (int16_t)floorf(rf - dx + 0.5f);
    }
    clippedSpan((int16_t)(x + inset), (int16_t)(x + w - 1 - inset), row, color);
  }
}

void SpanCanvas::fillCircle(int16_t cx, int16_t cy, int16_t r, uint8_t color) {
  if (r <= 0) return;
  const float rr = ((float)r + 0.5f) * ((float)r + 0.5f);
  const int16_t dyStart = max16((int16_t)-r, (int16_t)(clipTop_ - cy));
  const int16_t dyEnd = min16(r, (int16_t)(clipBottom_ - cy));
  for (int16_t dy = dyStart; dy <= dyEnd; ++dy) {
    int16_t row = (int16_t)(cy + dy);
    float inside = rr - (float)dy * (float)dy;
    int16_t dx = inside > 0.0f ? (int16_t)sqrtf(inside) : 0;
    clippedSpan((int16_t)(cx - dx), (int16_t)(cx + dx), row, color);
  }
}

void SpanCanvas::fillTriangle(int16_t x0, int16_t y0, int16_t x1, int16_t y1, int16_t x2, int16_t y2,
                              uint8_t color) {
  // Ordena por y (y0 <= y1 <= y2).
  if (y0 > y1) { swap16(y0, y1); swap16(x0, x1); }
  if (y1 > y2) { swap16(y1, y2); swap16(x1, x2); }
  if (y0 > y1) { swap16(y0, y1); swap16(x0, x1); }

  if (y0 == y2) {
    clippedSpan(min16(x0, min16(x1, x2)), max16(x0, max16(x1, x2)), y0, color);
    return;
  }
  const int32_t dx02 = x2 - x0, dy02 = y2 - y0;
  const int32_t dx01 = x1 - x0, dy01 = y1 - y0;
  const int32_t dx12 = x2 - x1, dy12 = y2 - y1;
  int16_t yStart = max16(y0, clipTop_);
  int16_t yEnd = min16(y2, clipBottom_);
  for (int16_t y = yStart; y <= yEnd; ++y) {
    int16_t xa = (int16_t)(x0 + dx02 * (y - y0) / dy02);
    int16_t xb;
    if (y < y1) {
      xb = (int16_t)(x0 + dx01 * (y - y0) / dy01);
    } else if (dy12 != 0) {
      xb = (int16_t)(x1 + dx12 * (y - y1) / dy12);
    } else {
      xb = x1;
    }
    clippedSpan(xa, xb, y, color);
  }
}

void RasterCanvas::clear(uint8_t color) { memset(buffer_, color, (size_t)width() * (size_t)height()); }

uint8_t RasterCanvas::at(int16_t x, int16_t y) const {
  if (x < 0 || y < 0 || x >= width() || y >= height()) return kColorBackground;
  return buffer_[(size_t)y * (size_t)width() + (size_t)x];
}

uint32_t RasterCanvas::count(uint8_t color) const {
  uint32_t n = 0;
  const size_t total = (size_t)width() * (size_t)height();
  for (size_t i = 0; i < total; ++i) n += buffer_[i] == color ? 1u : 0u;
  return n;
}

uint32_t RasterCanvas::countLit() const {
  const size_t total = (size_t)width() * (size_t)height();
  return (uint32_t)(total - count(kColorBackground));
}

void RasterCanvas::span(int16_t x0, int16_t x1, int16_t y, uint8_t color) {
  memset(buffer_ + (size_t)y * (size_t)width() + (size_t)x0, color, (size_t)(x1 - x0 + 1));
}

}  // namespace gmini
