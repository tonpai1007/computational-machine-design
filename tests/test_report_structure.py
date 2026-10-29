"""Structural regression tests for rendered engineering reports.

These tests guard the document, not the physics. They cover the defect classes
that substring-only tests miss: malformed tables, table-of-contents links that
point nowhere, unescaped user/AI text, and material constants that were typed
into the template instead of read from the solver.

Physics fidelity is covered separately by ``test_provenance.py`` and
``test_chair_design_report.py``.
"""

from __future__ import annotations

import re

import pytest

from core.frame_model import FrameDesignModel
from core.models import (
    EngineeringConstraints,
    EngineeringModel,
    ShaftSegment,
    Support,
    TorqueLoad,
)
from physics.frame_physics import FramePhysicsSolver
from physics.solver import PhysicsSolver
from reporting.academic_engine import AcademicAssignmentEngine
from reporting.frame_report import FrameReportGenerator
from reporting.generator import ReportGenerator, format_safety_factor
from reporting.validate import (
    ReportValidationError,
    validate_html,
    validate_markdown,
    write_validated,
)


@pytest.fixture(scope="module")
def frame() -> tuple[FrameDesignModel, object]:
    model = FrameDesignModel()
    return model, FramePhysicsSolver.solve(model)


@pytest.fixture(scope="module")
def aluminium_shaft() -> tuple[EngineeringModel, object]:
    model = EngineeringModel(
        name="Aluminium Drive Shaft",
        component_type="shaft",
        total_length=0.4,
        material_id="AL_6061_T6",
        segments=[
            ShaftSegment(
                start_pos=0.0,
                end_pos=0.4,
                outer_diameter=0.030,
                inner_diameter=0.0,
                feature_type="smooth",
            )
        ],
        supports=[
            Support(name="Left Bearing", support_type="bearing", position=0.05),
            Support(name="Right Bearing", support_type="bearing", position=0.35),
        ],
        torques=[TorqueLoad(name="Drive Torque", position=0.20, magnitude=50.0)],
        constraints=EngineeringConstraints(max_mass_kg=5.0),
    )
    return model, PhysicsSolver.solve(model)


def _toc_block(document: str) -> str:
    """Return only the table-of-contents markup."""
    marker = "<!-- ================= สารบัญ (TABLE OF CONTENTS) ================= -->"
    start = document.index(marker)
    end = document.index("<!-- ================= บทที่ 1 =================", start)
    return document[start:end]


# --------------------------------------------------------------------------
# 1. Every generated report must pass the structural validator
# --------------------------------------------------------------------------
def test_frame_report_is_structurally_valid(frame) -> None:
    model, result = frame
    html = FrameReportGenerator.generate_html_report(model, result)
    assert validate_html(html, profile="core") == []


def test_academic_report_is_structurally_valid(frame) -> None:
    model, result = frame
    html = AcademicAssignmentEngine.generate_assignment_report(model, result)
    assert validate_html(html, profile="academic") == []


def test_shaft_report_is_structurally_valid(aluminium_shaft) -> None:
    model, result = aluminium_shaft
    html = ReportGenerator.generate_html_report(model, result)
    assert validate_html(html, profile="core") == []


def test_shaft_report_prints_solver_safety_factors(aluminium_shaft) -> None:
    """The shaft sheet formats solver output; it must not recompute the SF."""
    model, result = aluminium_shaft
    html = ReportGenerator.generate_html_report(model, result)
    assert format_safety_factor(result.min_yield_safety_factor) in html
    assert format_safety_factor(result.min_fatigue_safety_factor) in html
    assert f"{result.max_deflection_mm:.3f}" in html


def test_shaft_markdown_tables_are_rectangular(aluminium_shaft) -> None:
    model, result = aluminium_shaft
    document = ReportGenerator.generate_markdown_report(model, result)
    assert validate_markdown(document, profile="core") == []


# --------------------------------------------------------------------------
# 2. Table of contents must describe the document that was actually rendered
# --------------------------------------------------------------------------
def test_academic_toc_links_resolve_to_rendered_sections(frame) -> None:
    model, result = frame
    html = AcademicAssignmentEngine.generate_assignment_report(model, result)
    toc = _toc_block(html)

    targets = re.findall(r'href="#([^"]+)"', toc)
    assert targets, "the table of contents contains no anchors"
    for target in targets:
        assert f'id="{target}"' in html, f"TOC points at #{target}, which was not rendered"


