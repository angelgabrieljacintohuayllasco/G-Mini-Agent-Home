# Cableado: Raspberry Pi: botones

Pantalla por HDMI o SPI y audio USB; los botones van a la cabecera GPIO.

![Raspberry Pi: botones](raspberry-pi.svg)

| Módulo | Pin del módulo | Pin de la placa | Función |
|---|---|---|---|
| Botones | `Botón HABLAR` | `GPIO17` | Botones |
| Botones | `Botón CANCELAR` | `GPIO27` | Botones |
| Botones | `Común` | `GND` | GND |

Notas:

- Numeración BCM: GPIO17 es el pin físico 11 y GPIO27 el 13.
- Micrófono y parlante USB (o un parlante con micrófono por USB); la pantalla por HDMI.
- Configura los pines en /etc/gmini-home/config.toml ([buttons]).

Guía paso a paso: [docs/guides/raspberry-pi.md](../../docs/guides/raspberry-pi.md). Seguridad: [docs/safety.md](../../docs/safety.md).

<!-- Generado por tools/diagrams/wiring.py: no editar a mano. -->
