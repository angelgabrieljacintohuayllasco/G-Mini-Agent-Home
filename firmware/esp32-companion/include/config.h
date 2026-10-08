// Configuracion de pines y valores por defecto de G-Mini Home (ESP32 / ESP32-S3).
//
// Todo se puede sobrescribir con build_flags en platformio.ini, por ejemplo:
//   -DPIN_BTN_TALK=41 -DGMINI_RELAY_COUNT=0 -DGMINI_OLED_SH1106=1
#pragma once

#define GMINI_DISPLAY_NONE 0
#define GMINI_DISPLAY_OLED 1
#define GMINI_DISPLAY_ST7789 2
#define GMINI_DISPLAY_GC9A01 3

#ifndef GMINI_DISPLAY
#define GMINI_DISPLAY GMINI_DISPLAY_OLED
#endif
#define GMINI_HAS_TFT (GMINI_DISPLAY == GMINI_DISPLAY_ST7789 || GMINI_DISPLAY == GMINI_DISPLAY_GC9A01)

#ifndef GMINI_FW_NAME
#define GMINI_FW_NAME "gmini-home-esp32"
#endif
#ifndef GMINI_FW_VERSION
#define GMINI_FW_VERSION "0.0.0-dev"
#endif

// --------------------------------------------------------------- pantalla OLED
#ifndef GMINI_OLED_SH1106
#define GMINI_OLED_SH1106 0  // 1 = controlador SH1106 (modulos de 1,3")
#endif
#ifndef GMINI_OLED_I2C_HZ
#define GMINI_OLED_I2C_HZ 800000  // baja a 400000 si ves rayas o el modulo no responde
#endif

// --------------------------------------------------------------- pantalla TFT
#ifndef GMINI_TFT_WIDTH
#define GMINI_TFT_WIDTH 240
#endif
#ifndef GMINI_TFT_HEIGHT
#define GMINI_TFT_HEIGHT 280
#endif
#ifndef GMINI_TFT_OFFSET_X
#define GMINI_TFT_OFFSET_X 0
#endif
#ifndef GMINI_TFT_OFFSET_Y
#define GMINI_TFT_OFFSET_Y 0
#endif
#ifndef GMINI_TFT_SPI_HZ
#define GMINI_TFT_SPI_HZ 40000000
#endif

// --------------------------------------------------------------- anillo LED
#ifndef GMINI_LED_RING
#define GMINI_LED_RING 0
#endif
#ifndef GMINI_LED_COUNT
#define GMINI_LED_COUNT 12
#endif

// --------------------------------------------------------------- reles
#ifndef GMINI_RELAY_COUNT
#define GMINI_RELAY_COUNT 2
#endif
#ifndef GMINI_RELAY_ACTIVE_LOW
#define GMINI_RELAY_ACTIVE_LOW 1  // la mayoria de modulos de rele se activan con nivel bajo
#endif

// --------------------------------------------------------------- pines
#if defined(GMINI_BOARD_S3)
// ESP32-S3-DevKitC-1 N16R8. Ojo: GPIO 26-37 son de la flash/PSRAM octal y 19/20 del USB nativo.
#ifndef PIN_I2C_SDA
#define PIN_I2C_SDA 8
#endif
#ifndef PIN_I2C_SCL
#define PIN_I2C_SCL 9
#endif
#ifndef PIN_TFT_SCLK
#define PIN_TFT_SCLK 12
#endif
#ifndef PIN_TFT_MOSI
#define PIN_TFT_MOSI 11
#endif
#ifndef PIN_TFT_CS
#define PIN_TFT_CS 10
#endif
#ifndef PIN_TFT_DC
#define PIN_TFT_DC 13
#endif
#ifndef PIN_TFT_RST
#define PIN_TFT_RST 14
#endif
#ifndef PIN_TFT_BL
#define PIN_TFT_BL 21
#endif
#ifndef PIN_MIC_SCK
#define PIN_MIC_SCK 4
#endif
#ifndef PIN_MIC_WS
#define PIN_MIC_WS 5
#endif
#ifndef PIN_MIC_SD
#define PIN_MIC_SD 6
#endif
#ifndef PIN_AMP_BCLK
#define PIN_AMP_BCLK 15
#endif
#ifndef PIN_AMP_LRC
#define PIN_AMP_LRC 16
#endif
#ifndef PIN_AMP_DIN
#define PIN_AMP_DIN 7
#endif
#ifndef PIN_BTN_TALK
#define PIN_BTN_TALK 17
#endif
#ifndef PIN_BTN_MODE
#define PIN_BTN_MODE 18
#endif
#ifndef PIN_LED_RING
#define PIN_LED_RING 47
#endif
#ifndef PIN_RELAY_1
#define PIN_RELAY_1 39
#endif
#ifndef PIN_RELAY_2
#define PIN_RELAY_2 40
#endif
#ifndef PIN_LIGHT_SENSOR
#define PIN_LIGHT_SENSOR -1  // GPIO 2 si conectas una LDR con divisor
#endif

