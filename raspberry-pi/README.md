# Cliente de pantalla de G-Mini Home

La cara de G-Mini a pantalla completa con voz, para Raspberry Pi (4, 5 o
Zero 2 W), mini PC o una PC vieja. Incluye la página de kiosco para tablets.

```bash
sudo ./install.sh --url http://192.168.1.50:8765 --pair 482913
```

Probar sin servidor: `python -m gmini_pi --demo --windowed` (desde esta
carpeta, con `PYTHONPATH=../common` si usas el repositorio).

| Archivo | Para qué |
|---|---|
| `install.sh` / `uninstall.sh` | Instala o quita el servicio `gmini-pi` |
| `config.example.toml` | Configuración comentada (se copia a `/etc/gmini-home/config.toml`) |
| `gmini-pi.service` | Plantilla del servicio de systemd |
| `gmini_pi/` | Código del cliente |

Guías: [Raspberry Pi](../docs/guides/raspberry-pi.md) y
[PC vieja o tablet](../docs/guides/kiosk.md).
