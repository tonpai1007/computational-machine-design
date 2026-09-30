"""Drawing-sheet conversion: SVG to PDF/PNG, and many sheets into one PDF.

PyMuPDF reads SVG directly, so rasterising or printing a sheet needs no
external renderer (no headless Chrome, no ImageMagick).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def svg_to_pdf(src: Path, dst: Path) -> Path:
    """Write a single SVG sheet as a vector PDF."""
    import fitz

    dst.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(str(src)) as doc:
        dst.write_bytes(doc.convert_to_pdf())
    return dst


def svg_to_png(src: Path, dst: Path, dpi: int = 200) -> Path:
    """Rasterise a single SVG sheet to PNG at ``dpi``."""
    import fitz

    dst.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(str(src)) as doc:
        pixmap = doc[0].get_pixmap(dpi=dpi)
        pixmap.save(str(dst))
    return dst


def sheets_to_pdf(srcs: Iterable[Path], dst: Path,
                  sort: bool = True) -> Path:
    """Merge many SVG sheets into a single multi-page PDF.

    Each sheet becomes one page at its own native size, so A3 and A4 sheets
    coexist in the same document without being rescaled.
    """
    import fitz

    paths = [Path(s) for s in srcs]
    if sort:
        paths.sort(key=lambda p: p.name.lower())
    if not paths:
        raise ValueError("no sheets to convert")

    dst.parent.mkdir(parents=True, exist_ok=True)
    out = fitz.open()
    for path in paths:
        # A sheet opened from SVG is a layout document, not a PDF, so it must be
        # converted before it can be inserted into the output.
        with fitz.open(str(path)) as sheet:
            as_pdf = sheet.convert_to_pdf()
        with fitz.open("pdf", as_pdf) as page_doc:
            out.insert_pdf(page_doc)
    out.save(str(dst), deflate=True)
    out.close()
    return dst


def sheets_to_png(srcs: Iterable[Path], out_dir: Path, dpi: int = 200) -> list[Path]:
    """Rasterise many sheets into ``out_dir``, returning the written PNGs."""
    written: list[Path] = []
    for src in sorted(Path(s) for s in srcs):
        dst = Path(out_dir) / f"{src.stem}.png"
        written.append(svg_to_png(src, dst, dpi=dpi))
    return written