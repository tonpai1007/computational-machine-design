from __future__ import annotations

from pathlib import Path
from typing import Any


def _next_output_path(docx_path: str | Path, suffix: str) -> Path:
    path = Path(docx_path)
    return path.with_name(f"{path.stem}{suffix}{path.suffix}")


def _normalize_heading(text: str) -> str:
    return " ".join(text.strip().split()).lower()


def insert_report_figure(
    docx_path: str | Path,
    image_path: str | Path,
    caption: str | None = None,
    section_heading: str | None = None,
    width: float | int | Any = 180,
) -> Path:
    """Insert an image into a DOCX report, optionally relative to a named section."""
    import docx as python_docx

    source = Path(docx_path)
    image = Path(image_path)
    if not source.exists():
        raise FileNotFoundError(f"Word document not found: {source}")
    if not image.exists():
        raise FileNotFoundError(f"Image not found: {image}")

    document = python_docx.Document(str(source))
    insert_at = len(document.paragraphs)

    if section_heading:
        target = _normalize_heading(section_heading)
        for index, para in enumerate(document.paragraphs):
            if _normalize_heading(para.text) == target:
                insert_at = index + 1
                while insert_at < len(document.paragraphs):
                    next_para = document.paragraphs[insert_at]
                    if next_para.style is not None and next_para.style.name.lower().startswith("heading"):
                        break
                    insert_at += 1
                break

    paragraph = document.paragraphs[insert_at] if insert_at < len(document.paragraphs) else None
    if paragraph is None:
        paragraph = document.add_paragraph()
    else:
        paragraph = document.insert_paragraph_before("", paragraph)

    run = paragraph.add_run()
    run.add_picture(str(image), width=_docx_picture_width(width))

    if caption:
        document.add_paragraph(caption, style="Caption")

    document.save(str(source))
    return source


def update_report_caption(
    docx_path: str | Path,
    old_caption: str,
    new_caption: str,
) -> Path:
    """Update an existing caption paragraph in-place within a Word document."""
    import docx as python_docx

    source = Path(docx_path)
    if not source.exists():
        raise FileNotFoundError(f"Word document not found: {source}")

    document = python_docx.Document(str(source))
    updated = False
    for para in document.paragraphs:
        text = para.text.strip()
        if text == old_caption or text.lower() == old_caption.lower():
            para.text = new_caption
            updated = True
            break

    if not updated:
        for para in document.paragraphs:
            text = para.text.strip()
            if old_caption.lower() in text.lower():
                para.text = text.replace(old_caption, new_caption)
                updated = True
                break

    if not updated:
        document.add_paragraph(new_caption, style="Caption")

    document.save(str(source))
    return source


def _resolve_embeddable_asset(path: Path) -> Path:
    """Return a Word-compatible image path for an existing asset."""
    lower = path.suffix.lower()
    if lower in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff"}:
        return path
    if lower == ".svg":
        from convert.sheets import svg_to_png

        target = path.parent / f"{path.stem}_docx_render.png"
        if not target.exists():
            svg_to_png(path, target, dpi=220)
        return target
    return path


def embed_project_report_assets(
    docx_path: str | Path,
    asset_dirs: str | Path | list[str | Path],
    section_heading: str | None = None,
    width: float | int | Any = 180,
) -> Path:
    """Insert all renderable assets from project directories into the DOCX report.

    The assets are inserted in a stable order: project directories first, then file names.
    SVGs are converted to PNGs on the fly so Word can embed them.
    """
    import docx as python_docx

    source = Path(docx_path)
    if not source.exists():
        raise FileNotFoundError(f"Word document not found: {source}")

    if isinstance(asset_dirs, (str, Path)):
        asset_dirs = [asset_dirs]

    asset_paths: list[Path] = []
    for asset_dir in asset_dirs:
        directory = Path(asset_dir)
        if not directory.exists():
            continue
        for candidate in sorted(directory.iterdir(), key=lambda p: p.name.lower()):
            if candidate.is_file() and candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".svg"}:
                asset_paths.append(candidate)

    if not asset_paths:
        return source

    document = python_docx.Document(str(source))
    insert_at = len(document.paragraphs)
    if section_heading:
        target = _normalize_heading(section_heading)
        for index, para in enumerate(document.paragraphs):
            if _normalize_heading(para.text) == target:
                insert_at = index + 1
                while insert_at < len(document.paragraphs):
                    next_para = document.paragraphs[insert_at]
                    if next_para.style is not None and next_para.style.name.lower().startswith("heading"):
                        break
                    insert_at += 1
                break

    for idx, asset_path in enumerate(asset_paths, start=1):
        prepared = _resolve_embeddable_asset(asset_path)
        if not prepared.exists():
            continue
        insert_paragraph = document.paragraphs[insert_at] if insert_at < len(document.paragraphs) else None
        if insert_paragraph is None:
            insert_paragraph = document.add_paragraph()
            insert_at = len(document.paragraphs) - 1
        else:
            insert_paragraph = insert_paragraph.insert_paragraph_before("")
            insert_at += 1

        run = insert_paragraph.add_run()
        run.add_picture(str(prepared), width=_docx_picture_width(width))
        caption = f"Figure {idx}: {prepared.stem.replace('_', ' ').replace('-', ' ')}"
        document.add_paragraph(caption, style="Caption")

    document.save(str(source))
    return source


def _docx_picture_width(width: float | int | Any) -> Any:
    """Convert a simple width to python-docx's expected length type."""
    from docx.shared import Inches

    if width is None:
        return None
    if isinstance(width, (int, float)):
        return Inches(float(width) / 96)
    return width
