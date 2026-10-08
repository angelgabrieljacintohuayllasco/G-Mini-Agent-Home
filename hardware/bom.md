# Lista de materiales (BOM)

Precios referenciales de octubre de 2026 para piezas genéricas: **USD** en
tiendas en línea internacionales (envío aparte) y **PEN** en tiendas de
electrónica de Perú. Tipo de cambio usado para comparar: 1 USD ≈ S/ 3,75. Los
precios locales suelen ser más altos pero llegan el mismo día y aceptan
cambios; para un primer prototipo conviene comprar en local lo crítico (placa,
pantalla) y en línea lo barato (pulsadores, cables, tornillos).

La columna "Buscar como" es el término que mejor funciona en buscadores de
tiendas. Comprueba siempre la foto y los pines antes de pagar.

## Variante 1: cara USB (Arduino Uno o Nano)

| Pieza | Cant. | USD | PEN | Buscar como |
|---|---|---|---|---|
| Arduino Uno R3 (clon CH340) o Nano V3 | 1 | 4-7 | 22-40 | "arduino uno r3 ch340" / "arduino nano v3 type-c" |
| OLED 0,96" 128x64 I2C (SSD1306) | 1 | 2-3 | 15-20 | "oled 0.96 i2c ssd1306 4 pines" |
| Pulsadores 12x12 mm con capuchón | 2 | 0,5 | 2-4 | "pulsador tactil 12x12 capuchon" |
| Protoboard 400 puntos | 1 | 1,5-2 | 6-10 | "protoboard 400 puntos" |
| Cables dupont macho-macho y macho-hembra | 15 | 1-2 | 6-10 | "cables dupont 20 cm" |
| Cable USB de datos (no solo carga) | 1 | 1-2 | 5-10 | "cable usb b arduino" / "cable usb c datos" |
| **Total aproximado** | | **10-17** | **55-95** | sin carcasa |

Opcional: carcasa impresa ([oled_companion](enclosures/oled_companion.scad), ~45 g de PLA:
US$ 1-2 / S/ 5-10 de material) y 4 tornillos M2,5 x 8 autorroscantes.

## Variante 2: compañero WiFi (ESP32-S3 + OLED o pantalla a color)

| Pieza | Cant. | USD | PEN | Buscar como |
|---|---|---|---|---|
| ESP32-S3-DevKitC-1 N16R8 (16 MB flash, 8 MB PSRAM) | 1 | 6-9 | 45-65 | "esp32-s3 devkitc-1 n16r8" |
| OLED 0,96" I2C SSD1306 (o 1,3" SH1106) | 1 | 2-4 | 15-30 | "oled 0.96 ssd1306 i2c" / "oled 1.3 sh1106 i2c" |
| *o* pantalla ST7789 1,69" 240x280 SPI | 1 | 4-6 | 30-40 | "st7789 1.69 240x280 spi" |
| *o* pantalla redonda GC9A01 1,28" 240x240 | 1 | 4-6 | 30-40 | "gc9a01 1.28 round lcd" |
| Micrófono I2S INMP441 | 1 | 2-3 | 15-25 | "inmp441 i2s microfono" |
| Amplificador I2S MAX98357A | 1 | 2-4 | 18-30 | "max98357a i2s amplificador 3w" |
| Parlante 40 mm 4-8 ohm 3 W | 1 | 1-2 | 5-10 | "parlante 40mm 4 ohm 3w" |
| Pulsadores 12x12 mm | 2 | 0,5 | 2-4 | "pulsador tactil 12x12" |
| Anillo WS2812B 12-24 LEDs (opcional) | 1 | 3-6 | 20-35 | "ws2812b anillo 24 leds" |
| Resistencia 330 ohm + condensador 470-1000 uF (para el anillo) | 1 | 0,3 | 1-3 | "resistencia 330 ohm" "condensador 1000uf 16v" |
| Protoboard 830 puntos + cables dupont | 1 | 3-4 | 12-20 | "protoboard 830 puntos" |
| Fuente USB 5 V / 2 A + cable USB-C de datos | 1 | 4-6 | 15-30 | "cargador 5v 2a" "cable usb c datos" |
| **Total aproximado (OLED, sin anillo)** | | **20-30** | **115-185** | |

