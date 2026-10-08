# Variante 3: parlante con LEDs (sin pantalla)

El "Alexa" de G-Mini: un cilindro con parlante, micrófono y un anillo de LEDs
que hace de cara. Mismo firmware que la variante 2, compilado sin pantalla.

![Cableado del parlante](../../hardware/wiring/esp32s3-speaker.svg)

**Dificultad:** media. **Costo:** US$ 20-35 / S/ 115-220
([BOM](../../hardware/bom.md#variante-3-parlante-con-leds-sin-pantalla)).
**Tiempo:** 2 horas más la impresión de la carcasa (~6 h).

## 1. Qué expresa el anillo

| Estado | Anillo |
|---|---|
| Reposo | Respira muy suave en el color de la emoción |
| Escuchando | Encendido, el brillo sigue tu voz |
| Pensando | Un punto violeta que gira |
| Trabajando (acting) | Dos puntos ámbar girando rápido |
| Hablando | El brillo late con la voz |
| Aviso | Tres pulsos azules |
| Error | Rojo parpadeante |
| Configuración (portal) | Azul girando |
| Sin red o sin servidor | Destello ámbar cada 4 s |

El agente puede fijar un color y efecto con `led.set` (y volver al modo
automático con `{"effect": "auto"}`).

## 2. Armar

El cableado es el de la variante 2 sin la OLED
([tabla](../../hardware/wiring/esp32s3-speaker.md)). Detalles del anillo:

- Resistencia de 330 ohm en serie con DIN y un condensador de 470-1000 uF entre
  5 V y GND cerca del anillo (evita que el primer LED se queme al enchufar).
- El ESP32 da 3,3 V en DIN: con cables cortos funciona; si ves colores al azar,
  agrega un 74AHCT125 como adaptador de nivel.
- El firmware limita el brillo del anillo a la mitad: a pleno, 24 LEDs blancos
  piden ~1,4 A.

Con un **ESP32 clásico** (DevKit V1, sin PSRAM) usa el entorno
`esp32dev-speaker` y el [cableado del DevKit](../../hardware/wiring/esp32dev.md):
funciona igual pero las grabaciones duran como máximo 3 s y el botón MODO es
el botón BOOT de la placa.

## 3. Firmware y configuración

```bash
cd firmware/esp32-companion
pio run -e esp32s3-speaker -t upload      # o esp32dev-speaker
```

Sin pantalla, el portal se reconoce por el anillo azul girando: conéctate a
`G-Mini-Home-XXXX` (clave `gminihome`) y sigue los pasos de la
[variante 2](esp32-wifi.md#3-configurar-wifi-y-emparejar). La consola serie
es la misma.

Este es el formato ideal para la palabra de activación: `activacion si` desde
la consola. Lee la nota de privacidad en la [guía de la variante 2](esp32-wifi.md#oye-g-mini-opcional).

## 4. Carcasa

[speaker_puck.scad](../../hardware/enclosures/speaker_puck.scad): cuerpo con
cuna para el DevKitC-1 (los pines de los headers quedan en el aire), tapa con
rejilla y canal para el aro difusor, y fondo con patas de goma.

![Carcasa del parlante](../../hardware/renders/speaker_puck.png)

Orden de montaje:

1. Pega el anillo LED bajo la tapa, centrado en las ventanas, con los LEDs
   hacia arriba.
2. Atornilla o pega el parlante en el aro de la tapa.
3. Coloca la placa en la cuna con el USB-C hacia el agujero trasero.
4. Pega el INMP441 por dentro del frente, con su agujero frente al de la
   carcasa, y el MAX98357A con cinta doble faz.
5. Encastra el difusor en la tapa, cierra con 3 tornillos M2,5 x 8 y pon el
   fondo a presión.

Problemas comunes: [solución de problemas](../troubleshooting.md#esp32).
