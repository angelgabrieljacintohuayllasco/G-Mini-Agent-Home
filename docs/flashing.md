# Grabar el firmware

## ESP32 / ESP32-S3

### Entornos

| Entorno | Placa | Pantalla | Anillo |
|---|---|---|---|
| `esp32s3-oled` | ESP32-S3-DevKitC-1 N16R8 | SSD1306 128x64 | opcional |
| `esp32s3-sh1106` | ESP32-S3-DevKitC-1 N16R8 | SH1106 128x64 (1,3") | opcional |
| `esp32s3-st7789` | ESP32-S3-DevKitC-1 N16R8 | ST7789 240x280 | opcional |
| `esp32s3-gc9a01` | ESP32-S3-DevKitC-1 N16R8 | GC9A01 240x240 redonda | opcional |
| `esp32s3-speaker` | ESP32-S3-DevKitC-1 N16R8 | sin pantalla | sí |
| `esp32dev-oled` | ESP32 DevKit V1 (WROOM-32) | SSD1306 | opcional |
| `esp32dev-speaker` | ESP32 DevKit V1 (WROOM-32) | sin pantalla | sí |

### Con los binarios de la release

Cada release trae, por entorno:

- `gmini-home-<entorno>-factory.bin`: imagen completa, se graba en `0x0`.
- Las piezas sueltas por si prefieres grabarlas aparte:

| Archivo | ESP32-S3 | ESP32 clásico |
|---|---|---|
| `bootloader.bin` | `0x0` | `0x1000` |
| `partitions.bin` | `0x8000` | `0x8000` |
| `boot_app0.bin` | `0xe000` | `0xe000` |
| `firmware.bin` | `0x10000` | `0x10000` |

```bash
pip install esptool
# Imagen completa
esptool.py --chip esp32s3 --port COM7 --baud 921600 write_flash 0x0 gmini-home-esp32s3-oled-factory.bin
# Piezas sueltas (ESP32-S3)
esptool.py --chip esp32s3 --port COM7 --baud 921600 write_flash \
  0x0 bootloader.bin 0x8000 partitions.bin 0xe000 boot_app0.bin 0x10000 firmware.bin
```

Sin instalar nada: abre [esptool-js](https://espressif.github.io/esptool-js/)
en Chrome o Edge, conecta la placa, agrega el `factory.bin` en `0x0` y graba.

Si la placa no entra en modo de grabación: mantén **BOOT**, toca **RST** y
suelta BOOT. En el DevKitC-1 usa el conector USB marcado **UART** (o el
**USB** nativo; ambos sirven con esptool).

### Compilando con PlatformIO

```bash
pip install platformio
cd firmware/esp32-companion
pio run -e esp32s3-oled                 # compila
pio run -e esp32s3-oled -t upload       # compila y graba
pio device monitor                      # consola serie (115200)
pio test -e native                      # pruebas en la PC (necesita gcc)
```

Tamaños de referencia (PlatformIO, espressif32 7.1.3, Arduino-ESP32 2.0.17):

| Entorno | RAM | Flash |
|---|---|---|
| esp32s3-oled | 66,0 KB (20,1 %) | 1,09 MB de 6,25 MB (16,7 %) |
| esp32s3-st7789 / gc9a01 | 66,8 KB (20,4 %) | 1,17 MB (17,8 %) |
| esp32s3-speaker | 64,4 KB (19,6 %) | 1,06 MB (16,1 %) |
| esp32dev-oled | 66,1 KB (20,2 %) | 1,14 MB de 1,88 MB (58,0 %) |
| esp32dev-speaker | 64,5 KB (19,7 %) | 1,11 MB (56,2 %) |

Cambiar pines u opciones sin tocar el código: agrega `build_flags` al entorno,
por ejemplo `-DPIN_BTN_TALK=41 -DGMINI_RELAY_COUNT=0 -DGMINI_LED_COUNT=16`.
Todas las opciones están en `firmware/esp32-companion/include/config.h`.

## Arduino Uno / Nano

```bash
arduino-cli core install arduino:avr
arduino-cli lib install U8g2
arduino-cli compile --fqbn arduino:avr:uno --library firmware/libraries/GMiniEyes firmware/arduino-usb-face
arduino-cli upload  --fqbn arduino:avr:uno -p COM5 firmware/arduino-usb-face
```

La release incluye los `.hex` para Uno, Nano y Nano con bootloader viejo:

```bash
avrdude -p atmega328p -c arduino -P COM5 -b 115200 -U flash:w:arduino-usb-face-uno.hex:i
avrdude -p atmega328p -c arduino -P COM5 -b 57600  -U flash:w:arduino-usb-face-nano-old.hex:i
```

Tamaño: 29 300 bytes de flash (95 % de un Nano) y 1 644 bytes de RAM.
