# Solución de problemas

## Conexión con G-Mini

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| "No encuentro a G-Mini" / `connect_failed` | El núcleo escucha solo en `127.0.0.1`, IP equivocada o firewall | `curl http://IP:8765/api/v1/health` desde otro equipo; activa "Permitir conexiones" o el modo servidor ([guía](connect-gmini.md)) |
| "Código inválido o vencido" | El código dura 5 minutos y sirve una vez | Pide uno nuevo y escríbelo sin espacios extra |
| "Demasiados intentos" | 5 intentos por minuto por IP | Espera un minuto |
| Se conecta y a los segundos se desconecta | Token revocado | El ESP32 lo detecta y pide emparejar; en el puente y la Pi usa `--pair` otra vez |
| "Me falta un permiso" | El código se creó sin el scope necesario | Empareja con `chat`, `voice` y `node` |
| Te entiende pero no contesta | El agente no tiene un proveedor de IA activo | Revisa el modelo en G-Mini; la cara muestra "G-Mini no respondió" |
| "Estoy ocupada" | El agente está en otro turno (409) | Espera o cancela con el botón de cancelar |

## Cara USB

| Síntoma | Qué hacer |
|---|---|
| OLED negra | Revisa VCC/GND, SDA en A4 y SCL en A5. Muchos módulos usan la dirección 0x3C (la que usa U8g2); si el tuyo es SH1106 compila con `GMINI_OLED_SH1106=1` |
| La imagen sale corrida 2 píxeles | Es una SH1106 grabada como SSD1306: recompila con `GMINI_OLED_SH1106=1` |
| El puente no encuentra la placa | `python gmini_serial_bridge.py --list-ports`; instala el driver CH340 en Windows; usa `--port COM5` |
| `ERR:overflow` en el monitor | Línea de más de 71 caracteres: el puente ya recorta, revisa scripts propios |
| Los botones disparan solos | Cables sueltos o botón entre pines equivocados: cada botón va de su pin a GND |
| El micrófono no graba | `--list-audio` y elige con `--mic`; en Windows revisa los permisos de micrófono para apps de escritorio |
| La carga falla en un Nano | Usa `arduino:avr:nano:cpu=atmega328old` |

## ESP32

| Síntoma | Qué hacer |
|---|---|
| No aparece la red `G-Mini-Home-XXXX` | Ya tiene WiFi guardado: mantén MODO 3 s y suelta, o enciéndela con MODO presionado |
| El portal no abre solo | Entra a `http://192.168.4.1`; desactiva los datos móviles mientras configuras |
| Pantalla negra (OLED) | SDA en GPIO8 y SCL en GPIO9; si ves rayas, baja el bus con `-DGMINI_OLED_I2C_HZ=400000` |
| Pantalla TFT blanca o con colores invertidos | Revisa CS/DC/RES; para colores invertidos cambia `cfg.invert` en `src/ui.cpp` |
| "audio no disponible" en la consola | Revisa los pines I2S del INMP441 y el MAX98357A |
| Grabación muda | L/R del INMP441 a GND; el firmware elige solo el canal con señal, pero si VDD no llega no hay nada que elegir |
| Se oye chasquido o ruido | GND común corto, fuente de 2 A, cables I2S cortos; baja el volumen (`volumen 50`) |
| Se reinicia al hablar | Caída de tensión: fuente de 2 A, cable USB corto y condensador de 470 uF en la alimentación del amplificador |
| LEDs con colores al azar | Falta GND común o la señal de 3,3 V no alcanza: resistencia de 330 ohm y, si sigue, un 74AHCT125 |
| "La voz del servidor no está lista" | G-Mini no tiene motor de voz: revisa TTS/STT en el núcleo |
| Responde muy lento | El servidor transcribe con CPU: usa un modelo de Whisper más chico o una PC más rápida |

Diagnóstico: `pio device monitor` y el comando `estado`. Para ver más
detalle compila con `-DCORE_DEBUG_LEVEL=4`.

## Raspberry Pi

| Síntoma | Qué hacer |
|---|---|
| El servicio no arranca | `journalctl -u gmini-pi -e`; prueba a mano con `python -m gmini_pi --demo --windowed` |
| "kmsdrm not available" | Con escritorio reinstala con `--desktop`; sin escritorio agrega el usuario al grupo `video` (lo hace el instalador) |
| Pantalla al revés o de costado | `display.rotate` en el config |
| Va lento | Baja `display.fps` o pon `display.supersample = 1` |
| Sin audio | `python -m gmini_pi --list-audio` y fija `audio.input` / `audio.output` |
| Los botones no responden | Pines BCM (no físicos) en `[buttons]`; el usuario debe estar en el grupo `gpio` |
| La tablet no ve el kiosco | `kiosk.listen = "0.0.0.0:8088"` y el puerto abierto en el firewall de la Pi |

## Hologramas

| Síntoma | Qué hacer |
|---|---|
| La imagen de la pirámide se ve doble | La lámina es gruesa: usa PET de 0,5 mm o acrílico más fino; los dos lados reflejan |
| La imagen sale al revés | Usa `layout = "pyramid"` (o `mirror` para la caja de Pepper); para la caja prueba girar la pantalla 180° |
| Se ve tenue | Apaga la luz de la sala, sube el brillo de la pantalla y usa fondo negro detrás de la pirámide |
