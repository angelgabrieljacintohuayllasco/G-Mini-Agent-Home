"""Entradas: botones GPIO (gpiozero) y teclado (eventos de pygame)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)

Action = Callable[[], Awaitable[None]]


class GpioButtons:
    """Pulsar para hablar y cancelar en pines BCM, con pull-up interno (boton a GND)."""

    def __init__(self, loop: asyncio.AbstractEventLoop, talk_pin: int, cancel_pin: int, *,
                 on_talk_down: Action, on_talk_up: Action, on_cancel: Action) -> None:
        self._buttons = []
        if not talk_pin and not cancel_pin:
            return
        try:
            from gpiozero import Button
        except ImportError:
            log.warning("gpiozero no esta instalado: los botones GPIO quedan desactivados")
            return

        def schedule(action: Action) -> Callable[[], None]:
            return lambda: asyncio.run_coroutine_threadsafe(action(), loop)

        try:
            if talk_pin:
                talk = Button(talk_pin, pull_up=True, bounce_time=0.03)
                talk.when_pressed = schedule(on_talk_down)
                talk.when_released = schedule(on_talk_up)
                self._buttons.append(talk)
            if cancel_pin:
                cancel = Button(cancel_pin, pull_up=True, bounce_time=0.03)
                cancel.when_pressed = schedule(on_cancel)
                self._buttons.append(cancel)
        except Exception as exc:
            log.warning("No se pudieron abrir los GPIO: %s", exc)

    def close(self) -> None:
        for button in self._buttons:
            button.close()


class KeyboardInput:
    """Espacio = pulsar para hablar, C = cancelar, F = pantalla completa, Esc/Q = salir."""

    def __init__(self, pygame: object, *, on_talk_down: Action, on_talk_up: Action, on_cancel: Action,
                 on_quit: Callable[[], None], on_fullscreen: Callable[[], None],
                 on_demo: Callable[[], None] | None = None) -> None:
        self.pg = pygame
        self.on_talk_down = on_talk_down
        self.on_talk_up = on_talk_up
        self.on_cancel = on_cancel
        self.on_quit = on_quit
        self.on_fullscreen = on_fullscreen
        self.on_demo = on_demo
        self._space_down = False

    def poll(self) -> list[Awaitable[None]]:
        """Procesa los eventos pendientes y devuelve las corrutinas a ejecutar."""
        pg = self.pg
        pending: list[Awaitable[None]] = []
        for event in pg.event.get():  # type: ignore[attr-defined]
            if event.type == pg.QUIT:  # type: ignore[attr-defined]
                self.on_quit()
            elif event.type == pg.KEYDOWN:  # type: ignore[attr-defined]
                if event.key in (pg.K_ESCAPE, pg.K_q):  # type: ignore[attr-defined]
                    self.on_quit()
                elif event.key == pg.K_SPACE and not self._space_down:  # type: ignore[attr-defined]
                    self._space_down = True
                    pending.append(self.on_talk_down())
                elif event.key == pg.K_c:  # type: ignore[attr-defined]
                    pending.append(self.on_cancel())
                elif event.key == pg.K_f:  # type: ignore[attr-defined]
                    self.on_fullscreen()
                elif event.key == pg.K_d and self.on_demo:  # type: ignore[attr-defined]
                    self.on_demo()
            elif event.type == pg.KEYUP and event.key == pg.K_SPACE:  # type: ignore[attr-defined]
                self._space_down = False
                pending.append(self.on_talk_up())
        return pending
