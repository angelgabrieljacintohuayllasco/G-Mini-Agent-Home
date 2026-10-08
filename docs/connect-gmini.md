# Conectar un dispositivo con G-Mini

Todas las variantes hablan con el núcleo de G-Mini Agent por la
**G-Mini Remote API v1** (REST + WebSocket en el puerto `8765`). Esta página
explica qué tiene que estar listo del lado de G-Mini antes de armar nada.

## 1. ¿Dónde corre G-Mini?

| Núcleo | Quién puede conectarse | Uso típico |
|---|---|---|
| Escritorio (Windows), por defecto | Solo la misma PC (`127.0.0.1`) | Cara USB (variante 1) con el puente en esa PC |
| Escritorio con **Permitir conexiones** por Tailscale | Equipos de tu Tailscale (PC, Pi, celular) | Raspberry Pi, otra PC con el puente |
| Escritorio con **Permitir conexiones** en todas las redes | Cualquier equipo de tu red, incluido un ESP32 | ESP32 en la misma WiFi |
| Servidor 24/7 (`--headless --host 0.0.0.0`) | Tu red local (y Tailscale/VPN si lo configuras) | Todas las variantes |

"Permitir conexiones" está en **Ajustes > Dispositivos > Este equipo** de la
app de escritorio. Con Tailscale instalado, G-Mini escucha además en tu IP de
Tailscale sin abrirse a la WiFi. Un ESP32 **no puede** unirse a Tailscale:
para las variantes 2 y 3 usa "todas las redes" o un G-Mini en modo servidor en
tu red.

Modo servidor (Linux, mini PC o una laptop vieja):

```bash
python -m backend.main --headless --host 0.0.0.0 --port 8765
```

Comprueba desde otro equipo que responde (no necesita token):

```bash
curl http://IP-DEL-SERVIDOR:8765/api/v1/health
# {"ok": true, "protocol": 1, "mode": "server", ...}
```

Si no responde: firewall del sistema (permite el puerto TCP 8765 solo en tu red
privada), IP equivocada o el núcleo escuchando solo en `127.0.0.1`.

## 2. Emparejar

Cada dispositivo recibe su propio token y se puede revocar por separado.

1. En G-Mini: **Ajustes > Dispositivos > Este equipo > Emparejar un
   dispositivo**. Aparece un código de 6 dígitos y un QR con un enlace
   `gmini://pair?host=...&port=8765&code=...`. El código vence a los 5 minutos
   y sirve una sola vez.
2. En el dispositivo, según la variante:
   - ESP32: en el portal WiFi pega el código o el enlace completo, o por la
     consola serie: `emparejar 482913`.
   - Puente USB: `python gmini_serial_bridge.py --url http://IP:8765 --pair 482913`.
   - Raspberry Pi: `sudo ./install.sh --url http://IP:8765 --pair 482913`.
3. El dispositivo aparece en la lista de **Dispositivos**. Desde ahí lo
   revocas si lo pierdes o lo regalas.

Límites del servidor: 5 intentos por minuto por IP; al quinto fallo el código
se invalida. Pide uno nuevo.

Sin la app (por ejemplo, un servidor recién instalado), un token con permiso
`admin` puede pedir el código:

```bash
curl -X POST http://IP:8765/api/v1/pairing \
  -H "Authorization: Bearer $(cat ~/.local/share/g-mini/data/runtime/session_token)" \
  -H "Content-Type: application/json" \
  -d '{"label": "Cara de la sala", "device_type": "esp32", "scopes": ["chat", "voice", "node"]}'
```

## 3. Qué permisos usa cada variante

| Scope | Para qué |
|---|---|
| `voice` | Turnos de voz, palabra de activación y texto a voz |
| `chat` | Pedidos en texto después de "Oye G-Mini" y el turno de voz |
| `node` | Registrar la cara como superficie (`display.face`, `led.set`, `relay.set`...) |

`relay.set` controla cargas físicas: el agente lo pasa por su política de
aprobaciones igual que cualquier acción local.

## 4. Fuera de casa

Para usar un dispositivo fuera de tu red: Tailscale (PC, Pi) o un proxy con
TLS delante del servidor (Caddy, Nginx). El ESP32 acepta direcciones
`https://`, pero solo cifra: no verifica el certificado del servidor (ver
[seguridad](safety.md#red-y-tokens)). Nunca publiques el puerto 8765
directamente en tu router.
