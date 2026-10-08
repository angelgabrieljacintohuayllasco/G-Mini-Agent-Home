# Licencia de los diseños de hardware y la documentación

Copyright (c) 2026 G-Mini Agent

Este repositorio usa dos licencias:

| Contenido | Licencia |
|---|---|
| Código: `firmware/`, `bridge/`, `raspberry-pi/`, `common/`, `kiosk/`, `tools/`, flujos de `.github/` | MIT (ver [`LICENSE`](LICENSE)) |
| Diseños de hardware y documentación: `hardware/` (BOM, tablas y diagramas de cableado, modelos OpenSCAD `.scad`, archivos STL, renders PNG, plantillas de corte SVG/DXF), `docs/` (guías, diagramas e imágenes) y los archivos `README*.md` | Creative Commons Atribución-CompartirIgual 4.0 Internacional (CC BY-SA 4.0) |

## CC BY-SA 4.0 en resumen

Puedes copiar, redistribuir, adaptar, fabricar y vender lo que construyas con
estos diseños, también con fines comerciales, siempre que:

1. **Atribución.** Indiques el origen ("Basado en G-Mini Home, de G-Mini
   Agent"), enlaces a la licencia y señales si hiciste cambios.
2. **Compartir igual.** Si publicas un diseño o documento derivado (por ejemplo,
   una carcasa modificada o una traducción de las guías), lo publiques bajo la
   misma licencia CC BY-SA 4.0 o una compatible.
3. **Sin restricciones adicionales.** No añadas términos legales ni medidas
   tecnológicas que impidan a otros hacer lo que la licencia permite.

Este resumen no sustituye al texto legal:

- Texto legal (español): <https://creativecommons.org/licenses/by-sa/4.0/legalcode.es>
- Texto legal (inglés): <https://creativecommons.org/licenses/by-sa/4.0/legalcode>

## Notas

- Los archivos que generan diagramas, plantillas y renders (`tools/`) son
  código y se rigen por MIT; lo que producen (SVG, DXF, STL, PNG) se rige por
  CC BY-SA 4.0.
- Las marcas y nombres de terceros (Arduino, Espressif, Raspberry Pi y otros)
  pertenecen a sus titulares y se mencionan solo para identificar piezas
  compatibles.
- Los diseños se entregan "tal cual", sin garantía. Lee
  [`docs/safety.md`](docs/safety.md) antes de construir cualquier variante,
  en especial las que usan relés, baterías de litio, agua o niebla.
