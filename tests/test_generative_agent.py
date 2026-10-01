"""
Test Suite: Generative Engineering Agent On-The-Fly Synthesis
"""

import pytest
from ai.generative_agent import GenerativeEngineeringAgent


def test_generative_gear_synthesis():
    prompt = "design a spur gear pair 15 kW at 1500 rpm with ratio 3, steel"
    res = GenerativeEngineeringAgent.process(prompt)

    assert "Gear" in res.title
    assert res.category == "Power Transmission"
    assert res.min_safety_factor > 0
    assert len(res.scad_code) > 100
    assert "<svg" in res.blueprint_svg


def test_generative_spring_synthesis():
    prompt = "design a helical compression spring for 200 N force, 3mm wire"
    res = GenerativeEngineeringAgent.process(prompt)

    assert "Spring" in res.title
    assert res.category == "Elastic Machine Element"
    assert res.min_safety_factor > 0
    assert len(res.scad_code) > 100
    assert "<svg" in res.blueprint_svg


def test_generative_custom_mechanism_synthesis():
    prompt = "design a mounting pivot link 100mm long with two 8mm pin holes, 500 N, aluminum"
    res = GenerativeEngineeringAgent.process(prompt)

    assert res.category == "Custom Synthesis"
    assert res.min_safety_factor > 0
    assert len(res.scad_code) > 50
    assert "<svg" in res.blueprint_svg
    assert "<!DOCTYPE html>" in res.report_html

    # The result must reflect the prompt, not a canned part: the stated 100 mm
    # span and 500 N load are honoured, and the safety factor is a real solver
    # value rather than a fabricated pass (guard against the old fixed-geometry
    # stub, which reported SF ~ 200 with dimensions unrelated to the prompt).
    assert res.key_metrics["Span (mm)"] == 100.0
    assert res.key_metrics["Load (N)"] == 500.0
    assert "100" in res.scad_code
    assert 2.0 <= res.min_safety_factor <= 6.0


def test_generative_custom_defaults_flagged_and_bounded():
    """A number-free prompt still solves, but flags its assumptions and returns
    a physically bounded safety factor - never a fabricated giant SF."""
    res = GenerativeEngineeringAgent.process("design a generic bracket")

    assert res.category == "Custom Synthesis"
    assert any("assumed" in r for r in res.recommendations)
    assert 2.0 <= res.min_safety_factor <= 6.0
