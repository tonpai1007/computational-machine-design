"""The template layer only formats; it must never invent or reshape a value."""

import pytest
from jinja2 import UndefinedError

from reporting.render import build_environment


@pytest.mark.parametrize(
    ("filter_name", "value", "expected"),
    [
        ("f0", 1234.56, "1235"),
        ("f1", 1234.56, "1234.6"),
        ("f2", 1234.567, "1234.57"),
        ("f3", 1234.5678, "1234.568"),
        ("f4", 1234.56789, "1234.5679"),
        ("f5", 1234.567891, "1234.56789"),
        ("sci", 0.00123, "1.230e-03"),
        ("sci4", 0.00123, "1.2300e-03"),
        ("g", 0.0001, "0.0001"),
    ],
)
def test_numeric_filters_are_pure_formatters(filter_name, value, expected):
    env = build_environment()
    assert env.filters[filter_name](value) == expected


def test_autoescape_is_enabled():
    env = build_environment()
    rendered = env.from_string("{{ value }}").render(value="A & B <tag>")
    assert rendered == "A &amp; B &lt;tag&gt;"


def test_missing_spec_field_fails_loudly():
    env = build_environment()
    with pytest.raises(UndefinedError):
        env.from_string("{{ spec.absent }}").render(spec=object())
