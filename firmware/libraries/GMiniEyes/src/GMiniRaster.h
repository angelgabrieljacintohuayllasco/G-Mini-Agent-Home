// Rasterizado por tramos horizontales para pantallas sin primitivas propias
// (o con primitivas que no recortan bien coordenadas negativas, como U8g2 en
// AVR). Una subclase solo implementa span(): pintar una fila ya recortada.
#pragma once

#include <stdint.h>

#include "GMiniEyes.h"

namespace gmini {

class SpanCanvas : public FaceCanvas {
 public:
  SpanCanvas(int16_t width, int16_t height)
      : width_(width), height_(height), clipTop_(0), clipBottom_((int16_t)(height - 1)) {}

  int16_t width() const { return width_; }
  int16_t height() const { return height_; }

  // Limita el dibujo a las filas [top, bottom]. Con pantallas por paginas
  // (U8g2 en AVR) cada pasada solo rasteriza sus filas.
  void setClipRows(int16_t top, int16_t bottom);
  void clearClip() { setClipRows(0, (int16_t)(height_ - 1)); }

  void fillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint8_t color) override;
  void fillRoundRect(int16_t x, int16_t y, int16_t w, int16_t h, int16_t r, uint8_t color) override;
  void fillCircle(int16_t cx, int16_t cy, int16_t r, uint8_t color) override;
  void fillTriangle(int16_t x0, int16_t y0, int16_t x1, int16_t y1, int16_t x2, int16_t y2,
                    uint8_t color) override;

 protected:
  ~SpanCanvas() {}
  // Pinta [x0, x1] (inclusive) en la fila y. Los valores ya estan dentro de la pantalla.
  virtual void span(int16_t x0, int16_t x1, int16_t y, uint8_t color) = 0;

 private:
  void clippedSpan(int16_t x0, int16_t x1, int16_t y, uint8_t color);

  int16_t width_;
  int16_t height_;
  int16_t clipTop_;
  int16_t clipBottom_;
};

// Lienzo en memoria (1 byte por pixel con el indice de color). Pensado para
// pruebas en el host y para generar vistas previas.
class RasterCanvas : public SpanCanvas {
 public:
  RasterCanvas(uint8_t* buffer, int16_t width, int16_t height)
      : SpanCanvas(width, height), buffer_(buffer) {}

  void clear(uint8_t color = kColorBackground);
  uint8_t at(int16_t x, int16_t y) const;
  uint32_t count(uint8_t color) const;
  uint32_t countLit() const;  // pixeles que no son fondo

 protected:
  void span(int16_t x0, int16_t x1, int16_t y, uint8_t color) override;

 private:
  uint8_t* buffer_;
};

}  // namespace gmini
