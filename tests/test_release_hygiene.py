"""Release-hygiene guards.

These tests pin facts that must stay true for a shippable release: the
distributed version is single-sourced and consistent, the licence declared in
the packaging metadata is actually present, and the removed web surface has not
crept back into the core dependency set.
"""

from pathlib import Path

import core

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_text() -> str:
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_version_matches_pyproject():
    """``core.__version__`` and the packaged version must not drift apart."""
    text = _pyproject_text()
    line = next(ln for ln in text.splitlines() if ln.startswith("version ="))
    packaged = line.split("=", 1)[1].strip().strip('"').strip("'")
    assert packaged == core.__version__, (
        f"version drift: pyproject={packaged!r} core={core.__version__!r}"
    )


def test_license_file_exists_and_is_mit():
    license_path = ROOT / "LICENSE"
    assert license_path.exists(), "LICENSE file is missing"
    text = license_path.read_text(encoding="utf-8")
    assert "MIT License" in text
    assert 'license = { text = "MIT" }' in _pyproject_text()


def test_web_surface_removed():
    """The CLI-first tool must not ship the optional FastAPI surface."""
    assert not (ROOT / "web").exists(), "web/ should have been removed"


def test_core_dependencies_exclude_web_stack():
    text = _pyproject_text()
    deps_block = text.split("[project.optional-dependencies]")[0]
    for banned in ("fastapi", "uvicorn"):
        assert banned not in deps_block, f"{banned} must not be a core dependency"
