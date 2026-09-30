"""Tests for the convert file converter."""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path

import pytest

from convert import convert_file
from convert.documents import (
    blocks_from_docx,
    blocks_from_html,
    blocks_from_markdown,
    blocks_from_source,
    blocks_to_html,
    blocks_to_markdown,
)
from convert.registry import (
    available_formats,
    describe_formats,
    format_for_extension,
    missing_dependencies,
)
from convert.sheets import sheets_to_pdf, svg_to_pdf, svg_to_png
from convert.solids import (
    ConversionError,
    convert_mesh,
    describe_mesh,
    mesh_bounds,
    read_3mf,
    read_obj,
    read_stl,
    triangle_normal,
    write_3mf,
    write_obj,
    write_stl,
)

MD_SAMPLE = """# Title

Intro paragraph with **bold** text.

## Section

- first bullet
- second bullet

1. step one
2. step two

| Part | Mass |
| --- | --- |
| Leg | 1.2 |
| Rail | 0.8 |

```python
x = 1
```

> a quoted note
"""

SAMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100">'
    '<rect x="10" y="10" width="180" height="80" fill="none" stroke="black" stroke-width="2"/>'
    '<circle cx="100" cy="50" r="20" fill="black"/>'
    '<text x="100" y="95" font-size="10" text-anchor="middle">SHEET</text>'
    '</svg>'
)


# ------------------------------------------------------------------ registry

def test_every_declared_format_resolves_back_from_its_extension():
    assert format_for_extension(Path("a.step")) == "step"
    assert format_for_extension(Path("a.STL")) == "stl"
    assert format_for_extension(Path("a.htm")) == "html"
    assert format_for_extension(Path("a.3mf")) == "3mf"
    assert format_for_extension(Path("a.unknown")) is None


def test_available_formats_excludes_formats_with_missing_dependencies():
    available = available_formats()
    assert "md" in available
    for name in available:
        assert name not in missing_dependencies()


def test_describe_formats_lists_every_category():
    text = describe_formats()
    for heading in ("Documents", "CAD solids", "Drawing sheets"):
        assert heading in text
    assert "**stl**" in text


# ----------------------------------------------------------------- documents

def test_markdown_parses_every_block_kind():
    kinds = [b[0] for b in blocks_from_markdown(MD_SAMPLE)]
    assert "heading" in kinds and "para" in kinds and "bullet" in kinds
    assert "numbered" in kinds and "table" in kinds and "code" in kinds and "quote" in kinds


def test_markdown_headings_keep_their_level():
    headings = [b for b in blocks_from_markdown(MD_SAMPLE) if b[0] == "heading"]
    assert (headings[0][1], headings[0][2]) == (1, "Title")
    assert (headings[1][1], headings[1][2]) == (2, "Section")


def test_markdown_table_rows_are_normalised_to_equal_width():
    table = next(b for b in blocks_from_markdown(MD_SAMPLE) if b[0] == "table")
    rows = table[1]
    assert rows[0] == ["Part", "Mass"]
    assert rows[1] == ["Leg", "1.2"]
    assert len({len(r) for r in rows}) == 1


def test_bullets_and_numbers_are_not_confused():
    bullets = [b[1] for b in blocks_from_markdown(MD_SAMPLE) if b[0] == "bullet"]
    numbers = [b[1] for b in blocks_from_markdown(MD_SAMPLE) if b[0] == "numbered"]
    assert bullets == ["first bullet", "second bullet"]
    assert numbers == ["step one", "step two"]


def test_html_parser_recovers_headings_lists_and_tables():
    html = blocks_to_html(blocks_from_markdown(MD_SAMPLE))
    kinds = [b[0] for b in blocks_from_html(html)]
    assert "heading" in kinds and "bullet" in kinds and "table" in kinds
    table = next(b for b in blocks_from_html(html) if b[0] == "table")
    assert table[1][0] == ["Part", "Mass"]


