// Consola serie (115200 baudios): emparejar, cambiar servidor, probar caras...
#pragma once

#include "settings.h"

namespace console {

struct Hooks {
  void (*restartSession)();
  void (*openPortal)();
  void (*factoryReset)();
};

void begin(Settings* settings, const Hooks& hooks);
void loop();

}  // namespace console
