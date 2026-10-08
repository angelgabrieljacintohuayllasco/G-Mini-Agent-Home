// Botones con antirrebote y pulsacion larga (activos en bajo, con pull-up interno).
#pragma once

#include <Arduino.h>

class Button {
 public:
  enum Event : uint8_t { kNone, kPress, kRelease, kLong, kVeryLong };

  void begin(int pin, uint32_t longMs, uint32_t veryLongMs);
  Event poll(uint32_t now);
  bool held() const { return stable_; }
  uint32_t heldMs(uint32_t now) const { return stable_ ? now - pressedAt_ : 0; }
  bool enabled() const { return pin_ >= 0; }

 private:
  int pin_ = -1;
  bool raw_ = false;
  bool stable_ = false;
  bool longSent_ = false;
  bool veryLongSent_ = false;
  uint32_t changedAt_ = 0;
  uint32_t pressedAt_ = 0;
  uint32_t longMs_ = 3000;
  uint32_t veryLongMs_ = 10000;
};
