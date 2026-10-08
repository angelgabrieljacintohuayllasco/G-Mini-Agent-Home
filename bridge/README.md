# Puente USB de G-Mini Home

Conecta la cara USB (Arduino Uno o Nano con OLED) con G-Mini Agent: reenvía el
estado del agente a la placa por el puerto serie y pone la voz con el
micrófono y los parlantes de la PC.

```bash
python -m venv .venv
.venv\Scripts\activate                 # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python gmini_serial_bridge.py --url http://127.0.0.1:8765 --pair 482913
```

Después del primer emparejamiento basta con `python gmini_serial_bridge.py`.
Opciones: `python gmini_serial_bridge.py --help`.

Guía completa: [docs/guides/usb-face.md](../docs/guides/usb-face.md).
Protocolo serie: [docs/serial-protocol.md](../docs/serial-protocol.md).

Requisitos: Python 3.11 o más nuevo; en Linux, `sudo apt install libportaudio2`.
