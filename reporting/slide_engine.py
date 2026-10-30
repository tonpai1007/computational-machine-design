"""Slide deck renderer.

Turns an AI-designed SlideSpec into a self-contained, styled HTML slide deck
using the Jinja2 template in reporting/templates/slide/.

Referenced images are copied next to the output HTML so relative paths work
regardless of where the deck is opened.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ai.slide_designer import SlideSpec

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "slide"


def _build_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(default=True),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )


def _collect_image_paths(spec: SlideSpec, project_root: Path) -> list[Path]:
    """Return every image path referenced by the spec, resolved against project_root."""
    paths: list[Path] = []
    for slide in spec.slides:
        for img in slide.get("images", []) or []:
            src = img.get("src")
            if not src:
                continue
            candidate = Path(src)
            if not candidate.is_absolute():
                candidate = project_root / candidate
            if candidate.exists():
                paths.append(candidate)
    return paths


def _copy_images(image_paths: list[Path], dest_dir: Path) -> dict[str, str]:
    """Copy referenced images into dest_dir, returning a src -> relpath map."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    mapping: dict[str, str] = {}
    for src in image_paths:
        dest = dest_dir / src.name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        mapping[str(src)] = dest.name
    return mapping


def render_slide_deck(spec: SlideSpec, output_path: Path, project_root: Path | None = None) -> Path:
    """Render spec to a self-contained HTML file, copying referenced images alongside."""
    env = _build_env()
    template = env.get_template("deck.html.j2")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    project_root = project_root or Path.cwd()
    image_paths = _collect_image_paths(spec, project_root)
    image_map = _copy_images(image_paths, output_path.parent)

    # Rewrite slide image srcs to the copied filenames
    for slide in spec.slides:
        for img in slide.get("images", []) or []:
            original = img.get("src")
            if original and original in image_map:
                img["src"] = image_map[original]

    html = template.render(spec=spec)
    output_path.write_text(html, encoding="utf-8")
    return output_path


__all__ = ["render_slide_deck"]
