# Variante 5: PC vieja, mini PC o tablet

Dos caminos según el equipo:

| Equipo | Qué usar | Voz |
|---|---|---|
| PC vieja o mini PC (Linux o Windows) | El cliente de la [Raspberry Pi](raspberry-pi.md) tal cual | Sí, con su micrófono y parlantes |
| Tablet o celular viejo | La página de kiosco en el navegador | No (la tablet solo muestra la cara) |

## PC vieja o mini PC

El cliente `gmini_pi` funciona en cualquier PC con Python 3.11:

```bash
cd raspberry-pi
python -m venv .venv
.venv/bin/pip install -r requirements.txt       # Windows: .venv\Scripts\pip ...
PYTHONPATH=../common .venv/bin/python -m gmini_pi --url http://IP:8765 --pair 482913
```

En Debian/Ubuntu también sirve `sudo ./install.sh --desktop`, que deja el
servicio de systemd configurado. Para arrancar en pantalla completa al
iniciar sesión en Windows, crea un acceso directo en `shell:startup` a
`pythonw -m gmini_pi` con la variable `PYTHONPATH` apuntando a `common`.

## Tablet: página de kiosco

La tablet no habla con G-Mini directamente: un cliente `gmini_pi` (en la Pi o
en una PC) le reenvía el estado de la cara por SSE. Así el token nunca llega al
navegador y no hay problemas de CORS ni del control de origen del núcleo.

1. En el equipo con `gmini_pi`, en `/etc/gmini-home/config.toml`:

   ```toml
   [kiosk]
   enabled = true
   listen = "0.0.0.0:8088"
   ```

   y reinicia el servicio. Con `0.0.0.0` cualquiera en tu red puede ver la cara
   **y los subtítulos** (que pueden incluir respuestas del agente). Déjalo en
   `127.0.0.1` si solo usas el navegador de ese mismo equipo.
2. En la tablet abre `http://IP-DEL-EQUIPO:8088` y toca **pantalla completa**
   (también pide mantener la pantalla encendida).
3. Opciones en la URL: `?layout=pyramid` o `?layout=mirror` para hologramas, y
   `?demo=1` para ver las expresiones sin servidor.

En Android, "Agregar a la pantalla principal" en Chrome la abre sin barras.
Para un kiosco dedicado, las apps tipo "Fully Kiosk Browser" bloquean la
tablet en esa página.

La página es HTML, CSS y JavaScript sin dependencias
([kiosk/](../../kiosk/)): usa el mismo motor de ojos que el resto, generado
desde `common/expressions.json`.
