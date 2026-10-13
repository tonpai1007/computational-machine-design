"""Guards convert/dxf.py -- STEP to orthographic DXF via FreeCAD.

The error paths are unit-tested with a stubbed kernel; the
projection itself is an integration test that only runs when
FreeCAD's console binary is present.
"""

import subprocess as sp
from pathlib import Path

import pytest

from cad.assembly import FrameCADEngine
from convert.dxf import (
    DIM_LAYER,
    TITLE_LAYER,
    VIEWS,
    _dxf_text,
    _fmt_dim,
    _linear_dim,
    assemble_dxf,
    calib_to_mapping,
    dxf_to_pdf,
    step_parts_to_dxf,
    step_to_dxf,
)
from convert.registry import has_dependency
from convert.solids import ConversionError, find_kernel
from core.frame_model import FrameDesignModel


@pytest.fixture
def step_file(tmp_path):
    """A real STEP assembly, written by the repo's own exporter."""
    model = FrameDesignModel(name="dxf_test")
    src = tmp_path / "part.step"
    src.write_text(FrameCADEngine.export_step_solid(model), encoding="utf-8")
    return src


def test_dxf_without_a_kernel_raises_a_clear_error(tmp_path, monkeypatch):
    src = tmp_path / "part.step"
    src.write_text("ISO-10301-21;", encoding="utf-8")
    monkeypatch.setattr("convert.dxf.find_kernel", lambda: None)
    with pytest.raises(ConversionError, match="geometry kernel"):
        step_to_dxf(src, tmp_path / "out")


def test_dxf_rejects_non_step_input(tmp_path):
    src = tmp_path / "part.stl"
    src.write_bytes(b"\x00")
    with pytest.raises(ConversionError, match="STEP"):
        step_to_dxf(src, tmp_path / "out")


def test_a_wedged_kernel_times_out_instead_of_hanging(tmp_path, monkeypatch):
    src = tmp_path / "part.step"
    src.write_text("ISO-10301-21;", encoding="utf-8")
    monkeypatch.setattr("convert.dxf.find_kernel", lambda: "freecadcmd")
    monkeypatch.setattr(
        "convert.dxf.subprocess.run",
        lambda *a, **k: (_ for _ in ()).throw(sp.TimeoutExpired("fc", 1)),
    )
    with pytest.raises(ConversionError, match="did not finish"):
        step_to_dxf(src, tmp_path / "out", timeout=1)


def test_a_kernel_failure_reports_its_stderr(tmp_path, monkeypatch):
    src = tmp_path / "part.step"
    src.write_text("ISO-10301-21;", encoding="utf-8")
    monkeypatch.setattr("convert.dxf.find_kernel", lambda: "freecadcmd")
    monkeypatch.setattr(
        "convert.dxf.subprocess.run",
        lambda *a, **k: type("R", (), {"returncode": 1, "stderr": "boom", "stdout": ""})(),
    )
    with pytest.raises(ConversionError, match="boom"):
        step_to_dxf(src, tmp_path / "out")


def test_missing_dxf_output_is_reported(tmp_path, monkeypatch):
    """A kernel that exits 0 but writes nothing is a failure, not a pass."""
    src = tmp_path / "part.step"
    src.write_text("ISO-10301-21;", encoding="utf-8")
    monkeypatch.setattr("convert.dxf.find_kernel", lambda: "freecadcmd")
    monkeypatch.setattr(
        "convert.dxf.subprocess.run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stderr": "", "stdout": ""})(),
    )
    with pytest.raises(ConversionError, match="produced no geometry"):
        step_to_dxf(src, tmp_path / "out.dxf")


