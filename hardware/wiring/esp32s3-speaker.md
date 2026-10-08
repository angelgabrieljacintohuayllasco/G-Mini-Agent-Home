# Cableado: ESP32-S3 parlante (sin pantalla)

La cara es el anillo de LEDs: respira en reposo, gira al pensar y late al hablar.

![ESP32-S3 parlante (sin pantalla)](esp32s3-speaker.svg)

| Módulo | Pin del módulo | Pin de la placa | Función |
|---|---|---|---|
| INMP441 | `VDD` | `3V3` | 3,3 V |
| INMP441 | `GND` | `GND` | GND |
| INMP441 | `L/R` | `GND` | GND |
| INMP441 | `SCK` | `GPIO4` | I2S BCLK / SCK |
| INMP441 | `WS` | `GPIO5` | I2S WS / LRC |
| INMP441 | `SD` | `GPIO6` | I2S datos |
| MAX98357A | `VIN` | `5V` | 5 V |
| MAX98357A | `GND` | `GND` | GND |
| MAX98357A | `DIN` | `GPIO7` | I2S datos |
| MAX98357A | `BCLK` | `GPIO15` | I2S BCLK / SCK |
| MAX98357A | `LRC` | `GPIO16` | I2S WS / LRC |
| Botones | `Botón HABLAR` | `GPIO17` | Botones |
| Botones | `Botón MODO` | `GPIO18` | Botones |
| Botones | `Común` | `GND` | GND |
| Anillo WS2812 | `5V` | `5V` | 5 V |
| Anillo WS2812 | `GND` | `GND` | GND |
| Anillo WS2812 | `DIN LED` | `GPIO47` | Datos LED |

Notas:

- Alimenta con una fuente USB de 5 V / 2 A: anillo y amplificador suman picos de 1 A.
- Entorno PlatformIO: esp32s3-speaker.
- MAX98357A: Parlante a los bornes + y - del módulo.
- Anillo WS2812: Resistencia de 330 ohm en serie con DIN LED.

Guía paso a paso: [docs/guides/speaker.md](../../docs/guides/speaker.md). Seguridad: [docs/safety.md](../../docs/safety.md).

<!-- Generado por tools/diagrams/wiring.py: no editar a mano. -->
