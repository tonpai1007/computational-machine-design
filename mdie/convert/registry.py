"""Format registry and optional-dependency probing.

MDIE ships converters that need nothing beyond the standard library, and
converters that lean on optional packages. Callers should treat a format as
unavailable rather than crashing when its dependency is missing -
:func:`missing_dependencies` reports what a given format needs.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field

DOCUMENT = "document"
SOLID = "solid"
SHEET = "sheet"


@dataclass(frozen=True)
class Format:
    """One convertible format."""

    name: str
    category: str
    extensions: tuple[str, ...]
    summary: str
    requires: tuple[str, ...] = ()
    reads: bool = False
    writes: bool = True


FORMATS: dict[str, Format] = {
    f.name: f for f in [
        Format("html", DOCUMENT, (".html", ".htm"),
               "Rich engineering report", ("Markdown",)),
        Format("md", DOCUMENT, (".md", ".markdown"),
               "Plain-text design report", ()),
        Format("docx", DOCUMENT, (".docx",),
               "Word document", ("docx", "bs4")),
        Format("pdf", DOCUMENT, (".pdf",),
               "Print-ready document", ("fitz",)),
        Format("txt", DOCUMENT, (".txt",), "Plain text", ()),

        Format("step", SOLID, (".step", ".stp"),
               "ISO 10303 AP214 solid", (), reads=True),
        Format("stl", SOLID, (".stl",),
               "Mesh for printing/visualisation", ("numpy",), reads=True),
        Format("3mf", SOLID, (".3mf",),
               "Compressed 3D Manufacturing mesh", ("numpy",), reads=True),
        Format("obj", SOLID, (".obj",),
               "Wavefront mesh interchange", (), reads=True),
        Format("iges", SOLID, (".igs", ".iges"),
               "Legacy surface exchange format", ()),
        Format("scad", SOLID, (".scad",),
               "OpenSCAD parametric source", ()),

        Format("svg", SHEET, (".svg",),
               "Vector drawing sheet", (), reads=True),
        Format("png", SHEET, (".png",),
               "Raster image of a sheet", ("fitz",)),
    ]
}

EXTENSION_TO_FORMAT: dict[str, str] = {
    ext: f.name for f in FORMATS.values() for ext in f.extensions
}

# Optional packages, probed lazily so a missing one degrades instead of raising.
_PROBE = {
    "docx": "docx",
    "bs4": "bs4",
    "Markdown": "markdown",
    "fitz": "fitz",
    "numpy": "numpy",
    "PIL": "PIL",
}


def has_dependency(package: str) -> bool:
    """True when an optional import is available in this interpreter."""
    module = _PROBE.get(package, package)
    try:
        importlib.import_module(module)
        return True
    except Exception:
        return False


def format_for_extension(path) -> str | None:
    """Map a filesystem path onto a known format name."""
    return EXTENSION_TO_FORMAT.get(path.suffix.lower())


def available_formats(category: str | None = None) -> list[str]:
    """Format names whose dependencies are importable right now."""
    out = []
    for name, f in FORMATS.items():
        if category and f.category != category:
            continue
        if all(has_dependency(p) for p in f.requires):
            out.append(name)
    return sorted(out)


def missing_dependencies() -> dict[str, list[str]]:
    """Map each unavailable format to the packages it is waiting on."""
    return {name: [p for p in f.requires if not has_dependency(p)]
            for name, f in FORMATS.items()
            if any(not has_dependency(p) for p in f.requires)}


def describe_formats() -> str:
    """Markdown summary of formats, grouped by category, for ``--list-formats``."""
    lines = ["# MDIE convertible formats", ""]
    for category, title in ((DOCUMENT, "Documents"), (SOLID, "CAD solids"), (SHEET, "Drawing sheets")):
        lines += [f"## {title}", ""]
        for name, f in sorted(FORMATS.items()):
            if f.category != category:
                continue
            mark = "" if all(has_dependency(p) for p in f.requires) else " *(dependency missing)*"
            lines.append(f"- **{name}** `{', '.join(f.extensions)}` - {f.summary}{mark}")
        lines.append("")
    return "\n".join(lines)