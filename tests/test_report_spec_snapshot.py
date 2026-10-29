"""Golden snapshot for the v2 dossier's plain-data spec.

The rendered HTML is guarded by ``test_assignment_report_v2``; this module pins
the *values* before the template formats them. A layout change therefore cannot
move an engineering number, and a solver change shows up as a readable JSON
diff instead of a string-grep failure.

Regenerate after an intentional value change:

    $env:MDIE_UPDATE_GOLDEN = "1"
    .venv\\Scripts\\python.exe -m pytest tests/test_report_spec_snapshot.py -q
"""

from __future__ import annotations

import difflib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from core.frame_model import FrameDesignModel
from physics.frame_physics import FramePhysicsSolver
from reporting.render import render
from reporting.spec import AcademicV2Spec, build_academic_v2_spec

_GOLDEN = Path(__file__).resolve().parent / "golden" / "academic_v2_spec.json"

#: Keys whose values are legitimately text. Everything else must be a number,
#: a bool, ``None`` or a container -- never a pre-formatted numeric string.
_TEXT_KEYS = {
    "title",
    "design_name",
    "name",
    "student_id",
    "description",
    "intro_paragraphs",
    "preview_image",
    "cad_caption",
}


def _build(
    geometry_updates: dict[str, Any] | None = None,
    students: list[dict[str, str]] | None = None,
) -> AcademicV2Spec:
    model = FrameDesignModel()
    if geometry_updates:
        model = FrameDesignModel(
            geometry=model.geometry.model_copy(update=geometry_updates)
        )
    result = FramePhysicsSolver.solve(model)
    return build_academic_v2_spec(model, result, students=students)


def _specs() -> dict[str, AcademicV2Spec]:
    return {
        "default": _build(),
        "students": _build(
            students=[{"name": "Somchai & Co <Test>", "id": "6501234"}]
        ),
        "bare": _build({"has_arms": False, "has_stretchers": False}),
        "no_stretcher": _build({"has_stretchers": False}),
    }


def _normalise(node: Any) -> Any:
    """Round floats to 12 significant digits.

    The golden file must survive a different C library's last-bit ``sqrt``/
    ``log10`` result; 12 significant digits still exposes every engineering
    change while hiding that noise.
    """
    if isinstance(node, float):
        return float(f"{node:.12g}")
    if isinstance(node, dict):
        return {key: _normalise(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_normalise(value) for value in node]
    return node


def _dump(specs: dict[str, AcademicV2Spec]) -> str:
    payload = {
        name: _normalise(spec.model_dump(mode="json")) for name, spec in specs.items()
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def test_academic_v2_spec_matches_golden():
    actual = _dump(_specs())
    if os.environ.get("MDIE_UPDATE_GOLDEN"):
        _GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        _GOLDEN.write_text(actual, encoding="utf-8")
        pytest.skip("golden snapshot regenerated")

    expected = _GOLDEN.read_text(encoding="utf-8")
    if actual != expected:
        diff = "\n".join(
            difflib.unified_diff(
                expected.splitlines(),
                actual.splitlines(),
                fromfile="golden/academic_v2_spec.json",
                tofile="actual",
                lineterm="",
            )
        )
        pytest.fail(f"spec values drifted:\n{diff}")


def _walk(node: Any, path: str = ""):
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            yield from _walk(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")
    else:
        yield path, node


def test_spec_stores_values_not_formatted_strings():
    """Formatting belongs to the template; the spec must stay numeric."""
    for name, spec in _specs().items():
        for path, value in _walk(spec.model_dump(mode="json")):
            if not isinstance(value, str):
                continue
            key = path.rsplit(".", 1)[-1].split("[")[0]
            assert key in _TEXT_KEYS, (
                f"{name}.{path} is a string ({value!r}); store the raw number "
                "and format it in the template"
            )


def test_preview_image_is_only_kept_when_the_file_exists(tmp_path):
    model = FrameDesignModel()
    result = FramePhysicsSolver.solve(model)

    missing = build_academic_v2_spec(
        model, result, preview_image=str(tmp_path / "missing.png")
    )
    assert missing.preview_image is None

    image = tmp_path / "preview.png"
    image.write_bytes(b"not-a-real-png")
    present = build_academic_v2_spec(model, result, preview_image=str(image))
    assert present.preview_image == str(image)
    assert f'src="{image}"' in render("academic_v2/report.html.j2", present)