def test_academic_toc_includes_fea_only_when_fea_is_rendered(frame) -> None:
    model, result = frame
    fea = {
        "num_members": 28,
        "num_nodes": 24,
        "active_free_dof": 120,
        "total_dof": 144,
        "max_von_mises_mpa": 12.3,
        "min_safety_factor": 3.4,
        "max_displacement_mm": 0.8,
    }

    with_fea = AcademicAssignmentEngine.generate_assignment_report(
        model, result, fea_result=fea
    )
    without_fea = AcademicAssignmentEngine.generate_assignment_report(model, result)

    assert 'href="#ch7"' in _toc_block(with_fea)
    assert 'id="ch7"' in with_fea
    assert 'href="#ch7"' not in _toc_block(without_fea)
    assert 'id="ch7"' not in without_fea


def test_academic_chapter_numbers_are_contiguous_without_fea(frame) -> None:
    """Omitting the FEA chapter must not leave a 6 -> 8 hole in the dossier."""
    model, result = frame
    html = AcademicAssignmentEngine.generate_assignment_report(model, result)

    numbers = [int(n) for n in re.findall(r"บทที่ (\d+)", _toc_block(html))]
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"chapter numbers are not contiguous: {numbers}"
    )


def test_academic_toc_and_body_chapter_numbers_agree(frame) -> None:
    """A heading in the body must carry the number the TOC assigned to it."""
    model, result = frame
    fea = {
        "num_members": 28,
        "num_nodes": 24,
        "active_free_dof": 120,
        "total_dof": 144,
        "max_von_mises_mpa": 12.3,
        "min_safety_factor": 3.4,
        "max_displacement_mm": 0.8,
    }

    for kwargs in ({}, {"fea_result": fea}):
        html = AcademicAssignmentEngine.generate_assignment_report(model, result, **kwargs)
        toc_numbers = re.findall(r"บทที่ (\d+)", _toc_block(html))
        body_numbers = re.findall(r'section-num">บทที่ (\d+)<', html)
        assert toc_numbers == body_numbers, (
            f"TOC numbering {toc_numbers} does not match body headings {body_numbers}"
        )


def test_academic_toc_has_no_baked_page_numbers(frame) -> None:
    """Page numbers must come from the renderer, never from a hardcoded digit."""
    model, result = frame
    html = AcademicAssignmentEngine.generate_assignment_report(model, result)
    toc = _toc_block(html)

    assert "target-counter" in html, "print CSS cannot resolve real page numbers"
    assert 'class="toc-page"' in toc
    assert not re.search(r'<span style="font-weight: 700;">\d+</span>', toc), (
        "a hardcoded page number survived in the TOC; it will drift as soon as "
        "a section grows"
    )


# --------------------------------------------------------------------------
# 3. User and AI text must be escaped
# --------------------------------------------------------------------------
def test_model_name_is_escaped_in_every_tier() -> None:
    evil = FrameDesignModel(name='Bench <script>alert("x")</script>')
    result = FramePhysicsSolver.solve(evil)

    documents = [
        FrameReportGenerator.generate_html_report(evil, result),
        AcademicAssignmentEngine.generate_assignment_report(evil, result),
    ]
    for document in documents:
        assert "<script>alert" not in document, "model name was injected as markup"
        assert "&lt;script&gt;" in document


def test_v2_escapes_ai_narrative(monkeypatch, frame) -> None:
    """AI-authored prose is untrusted input and must not become markup."""
    model, result = frame

    def fake_narrative(cls, model, component_names, use_ai=True):
        return {
            "introduction": "<script>alert(1)</script>\n\nSecond paragraph",
            "components": {
                "columns": "<img src=x onerror=alert(1)>",
                "seat_rails": "seat rails",
                "stretchers": "stretchers",
                "armrests": "armrests",
            },
        }

    monkeypatch.setattr(
        AcademicAssignmentEngine,
        "_synthesize_academic_narrative",
        classmethod(fake_narrative),
    )
    html = AcademicAssignmentEngine.generate_assignment_report_v2(model, result, use_ai=False)

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x onerror" not in html


