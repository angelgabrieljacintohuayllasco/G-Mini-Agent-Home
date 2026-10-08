# Protocolo serie de la cara USB (versión 1)

Protocolo de texto por líneas entre la PC (puente) y una cara con
microcontrolador. Pensado para depurar a mano desde cualquier monitor serie.

- 115200 baudios, 8N1. Cada mensaje es una línea terminada en `\n` (se ignora `\r`).
- Texto en **ISO-8859-1** (Latin-1). El puente convierte desde UTF-8, cambia
  comillas tipográficas y guiones largos por sus equivalentes y descarta lo que
  no tiene representación (emojis).
- Longitud máxima de línea: 71 caracteres en el Uno/Nano. Una línea más larga
  se descarta y la placa responde `ERR:overflow`.
- Las órdenes desconocidas o con valores inválidos responden `ERR:unknown` o
  `ERR:value`; las válidas no responden nada (salvo `?` y `V`).
- Al abrir el puerto, el Uno/Nano se reinicia y saluda con `H:`. El puente
  reenvía el estado completo cada vez que detecta la placa.

## PC -> placa

| Orden | Ejemplo | Efecto |
|---|---|---|
| `S:<estado>` | `S:thinking` | Estado del agente: `idle`, `listening`, `thinking`, `acting`, `speaking` |
| `E:<emoción>` | `E:happy` | `neutral`, `happy`, `sad`, `surprised`, `angry`, `thinking`, `sleepy`, `love`, `error` (y los alias de `expressions.json`, p. ej. `curious`) |
| `T:<texto>` | `T:Son las 6` | Subtítulo bajo la cara (2 líneas de 21 caracteres). `T:` lo borra |
| `N:<título>\|<cuerpo>` | `N:Correo\|3 nuevos` | Tarjeta de aviso por 6 s |
| `L:<0-9>` | `L:7` | Nivel de audio: mueve la boca al hablar y agranda los ojos al escuchar |
| `G:<x>,<y>` | `G:-50,20` | Mirada manual (-100..100). `G:` vuelve a la automática |
| `K` | `K` | Parpadeo |
| `Z:<0\|1>` | `Z:1` | Dormir (1) o despertar (0) |
| `C:<0-255>` | `C:120` | Contraste de la OLED |
| `?` | `?` | Responde `OK` |
| `V` | `V` | Responde el saludo `H:` |

## Placa -> PC

| Mensaje | Significado |
|---|---|
| `H:gmini-usb-face;0.1.0;1` | Firmware, versión y versión del protocolo |
| `OK` | Respuesta a `?` |
| `B:<id>:down` | Botón presionado (id 1 = hablar, 2 = cancelar) |
| `B:<id>:up` | Botón soltado |
| `B:<id>:long` | Botón mantenido 1,5 s |
| `ERR:<código>` | `unknown`, `value` u `overflow` |
| `# ...` | Comentario de depuración: el puente lo ignora |

## Ejemplo de una sesión

```
<- H:gmini-usb-face;0.1.0;1
-> E:neutral
-> S:idle
-> T:Conectada a G-Mini
<- B:1:down
-> S:listening
-> L:3
-> L:6
<- B:1:up
-> S:thinking
-> E:happy
-> T:¡Claro! Son las seis y diez.
-> S:speaking
-> L:7
-> L:2
-> L:0
-> S:idle
```

## Implementación

- Placa: `firmware/libraries/GMiniEyes/src/GMiniSerialProto.*` (con pruebas
  nativas en `firmware/esp32-companion/test/test_eyes`).
- PC: `bridge/gmini_bridge/protocol.py` (pruebas en `tests/test_bridge.py`).

Los cambios dentro de la versión 1 son solo aditivos: una placa vieja ignora
órdenes nuevas con `ERR:unknown` y el puente sigue funcionando.