@pytest.mark.skipif(find_kernel() is None, reason="FreeCAD console binary not installed")
def test_dxf_produces_a_valid_standalone_dxf(tmp_path, step_file):
    """The combined DXF must be a complete document carrying every view."""
    out = step_to_dxf(step_file, tmp_path / "out.dxf")

    assert out.name == "out.dxf"
    text = out.read_text(encoding="utf-8")
    assert "2\nHEADER" in text, "no HEADER section"
    assert "2\nENTITIES" in text, "no ENTITIES section"
    assert text.rstrip().endswith("EOF"), "no EOF"
    assert "$INSUNITS" in text, "does not declare units"
    # Every requested view is present as a named layer with projected geometry.
    for view in VIEWS:
        assert f"2\n{view}\n" in text, f"{view} layer missing"
    assert text.count("LINE") >= len(VIEWS), "projected no geometry"


def _line(x1, y1, x2, y2):
    """One bare LINE entity fragment with TechDraw's group-code layout."""
    return (
        "0\nLINE\n8\nsheet_layer\n"
        f"10\n{x1}\n20\n{y1}\n30\n0.0\n"
        f"11\n{x2}\n21\n{y2}\n31\n0.0\n"
    )


def test_calib_to_mapping_reads_probe_landings():
    """A +X probe landing on drawing-Y with +sign maps X -> (Y, +1)."""
    mapping = calib_to_mapping({"X": [0.0, 10.0], "Y": None, "Z": [-10.0, 0.0]})
    assert mapping == {"X": ("Y", 1.0), "Z": ("X", -1.0)}


def test_calib_to_mapping_rejects_a_ambiguous_calibration():
    """Two probes landing on the same drawing axis is a failure, not a guess."""
    with pytest.raises(ConversionError, match="not orthogonal"):
        calib_to_mapping({"X": [10.0, 0.0], "Y": None, "Z": [10.0, 0.0]})


def test_calib_to_mapping_rejects_a_missing_view_axis():
    """A single surviving planar axis cannot orient a view."""
    with pytest.raises(ConversionError, match="two planar axes"):
        calib_to_mapping({"X": [10.0, 0.0], "Y": None, "Z": None})


def test_assemble_reorients_and_lays_out_first_angle():
    """Synthetic fragments through the chair's real mappings end up aligned.

    The chair's measured calibration: front X2=-Z/Y2=+X, top X2=-X/Y2=+Y,
    side X2=-Z/Y2=-Y. A 100x50 model rectangle in each raw view plane must
    land upright (width right, height up) with the top view below the
    front view sharing X and the right-side view left of the front view
    sharing Z - the ISO 128 first-angle arrangement.
    """
    views = {
        "front": _line(0.0, 0.0, -50.0, 100.0),  # X2=-Z, Y2=+X
        "top": _line(0.0, 0.0, -100.0, 50.0),  # X2=-X, Y2=+Y
        "side": _line(0.0, 0.0, -50.0, -100.0),  # X2=-Z, Y2=-Y
    }
    calibs = {
        "front": {"X": [0.0, 10.0], "Y": None, "Z": [-10.0, 0.0]},
        "top": {"X": [-10.0, 0.0], "Y": [0.0, 10.0], "Z": None},
        "side": {"X": None, "Y": [0.0, -10.0], "Z": [-10.0, 0.0]},
    }
    text = assemble_dxf(views, calibs, gap=10.0)

    def layer_bbox(layer):
        xs, ys = [], []
        codes = text.splitlines()
        on_layer, pending = False, None
        for i in range(0, len(codes) - 1, 2):
            code, val = codes[i].strip(), codes[i + 1]
            if code == "8":
                on_layer = val == layer
            elif on_layer and code in ("10", "11"):
                pending = float(val)
            elif on_layer and code in ("20", "21") and pending is not None:
                xs.append(pending)
                ys.append(float(val))
                pending = None
        return min(xs), min(ys), max(xs), max(ys)

    fx0, fy0, fx1, fy1 = layer_bbox("front")
    tx0, ty0, tx1, ty1 = layer_bbox("top")
    sx0, sy0, sx1, sy1 = layer_bbox("side")
    # Every view upright: 100 wide, 50 tall.
    assert (fx1 - fx0, fy1 - fy0) == (100.0, 50.0)
    assert (tx1 - tx0, ty1 - ty0) == (100.0, 50.0)
    assert (sx1 - sx0, sy1 - sy0) == (100.0, 50.0)
    # First-angle: top below front sharing X; right-side view left of
    # front sharing Z.
    assert (tx0, tx1) == (fx0, fx1)
    assert ty1 == fy0 - 10.0
    assert (sy0, sy1) == (fy0, fy1)
    assert sx1 == fx0 - 10.0


