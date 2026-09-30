"""Optional bridge to the learning-tools DOCX converter.

The richest HTML-to-DOCX implementation (and the only one with the AI
peer-review pass) lives in the separate ``learning-tools`` repository:

    c:\\codework\\learning-tools\\lt\\docx_converter.py

It is an *optional* integration, so this module must never make an import
fail. :func:`is_available` reports whether the bridge is usable, and
:data:`HTMLToDocxConverter` stays importable either way - it raises
:class:`LearningToolsUnavailable` on use when the dependency is missing.
Callers that just need a Word file should use the native renderer in
:mod:`mdie.convert.documents` instead.

Point ``LEARNING_TOOLS_PATH`` at the checkout to override discovery.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: Candidate locations for the learning-tools checkout, most specific first.
_CANDIDATES = (
    os.environ.get("LEARNING_TOOLS_PATH"),
    r"c:\codework\learning-tools",
    str(Path.home() / "codework" / "learning-tools"),
)


def learning_tools_path() -> Path | None:
    """Locate the learning-tools checkout, or ``None`` if it is not present."""
    for candidate in _CANDIDATES:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        if (path / "lt" / "docx_converter.py").exists():
            return path
    return None


class LearningToolsUnavailable(RuntimeError):
    """Raised when the optional learning-tools bridge is used but missing."""


def _load():
    """Import the real converter, or return ``None`` if it is unavailable."""
    path = learning_tools_path()
    if path is None:
        return None
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    try:
        from lt.docx_converter import HTMLToDocxConverter
    except Exception:
        return None
    return HTMLToDocxConverter


def is_available() -> bool:
    """True when the learning-tools DOCX converter can be used."""
    return _load() is not None


class _UnavailableConverter:
    """Stand-in that fails with an actionable message instead of at import."""

    @staticmethod
    def convert(*_args, **_kwargs):
        raise LearningToolsUnavailable(
            "The learning-tools DOCX converter is not installed. Set "
            "LEARNING_TOOLS_PATH to its checkout, or convert without the AI "
            "pass to use MDIE's built-in renderer.")


#: The real converter when present, otherwise an in-repo stand-in.
HTMLToDocxConverter = _load() or _UnavailableConverter

__all__ = [
    "HTMLToDocxConverter",
    "LearningToolsUnavailable",
    "is_available",
    "learning_tools_path",
]