def test_markdown_roundtrips_through_html():
    original = [b for b in blocks_from_markdown(MD_SAMPLE) if b[0] != "code"]
    recovered = [b for b in blocks_from_html(blocks_to_html(original)) if b[0] != "code"]
    assert len(original) == len(recovered)
    assert [b[0] for b in original] == [b[0] for b in recovered]
    assert blocks_to_markdown(original).count("| Leg | 1.2 |") == 1


def test_html_head_and_title_content_is_ignored():
    html = "<html><head><title>Sheet Title</title><style>p{}</style></head>" \
           "<body><p>body text</p></body></html>"
    blocks = blocks_from_html(html)
    assert [b for b in blocks if b[0] == "para"] == [("para", "body text")]


def test_code_fence_content_is_preserved_verbatim(tmp_path):
    src = tmp_path / "s.md"
    src.write_text(MD_SAMPLE, encoding="utf-8")
    md = blocks_to_markdown(blocks_from_source(src, "md"))
    assert "x = 1" in md


@pytest.mark.parametrize("fmt", ["md", "html", "txt", "docx", "pdf"])
def test_markdown_converts_to_every_document_format(tmp_path, fmt):
    src = tmp_path / "report.md"
    src.write_text(MD_SAMPLE, encoding="utf-8")
    dst = convert_file(src, target_format=fmt, output_path=tmp_path / f"report.{fmt}")
    assert dst.exists()
    assert dst.stat().st_size > 0


def test_html_converts_to_docx_and_reads_back(tmp_path):
    src = tmp_path / "report.html"
    src.write_text(blocks_to_html(blocks_from_markdown(MD_SAMPLE), "Report"), encoding="utf-8")
    dst = convert_file(src, target_format="docx", output_path=tmp_path / "report.docx")

    blocks = blocks_from_docx(dst)
    headings = [b for b in blocks if b[0] == "heading"]
    assert any(b[2] == "Section" for b in headings)
    assert any(b[0] == "bullet" and "first bullet" in b[1] for b in blocks)


def test_docx_converts_back_to_markdown(tmp_path):
    src = tmp_path / "report.md"
    src.write_text(MD_SAMPLE, encoding="utf-8")
    docx_path = convert_file(src, "docx", tmp_path / "report.docx")
    md = convert_file(docx_path, "md", tmp_path / "back.md")

    text = md.read_text(encoding="utf-8")
    assert "Section" in text
    assert "first bullet" in text


def test_target_format_is_inferred_from_the_output_suffix(tmp_path):
    src = tmp_path / "r.md"
    src.write_text("# hi", encoding="utf-8")
    dst = convert_file(src, output_path=tmp_path / "r.pdf")
    assert dst.suffix == ".pdf" and dst.exists()


def test_unknown_target_format_is_rejected(tmp_path):
    src = tmp_path / "r.md"
    src.write_text("# hi", encoding="utf-8")
    with pytest.raises(ConversionError, match="unknown target format"):
        convert_file(src, "dwg", tmp_path / "r.dwg")


def test_missing_input_is_rejected(tmp_path):
    with pytest.raises(ConversionError, match="input not found"):
        convert_file(tmp_path / "nope.md", "pdf")


def test_thai_text_survives_a_document_roundtrip(tmp_path):
    src = tmp_path / "th.md"
    src.write_text("# ขนาดเส้นผ่านศูนย์กลาง\n\nค่าที่คำนวณได้ 45 มม.\n", encoding="utf-8")
    dst = convert_file(src, "docx", tmp_path / "th.docx")
    assert any("45" in b[1] for b in blocks_from_docx(dst) if b[0] == "para")


# -------------------------------------------------------------------- sheets

@pytest.fixture
def sheet(tmp_path) -> Path:
    path = tmp_path / "Sheet.svg"
    path.write_text(SAMPLE_SVG, encoding="utf-8")
    return path


def test_svg_to_pdf_produces_one_page(sheet, tmp_path):
    out = svg_to_pdf(sheet, tmp_path / "sheet.pdf")
    import fitz

    with fitz.open(str(out)) as doc:
        assert doc.page_count == 1