#else
// ESP32 DevKit V1 (WROOM-32). GPIO 34-39 son solo entrada; 6-11 son de la flash; 12 es de arranque.
#if GMINI_HAS_TFT
#error "Las pantallas TFT solo estan configuradas para el ESP32-S3 (usa esp32s3-st7789 o esp32s3-gc9a01)"
#endif
#ifndef PIN_I2C_SDA
#define PIN_I2C_SDA 21
#endif
#ifndef PIN_I2C_SCL
#define PIN_I2C_SCL 22
#endif
#ifndef PIN_MIC_SCK
#define PIN_MIC_SCK 26
#endif
#ifndef PIN_MIC_WS
#define PIN_MIC_WS 25
#endif
#ifndef PIN_MIC_SD
#define PIN_MIC_SD 33
#endif
#ifndef PIN_AMP_BCLK
#define PIN_AMP_BCLK 27
#endif
#ifndef PIN_AMP_LRC
#define PIN_AMP_LRC 14
#endif
#ifndef PIN_AMP_DIN
#define PIN_AMP_DIN 13
#endif
#ifndef PIN_BTN_TALK
#define PIN_BTN_TALK 4
#endif
#ifndef PIN_BTN_MODE
#define PIN_BTN_MODE 0  // boton BOOT de la placa
#endif
#ifndef PIN_LED_RING
#define PIN_LED_RING 18
#endif
#ifndef PIN_RELAY_1
#define PIN_RELAY_1 23
#endif
#ifndef PIN_RELAY_2
#define PIN_RELAY_2 19
#endif
#ifndef PIN_LIGHT_SENSOR
#define PIN_LIGHT_SENSOR -1  // GPIO 34 si conectas una LDR con divisor
#endif
#endif

// --------------------------------------------------------------- audio
#define GMINI_SAMPLE_RATE 16000
#ifndef GMINI_MIC_SHIFT
#define GMINI_MIC_SHIFT 14  // ganancia del INMP441: menor = mas fuerte
#endif
#ifndef GMINI_MAX_RECORD_SECONDS
#if defined(BOARD_HAS_PSRAM)
#define GMINI_MAX_RECORD_SECONDS 15
#else
#define GMINI_MAX_RECORD_SECONDS 3
#endif
#endif
#define GMINI_MIN_RECORD_MS 350

// --------------------------------------------------------------- red y portal
#define GMINI_DEFAULT_PORT 8765
#define GMINI_AP_PREFIX "G-Mini-Home-"
#define GMINI_AP_PASSWORD "gminihome"
#define GMINI_PORTAL_TIMEOUT_S 300
#define GMINI_WS_PING_MS 25000
#define GMINI_HTTP_CONNECT_MS 6000
#define GMINI_HTTP_IDLE_MS 45000

// --------------------------------------------------------------- interfaz
#ifndef GMINI_FACE_FPS
#define GMINI_FACE_FPS 40
#endif
#define GMINI_LONG_PRESS_MS 3000
#define GMINI_FACTORY_PRESS_MS 10000
