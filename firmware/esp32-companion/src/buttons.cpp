#include "buttons.h"

namespace {
const uint32_t kDebounceMs = 25;
}

void Button::begin(int pin, uint32_t longMs, uint32_t veryLongMs) {
  pin_ = pin;
  longMs_ = longMs;
  veryLongMs_ = veryLongMs;
  if (pin_ < 0) return;
  pinMode(pin_, INPUT_PULLUP);
  raw_ = stable_ = digitalRead(pin_) == LOW;
  changedAt_ = pressedAt_ = millis();
  // Si arranca presionado no se emiten eventos hasta soltarlo.
  longSent_ = veryLongSent_ = stable_;
}

Button::Event Button::poll(uint32_t now) {
  if (pin_ < 0) return kNone;
  const bool level = digitalRead(pin_) == LOW;
  if (level != raw_) {
    raw_ = level;
    changedAt_ = now;
  }
  if (raw_ != stable_ && now - changedAt_ >= kDebounceMs) {
    stable_ = raw_;
    if (stable_) {
      pressedAt_ = now;
      longSent_ = veryLongSent_ = false;
      return kPress;
    }
    return kRelease;
  }
  if (stable_ && !longSent_ && now - pressedAt_ >= longMs_) {
    longSent_ = true;
    return kLong;
  }
  if (stable_ && !veryLongSent_ && now - pressedAt_ >= veryLongMs_) {
    veryLongSent_ = true;
    return kVeryLong;
  }
  return kNone;
}