def test_assemble_requires_a_calibration_per_view():
    """A view without probe landings is an error, not a silent misorient."""
    with pytest.raises(ConversionError, match="no calibration"):
        assemble_dxf({"front": _line(0, 0, 1, 1)}, {})


def test_fmt_dim_is_locale_independent():
    """Millimetre values keep an ISO decimal point at one decimal."""
    assert _fmt_dim(575.0) == "575.0"
    assert _fmt_dim(559.814) == "559.8"


def test_linear_dim_is_plain_line_and_text_geometry():
    """A dimension carries witness/dimension/arrow LINEs and a TEXT value."""
    frag = _linear_dim("dimensions", 0.0, 0.0, 100.0, 100.0, True, -1)
    assert frag.count("LINE") == 7  # 2 witness + 1 dimension + 4 arrow barbs
    assert frag.count("TEXT") == 1
    assert "\n1\n100.0\n" in frag
    # AC1009-safe: no DIMENSION objects, no style tables.
    assert "DIMENSION" not in frag


def test_dxf_text_sets_the_second_alignment_point():
    """Justified TEXT must carry 11/21 - viewers centre on the origin without it."""
    frag = _dxf_text("dimensions", 100.0, -40.0, "575.0", 12.0)
    assert "\n72\n1\n73\n2\n" in frag
    assert "\n11\n100.0\n21\n-40.0\n" in frag
    assert "\n7\nSTANDARD\n" in frag


def test_wrapped_dxf_declares_the_standard_style():
    """TEXT entities reference a style by name; the document must declare it."""
    views = {"front": _line(0.0, 0.0, -50.0, 100.0)}
    calibs = {"front": {"X": [0.0, 10.0], "Y": None, "Z": [-10.0, 0.0]}}
    text = assemble_dxf(views, calibs)
    assert "2\nSTYLE\n" in text
    assert "2\nSTANDARD\n" in text


def test_assemble_adds_a_title_block_and_part_label():
    """A named part gets the sheet border, part label and title block."""
    views = {"front": _line(0.0, 0.0, -50.0, 100.0)}
    calibs = {"front": {"X": [0.0, 10.0], "Y": None, "Z": [-10.0, 0.0]}}
    text = assemble_dxf(views, calibs, gap=10.0, part_name="Test Part")
    assert "2\n{}\n".format(TITLE_LAYER) in text
    assert "\n1\nTEST PART\n" in text
    assert "PROJECTION: FIRST ANGLE" in text
    assert "UNITS: MM" in text


def test_assemble_adds_overall_dimensions_from_measured_extents():
    """Dimension values come from the kernel bbox; witnesses from the views."""
    views = {"front": _line(0.0, 0.0, -50.0, 100.0)}
    calibs = {"front": {"X": [0.0, 10.0], "Y": None, "Z": [-10.0, 0.0]}}
    model_bbox = {"X": [0.0, 575.0], "Y": [0.0, 560.0], "Z": [0.0, 869.0]}
    text = assemble_dxf(views, calibs, gap=10.0, model_bbox=model_bbox)
    assert "2\n{}\n".format(DIM_LAYER) in text
    assert "\n1\n575.0\n" in text  # width text is the measured X extent
    assert "\n1\n869.0\n" in text  # height text is the measured Z extent


def test_assemble_without_a_model_bbox_skips_dimensions():
    """No measured extents means no dimension layer rather than estimates."""
    views = {"front": _line(0.0, 0.0, -50.0, 100.0)}
    calibs = {"front": {"X": [0.0, 10.0], "Y": None, "Z": [-10.0, 0.0]}}
    text = assemble_dxf(views, calibs, gap=10.0, model_bbox=None)
    assert "2\n{}\n".format(DIM_LAYER) not in text


