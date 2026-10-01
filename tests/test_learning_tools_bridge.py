"""
Unit tests for the Learning Tools Integration Bridge (Dual-Mode).
"""

import importlib.util
from pathlib import Path

import pytest

from convert.docx_bridge import HTMLToDocxConverter
from integrations.learning_tools import LearningToolsBridge


def test_docx_converter_bridge_import():
    """Verify that importing HTMLToDocxConverter from convert.docx_bridge resolves properly."""
    assert HTMLToDocxConverter is not None
    assert hasattr(HTMLToDocxConverter, "convert")


def test_learning_tools_bridge_status():
    """Verify LearningToolsBridge status query."""
    bridge = LearningToolsBridge()
    assert isinstance(bridge.is_online(), bool)


def _require_learning_tools_deps():
    """Skip when the external learning-tools project's own deps are absent.

    The bridge is an optional integration (see AGENTS.md: `convert` must degrade
    gracefully when an optional dependency is missing). Those dependencies
    (bs4, yaml) belong to learning-tools, not to this project, so they are not
    declared in pyproject.toml. Skip rather than fail when they are missing.
    """
    missing = [m for m in ("bs4", "yaml") if importlib.util.find_spec(m) is None]
    if missing:
        pytest.skip(f"optional learning-tools deps not installed: {missing}")


def test_learning_tools_bridge_convert_docx(tmp_path):
    """Verify dual-mode convert_docx runs successfully (library fallback mode)."""
    _require_learning_tools_deps()
    bridge = LearningToolsBridge()

    html_file = tmp_path / "test_report.html"
    html_file.write_text(
        "<html><body><h1>Test Calculation</h1><p>Stress = 120 MPa</p></body></html>",
        encoding="utf-8",
    )

    out_docx = tmp_path / "test_report.docx"
    result_docx = bridge.convert_docx(html_file, out_docx)

    assert result_docx.exists()
    assert result_docx.stat().st_size > 0


def test_learning_tools_bridge_consolidate(tmp_path):
    """Verify consolidate_report ingests, chunks, and creates study materials using learning-tools."""
    _require_learning_tools_deps()
    bridge = LearningToolsBridge()

    doc_file = tmp_path / "shaft_design_guide.md"
    doc_file.write_text(
        "# Transmission Shaft Design\n\n"
        "Shafts are rotating machine elements used to transmit power and torque. "
        "Under ASME shaft design codes, fatigue is evaluated using the modified Goodman criterion. "
        "Deflection must be limited to prevent tooth misalignment in spur gears.\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "study_output"
    res = bridge.consolidate_report(
        report_path=doc_file,
        output_dir=out_dir,
        convert_docx=False,
        generate_summaries=False,
        generate_notebooklm=False,
    )

    assert res["status"] == "ok"
    assert res["chunks_count"] >= 1
    assert Path(res["output_dir"]).exists()