## Variante 3: parlante con LEDs (sin pantalla)

Igual que la variante 2 sin pantalla y con el anillo obligatorio:

| Pieza | Cant. | USD | PEN | Buscar como |
|---|---|---|---|---|
| ESP32-S3-DevKitC-1 N16R8 (o ESP32 DevKit V1, más barato y sin PSRAM) | 1 | 4-9 | 25-65 | "esp32-s3 devkitc-1 n16r8" / "esp32 devkit v1 30 pines" |
| INMP441 | 1 | 2-3 | 15-25 | "inmp441" |
| MAX98357A | 1 | 2-4 | 18-30 | "max98357a" |
| Parlante 40 mm 4 ohm 3-5 W | 1 | 1-3 | 5-15 | "parlante 40mm 4 ohm" |
| Anillo WS2812B 24 LEDs (66 mm) | 1 | 4-6 | 25-35 | "ws2812b ring 24" |
| Pulsadores 12x12 mm | 2 | 0,5 | 2-4 | |
| Patas de goma 10 mm | 4 | 0,5 | 2-4 | "patas de goma autoadhesivas 10mm" |
| Carcasa [speaker_puck](enclosures/speaker_puck.scad) (~110 g PLA + 6 g PETG natural) | 1 | 2-3 | 10-15 | |
| Fuente USB 5 V / 2 A | 1 | 4-6 | 15-30 | |
| **Total aproximado** | | **20-35** | **115-220** | |

## Variante 4: Raspberry Pi con pantalla

| Pieza | Cant. | USD | PEN | Buscar como |
|---|---|---|---|---|
| Raspberry Pi 4 (2 GB) / Pi 5 (4 GB) / Zero 2 W | 1 | 15-60 | 90-450 | "raspberry pi 4 2gb" / "raspberry pi zero 2 w" |
| Fuente oficial USB-C 5 V / 3 A (Pi 4) o 5 A (Pi 5) | 1 | 8-12 | 35-60 | "fuente raspberry pi 4 oficial" |
| microSD 32 GB clase A1 | 1 | 5-8 | 20-35 | "microsd 32gb a1" |
| Pantalla HDMI 7" 1024x600 (o SPI 3,5" para la Zero) | 1 | 15-40 | 70-250 | "pantalla 7 pulgadas hdmi raspberry" |
| Micrófono USB pequeño | 1 | 4-8 | 20-40 | "microfono usb mini" |
| Parlante USB o con jack 3,5 mm (Pi 4) | 1 | 6-12 | 30-60 | "parlante usb pequeño" |
| *o* altavoz manos libres USB (micrófono + parlante) | 1 | 15-25 | 80-150 | "speakerphone usb conferencia" |
| Pulsadores 12x12 + cables hembra-hembra | 2 | 1 | 4-8 | |
| **Total aproximado (Pi 4 + 7")** | | **75-140** | **330-650** | |

## Variante 5: PC vieja, mini PC o tablet

Sin compras obligatorias: el cliente de la Raspberry Pi corre en cualquier PC
con Linux o Windows, y la página de kiosco funciona en el navegador de una
tablet. Para voz en una tablet usa la PC o la Pi como "cerebro" y la tablet
solo como pantalla (estado por SSE).

## Hologramas

Costos de cada técnica en [docs/holograms/README.md](../docs/holograms/README.md).

## Herramientas

Cautín de 30-60 W con estaño 0,8 mm (si tus módulos vienen sin pines soldados),
multímetro básico, pelacables, cutter y regla metálica (pirámides), y acceso a
una impresora 3D (FDM, cama de 180 x 180 mm o más) para las carcasas.
