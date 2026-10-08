"""Rasterizado por tramos (port de GMiniRaster): mapas de bits en memoria.

Sirve para pruebas y para exportar vistas previas sin dependencias externas.
"""

from __future__ import annotations

import math
import struct
import zlib

from .face import COLOR_BACKGROUND


class BitmapCanvas:
    """Lienzo de width x height con un indice de color por pixel."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(width * height)

    def clear(self, color: int = COLOR_BACKGROUND) -> None:
        self.pixels[:] = bytes([color]) * (self.width * self.height)

    def at(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.pixels[y * self.width + x]
        return COLOR_BACKGROUND

    def count(self, color: int) -> int:
        return self.pixels.count(color)

    def count_lit(self) -> int:
        return len(self.pixels) - self.pixels.count(COLOR_BACKGROUND)

    # ------------------------------------------------------------ primitivas

    def _span(self, x0: int, x1: int, y: int, color: int) -> None:
        if y < 0 or y >= self.height:
            return
        if x0 > x1:
            x0, x1 = x1, x0
        x0 = max(x0, 0)
        x1 = min(x1, self.width - 1)
        if x0 > x1:
            return
        start = y * self.width
        self.pixels[start + x0 : start + x1 + 1] = bytes([color]) * (x1 - x0 + 1)

    def fill_rect(self, x: float, y: float, w: float, h: float, color: int) -> None:
        x, y, w, h = int(x), int(y), int(w), int(h)
        for row in range(max(y, 0), min(y + h, self.height)):
            self._span(x, x + w - 1, row, color)

    def fill_round_rect(self, x: float, y: float, w: float, h: float, r: float, color: int) -> None:
        x, y, w, h, r = int(x), int(y), int(w), int(h), int(r)
        if w <= 0 or h <= 0:
            return
        r = min(r, min(w, h) // 2)
        if r <= 0:
            self.fill_rect(x, y, w, h, color)
            return
        for j in range(h):
            row = y + j
            if row < 0 or row >= self.height:
                continue
            dy = -1.0
            if j < r:
                dy = r - j - 0.5
            elif j >= h - r:
                dy = (j - (h - r)) + 0.5
            inset = 0
            if dy >= 0:
                inside = r * r - dy * dy
                dx = math.sqrt(inside) if inside > 0 else 0.0
                inset = math.floor(r - dx + 0.5)
            self._span(x + inset, x + w - 1 - inset, row, color)

    def fill_circle(self, cx: float, cy: float, r: float, color: int) -> None:
        cx, cy, r = int(cx), int(cy), int(r)
        if r <= 0:
            return
        rr = (r + 0.5) ** 2
        for dy in range(-r, r + 1):
            inside = rr - dy * dy
            dx = int(math.sqrt(inside)) if inside > 0 else 0
            self._span(cx - dx, cx + dx, cy + dy, color)

    def fill_triangle(self, x0: float, y0: float, x1: float, y1: float, x2: float, y2: float, color: int) -> None:
        pts = sorted(((int(y0), int(x0)), (int(y1), int(x1)), (int(y2), int(x2))))
        (y0, x0), (y1, x1), (y2, x2) = pts
        if y0 == y2:
            self._span(min(x0, x1, x2), max(x0, x1, x2), y0, color)
            return

        def lerp(xa: int, ya: int, xb: int, yb: int, y: int) -> int:
            # Division entera truncada hacia cero, igual que en C++.
            return xa + int((xb - xa) * (y - ya) / (yb - ya))

        for y in range(max(y0, 0), min(y2, self.height - 1) + 1):
            xa = lerp(x0, y0, x2, y2, y)
            if y < y1:
                xb = lerp(x0, y0, x1, y1, y)
            elif y2 != y1:
                xb = lerp(x1, y1, x2, y2, y)
            else:
                xb = x1
            self._span(xa, xb, y, color)

    # ------------------------------------------------------------ exportar

    def to_png(self, palette: dict[int, tuple[int, int, int]], scale: int = 1) -> bytes:
        """Codifica el lienzo como PNG RGB (sin dependencias)."""
        rows = []
        for y in range(self.height):
            line = bytearray()
            for x in range(self.width):
                rgb = palette.get(self.pixels[y * self.width + x], (0, 0, 0))
                line.extend(bytes(rgb) * scale)
            for _ in range(scale):
                rows.append(b"\x00" + bytes(line))
        raw = b"".join(rows)
        width, height = self.width * scale, self.height * scale

        def chunk(tag: bytes, data: bytes) -> bytes:
            body = tag + data
            return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

        header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(
            b"IEND", b""
        )
