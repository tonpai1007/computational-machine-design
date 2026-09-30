"""
End-to-end integration tests for MDIE Multi-Domain Web API.
Verifies Shaft, Chair Multi-Body Solid, and 3D Frame/Truss FEA endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from web.app import app

client = TestClient(app)

def test_api_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_parse_shaft_domain():
    response = client.post("/api/parse", json={"prompt": "Design a stepped shaft 500 mm long with 30 mm diameter, power 10 kW"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "shaft"
    assert "model" in data
    assert "result" in data
    assert "mesh" in data

def test_parse_chair_domain():
    response = client.post("/api/parse", json={"prompt": "Design an armchair with 4 splayed legs and 2 arms, steel material"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "chair"
    assert "chair_model" in data
    assert "chair_result" in data
    assert "chair_fea" in data
    assert "mesh" in data
    assert data["chair_result"]["min_leg_buckling_sf"] > 1.0

def test_parse_fea3d_domain():
    response = client.post("/api/parse", json={"prompt": "Solve a 3D space frame tower under 3 kN wind load"})
    assert response.status_code == 200
    data = response.json()
    assert data["domain"] == "fea3d"
    assert "fea" in data
    assert data["fea"]["num_nodes"] >= 8
    assert data["fea"]["num_members"] >= 12
    assert data["fea"]["max_displacement_mm"] > 0.0

def test_chair_endpoints():
    payload = {
        "seat_load_n": 1400.0,
        "arm_load_n": 600.0,
        "leg_dia_mm": 30.0,
        "splay_deg": 3.5,
        "material_id": "STEEL_1018"
    }

    # Solve
    res_solve = client.post("/api/chair/solve", json=payload)
    assert res_solve.status_code == 200
    solve_data = res_solve.json()
    assert solve_data["result"]["all_safety_criteria_passed"] is True
    assert solve_data["fea"]["min_safety_factor"] > 1.0
    assert solve_data["fea"]["max_displacement_mm"] > 0.0

    # STEP export
    res_step = client.post("/api/chair/export/step", json=payload)
    assert res_step.status_code == 200
    assert "ISO-10303-21;" in res_step.text
    assert "MANIFOLD_SOLID_BREP" in res_step.text
    assert "NEXT_ASSEMBLY_USAGE_OCCURRENCE" in res_step.text

    # STL export
    res_stl = client.post("/api/chair/export/stl", json=payload)
    assert res_stl.status_code == 200
    assert len(res_stl.content) > 1000

    # SCAD export
    res_scad = client.post("/api/chair/export/scad", json=payload)
    assert res_scad.status_code == 200
    assert "chair_assembly()" in res_scad.text

    # HTML Report
    res_html = client.post("/api/chair/report/html", json=payload)
    assert res_html.status_code == 200
    assert "ANSI/BIFMA X5.1" in res_html.text

def test_fea3d_presets():
    res_list = client.get("/api/fea3d/presets")
    assert res_list.status_code == 200
    presets = res_list.json()
    assert len(presets) >= 3

    for p in presets:
        res = client.get(f"/api/fea3d/preset/{p['id']}")
        assert res.status_code == 200
        data = res.json()
        assert data["num_nodes"] > 0
        assert data["num_members"] > 0
        assert data["max_displacement_mm"] >= 0.0
