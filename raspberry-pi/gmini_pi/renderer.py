"""Dibujo de la cara con pygame, a cualquier resolucion.

Disposiciones:
  normal   la cara centrada (con subtitulos debajo).
  mirror   espejada en horizontal: para cajas de Pepper con placa a 45 grados.
  pyramid  cuatro copias giradas alrededor del centro: para piramides de Pepper
           apoyadas sobre una pantalla horizontal.
"""

from __future__ import annotations

import os
from typing import Any

from gmini_link import eye_presets
from gmini_link.face import (
    COLOR_ACCENT,
    COLOR_BACKGROUND,
    COLOR_EYE,
    COLOR_GLOW,
    COLOR_TEXT,
    FaceFrame,
    FaceLayout,
    draw_face,
)

from .config import DisplayConfig
from .face_model import FaceModel


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


PALETTE = {
    COLOR_BACKGROUND: _rgb(eye_presets.COLORS["background"]),
    COLOR_EYE: _rgb(eye_presets.COLORS["eye"]),
    COLOR_ACCENT: _rgb(eye_presets.COLORS["accent"]),
    COLOR_GLOW: _rgb(eye_presets.COLORS["glow"]),
    COLOR_TEXT: _rgb(eye_presets.COLORS["text"]),
}


class PygameCanvas:
    """FaceCanvas sobre una Surface de pygame."""

    def __init__(self, pygame: Any, surface: Any) -> None:
        self.pg = pygame
        self.surface = surface

    def _c(self, color: int) -> tuple[int, int, int]:
        return PALETTE.get(color, PALETTE[COLOR_EYE])

    def fill_rect(self, x: float, y: float, w: float, h: float, color: int) -> None:
        self.pg.draw.rect(self.surface, self._c(color), self.pg.Rect(round(x), round(y), round(w), round(h)))

    def fill_round_rect(self, x: float, y: float, w: float, h: float, r: float, color: int) -> None:
        rect = self.pg.Rect(round(x), round(y), max(1, round(w)), max(1, round(h)))
        self.pg.draw.rect(self.surface, self._c(color), rect, border_radius=max(0, round(r)))

    def fill_circle(self, cx: float, cy: float, r: float, color: int) -> None:
        self.pg.draw.circle(self.surface, self._c(color), (round(cx), round(cy)), max(1, round(r)))

    def fill_triangle(self, x0: float, y0: float, x1: float, y1: float, x2: float, y2: float, color: int) -> None:
        self.pg.draw.polygon(self.surface, self._c(color), [(x0, y0), (x1, y1), (x2, y2)])


def wrap(font: Any, text: str, width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and " ".join(lines) != " ".join(text.split()):
        lines[-1] = lines[-1].rstrip(".,;: ") + "..."
    return lines


class FaceRenderer:
    def __init__(self, config: DisplayConfig, model: FaceModel) -> None:
        if config.fullscreen and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            # Raspberry Pi OS Lite: sin escritorio se dibuja directo con KMS/DRM.
            os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
        import pygame

        self.pg = pygame
        self.config = config
        self.model = model
        pygame.display.init()
        pygame.font.init()
        flags = pygame.FULLSCREEN if config.fullscreen else pygame.RESIZABLE
        size = (config.width, config.height) if config.width and config.height else (
            (0, 0) if config.fullscreen else (800, 480))
        self.screen = pygame.display.set_mode(size, flags)
        pygame.display.set_caption("G-Mini Home")
        if config.hide_cursor:
            pygame.mouse.set_visible(False)
        self._fonts: dict[int, Any] = {}

    def font(self, size: int, bold: bool = False) -> Any:
        key = size * 2 + int(bold)
        if key not in self._fonts:
            font = self.pg.font.SysFont("dejavusans,segoeui,arial", size, bold=bold)
            self._fonts[key] = font
        return self._fonts[key]

    def toggle_fullscreen(self) -> None:
        self.pg.display.toggle_fullscreen()

    # ------------------------------------------------------------ dibujo

    def _face_surface(self, frame: FaceFrame, width: int, height: int) -> Any:
        scale = self.config.supersample
        surf = self.pg.Surface((width * scale, height * scale))
        surf.fill(PALETTE[COLOR_BACKGROUND])
        layout = FaceLayout.fit(width * scale, height * scale, 0.92, glow=True, snap=False)
        draw_face(frame, PygameCanvas(self.pg, surf), layout)
        if scale > 1:
            surf = self.pg.transform.smoothscale(surf, (width, height))
        return surf

    def _draw_text_block(self, target: Any, rect: Any, title: str, body: str) -> None:
        y = rect.top
        if title:
            font = self.font(max(16, rect.height // 5), bold=True)
            img = font.render(title, True, PALETTE[COLOR_ACCENT])
            target.blit(img, img.get_rect(midtop=(rect.centerx, y)))
            y += img.get_height() + 6
        font = self.font(max(14, rect.height // 6))
        for line in wrap(font, body, rect.width, max(1, (rect.bottom - y) // (font.get_linesize() or 1))):
            img = font.render(line, True, PALETTE[COLOR_TEXT])
            target.blit(img, img.get_rect(midtop=(rect.centerx, y)))
            y += font.get_linesize()

    def render(self, now_ms: int) -> None:
        pg = self.pg
        frame = self.model.update(now_ms)
        screen = self.screen
        width, height = screen.get_size()
        screen.fill(PALETTE[COLOR_BACKGROUND])
        layout = self.config.layout
        notify = self.model.current_notify()
        caption = self.model.current_caption() if self.config.captions else ""

        if layout == "pyramid":
            # Cuatro vistas con la parte de arriba de la cara hacia afuera: en cada
            # cara de la piramide lo que esta mas lejos del centro se ve mas alto.
            # El volteo previo compensa el espejo del reflejo.
            side = min(width, height) // 3
            face = self._face_surface(frame, side, side * 2 // 3)
            cx, cy = width // 2, height // 2
            placements = ((0, (cx, cy - side)), (180, (cx, cy + side)), (90, (cx - side, cy)), (270, (cx + side, cy)))
            for angle, center in placements:
                view = pg.transform.rotate(pg.transform.flip(face, True, False), angle)
                screen.blit(view, view.get_rect(center=center))
        else:
            text_h = height // 4 if (caption or notify) else 0
            face = self._face_surface(frame, width, height - text_h)
            if layout == "mirror":
                face = pg.transform.flip(face, True, False)
            screen.blit(face, (0, 0))
            if text_h:
                box = pg.Rect(width // 12, height - text_h, width - width // 6, text_h - height // 30)
                title, body = notify if notify else ("", caption)
                block = pg.Surface(box.size)
                block.fill(PALETTE[COLOR_BACKGROUND])
                self._draw_text_block(block, block.get_rect(), title, body)
                if layout == "mirror":
                    block = pg.transform.flip(block, True, False)
                screen.blit(block, box.topleft)

        if self.config.invert:
            inverted = pg.Surface((width, height))
            inverted.fill((255, 255, 255))
            inverted.blit(screen, (0, 0), special_flags=pg.BLEND_RGB_SUB)
            screen.blit(inverted, (0, 0))
        if self.config.rotate:
            rotated = pg.transform.rotate(screen.copy(), -self.config.rotate)
            screen.fill(PALETTE[COLOR_BACKGROUND])
            screen.blit(rotated, rotated.get_rect(center=(width // 2, height // 2)))
        pg.display.flip()

    def close(self) -> None:
        self.pg.quit()
