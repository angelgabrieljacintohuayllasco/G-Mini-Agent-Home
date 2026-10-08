# Cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/);
el proyecto sigue [versionado semántico](https://semver.org/lang/es/).

## [Sin publicar]

## [0.1.1] - 2026-10-08

### Cambiado

- Firmware ESP32 0.1.1: el portal WiFi queda entero en español. Los menús, botones y mensajes
  de WiFiManager usan una traducción propia (`include/gmini_wm_strings_es.h`).

## [0.1.0] - 2026-10-08

Primera versión.

### Agregado

- Motor de ojos compartido (`GMiniEyes`) con nueve emociones y cinco estados,
  parpadeo natural, movimientos de mirada, sueño automático y transiciones
  suaves; presets generados desde `common/expressions.json` para C++, Python y
  JavaScript, con pruebas en el host.
- Firmware WiFi para ESP32-S3 y ESP32 clásico (PlatformIO, 7 entornos): OLED
  SSD1306/SH1106, TFT ST7789 y GC9A01, variante sin pantalla con anillo
  WS2812; portal cautivo, emparejamiento con código o enlace `gmini://`, token
  en NVS, sesión WebSocket con superficies de nodo, pulsar para hablar con
  INMP441 y MAX98357A, reproducción en flujo y palabra de activación por el
  servidor.
- Biblioteca `GMiniLink`: HTTP, JSON, base64 y WAV en flujo, enlaces de
  emparejamiento y detector de voz, con pruebas en el host.
- Sketch para Arduino Uno y Nano con protocolo serie documentado (29 300 bytes
  de flash).
- Biblioteca Python `gmini_link`: cliente de la Remote API v1, sesión
  WebSocket con reconexión, almacén de tokens, WAV, detector de voz y flujos de
  voz compartidos.
- Puente USB (`bridge/`) con detección automática del puerto y voz por la PC.
- Cliente de pantalla (`raspberry-pi/`) con pygame, disposiciones normal,
  espejo y pirámide, colores invertidos para LCD transparente, botones GPIO,
  openWakeWord opcional, instalador y servicio systemd.
- Página de kiosco para tablets con el estado por SSE.
- Hardware: BOM con precios en USD y PEN, diagramas y tablas de cableado
  generados, carcasas OpenSCAD con STL y renders, y plantillas de corte de la
  pirámide de Pepper para nueve pantallas.
- Documentación en español: guías de las cinco variantes, diez técnicas de
  hologramas, seguridad, solución de problemas y preguntas frecuentes.
- CI (firmware, pruebas, archivos generados y OpenSCAD) y release por etiqueta.

[Sin publicar]: https://github.com/angelgabrieljacintohuayllasco/G-Mini-Agent-Home/compare/v0.1.0...HEAD
[0.1.1]: https://github.com/angelgabrieljacintohuayllasco/G-Mini-Agent-Home/releases/tag/v0.1.1
[0.1.0]: https://github.com/angelgabrieljacintohuayllasco/G-Mini-Agent-Home/releases/tag/v0.1.0
