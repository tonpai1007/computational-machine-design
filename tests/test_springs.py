"""
Test Suite: Helical Spring DIN 2089 / Shigley Physics & CAD
"""

import pytest
from components.springs import SpringSpecification
from physics.springs import SpringSolver
from cad.springs_cad import SpringCADGenerator


def test_compression_spring_solver():
    spec = SpringSpecification(
        name="Test_Spring",
        wire_diameter_d_mm=3.0,
        mean_diameter_d_mm=24.0,
        active_coils_na=8.0,
        max_operating_force_n=200.0,
        min_operating_force_n=40.0
    )

    res = SpringSolver.solve(spec)

    assert res.geometry.spring_index_c == 8.0
    assert res.spring_rate_k_n_mm > 0
    assert res.wahl_factor_kw > 1.0
    assert res.shear_stress_max_mpa > res.shear_stress_min_mpa
    assert res.solid_yield_safety_factor > 0
    assert res.fatigue_safety_factor > 0

    scad = SpringCADGenerator.generate_scad(res)
    assert "helical_spring" in scad
    assert "$fn" in scad
