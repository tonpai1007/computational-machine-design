"""Architecture guard: the reporting layer formats, it does not compute.

Reports may import solver *result* models (and the solvers they drive), but
they must never import the fatigue/buckling/stress formula modules to rebuild a
number the solver already produced. That second copy is how the dossier and the
data sheet drifted apart before.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

_REPORTING = Path(__file__).resolve().parents[1] / "reporting"
_FORBIDDEN = ("physics.fatigue", "physics.buckling", "physics.stress")


def _imports(path: Path) -> Iterator[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                yield module
            for alias in node.names:
                yield f"{module}.{alias.name}" if module else alias.name


@pytest.mark.parametrize(
    "path", sorted(_REPORTING.glob("*.py")), ids=lambda p: p.name
)
def test_reporting_never_imports_physics_formula_modules(path: Path):
    imported = set(_imports(path))
    for forbidden in _FORBIDDEN:
        offenders = {
            name
            for name in imported
            if name == forbidden or name.startswith(f"{forbidden}.")
        }
        assert not offenders, (
            f"{path.name} imports {sorted(offenders)}; read the solver result "
            "model instead of recomputing the check"
        )