def test_assemble_opt_out_removes_the_dimension_layer():
    """--no-dims produces the bare projection sheet."""
    views = {"front": _line(0.0, 0.0, -50.0, 100.0)}
    calibs = {"front": {"X": [0.0, 10.0], "Y": None, "Z": [-10.0, 0.0]}}
    model_bbox = {"X": [0.0, 575.0], "Y": [0.0, 560.0], "Z": [0.0, 869.0]}
    text = assemble_dxf(views, calibs, gap=10.0, model_bbox=model_bbox, dimensions=False)
    assert "2\n{}\n".format(DIM_LAYER) not in text
    assert "TEXT" not in text


def test_parts_batch_rejects_an_empty_folder(tmp_path):
    """A folder with no STEP files is a clear error, not an empty pass."""
    with pytest.raises(ConversionError, match="no STEP files"):
        step_parts_to_dxf(tmp_path)


def test_parts_batch_writes_one_dxf_per_step(tmp_path, monkeypatch):
    """Each part STEP becomes <stem>.dxf; the batch returns every path."""
    parts = tmp_path / "parts"
    parts.mkdir()
    for stem in ("Leg_Front_Left", "Seat_Pan_Deck"):
        (parts / f"{stem}.step").write_text("ISO-10303-21;", encoding="utf-8")
    calls: list[str] = []

    def fake_step_to_dxf(src, dst, **kwargs):
        calls.append(Path(src).stem)
        Path(dst).write_text("dxf", encoding="utf-8")
        return Path(dst)

    monkeypatch.setattr("convert.dxf.step_to_dxf", fake_step_to_dxf)
    out = tmp_path / "diagrams"
    written = step_parts_to_dxf(parts, out)
    assert [p.name for p in written] == ["Leg_Front_Left.dxf", "Seat_Pan_Deck.dxf"]
    assert calls == ["Leg_Front_Left", "Seat_Pan_Deck"]
    assert all(p.exists() for p in written)


def test_parts_batch_defaults_to_a_diagrams_sibling(tmp_path, monkeypatch):
    """Omitting the output lands DXFs in <parent>/diagrams/."""
    parts = tmp_path / "project" / "parts"
    parts.mkdir(parents=True)
    (parts / "a.step").write_text("ISO-10303-21;", encoding="utf-8")
    monkeypatch.setattr(
        "convert.dxf.step_to_dxf",
        lambda src, dst, **k: (Path(dst).write_text("dxf", encoding="utf-8"), Path(dst))[1],
    )
    (written,) = step_parts_to_dxf(parts)
    assert written.parent == tmp_path / "project" / "diagrams"


@pytest.mark.skipif(not has_dependency("fitz"), reason="PyMuPDF not installed")
def test_dxf_to_pdf_renders_the_sheet(tmp_path):
    """The PDF carries the views, the dimension numbers and the title block."""
    views = {"front": _line(0.0, 0.0, -50.0, 100.0)}
    calibs = {"front": {"X": [0.0, 10.0], "Y": None, "Z": [-10.0, 0.0]}}
    model_bbox = {"X": [0.0, 575.0], "Y": [0.0, 560.0], "Z": [0.0, 869.0]}
    src = tmp_path / "sheet.dxf"
    src.write_text(
        assemble_dxf(
            views, calibs, gap=10.0, model_bbox=model_bbox, part_name="PDF Part"
        ),
        encoding="utf-8",
    )
    out = dxf_to_pdf(src, tmp_path / "sheet.pdf")
    assert out.suffix == ".pdf"

    import fitz

    with fitz.open(str(out)) as doc:
        assert doc.page_count == 1
        text = doc[0].get_text()
        assert "575.0" in text  # the dimension number survives the render
        assert "PDF PART" in text  # the part label survives
