"""Tests for the generative agent's deterministic size-selection search.

The agent must not ship a rule-of-thumb first guess that fails when a larger
catalogue size would pass. These tests pin that behaviour down.
"""

import pytest

from ai.generative_agent import (
    BEAM_SECTION_HEIGHTS_MM,
    BOLT_DESIGNATIONS,
    GEAR_MODULES_MM,
    POWER_SCREW_DIAMETERS_MM,
    SPRING_WIRE_DIAMETERS_MM,
    GenerativeEngineeringAgent as G,
)


def _all_pass(results):
    return all(r[1] for r in results)


class TestSelectSize:
    def test_returns_first_passing_candidate(self):
        calls = []

        def solve(size):
            calls.append(size)
            return {"sf": size}

        def passed(r):
            return r["sf"] >= 5

        res, size, tried, pinned = G._select_size([1, 2, 3, 4, 5], solve, passed,
                                                 requested=1)
        assert size == 5
        assert res == {"sf": 5}
        assert [s for s, _ in tried] == [1, 2, 3, 4, 5]
        assert pinned is False

    def test_honours_explicitly_requested_size_when_it_passes(self):
        res, size, tried, pinned = G._select_size(
            [1, 2, 3, 4],
            lambda s: {"sf": s},
            lambda r: r["sf"] >= 3,
            requested=4,
        )
        assert size == 4
        assert pinned is True
        assert [s for s, _ in tried] == [4]

    def test_steps_up_when_requested_size_fails(self):
        res, size, tried, pinned = G._select_size(
            [1, 2, 3, 4],
            lambda s: {"sf": s},
            lambda r: r["sf"] >= 3,
            requested=1,
        )
        assert size == 3
        assert pinned is False

    def test_returns_largest_attempt_when_nothing_passes(self):
        res, size, tried, pinned = G._select_size(
            [1, 2, 3],
            lambda s: {"sf": s},
            lambda r: r["sf"] >= 99,
            requested=1,
        )
        assert size == 3, "must report the largest attempt, not a silent success"

    def test_order_key_fixes_string_series_ordering(self):
        """Bolt designations sort wrongly as plain strings ('M16' < 'M6')."""
        order_key = lambda d: float(d[1:])  # noqa: E731
        res, size, tried, pinned = G._select_size(
            BOLT_DESIGNATIONS,
            lambda d: {"sf": float(d[1:])},
            lambda r: r["sf"] >= 20,
            requested="M16",
            order_key=order_key,
        )
        assert [s for s, _ in tried] == ["M16", "M20"]
        assert size == "M20"


class TestGenerativePromptsPass:
    """Each supported prompt family must yield a verified-passing design."""

    @pytest.mark.parametrize("prompt", [
        "spur gear pair for 15 kW at 1500 rpm, steel",
        "helical compression spring for 200 N force, 3mm wire",
        "24mm acme lead screw with 8 kN axial load",
        "bolted joint M16 class 10.9 with 40 kN load",
    ])
    def test_prompt_produces_passing_design(self, prompt, tmp_path):
        res = G.process(prompt, tmp_path)
        assert res.passed, f"{prompt!r} still fails: {res.verdict}"
        assert res.min_safety_factor > 1.0
        # A CAD solid and a report must accompany the verified result.
        assert res.scad_code.strip()
        assert "<html" in res.report_html.lower()

    @pytest.mark.parametrize("prompt", [
        "spur gear pair for 15 kW at 1500 rpm, steel",
        "helical compression spring for 200 N force, 3mm wire",
        "24mm acme lead screw with 8 kN axial load",
        "bolted joint M16 class 10.9 with 40 kN load",
    ])
    def test_size_search_is_reported(self, prompt, tmp_path):
        res = G.process(prompt, tmp_path)
        assert any("Tried" in k for k in res.key_metrics), res.key_metrics.keys()


def test_gear_honours_requested_module():
    """An explicit module is tried first, and stepping up is visible."""
    res = G.process("spur gear module 2 for 3 kW at 1500 rpm, steel", None)
    assert "Module Tried" in res.key_metrics
    assert "m2" in res.key_metrics["Module Tried"]


class TestSizeSeries:
    def test_series_are_ascending_and_unique(self):
        for series in (BEAM_SECTION_HEIGHTS_MM, GEAR_MODULES_MM,
                       SPRING_WIRE_DIAMETERS_MM, POWER_SCREW_DIAMETERS_MM):
            assert list(series) == sorted(series)
            assert len(set(series)) == len(series)

    def test_bolt_series_is_numerically_ascending(self):
        nums = [float(d[1:]) for d in BOLT_DESIGNATIONS]
        assert nums == sorted(nums)
