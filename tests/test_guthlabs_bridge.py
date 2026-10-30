"""Regression tests for the Guth Labs surrogate instruments.

These instruments are advisory. When the optional service is absent they must
degrade to a conservative value, never raise, and never invent a safety factor
that no solver produced.
"""

from __future__ import annotations

import pytest

from integrations import guthlabs_bridge


def test_fatigue_reader_without_endurance_limit_does_not_divide_by_none(monkeypatch):
    """No endurance limit and no API answer yields 0.0, not a TypeError.

    Regression: the fallback expression divided ``material_endurance_mpa``
    directly, so the optional argument being ``None`` crashed the instrument.
    """
    monkeypatch.setattr(
        guthlabs_bridge, "_guthlabs_api_call", lambda instrument, payload: {}
    )

    result = guthlabs_bridge.run_fatigue_curve_reader(120.0)

    assert result["safety_factor"] == 0.0
    assert result["life_cycles"] >= 1


def test_fatigue_reader_uses_the_endurance_limit_when_available(monkeypatch):
    monkeypatch.setattr(
        guthlabs_bridge, "_guthlabs_api_call", lambda instrument, payload: {}
    )

    result = guthlabs_bridge.run_fatigue_curve_reader(
        100.0, material_endurance_mpa=250.0
    )

    assert result["safety_factor"] == pytest.approx(2.5)
