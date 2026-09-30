"""MDIE file converter.

One entry point, :func:`convert_file`, covering documents, CAD solids and
drawing sheets::

    mdie convert report.html --to docx
    mdie convert notes.md      --to pdf
    mdie convert part.step     --to stl
    mdie convert part.stl      --to 3mf
    mdie convert sheet.svg     --to png --dpi 300
    mdie convert Project/chair/drawings --to pdf     # merges every sheet

Documents (Markdown/HTML/DOCX/PDF/TXT) are translated through a common block
model, so any source/target pair works. Mesh formats (STL/OBJ/3MF) convert in
pure Python. B-rep formats (STEP/IGES) need FreeCAD - see :mod:`mdie.convert.solids`.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from mdie.convert.documents import (
    _RENDERERS,
    blocks_from_source,
    blocks_to_docx,
    blocks_to_html,
    blocks_to_markdown,
    blocks_to_pdf,
    blocks_to_text,
)
from mdie.convert.registry import (
    DOCUMENT,
    EXTENSION_TO_FORMAT,
    FORMATS,
    SHEET,
    SOLID,
    available_formats,
    describe_formats,
    format_for_extension,
    missing_dependencies,
)
from mdie.convert.sheets import sheets_to_pdf, sheets_to_png, svg_to_pdf, svg_to_png
from mdie.convert.solids import (
    ConversionError,
    convert_mesh,
    convert_via_kernel,
    describe_mesh,
    find_kernel,
)

__all__ = [
    "convert_file",
    "available_formats",
    "missing_dependencies",
    "describe_formats",
    "ConversionError",
]

_DOC_RENDERERS = {
    "md": blocks_to_markdown,
    "html": blocks_to_html,
    "txt": blocks_to_text,
    "docx": blocks_to_docx,
    "pdf": blocks_to_pdf,
}


def convert_file(source: str | Path, target_format: str | None = None,
                 output_path: str | Path | None = None,
                 use_ai: bool = False, dpi: int = 200,
                 timeout: int = 300) -> Path:
    """Convert ``source`` into ``target_format`` and return the written path.

    ``target_format`` may be omitted when ``output_path`` carries the
    extension. A directory source is treated as a set of drawing sheets and
    merged into one document.
    """
    src = Path(source)
    if not src.exists():
        raise ConversionError(f"input not found: {src}")

    if src.is_dir():
        return _convert_sheets(src, target_format, output_path, dpi)

    src_format = format_for_extension(src)
    if src_format is None:
        raise ConversionError(
            f"unrecognised input format for {src.name}; "
            f"known extensions: {', '.join(sorted(EXTENSION_TO_FORMAT))}")

    fmt = target_format
    if fmt is None:
        if output_path is None:
            raise ConversionError("specify a target format or an output path")
        fmt = format_for_extension(Path(output_path))
        if fmt is None:
            raise ConversionError(f"cannot infer target format from {output_path}")

    fmt = fmt.lower().lstrip(".")
    if fmt not in FORMATS:
        raise ConversionError(f"unknown target format '{fmt}'")

    dst = Path(output_path) if output_path else src.with_suffix("." + fmt)

    if src_format == "svg":
        if fmt == "pdf":
            return svg_to_pdf(src, dst)
        if fmt == "png":
            return svg_to_png(src, dst, dpi=dpi)
        raise ConversionError(f"cannot convert an SVG sheet to '{fmt}'")

    if FORMATS[fmt].category == DOCUMENT:
        return _convert_document(src, src_format, fmt, dst, use_ai)

    if FORMATS[src_format].category == SOLID and FORMATS[fmt].category == SOLID:
        return _convert_solid(src, src_format, dst, fmt, timeout)

    raise ConversionError(f"no conversion path from '{src_format}' to '{fmt}'")


def _convert_document(src: Path, src_format: str, fmt: str,
                      dst: Path, use_ai: bool) -> Path:
    # The learning-tools bridge adds an AI peer-review pass, but it is an
    # optional external install. Fall back to the in-repo renderer rather than
    # failing - but only for its absence, so real bridge errors still surface.
    if use_ai and fmt == "docx" and src_format == "html":
        from mdie.convert import docx_bridge

        if docx_bridge.is_available():
            result = docx_bridge.HTMLToDocxConverter.convert(
                str(src), output_docx_path=str(dst), enable_ai=True)
            return Path(result)
        warnings.warn(
            "AI peer-review pass skipped: the learning-tools DOCX converter is "
            "not installed. Set LEARNING_TOOLS_PATH to enable it.",
            RuntimeWarning, stacklevel=2)

    blocks = blocks_from_source(src, src_format)

    # Markdown/HTML/TXT renderers return a string; the rest write their own file.
    if fmt == "docx":
        return blocks_to_docx(blocks, dst, title=src.stem)
    if fmt == "pdf":
        return blocks_to_pdf(blocks, dst, title=src.stem)

    text = _DOC_RENDERERS[fmt](blocks)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    return dst


def _convert_solid(src: Path, src_format: str, dst: Path, fmt: str,
                   timeout: int = 300) -> Path:
    from mdie.convert.solids import KERNEL_FORMATS, MESH_FORMATS

    if src_format in MESH_FORMATS and fmt in MESH_FORMATS:
        return convert_mesh(src, src_format, dst, fmt)
    if src_format in KERNEL_FORMATS:
        return convert_via_kernel(src, dst, fmt, timeout=timeout)
    raise ConversionError(f"no solid conversion path from '{src_format}' to '{fmt}'")


def _convert_sheets(folder: Path, target_format: str | None,
                    output_path: str | Path | None, dpi: int) -> Path:
    sheets = sorted([*folder.glob("*.svg"), *folder.glob("*.html")])
    if not sheets:
        raise ConversionError(f"no drawing sheets found in {folder}")

    fmt = (target_format or format_for_extension(Path(output_path or "")) or "pdf").lower()
    dst = Path(output_path) if output_path else folder / f"{folder.name}.{fmt}"

    if fmt == "pdf":
        if len(sheets) == 1:
            return svg_to_pdf(sheets[0], dst) if sheets[0].suffix == ".svg" \
                else blocks_to_pdf(blocks_from_source(sheets[0], "html"), dst, title=folder.name)
        return sheets_to_pdf([s for s in sheets if s.suffix == ".svg"], dst)

    if fmt == "png":
        return sheets_to_png(sheets, dst.parent, dpi=dpi)[0]

    raise ConversionError(f"cannot merge sheets into '{fmt}'")