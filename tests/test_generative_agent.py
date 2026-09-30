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

    assert res.min_safety_factor > 0
    assert len(res.scad_code) > 50
    assert "<svg" in res.blueprint_svg
    assert "<!DOCTYPE html>" in res.report_html
