"""Deteccion del puerto serie de la cara USB."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)

# (VID, PID) de placas y conversores USB-serie habituales. PID None = cualquiera.
KNOWN_USB_IDS: dict[tuple[int, int | None], str] = {
    (0x2341, None): "Arduino",
    (0x2A03, None): "Arduino (arduino.org)",
    (0x1A86, 0x7523): "CH340",
    (0x1A86, 0x55D4): "CH9102",
    (0x0403, 0x6001): "FTDI FT232R",
    (0x10C4, 0xEA60): "CP210x",
    (0x303A, None): "Espressif USB",
}


@dataclass(frozen=True)
class PortInfo:
    device: str
    description: str
    vid: int | None
    pid: int | None

    @property
    def label(self) -> str:
        if self.vid is None:
            return ""
        return KNOWN_USB_IDS.get((self.vid, self.pid)) or KNOWN_USB_IDS.get((self.vid, None)) or ""


def list_ports() -> list[PortInfo]:
    from serial.tools import list_ports as lp

    return [PortInfo(p.device, p.description or "", p.vid, p.pid) for p in lp.comports()]


def candidates(ports: list[PortInfo]) -> list[PortInfo]:
    """Primero los conversores conocidos; si no hay ninguno, todos los puertos con USB."""
    known = [p for p in ports if p.label]
    if known:
        return known
    return [p for p in ports if p.vid is not None]


def probe(device: str, baud: int, timeout: float = 4.0) -> str | None:
    """Abre el puerto y espera el saludo "H:..." de la cara. Devuelve la linea o None.

    Al abrir el puerto el Uno/Nano se reinicia (DTR) y saluda al arrancar; si
    no lo hace (placas sin reinicio automatico) se le pide con "V".
    """
    import serial

    try:
        with serial.Serial(device, baud, timeout=0.2) as ser:
            deadline = time.monotonic() + timeout
            asked = False
            while time.monotonic() < deadline:
                raw = ser.readline()
                if raw:
                    line = raw.decode("latin-1", "replace").strip()
                    if line.startswith("H:"):
                        return line
                elif not asked and time.monotonic() > deadline - timeout / 2:
                    ser.write(b"V\n")
                    asked = True
    except (OSError, serial.SerialException) as exc:
        log.debug("No se pudo probar %s: %s", device, exc)
    return None


def find_device(baud: int) -> tuple[str, str] | None:
    for port in candidates(list_ports()):
        hello = probe(port.device, baud)
        if hello:
            return port.device, hello
    return None
