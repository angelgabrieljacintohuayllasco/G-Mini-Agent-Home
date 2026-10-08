"""Plantillas de la piramide de Pepper: geometria y archivos generados."""

from __future__ import annotations

import math

import pytest
from templates import pepper_pyramid as pp


def test_phone_template_matches_the_classic_6_1_3_5_cm_design() -> None:
    p = pp.design(next(s for s in pp.SCREENS if s.slug == "phone-6.1"))
    assert (p.b, p.a) == (60.0, 10.0)
    assert p.height == pytest.approx(25.0)
    assert p.slant == pytest.approx(35.36, abs=0.01)


@pytest.mark.parametrize("screen", pp.SCREENS, ids=lambda s: s.slug)
def test_every_pyramid_fits_its_screen_and_faces_are_at_45_degrees(screen: pp.Screen) -> None:
    p = pp.design(screen)
    assert p.b <= screen.short_side_mm
    assert p.a < p.b / 4
    # Cara a 45 grados: la altura es igual a lo que retrocede cada cara.
    assert math.degrees(math.atan2(p.height, (p.b - p.a) / 2)) == pytest.approx(45.0)
    # Angulo del lado del trapecio respecto de la base.
    assert math.degrees(math.atan2(p.slant, (p.b - p.a) / 2)) == pytest.approx(54.7356, abs=1e-3)


def test_fan_net_edges_have_the_right_lengths() -> None:
    p = pp.design(pp.SCREENS[2])
    cuts, folds, _ = pp.fan_net(p)
    small_edges = [math.dist(*cuts[i]) for i in range(0, 8, 2)]
    large_edges = [math.dist(*cuts[i]) for i in range(1, 8, 2)]
    assert all(e == pytest.approx(p.a) for e in small_edges)
    assert all(e == pytest.approx(p.b) for e in large_edges)
    assert all(math.dist(*f) == pytest.approx(p.leg) for f in folds)
    assert math.degrees(4 * p.fan_angle) == pytest.approx(282.12, abs=0.01)


def test_generated_templates_are_up_to_date() -> None:
    assert pp.main(["--check"]) == 0