def test_svg_to_png_honours_dpi(sheet, tmp_path):
    small = svg_to_png(sheet, tmp_path / "small.png", dpi=72)
    large = svg_to_png(sheet, tmp_path / "large.png", dpi=288)
    assert small.exists() and large.exists()
    assert large.stat().st_size > small.stat().st_size


def test_many_sheets_merge_into_one_pdf_in_name_order(tmp_path):
    paths = []
    for name in ("B_second", "A_first", "C_third"):
        p = tmp_path / f"{name}.svg"
        p.write_text(SAMPLE_SVG, encoding="utf-8")
        paths.append(p)

    out = sheets_to_pdf(paths, tmp_path / "merged.pdf")
    import fitz

    with fitz.open(str(out)) as doc:
        assert doc.page_count == 3


def test_converting_a_sheet_folder_produces_a_full_drawing_set(tmp_path):
    for name in ("Part_A", "Part_B", "Part_C"):
        (tmp_path / f"{name}.svg").write_text(SAMPLE_SVG, encoding="utf-8")

    out = convert_file(tmp_path, "pdf", tmp_path / "set.pdf")
    import fitz

    with fitz.open(str(out)) as doc:
        assert doc.page_count == 3


def test_empty_sheet_folder_is_reported(tmp_path):
    with pytest.raises(ConversionError, match="no drawing sheets"):
        convert_file(tmp_path, "pdf", tmp_path / "empty.pdf")


def test_svg_cannot_be_converted_to_a_solid(sheet, tmp_path):
    with pytest.raises(ConversionError):
        convert_file(sheet, "stl", tmp_path / "bad.stl")


# -------------------------------------------------------------------- solids

