"""
Tests for OpenSCAD & STL CAD Generation
"""

import os
import struct
import pytest
from mdie.core.models import EngineeringModel, ShaftSegment, KeywaySpec, Support
from mdie.cad.openscad import OpenSCADGenerator
from mdie.cad.stl_exporter import STLExporter

def test_openscad_code_generation():
    model = EngineeringModel(
        name="Stepped Motor Shaft",
        total_length=0.4,
        segments=[
            ShaftSegment(start_pos=0.0, end_pos=0.1, outer_diameter=0.025, feature_type="bearing_seat"),
            ShaftSegment(
                start_pos=0.1,
                end_pos=0.3,
                outer_diameter=0.035,
                feature_type="gear_mount",
                keyway=KeywaySpec(position=0.15, length=0.04, width=0.008, depth=0.004)
            ),
            ShaftSegment(start_pos=0.3, end_pos=0.4, outer_diameter=0.025, feature_type="bearing_seat")
        ],
        supports=[Support(position=0.05), Support(position=0.35)]
    )
    scad = OpenSCADGenerator.generate_scad(model, critical_x=0.20)
    assert "module machine_shaft()" in scad
    assert "cylinder(" in scad
    assert "cube(" in scad  # keyway slot
    assert "critical_stress_indicator" in scad

def test_stl_binary_export():
    model = EngineeringModel(
        name="Test STL Shaft",
        total_length=0.3,
        segments=[
            ShaftSegment(start_pos=0.0, end_pos=0.15, outer_diameter=0.030),
            ShaftSegment(start_pos=0.15, end_pos=0.30, outer_diameter=0.040)
        ]
    )
    stl_bytes = STLExporter.export_binary_stl(model, n_slices=32)
    assert len(stl_bytes) > 84  # Header + triangle count + facets
    # Parse header and triangle count
    header = stl_bytes[:80]
    n_tris = struct.unpack("<I", stl_bytes[80:84])[0]
    assert n_tris > 0
    # Expected byte length = 84 + n_tris * 50
    assert len(stl_bytes) == 84 + (n_tris * 50)

def test_stl_ascii_export():
    model = EngineeringModel(
        name="AsciiShaft",
        total_length=0.2,
        segments=[ShaftSegment(start_pos=0.0, end_pos=0.2, outer_diameter=0.025)]
    )
    ascii_str = STLExporter.export_ascii_stl(model, n_slices=16)
    assert ascii_str.startswith("solid AsciiShaft")
    assert "facet normal" in ascii_str
    assert "vertex" in ascii_str
    assert ascii_str.strip().endswith("endsolid AsciiShaft")
