"""
Unit tests for the Learning Tools Integration Bridge (Dual-Mode)
and corresponding MDIE Web API endpoints.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from mdie.integrations.learning_tools import LearningToolsBridge
from mdie.convert.docx_bridge import HTMLToDocxConverter
from mdie.web.app import app

client = TestClient(app)


def test_docx_converter_bridge_import():
    """Verify that importing HTMLToDocxConverter from mdie.convert.docx_bridge resolves properly."""
    assert HTMLToDocxConverter is not None
    assert hasattr(HTMLToDocxConverter, "convert")


def test_learning_tools_bridge_status():
    """Verify LearningToolsBridge status query."""
    bridge = LearningToolsBridge()
    assert isinstance(bridge.is_online(), bool)


def test_learning_tools_bridge_convert_docx(tmp_path):
    """Verify dual-mode convert_docx runs successfully (library fallback mode)."""
    bridge = LearningToolsBridge()

    html_file = tmp_path / "test_report.html"
    html_file.write_text("<html><body><h1>Test Calculation</h1><p>Stress = 120 MPa</p></body></html>", encoding="utf-8")

    out_docx = tmp_path / "test_report.docx"
    result_docx = bridge.convert_docx(html_file, out_docx)

    assert result_docx.exists()
    assert result_docx.stat().st_size > 0


def test_learning_tools_bridge_consolidate(tmp_path):
    """Verify consolidate_report ingests, chunks, and creates study materials using learning-tools."""
    bridge = LearningToolsBridge()

    doc_file = tmp_path / "shaft_design_guide.md"
    doc_file.write_text(
        "# Transmission Shaft Design\n\n"
        "Shafts are rotating machine elements used to transmit power and torque. "
        "Under ASME shaft design codes, fatigue is evaluated using the modified Goodman criterion. "
        "Deflection must be limited to prevent tooth misalignment in spur gears.\n",
        encoding="utf-8"
    )

    out_dir = tmp_path / "study_output"
    res = bridge.consolidate_report(
        report_path=doc_file,
        output_dir=out_dir,
        convert_docx=False,
        generate_summaries=False,
        generate_notebooklm=False
    )

    assert res["status"] == "ok"
    assert res["chunks_count"] >= 1
    assert Path(res["output_dir"]).exists()


def test_web_api_learning_tools_endpoints():
    """Verify FastAPI routes for learning tools integration."""
    # 1. Status endpoint
    resp = client.get("/api/learning-tools/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "learning_tools_url" in data
    assert "is_online" in data
    assert "bridge_mode" in data

    # 2. Health endpoint
    resp_health = client.get("/api/health")
    assert resp_health.status_code == 200
