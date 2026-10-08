# Cómo contribuir

Gracias por sumar. Este repositorio mezcla firmware, Python, documentación y
diseños de hardware; abajo está lo necesario para cada parte.

## Antes de empezar

- Para cambios grandes abre primero un issue con la propuesta.
- Un cambio por pull request, con una descripción de qué cambia y cómo lo
  probaste (comandos y salida, fotos si es hardware).
- Escribe en español la documentación, los textos de interfaz y los mensajes
  de commit. Los identificadores del código pueden ir en inglés.

## Entorno

```bash
pip install -r requirements-dev.txt     # Python 3.11 o más nuevo
pip install platformio                  # firmware ESP32 y pruebas nativas
# arduino-cli para el sketch del Uno/Nano: https://arduino.github.io/arduino-cli/
```

## Comprobaciones

Lo mismo que corre la CI:

```bash
ruff check common bridge raspberry-pi tools tests
pytest
python tools/codegen/gen_expressions.py --check
python tools/diagrams/build_all.py --check
python tools/templates/pepper_pyramid.py --check
cd firmware/esp32-companion && pio test -e native && pio run
arduino-cli compile --fqbn arduino:avr:nano --library firmware/libraries/GMiniEyes firmware/arduino-usb-face
```

## Archivos generados

No edites a mano:

| Archivo | Fuente | Comando |
|---|---|---|
| `GMiniEyesPresets.h`, `eye_presets.py`, `kiosk/presets.js` | `common/expressions.json` | `python tools/codegen/gen_expressions.py` |
| `docs/img/*.svg`, `docs/holograms/img/*.svg`, `hardware/wiring/*` | `tools/diagrams/*.py` | `python tools/diagrams/build_all.py` |
| `hardware/templates/*` | `tools/templates/pepper_pyramid.py` | `python tools/templates/pepper_pyramid.py` |
| `hardware/stl/*`, `hardware/renders/*` | `hardware/enclosures/*.scad` | `python tools/render_enclosures.py` |

Si cambias una carcasa, vuelve a exportar sus STL y renders en el mismo commit
(cada STL debe pesar menos de 5 MB).

## Estilo

- Python: ruff (configuración en `pyproject.toml`), tipos en las funciones
  públicas, sin dependencias nuevas sin motivo.
- C++: dos espacios, sin excepciones ni memoria dinámica en los bucles
  calientes, `millis()` comparado con resta (soporta el desborde). El motor de
  ojos tiene que seguir entrando en un Arduino Nano: revisa el tamaño al
  compilar.
- Sin emojis en código, documentación ni interfaz.
- Commits con [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/)
  en español: `feat(esp32): ...`, `fix(puente): ...`, `docs(hologramas): ...`.

## Hardware

- Cambios de pines: actualiza `include/config.h`, las tablas de
  `tools/diagrams/wiring.py` y la guía de la variante en el mismo cambio.
- Carcasas: deja los parámetros nuevos comentados en el archivo `.scad` y
  prueba la impresión antes de proponerla (una foto ayuda).
- Las piezas nuevas en la BOM llevan precio en USD y PEN y el término de
  búsqueda que mejor funciona.

## Licencias

Al contribuir aceptas que tu código se publique bajo MIT y tus diseños y
documentación bajo CC BY-SA 4.0 ([LICENSE-hardware.md](LICENSE-hardware.md)).
