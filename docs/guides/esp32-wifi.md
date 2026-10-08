# Variante 2: compañero WiFi (ESP32-S3)

Un compañero independiente: escucha con su propio micrófono, habla por su
parlante y se conecta por WiFi a G-Mini. La cara puede ser una OLED de 0,96"
o 1,3", una ST7789 de 1,69" o una GC9A01 redonda de 1,28".

![Cableado ESP32-S3 + OLED](../../hardware/wiring/esp32s3-oled.svg)

**Dificultad:** media (soldar pines de los módulos). **Costo:** US$ 20-30 /
S/ 115-185 ([BOM](../../hardware/bom.md#variante-2-compañero-wifi-esp32-s3--oled-o-pantalla-a-color)).
**Tiempo:** 1,5-2 horas.

Antes de empezar: G-Mini tiene que ser accesible desde tu WiFi (modo servidor
o "Permitir conexiones" en todas las redes). Ver [conectar con G-Mini](../connect-gmini.md).

## 1. Cableado

Tabla completa en [hardware/wiring/esp32s3-oled.md](../../hardware/wiring/esp32s3-oled.md)
(pantalla a color: [esp32s3-tft.md](../../hardware/wiring/esp32s3-tft.md)).

| Función | GPIO | Notas |
|---|---|---|
| OLED SDA / SCL | 8 / 9 | 3,3 V |
| INMP441 SCK / WS / SD | 4 / 5 / 6 | VDD a 3,3 V, L/R a GND |
| MAX98357A BCLK / LRC / DIN | 15 / 16 / 7 | VIN a 5 V |
| Botón HABLAR / MODO | 17 / 18 | a GND |
| Anillo WS2812 | 47 | 5 V, 330 ohm en serie con DIN |
| Pantalla SPI SCL / SDA / CS / DC / RES / BLK | 12 / 11 / 10 / 13 / 14 / 21 | solo variantes TFT |
| Relés IN1 / IN2 | 39 / 40 | ver [relés](../../hardware/wiring/esp32s3-relays.md) |

No uses los GPIO 26-37 (flash y PSRAM octal del N16R8) ni 19/20 (USB nativo).
Todos los pines se pueden cambiar con `build_flags` (ver `include/config.h`).

Consejos de armado:

1. Primero solo la placa y la OLED: graba el firmware y comprueba que aparezcan
   los ojos. Después suma micrófono, amplificador y botones.
2. Cables cortos para el I2S (menos de 15 cm) y GND común para todo.
3. El amplificador consume picos de ~700 mA: alimenta con una fuente de 2 A.

## 2. Grabar el firmware

Opción A, binarios de la release (sin instalar nada): descarga
`gmini-home-esp32s3-oled-factory.bin` y grábalo en `0x0` con
[ESP Web Tool](https://espressif.github.io/esptool-js/) o con esptool:

```bash
pip install esptool
esptool.py --chip esp32s3 --port COM7 write_flash 0x0 gmini-home-esp32s3-oled-factory.bin
```

Opción B, compilar con PlatformIO:

```bash
pip install platformio
cd firmware/esp32-companion
pio run -e esp32s3-oled -t upload      # o esp32s3-sh1106, esp32s3-st7789, esp32s3-gc9a01
pio device monitor
```

Direcciones y entornos: [grabación del firmware](../flashing.md).

## 3. Configurar WiFi y emparejar

1. Al primer arranque la pantalla muestra **Configura tu G-Mini** con una red
   `G-Mini-Home-XXXX` (clave `gminihome`). Conéctate desde el celular; si no
   se abre solo, entra a `http://192.168.4.1`.
2. Elige tu WiFi y completa:
   - **Servidor G-Mini**: IP, nombre o URL (`192.168.1.50`, `http://tv-server:8765`).
   - **Código**: los 6 dígitos de Ajustes > Dispositivos, o pega el enlace
     `gmini://pair?...` completo (trae servidor y puerto).
   - **Nombre de este dispositivo**: cómo aparecerá en G-Mini.
3. Guarda. La placa se conecta, se empareja y muestra *Conectada a G-Mini*.

Volver a configurar: mantén **MODO** 3 s y suelta (o enciéndela con MODO
presionado). Borrar todo: mantén MODO 10 s.

## 4. Usarlo

- **HABLAR**: mantén presionado y habla; suelta para enviar. Suena un tono al
  empezar. La respuesta se reproduce mientras llega (no espera el audio entero).
- **MODO** (pulsación corta): corta la respuesta en curso y muestra la IP.
- Los ojos siguen el estado del agente aunque la conversación venga de otro
  dispositivo, y los avisos (`notify`) aparecen como tarjeta.
- Después de 10 minutos sin actividad los ojos se duermen; cualquier botón o
  mensaje los despierta.

### "Oye G-Mini" (opcional)

Por la consola serie: `activacion si`. El ESP32 detecta voz por energía y
manda frases cortas (menos de 4 s) a `/api/v1/voice/wake`; si empiezan con
"Oye G-Mini", atiende el pedido. Implica que **frases cortas de lo que se
dice cerca viajan a tu servidor G-Mini** (no a terceros). Desactívala con
`activacion no`.

## 5. Consola serie (115200 baudios)

| Comando | Qué hace |
|---|---|
| `estado` | WiFi, servidor, emparejamiento, memoria |
| `emparejar 482913` o `emparejar gmini://pair?...` | Empareja |
| `servidor 192.168.1.50:8765` | Cambia el servidor |
| `olvidar` | Borra el token (revócalo también en G-Mini) |
| `wifi` | Abre el portal |
| `activacion si/no`, `avisos-voz si/no` | Palabra de activación y avisos hablados |
| `volumen 0-100`, `brillo 0-255` | Ajustes de audio y pantalla |
| `cara happy`, `cara thinking` | Prueba expresiones y estados |
| `decir Hola` | Prueba la voz del servidor |
| `reiniciar`, `fabrica` | Reinicia o borra todo |

## 6. Lo que el agente puede usar

Al conectarse, el ESP32 se registra como nodo con estas superficies:

| Superficie | Ejemplo |
|---|---|
| `display.face` | `{"expression": "love", "text": "Te extrañé"}` |
| `display.text` | `{"text": "Reunión en 5 minutos", "seconds": 20}` |
| `led.set` | `{"color": "#ff8800", "effect": "breathe"}` (efectos: solid, breathe, blink, spin, rainbow, off, auto) |
| `relay.set` | `{"channel": 1, "on": true}` (pasa por las aprobaciones del agente) |
| `sensor.read` | `{"name": "chip_temp"}` (también `wifi_rssi`, `uptime`, `free_heap`, `light`) |
| `system.info` | firmware, IP, memoria y señal |
| `tts.speak` | `{"text": "Ya terminé el informe"}` |

## 7. Carcasa

[oled_companion.scad](../../hardware/enclosures/oled_companion.scad):
cabecita con ventana para la OLED, botones arriba, micrófono al frente y
parlante en la tapa trasera.

![Carcasa del compañero OLED](../../hardware/renders/oled_companion.png)

Problemas comunes: [solución de problemas](../troubleshooting.md#esp32).
