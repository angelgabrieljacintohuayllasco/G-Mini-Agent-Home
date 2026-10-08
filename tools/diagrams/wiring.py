"""Diagramas de cableado de cada variante (placa real con sus cabeceras + modulos).

La placa se dibuja con el orden real de pines de sus cabeceras; cada modulo se
coloca del lado de la cabecera que usa y los cables van por carriles
verticales propios, con color por funcion, puntos de union y saltos en los
cruces. Todo sale de las tablas de este archivo, que son las mismas que
documenta hardware/wiring/*.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from svgkit import (
    BRAND,
    FONT_MONO,
    INK,
    LINE,
    MUTED,
    PANEL,
    PANEL_DARK,
    WIRE,
    Svg,
)

PITCH = 22.0  # separacion entre pines dibujados
HOP = 5.0  # radio del salto en los cruces

# ---------------------------------------------------------------- placas

S3_LEFT = ["3V3", "3V3", "RST", "GPIO4", "GPIO5", "GPIO6", "GPIO7", "GPIO15", "GPIO16", "GPIO17", "GPIO18",
           "GPIO8", "GPIO3", "GPIO46", "GPIO9", "GPIO10", "GPIO11", "GPIO12", "GPIO13", "GPIO14", "5V", "GND"]
S3_RIGHT = ["GND", "TX", "RX", "GPIO1", "GPIO2", "GPIO42", "GPIO41", "GPIO40", "GPIO39", "GPIO38", "GPIO37",
            "GPIO36", "GPIO35", "GPIO0", "GPIO45", "GPIO48", "GPIO47", "GPIO21", "GPIO20", "GPIO19", "GND", "GND"]
DEVKIT_LEFT = ["EN", "GPIO36", "GPIO39", "GPIO34", "GPIO35", "GPIO32", "GPIO33", "GPIO25", "GPIO26", "GPIO27",
               "GPIO14", "GPIO12", "GPIO13", "GND", "VIN"]
DEVKIT_RIGHT = ["GPIO23", "GPIO22", "TX0", "RX0", "GPIO21", "GPIO19", "GPIO18", "GPIO5", "GPIO17", "GPIO16",
                "GPIO4", "GPIO2", "GPIO15", "GND", "3V3"]
UNO_LEFT = ["IOREF", "RESET", "3V3", "5V", "GND", "GND", "VIN", "A0", "A1", "A2", "A3", "A4/SDA", "A5/SCL"]
UNO_RIGHT = ["D0", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D12", "D13", "GND",
             "AREF", "SDA", "SCL"]
PI_LEFT = ["3V3", "GPIO2", "GPIO3", "GPIO4", "GND", "GPIO17", "GPIO27", "GPIO22", "3V3", "GPIO10", "GPIO9",
           "GPIO11", "GND", "ID_SD", "GPIO5", "GPIO6", "GPIO13", "GPIO19", "GPIO26", "GND"]
PI_RIGHT = ["5V", "5V", "GND", "GPIO14", "GPIO15", "GPIO18", "GND", "GPIO23", "GPIO24", "GND", "GPIO25", "GPIO8",
            "GPIO7", "ID_SC", "GND", "GPIO12", "GND", "GPIO16", "GPIO20", "GPIO21"]


@dataclass
class Board:
    name: str
    subtitle: str
    left: list[str]
    right: list[str]
    width: float = 300.0
    chip: str = "ESP32-S3-WROOM-1"
    usb: str = "USB-C"
    pin_numbers: bool = False  # Raspberry Pi: numero fisico 1..40


@dataclass
class Module:
    name: str
    subtitle: str
    pins: list[tuple[str, str]]  # (pin del modulo, pin de la placa)
    side: str = "left"
    accent: str = BRAND
    note: str = ""
    width: float = 190.0
    gap_after: float = 26.0


@dataclass
class Diagram:
    slug: str
    title: str
    subtitle: str
    board: Board
    modules: list[Module]
    notes: list[str] = field(default_factory=list)
    warning: tuple[str, list[str]] | None = None


POWER = {"3V3", "5V", "VIN", "GND"}


def wire_kind(board_pin: str, module_pin: str) -> str:
    """Color del cable segun la funcion del pin del modulo."""
    pin = module_pin.upper()
    if board_pin == "GND" or pin in ("GND", "L/R", "-"):
        return "gnd"
    if board_pin in ("5V", "VIN"):
        return "5v"
    if board_pin == "3V3":
        return "3v3"
    table = {
        "SDA": "sda", "SCL": "scl", "SCK": "bclk", "BCLK": "bclk", "WS": "ws", "LRC": "ws", "SD": "i2s_data",
        "DIN": "i2s_data" if "LED" not in pin else "data", "DI": "data", "MOSI": "spi", "SCLK": "spi",
        "CS": "ctrl", "DC": "ctrl", "RST": "ctrl", "BL": "ctrl", "IN1": "relay", "IN2": "relay", "AO": "analog",
        "S": "analog",
    }
    if pin in table:
        return table[pin]
    if pin.startswith(("BOTON", "BOTÓN")) or pin in ("1", "2", "A", "B"):
        return "button"
    return "data"


# ---------------------------------------------------------------- variantes

def diagrams() -> list[Diagram]:
    s3 = Board("ESP32-S3-DevKitC-1", "N16R8 (16 MB flash, 8 MB PSRAM)", S3_LEFT, S3_RIGHT)
    mic = Module("INMP441", "Micrófono I2S", [("VDD", "3V3"), ("GND", "GND"), ("L/R", "GND"), ("SCK", "GPIO4"),
                                               ("WS", "GPIO5"), ("SD", "GPIO6")], accent="#7c3aed")
    amp = Module("MAX98357A", "Amplificador I2S 3 W + parlante 4-8 ohm",
                 [("VIN", "5V"), ("GND", "GND"), ("DIN", "GPIO7"), ("BCLK", "GPIO15"), ("LRC", "GPIO16")],
                 accent="#059669", note="Parlante a los bornes + y - del módulo")
    buttons = Module("Botones", "Pulsadores a GND (pull-up interno)",
                     [("Botón HABLAR", "GPIO17"), ("Botón MODO", "GPIO18"), ("Común", "GND")], accent="#64748b")
    oled = Module("OLED 0,96\" I2C", "SSD1306 o SH1106 128x64",
                  [("VCC", "3V3"), ("GND", "GND"), ("SCL", "GPIO9"), ("SDA", "GPIO8")], accent="#2563eb")
    ring = Module("Anillo WS2812", "12-16 LEDs", [("5V", "5V"), ("GND", "GND"), ("DIN LED", "GPIO47")],
                  side="right", accent="#0ca678", note="Resistencia de 330 ohm en serie con DIN LED")
    tft = Module("Pantalla SPI", "ST7789 240x280 o GC9A01 240x240",
                 [("VCC", "3V3"), ("GND", "GND"), ("SCL", "GPIO12"), ("SDA", "GPIO11"), ("RES", "GPIO14"),
                  ("DC", "GPIO13"), ("CS", "GPIO10"), ("BLK", "GPIO21")], accent="#0891b2")
    relays = Module("Módulo de 2 relés", "Optoacoplado, entrada activa en bajo",
                    [("VCC", "5V"), ("GND", "GND"), ("IN1", "GPIO39"), ("IN2", "GPIO40")], side="right",
                    accent="#a61e4d", note="Cargas de 220 V: ver docs/safety.md")
    ldr = Module("LDR (opcional)", "Divisor con 10 kohm", [("AO", "GPIO2"), ("VCC", "3V3"), ("GND", "GND")],
                 side="right", accent="#9c36b5")

    devkit = Board("ESP32 DevKit V1", "WROOM-32, 30 pines (sin PSRAM)", DEVKIT_LEFT, DEVKIT_RIGHT, width=290,
                   chip="ESP32-WROOM-32", usb="micro-USB")
    uno = Board("Arduino Uno / Nano", "ATmega328P (Nano: mismos pines)", UNO_LEFT, UNO_RIGHT, width=280,
                chip="ATmega328P", usb="USB-B")
    pi = Board("Raspberry Pi", "Cabecera de 40 pines (Pi 3/4/5, Zero 2 W)", PI_LEFT, PI_RIGHT, width=250,
               chip="BCM", usb="USB", pin_numbers=True)

    tft_amp = Module("MAX98357A", "Amplificador I2S + parlante",
                     [("VIN", "5V"), ("GND", "GND"), ("DIN", "GPIO7"), ("BCLK", "GPIO15"), ("LRC", "GPIO16")],
                     accent="#059669")
    return [
        Diagram("esp32s3-oled", "ESP32-S3 + OLED (variante WiFi)",
                "Cara OLED, micrófono INMP441, amplificador MAX98357A, dos botones y anillo LED opcional",
                s3, [mic, amp, buttons, oled, ring],
                notes=["El INMP441 y la OLED van a 3,3 V; el amplificador y el anillo, a 5 V del USB.",
                       "L/R del INMP441 a GND (canal izquierdo); el firmware detecta solo la ranura con señal.",
                       "Entorno PlatformIO: esp32s3-oled (o esp32s3-sh1106 para pantallas de 1,3\")."]),
        Diagram("esp32s3-tft", "ESP32-S3 + pantalla a color",
                "ST7789 de 1,69\" o GC9A01 redonda de 1,28\" por SPI, con el mismo audio que la variante OLED",
                s3, [mic, tft_amp, buttons, tft],
                notes=["Los pines SCL/SDA de estos módulos son SPI: SCL = reloj y SDA = datos (MOSI).",
                       "Entornos PlatformIO: esp32s3-st7789 y esp32s3-gc9a01."]),
        Diagram("esp32s3-speaker", "ESP32-S3 parlante (sin pantalla)",
                "La cara es el anillo de LEDs: respira en reposo, gira al pensar y late al hablar",
                s3, [mic, amp, buttons, ring],
                notes=["Alimenta con una fuente USB de 5 V / 2 A: anillo y amplificador suman picos de 1 A.",
                       "Entorno PlatformIO: esp32s3-speaker."]),
        Diagram("esp32s3-relays", "ESP32-S3 + relés y sensor de luz",
                "Superficies relay.set y sensor.read para domótica básica",
                s3, [relays, ldr],
                warning=("Tensión de red (220 V)", [
                    "Desconecta la energía antes de tocar los bornes del relé.",
                    "Usa caja cerrada, cable de sección adecuada y fusible.",
                    "Si no tienes experiencia con 220 V, usa solo cargas de 5-12 V."])),
        Diagram("esp32dev", "ESP32 clásico (DevKit V1)",
                "Versión económica sin PSRAM: grabaciones de hasta 3 s; la OLED es opcional",
                devkit,
                [Module("INMP441", "Micrófono I2S", [("VDD", "3V3"), ("GND", "GND"), ("L/R", "GND"),
                                                     ("SCK", "GPIO26"), ("WS", "GPIO25"), ("SD", "GPIO33")],
                        accent="#7c3aed"),
                 Module("MAX98357A", "Amplificador I2S + parlante",
                        [("VIN", "VIN"), ("GND", "GND"), ("DIN", "GPIO13"), ("BCLK", "GPIO27"),
                         ("LRC", "GPIO14")], accent="#059669"),
                 Module("OLED 0,96\" I2C", "Opcional (esp32dev-oled)",
                        [("VCC", "3V3"), ("GND", "GND"), ("SCL", "GPIO22"), ("SDA", "GPIO21")], side="right",
                        accent="#2563eb"),
                 Module("Anillo WS2812", "12 LEDs", [("5V", "VIN"), ("GND", "GND"), ("DIN LED", "GPIO18")],
                        side="right", accent="#0ca678", note="Resistencia de 330 ohm en serie con DIN LED"),
                 Module("Botón HABLAR", "A GND", [("Botón HABLAR", "GPIO4"), ("Común", "GND")], side="right",
                        accent="#64748b", note="MODO = botón BOOT de la placa")],
                notes=["VIN entrega los 5 V del USB: alimenta ahi el amplificador y el anillo.",
                       "No uses GPIO12 para botones: decide el voltaje de la flash al arrancar."]),
        Diagram("arduino-usb-face", "Arduino Uno / Nano por USB",
                "La cara se conecta a la PC; el puente de Python pone la voz con el micrófono y los parlantes de la PC",
                uno,
                [Module("OLED 0,96\" I2C", "SSD1306 o SH1106 128x64",
                        [("VCC", "5V"), ("GND", "GND"), ("SCL", "A5/SCL"), ("SDA", "A4/SDA")], accent="#2563eb"),
                 Module("Botones", "Pulsadores a GND",
                        [("Botón 1 HABLAR", "D2"), ("Botón 2 CANCELAR", "D3"), ("Común", "GND")], side="right",
                        accent="#64748b")],
                notes=["Los módulos OLED comunes aceptan 5 V (tienen regulador). Si el tuyo dice 3,3 V, usa 3V3.",
                       "En el Nano los pines son los mismos: A4 = SDA, A5 = SCL, D2 y D3."]),
        Diagram("raspberry-pi", "Raspberry Pi: botones",
                "Pantalla por HDMI o SPI y audio USB; los botones van a la cabecera GPIO",
                pi,
                [Module("Botones", "Pulsadores a GND (pull-up interno)",
                        [("Botón HABLAR", "GPIO17"), ("Botón CANCELAR", "GPIO27"), ("Común", "GND")],
                        accent="#64748b")],
                notes=["Numeración BCM: GPIO17 es el pin físico 11 y GPIO27 el 13.",
                       "Micrófono y parlante USB (o un parlante con micrófono por USB); la pantalla por HDMI.",
                       "Configura los pines en /etc/gmini-home/config.toml ([buttons])."]),
    ]


# ---------------------------------------------------------------- dibujo


@dataclass
class _Seg:
    x: float
    y0: float
    y1: float
    color: str


def _board_geometry(board: Board, top: float, center_x: float) -> dict:
    rows = max(len(board.left), len(board.right))
    height = 70 + rows * PITCH + 50
    x = center_x - board.width / 2
    return {"x": x, "y": top, "w": board.width, "h": height, "first": top + 70}


def _pin_y(geo: dict, index: int) -> float:
    return geo["first"] + index * PITCH


def _draw_board(svg: Svg, board: Board, geo: dict, used: set[tuple[str, int]]) -> None:
    x, y, w, h = geo["x"], geo["y"], geo["w"], geo["h"]
    svg.rect(x + 4, y + 6, w, h, rx=16, fill="#000000", opacity=0.08)
    svg.rect(x, y, w, h, rx=16, fill="#1f3b4d", stroke="#0f2533", sw=1.5)
    svg.text(x + w / 2, y + 26, board.name, size=14, weight=700, fill="#ffffff", anchor="middle")
    svg.text(x + w / 2, y + 44, board.subtitle, size=10.5, fill="#a9c2cf", anchor="middle")
    # modulo / chip (entre las dos columnas de etiquetas)
    cw, ch = w - 176, 120
    cx, cy = x + (w - cw) / 2, y + h / 2 - ch / 2
    svg.rect(cx, cy, cw, ch, rx=6, fill="#c9d3da", stroke="#8fa1ad", sw=1)
    svg.rect(cx + 10, cy + 12, cw - 20, ch - 24, rx=4, fill="#e8edf0")
    svg.text(cx + cw / 2, cy + ch / 2 + 4, board.chip, size=10.5, weight=700, fill="#4a5a66", anchor="middle",
             family=FONT_MONO)
    # conector USB
    svg.rect(x + w / 2 - 22, y + h - 12, 44, 18, rx=4, fill="#9aa8b2", stroke="#6c7a84", sw=1)
    svg.text(x + w / 2, y + h - 20, board.usb, size=10, fill="#a9c2cf", anchor="middle")
    for side, pins in (("left", board.left), ("right", board.right)):
        px = x + 14 if side == "left" else x + w - 14
        for i, label in enumerate(pins):
            py = _pin_y(geo, i)
            active = (side, i) in used
            svg.rect(px - 6, py - 6, 12, 12, rx=2, fill="#f5c542" if active else "#6b8191",
                     stroke="#8a6d10" if active else "#506473", sw=1)
            svg.circle(px, py, 2.6, fill="#2b2b2b" if active else "#3d4f5b")
            tx = px + 12 if side == "left" else px - 12
            anchor = "start" if side == "left" else "end"
            text = label
            if board.pin_numbers:
                number = 2 * i + (1 if side == "left" else 2)
                text = f"{number} {label}" if side == "left" else f"{label} {number}"
            svg.text(tx, py + 3.5, text, size=9.5, fill="#ffffff" if active else "#a9c2cf", anchor=anchor,
                     family=FONT_MONO, weight=700 if active else 400)


def _module_height(module: Module) -> float:
    return 48 + len(module.pins) * PITCH + (16 if module.note else 0)


def _draw_module(svg: Svg, module: Module, x: float, y: float) -> dict[str, float]:
    h = _module_height(module)
    w = module.width
    svg.rect(x + 3, y + 4, w, h, rx=10, fill="#000000", opacity=0.06)
    svg.rect(x, y, w, h, rx=10, fill="#ffffff", stroke=LINE, sw=1.2)
    svg.rect(x, y, w, 6, rx=3, fill=module.accent)
    svg.text(x + 14, y + 26, module.name, size=13, weight=700, fill=INK)
    svg.text(x + 14, y + 41, module.subtitle, size=10, fill=MUTED)
    ys: dict[str, float] = {}
    for i, (pin, _target) in enumerate(module.pins):
        py = y + 60 + i * PITCH
        ys[pin] = py
        edge = x + w if module.side == "left" else x
        svg.rect(edge - 5, py - 5, 10, 10, rx=2, fill="#f5c542", stroke="#8a6d10", sw=1)
        tx = edge - 12 if module.side == "left" else edge + 12
        svg.text(tx, py + 3.5, pin, size=10, fill=INK, anchor="end" if module.side == "left" else "start",
                 family=FONT_MONO, weight=600)
    if module.note:
        svg.text(x + 14, y + h - 10, module.note, size=9.5, fill=MUTED, italic=True)
    return ys


def _find_pin(board: Board, side: str, label: str, near_y: float, geo: dict) -> tuple[str, int]:
    """Pin de la placa para una conexion; si no esta en ese lado, se busca en el otro."""
    for pin_side in (side, "right" if side == "left" else "left"):
        pins = board.left if pin_side == "left" else board.right
        candidates = [i for i, p in enumerate(pins) if p == label]
        if candidates:
            return pin_side, min(candidates, key=lambda i: abs(_pin_y(geo, i) - near_y))
    raise ValueError(f"{board.name}: no hay pin {label}")


def render(d: Diagram, path: Path) -> bool:
    left_mods = [m for m in d.modules if m.side == "left"]
    right_mods = [m for m in d.modules if m.side == "right"]
    lane_gap = 13.0
    lane_width = 70.0
    board_geo_probe = _board_geometry(d.board, 0, 0)

    def column_height(mods: list[Module]) -> float:
        return sum(_module_height(m) + m.gap_after for m in mods) - (mods[-1].gap_after if mods else 0)

    needs_bus = any(target not in (d.board.left if m.side == "left" else d.board.right)
                    for m in d.modules for _, target in m.pins)
    bus_room = 70 if needs_bus else 0
    content_h = max(board_geo_probe["h"] + bus_room, column_height(left_mods), column_height(right_mods))
    top = 112
    width = 1200.0
    left_lanes = sum(len({t for _, t in m.pins}) for m in left_mods) or 1
    right_lanes = sum(len({t for _, t in m.pins}) for m in right_mods) or 1
    lanes_l = max(lane_width, left_lanes * lane_gap + 30)
    lanes_r = max(lane_width, right_lanes * lane_gap + 30)
    mod_w = 190.0
    board_x = 40 + (mod_w + lanes_l if left_mods else 0) + d.board.width / 2
    total_w = board_x + d.board.width / 2 + (lanes_r + mod_w if right_mods else 0) + 40
    width = max(width, total_w)
    offset = (width - total_w) / 2
    board_x += offset
    notes_h = 22 * len(d.notes) + (110 if d.warning else 0)
    legend_h = 70
    height = top + content_h + 50 + legend_h + notes_h + 40
    svg = Svg(width, height, title=d.title, desc=d.subtitle)
    svg.heading(d.title, d.subtitle)

    geo = _board_geometry(d.board, top + (content_h - bus_room - board_geo_probe["h"]) / 2, board_x)
    used: set[tuple[str, int]] = set()
    wires: list[dict] = []

    for side, mods in (("left", left_mods), ("right", right_mods)):
        if not mods:
            continue
        col_h = column_height(mods)
        y = top + (content_h - col_h) / 2
        mx = geo["x"] - lanes_l - mod_w if side == "left" else geo["x"] + geo["w"] + lanes_r
        for m in mods:
            m.width = mod_w
            ys = _draw_module(svg, m, mx, y)
            for pin, target in m.pins:
                pin_side, index = _find_pin(d.board, side, target, ys[pin], geo)
                used.add((pin_side, index))
                bx = geo["x"] + 14 if pin_side == "left" else geo["x"] + geo["w"] - 14
                end_x = mx + m.width + 5 if side == "left" else mx - 5
                wires.append({"side": side, "net": f"{pin_side}:{target}:{index}", "by": _pin_y(geo, index),
                              "bx": bx, "my": ys[pin], "mx": end_x, "kind": wire_kind(target, pin),
                              "target": target, "cross": pin_side != side, "pin_side": pin_side})
            y += _module_height(m) + m.gap_after

    _draw_board(svg, d.board, geo, used)

    # Carriles: uno por pin de placa usado; los mas lejanos del tablero para las redes de alimentacion.
    for side in ("left", "right"):
        nets = []
        for w in wires:
            if w["side"] == side and w["net"] not in nets:
                nets.append(w["net"])
        nets.sort(key=lambda n: (n.split(":")[1] in POWER,
                                 min(w["my"] for w in wires if w["net"] == n and w["side"] == side)))
        edge = geo["x"] if side == "left" else geo["x"] + geo["w"]
        for k, net in enumerate(nets):
            lane_x = edge - 22 - k * lane_gap if side == "left" else edge + 22 + k * lane_gap
            for w in wires:
                if w["net"] == net and w["side"] == side:
                    w["lane"] = lane_x

    # Las conexiones a un pin del otro lado pasan por debajo de la placa.
    cross_nets = sorted({w["net"] for w in wires if w["cross"]})
    for k, net in enumerate(cross_nets):
        for w in wires:
            if w["net"] == net and w["cross"]:
                w["bus_y"] = geo["y"] + geo["h"] + 30 + k * 10
                w["stub_x"] = geo["x"] - 7 - k * 5 if w["pin_side"] == "left" else geo["x"] + geo["w"] + 7 + k * 5

    verticals: list[_Seg] = []
    for w in wires:
        top_y = w["bus_y"] if w["cross"] else w["by"]
        verticals.append(_Seg(w["lane"], min(top_y, w["my"]), max(top_y, w["my"]), WIRE[w["kind"]][0]))

    def hline(x0: float, x1: float, y: float, color: str, own_lane: float) -> None:
        lo, hi = sorted((x0, x1))
        hops = sorted({round(s.x, 2) for s in verticals
                       if lo + 2 < s.x < hi - 2 and s.y0 + 1 < y < s.y1 - 1 and abs(s.x - own_lane) > 0.5})
        direction = 1 if x1 >= x0 else -1
        points = hops if direction == 1 else list(reversed(hops))
        d_path = f"M{x0:.1f},{y:.1f}"
        for hx in points:
            a, b = hx - HOP * direction, hx + HOP * direction
            d_path += f" L{a:.1f},{y:.1f} A{HOP},{HOP} 0 0 {1 if direction == 1 else 0} {b:.1f},{y:.1f}"
        d_path += f" L{x1:.1f},{y:.1f}"
        svg.path(d_path, stroke=color, sw=2.6, extra='stroke-linecap="round" stroke-linejoin="round"')

    # Primero los tramos verticales (debajo), luego los horizontales con sus saltos.
    drawn_vertical: set[tuple[float, float, float]] = set()
    for w in wires:
        color = WIRE[w["kind"]][0]
        start = w["bus_y"] if w["cross"] else w["by"]
        key = (w["lane"], min(start, w["my"]), max(start, w["my"]))
        if key not in drawn_vertical:
            svg.line(w["lane"], key[1], w["lane"], key[2], stroke=color, sw=2.6)
            drawn_vertical.add(key)
    board_taps: set[tuple[float, float]] = set()
    for w in wires:
        color = WIRE[w["kind"]][0]
        if w["cross"] and (w["lane"], w["by"]) not in board_taps:
            out = 6 if w["pin_side"] == "left" else -6
            svg.polyline([(w["bx"] - out, w["by"]), (w["stub_x"], w["by"]), (w["stub_x"], w["bus_y"]),
                          (w["lane"], w["bus_y"])], stroke=color, sw=2.6)
            board_taps.add((w["lane"], w["by"]))
        elif not w["cross"] and (w["lane"], w["by"]) not in board_taps:
            hline(w["bx"] + (6 if w["side"] == "left" else -6), w["lane"], w["by"], color, w["lane"])
            board_taps.add((w["lane"], w["by"]))
        hline(w["lane"], w["mx"], w["my"], color, w["lane"])
    # Puntos de union donde un carril reparte a varios modulos.
    # dict.fromkeys y no un set: el orden de un set de cadenas cambia con PYTHONHASHSEED.
    for side, net in dict.fromkeys((w["side"], w["net"]) for w in wires):
        group = [w for w in wires if w["net"] == net and w["side"] == side]
        if len(group) > 1:
            lane = group[0]["lane"]
            start = group[0]["bus_y"] if group[0]["cross"] else group[0]["by"]
            span = (min(min(start, g["my"]) for g in group), max(max(start, g["my"]) for g in group))
            for g in group:
                if span[0] < g["my"] < span[1]:
                    svg.circle(lane, g["my"], 3.4, fill=WIRE[g["kind"]][0])

    # Leyenda con los colores usados.
    kinds = []
    for w in wires:
        if w["kind"] not in kinds:
            kinds.append(w["kind"])
    ly = top + content_h + 62
    svg.text(40, ly, "Colores", size=12, weight=700, fill=INK)
    lx = 110.0
    for kind in kinds:
        color, label = WIRE[kind]
        if lx + 30 + len(label) * 7 > width - 40:
            lx = 110.0
            ly += 22
        svg.line(lx, ly - 4, lx + 22, ly - 4, stroke=color, sw=4)
        svg.text(lx + 30, ly, label, size=11.5, fill=INK)
        lx += 52 + len(label) * 6.6
    ny = ly + 36
    for note in d.notes:
        svg.circle(46, ny - 4, 2.5, fill=BRAND)
        svg.text(56, ny, note, size=12, fill=INK)
        ny += 22
    if d.warning:
        svg.callout(40, ny - 6, width - 80, d.warning[1], title=d.warning[0], tone="danger")
    svg.footer(f"Generado por tools/diagrams/wiring.py  |  hardware/wiring/{d.slug}.md")
    return svg.save(path)


GUIDES = {
    "esp32s3-oled": "docs/guides/esp32-wifi.md",
    "esp32s3-tft": "docs/guides/esp32-wifi.md",
    "esp32s3-speaker": "docs/guides/speaker.md",
    "esp32s3-relays": "docs/guides/esp32-wifi.md",
    "esp32dev": "docs/guides/speaker.md",
    "arduino-usb-face": "docs/guides/usb-face.md",
    "raspberry-pi": "docs/guides/raspberry-pi.md",
}


def markdown(d: Diagram, path: Path) -> bool:
    """Tabla de conexiones en Markdown con el diagrama incrustado."""
    lines = [
        f"# Cableado: {d.title}",
        "",
        f"{d.subtitle}.",
        "",
        f"![{d.title}]({d.slug}.svg)",
        "",
        "| Módulo | Pin del módulo | Pin de la placa | Función |",
        "|---|---|---|---|",
    ]
    for m in d.modules:
        for pin, target in m.pins:
            lines.append(f"| {m.name} | `{pin}` | `{target}` | {WIRE[wire_kind(target, pin)][1]} |")
    if d.notes:
        lines += ["", "Notas:", ""] + [f"- {n}" for n in d.notes]
    for m in d.modules:
        if m.note:
            lines.append(f"- {m.name}: {m.note}.")
    if d.warning:
        lines += ["", f"> **{d.warning[0]}.** " + " ".join(d.warning[1])]
    guide = GUIDES.get(d.slug)
    if guide:
        lines += ["", f"Guía paso a paso: [{guide}](../../{guide}). Seguridad: [docs/safety.md](../../docs/safety.md)."]
    lines += ["", "<!-- Generado por tools/diagrams/wiring.py: no editar a mano. -->", ""]
    content = "\n".join(lines)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def targets() -> dict[str, Callable[[Path], bool]]:
    out: dict[str, Callable[[Path], bool]] = {}
    for d in diagrams():
        out[f"hardware/wiring/{d.slug}.svg"] = (lambda dd: (lambda p: render(dd, p)))(d)
        out[f"hardware/wiring/{d.slug}.md"] = (lambda dd: (lambda p: markdown(dd, p)))(d)
    return out


def tables() -> dict[str, list[tuple[str, str, str, str]]]:
    """Filas (modulo, pin del modulo, pin de la placa, funcion) para la documentacion."""
    out: dict[str, list[tuple[str, str, str, str]]] = {}
    for d in diagrams():
        rows = []
        for m in d.modules:
            for pin, target in m.pins:
                rows.append((m.name, pin, target, WIRE[wire_kind(target, pin)][1]))
        out[d.slug] = rows
    return out


_ = (PANEL, PANEL_DARK)  # paleta disponible para variantes futuras
