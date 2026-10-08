// Conexion WiFi con portal cautivo (WiFiManager) y emparejamiento con G-Mini.
#pragma once

#include <stddef.h>

#include "settings.h"

namespace provision {

// Conecta con el WiFi guardado; si no hay o falla, abre el portal.
// force abre el portal aunque haya WiFi guardado.
bool connect(Settings& s, bool force);
// Empareja con un codigo de 6 digitos o un enlace gmini://pair?...
bool pair(Settings& s, const char* input, char* message, size_t len);
// Olvida la red WiFi guardada.
void forgetWifi();
// Nombre del punto de acceso del portal (G-Mini-Home-XXXX).
const char* apName();

}  // namespace provision