# --------------------------------------------------------------------------
# 4. Material data must come from the selected alloy, not the template
# --------------------------------------------------------------------------
def test_shaft_report_reads_elastic_modulus_and_density_from_material(
    aluminium_shaft,
) -> None:
    model, result = aluminium_shaft
    html = ReportGenerator.generate_html_report(model, result)

    assert "68.9 GPa" in html, "aluminium modulus was not read from the material database"
    assert "2,700 kg/m" in html, "aluminium density was not read from the material database"
    assert "206.0 GPa" not in html, "steel modulus is still hardcoded in the template"
    assert "7,850 kg/m" not in html, "steel density is still hardcoded in the template"


# --------------------------------------------------------------------------
# 5. The validator itself must catch the defects it exists for
# --------------------------------------------------------------------------
def test_validator_catches_malformed_html_table() -> None:
    document = (
        "<table><thead><tr><th>A</th><th>B</th></tr></thead>"
        "<tbody><tr><td>1</td><td>2</td><td>3</td></tr></tbody></table>"
    )
    codes = {issue.code for issue in validate_html(document, profile="core")}
    assert "table-shape" in codes


def test_validator_catches_malformed_markdown_table() -> None:
    document = (
        "| Metric | Calculated | Allowable | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| SF | 2.0 | N/A | N/A | PASS |\n"
    )
    codes = {issue.code for issue in validate_markdown(document)}
    assert "table-shape" in codes


def test_validator_catches_broken_anchor_and_sentinel() -> None:
    document = '<p>None</p><a href="#missing">jump</a>'
    codes = {issue.code for issue in validate_html(document, profile="core")}
    assert "broken-anchor" in codes
    assert "sentinel-leak" in codes


# --------------------------------------------------------------------------
# 6. Generation is gated: an invalid report must never reach disk
# --------------------------------------------------------------------------
def test_write_validated_refuses_to_write_an_invalid_report(tmp_path) -> None:
    target = tmp_path / "chair_report.html"
    broken = (
        "<html><body><table><tr><th>A</th><th>B</th></tr>"
        "<tr><td>1</td><td>2</td><td>3</td></tr></table>"
        "<p>None</p></body></html>"
    )

    with pytest.raises(ReportValidationError) as excinfo:
        write_validated(target, broken)

    assert not target.exists(), "an invalid report was written to disk"
    codes = {issue.code for issue in excinfo.value.issues}
    assert {"table-shape", "sentinel-leak"} <= codes


def test_write_validated_writes_a_clean_report(frame, tmp_path) -> None:
    model, result = frame
    document = FrameReportGenerator.generate_html_report(model, result)
    target = tmp_path / "chair_report.html"

    written = write_validated(target, document)

    assert written == target
    assert target.read_text(encoding="utf-8") == document


def test_write_validated_rejects_a_missing_preview_image(frame, tmp_path) -> None:
    """A report pointing at an image that was never written is not shippable."""
    model, result = frame
    document = AcademicAssignmentEngine.generate_assignment_report(
        model, result, preview_image="chair_preview.png"
    )

    with pytest.raises(ReportValidationError) as excinfo:
        write_validated(tmp_path / "academic_assignment_report.html", document)

    assert any(issue.code == "missing-image" for issue in excinfo.value.issues)


def test_designer_refuses_to_write_an_invalid_report(monkeypatch, tmp_path) -> None:
    """The CLI design pipeline must go through the gate, not around it."""
    import cli.designers as designers

    monkeypatch.setattr(
        ReportGenerator,
        "generate_html_report",
        staticmethod(lambda model, result: "<html><body><p>None</p></body></html>"),
    )

    prompt = "stepped shaft 500 mm long"
    with pytest.raises(ReportValidationError):
        designers._handle_shaft(prompt, prompt.lower(), str(tmp_path))

    assert not (tmp_path / "shaft_report.html").exists()


# --------------------------------------------------------------------------
# 7. Missing solver values must render, never crash the console summary
# --------------------------------------------------------------------------
def test_format_safety_factor_handles_missing_values() -> None:
    assert format_safety_factor(None) == "N/A"
    assert format_safety_factor(2.345) == "2.35"
