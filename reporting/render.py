"""Jinja2 rendering for report specifications.

Templates own layout and numeric precision; specs own the values. Every
numeric filter here is a pure formatter -- none of them derive, round-trip or
reinterpret an engineering quantity, so the value printed is always the value
the solver produced.

Autoescaping is on. Specs therefore store raw text (material names, AI-written
narrative, student names) and the template layer is the single place that
turns it into HTML-safe output.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_TEMPLATE_ROOT = Path(__file__).resolve().parent / "templates"


def _fixed(decimals: int):
    """Format a float with a fixed number of decimal places."""

    def formatter(value: float) -> str:
        return f"{float(value):.{decimals}f}"

    return formatter


def _scientific(decimals: int):
    def formatter(value: float) -> str:
        return f"{float(value):.{decimals}e}"

    return formatter


def _general(value: float) -> str:
    return f"{float(value):g}"


def build_environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_ROOT)),
        autoescape=select_autoescape(default=True),
        undefined=StrictUndefined,
        trim_blocks=False,
        lstrip_blocks=False,
        keep_trailing_newline=True,
    )
    for decimals in range(6):
        env.filters[f"f{decimals}"] = _fixed(decimals)
    env.filters["sci"] = _scientific(3)
    env.filters["sci4"] = _scientific(4)
    env.filters["g"] = _general
    return env


_ENV = build_environment()


def render(template_name: str, spec: object) -> str:
    """Render ``spec`` through ``template_name`` (relative to ``templates/``)."""
    return _ENV.get_template(template_name).render(spec=spec)