def _sample_tris():
    return [((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
            ((0.0, 0.0, 1.0), (1.0, 0.0, 1.0), (0.0, 1.0, 1.0))]


def test_binary_stl_roundtrips_triangles(tmp_path):
    path = write_stl(tmp_path / "m.stl", _sample_tris())
    assert path.read_bytes()[:6] != b"solid "
    assert len(read_stl(path)) == 2


def test_ascii_stl_roundtrips_triangles(tmp_path):
    path = write_stl(tmp_path / "m.stl", _sample_tris(), binary=False)
    assert path.read_text(encoding="utf-8").startswith("solid mdie")
    assert len(read_stl(path)) == 2


def test_triangle_normal_is_unit_length():
    n = triangle_normal(_sample_tris()[0])
    assert abs(sum(c * c for c in n) ** 0.5 - 1.0) < 1e-9


def test_mesh_bounds_report_the_extents():
    lo, hi = mesh_bounds(_sample_tris())
    assert lo == (0.0, 0.0, 0.0)
    assert hi == (1.0, 1.0, 1.0)


def test_obj_roundtrips_triangles(tmp_path):
    path = write_obj(tmp_path / "m.obj", _sample_tris())
    assert read_obj(path) == _sample_tris()


def test_3mf_roundtrips_triangles_and_is_a_valid_package(tmp_path):
    path = write_3mf(tmp_path / "m.3mf", _sample_tris())
    with zipfile.ZipFile(path) as zf:
        assert "3D/3dmodel.model" in zf.namelist()
    assert len(read_3mf(path)) == 2


@pytest.mark.parametrize("dst_format", ["stl", "obj", "3mf"])
def test_stl_converts_into_every_mesh_format(tmp_path, dst_format):
    src = write_stl(tmp_path / "m.stl", _sample_tris())
    out = convert_file(src, dst_format, tmp_path / f"m.{dst_format}")
    assert out.exists() and out.stat().st_size > 0


def test_mesh_conversion_preserves_the_number_of_triangles(tmp_path):
    src = write_stl(tmp_path / "m.stl", _sample_tris())
    out = convert_mesh(src, "stl", tmp_path / "m.3mf", "3mf")
    assert len(read_3mf(out)) == 2


def test_describe_mesh_reports_bounds(tmp_path):
    src = write_stl(tmp_path / "m.stl", _sample_tris())
    text = describe_mesh(src)
    assert "2 triangles" in text
    assert "1.000 x 1.000 x 1.000" in text


def test_step_without_a_kernel_raises_a_clear_error(tmp_path, monkeypatch):
    src = tmp_path / "part.step"
    src.write_text("ISO-10303-21;", encoding="utf-8")
    monkeypatch.setattr("convert.solids.find_kernel", lambda: None)
    with pytest.raises(ConversionError, match="geometry kernel"):
        convert_file(src, "stl", tmp_path / "part.stl")


# ------------------------------------------------------- external tool safety

def test_find_kernel_never_returns_the_gui_binary(monkeypatch):
    """Driving FreeCAD.exe from a script pops a window and hangs the caller."""
    from convert.solids import find_kernel

    monkeypatch.setattr("convert.solids.shutil.which",
                        lambda name: r"C:\FreeCAD\bin\freecadcmd.exe")
    assert "freecadcmd" in find_kernel().lower()

    monkeypatch.setattr("convert.solids.shutil.which", lambda name: None)
    monkeypatch.setattr("cli.viewers.find_cad_tools",
                        lambda: {"freecad": r"C:\FreeCAD\bin\FreeCAD.exe"})
    monkeypatch.setattr(Path, "exists", lambda self: False)
    assert find_kernel() is None


def test_scad_routes_to_openscad_not_freecad(tmp_path, monkeypatch):
    src = tmp_path / "part.scad"
    src.write_text("cube(1);", encoding="utf-8")
    monkeypatch.setattr("convert.solids.find_openscad", lambda: None)
    with pytest.raises(ConversionError, match="OpenSCAD"):
        convert_file(src, "stl", tmp_path / "part.stl")


def test_a_wedged_kernel_times_out_instead_of_hanging(tmp_path, monkeypatch):
    import subprocess as sp

    src = tmp_path / "part.step"
    src.write_text("ISO-10303-21;", encoding="utf-8")
    monkeypatch.setattr("convert.solids.find_kernel", lambda: "freecadcmd")
    monkeypatch.setattr("convert.solids.subprocess.run",
                        lambda *a, **k: (_ for _ in ()).throw(sp.TimeoutExpired("fc", 1)))
    with pytest.raises(ConversionError, match="did not finish"):
        convert_file(src, "stl", tmp_path / "part.stl", timeout=1)


def test_a_kernel_that_writes_nothing_reports_its_stderr(tmp_path, monkeypatch):
    import subprocess as sp

    src = tmp_path / "part.step"
    src.write_text("ISO-10303-21;", encoding="utf-8")
    monkeypatch.setattr("convert.solids.find_kernel", lambda: "freecadcmd")
    monkeypatch.setattr(
        "convert.solids.subprocess.run",
        lambda *a, **k: sp.CompletedProcess(a[0], 1, "", "shape not a solid"))
    with pytest.raises(ConversionError, match="shape not a solid"):
        convert_file(src, "stl", tmp_path / "part.stl")


def test_kernel_output_survives_the_temporary_directory(tmp_path, monkeypatch):
    """Regression: the result was copied out *after* the temp dir was deleted."""
    import subprocess as sp

    src = tmp_path / "part.step"
    src.write_text("ISO-10303-21;", encoding="utf-8")
    dst = tmp_path / "part.stl"
    monkeypatch.setattr("convert.solids.find_kernel", lambda: "freecadcmd")

    def fake_run(*a, **k):
        # Write the mesh to the path the script was told to use.
        Path(k["env"]["MDIE_DST"]).write_bytes(
            b"solid x\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\n"
            b"vertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid x\n")
        return sp.CompletedProcess(a[0], 0, "", "")

    monkeypatch.setattr("convert.solids.subprocess.run", fake_run)
    assert convert_file(src, "stl", dst) == dst
    assert dst.exists() and dst.stat().st_size > 0