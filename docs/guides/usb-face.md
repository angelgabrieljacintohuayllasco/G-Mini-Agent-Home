# Variante 1: cara USB (Arduino Uno o Nano)

La forma más barata y rápida: un Arduino con una OLED y dos botones,
conectado por USB a la PC donde corre G-Mini. El Arduino solo dibuja la cara;
el puente de Python (en la PC) recibe el estado del agente y usa el micrófono
y los parlantes de la PC para hablar.

![Cableado de la cara USB](../../hardware/wiring/arduino-usb-face.svg)

**Dificultad:** fácil (sin soldar si tu OLED trae pines). **Costo:** US$ 10-17 /
S/ 55-95 ([BOM](../../hardware/bom.md#variante-1-cara-usb-arduino-uno-o-nano)).
**Tiempo:** 30-45 minutos.

## 1. Armar en la protoboard

| OLED | Arduino |
|---|---|
| VCC | 5V (o 3V3 si tu módulo dice "3.3V only") |
| GND | GND |
| SCL | A5 |
| SDA | A4 |

Botón 1 (hablar) entre **D2** y **GND**; botón 2 (cancelar) entre **D3** y
**GND**. No hacen falta resistencias: el firmware activa el pull-up interno.
En el Nano los pines se llaman igual (A4, A5, D2, D3).

## 2. Grabar el sketch

Con arduino-cli (o abre `firmware/arduino-usb-face/arduino-usb-face.ino` en el
Arduino IDE y agrega la carpeta `firmware/libraries/GMiniEyes` como biblioteca
ZIP o cópiala a `Documentos/Arduino/libraries`):

```bash
arduino-cli core install arduino:avr
arduino-cli lib install U8g2
arduino-cli compile --fqbn arduino:avr:uno --library firmware/libraries/GMiniEyes firmware/arduino-usb-face
arduino-cli upload  --fqbn arduino:avr:uno -p COM5 firmware/arduino-usb-face
```

Para el Nano usa `--fqbn arduino:avr:nano` (o `arduino:avr:nano:cpu=atmega328old`
si la carga falla: muchos clones traen el bootloader viejo). Para una OLED de
1,3" (SH1106) agrega `--build-property "compiler.cpp.extra_flags=-DGMINI_OLED_SH1106=1"`.

Al encender verás dos ojos cian que parpadean y miran alrededor. Si abres el
monitor serie a 115200 baudios verás `H:gmini-usb-face;0.1.0;1`; escribe
`E:happy` y Enter para probar una emoción (ver [protocolo serie](../serial-protocol.md)).

Ocupa 29 300 bytes de flash (de 30 720 en el Nano) y 1 644 bytes de RAM.

## 3. Instalar el puente en la PC

Requisitos: Python 3.11 o más nuevo. Desde la raíz del repositorio (o desde la
carpeta del zip `gmini-bridge` de la release):

```bash
cd bridge
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

En Linux instala también PortAudio: `sudo apt install libportaudio2`.

## 4. Emparejar y arrancar

Con G-Mini de escritorio en la misma PC tienes dos opciones:

```bash
# a) Token propio para el puente (recomendado: aparece en Dispositivos y se revoca aparte)
python gmini_serial_bridge.py --url http://127.0.0.1:8765 --pair 482913

# b) Token de sesión del escritorio (sin emparejar; solo en la misma PC)
python gmini_serial_bridge.py --session-token-file "C:/ruta/a/G-Mini-Agent/data/runtime/session_token"
```

El código sale de **Ajustes > Dispositivos > Este equipo**. Después del primer
emparejamiento basta con `python gmini_serial_bridge.py`: guarda el token en el
llavero del sistema (o en un archivo solo legible por tu usuario).

El puente busca la placa solo (Arduino, CH340, CP210x, FTDI). Si tienes varias,
elige el puerto con `--port COM5`; para listar: `--list-ports`.

## 5. Usarla

- Mantén presionado el **botón 1** y habla; suéltalo para enviar. La cara pasa
  por *escuchando*, *pensando* y *hablando* (con la boca siguiendo el audio).
- **Botón 2** corta la respuesta en curso.
- Cuando el agente trabaja en otra cosa (por ejemplo una tarea desde el
  celular), la cara muestra su estado igual.
- El agente puede cambiar la cara por su cuenta (superficie `display.face`) o
  mostrar un texto (`display.text`).

Opciones útiles: `--no-audio` (solo cara), `--mic` y `--speaker` (dispositivos
de `--list-audio`), `--wake` (activa "Oye G-Mini"; manda frases cortas a tu
G-Mini para detectarla) y `-v` (muestra el tráfico serie).

## 6. Carcasa

[oled_companion.scad](../../hardware/enclosures/oled_companion.scad) entra un
Nano, la OLED y los dos botones. Ver [hardware](../../hardware/README.md#carcasas).

Problemas comunes: [solución de problemas](../troubleshooting.md#cara-usb).
