"""
Structural validation for generated engineering reports.

This module checks the document that was actually emitted, not the model that
produced it. Every check below corresponds to a defect that reached a real
deliverable:

* a hardcoded material constant that ignored the selected alloy,
* a Markdown summary table whose rows had more cells than its header,
* a table of contents that pointed at a section which was never rendered,
* an unrendered f-string placeholder or a ``None`` / ``nan`` leak.

Nothing here recomputes engineering values. It only inspects markup, so it is
safe to run on any report tier without weakening the physics-authority rule.

CLI::

    python -m reporting.validate Project/chair/chair_report.html
    python -m reporting.validate Project/chair/academic_assignment_report.html --profile academic
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, TypedDict

Severity = Literal["error", "warning"]

#: Words that must never survive into a rendered deliverable. ``inf``/``nan``
#: are matched as whole words so ordinary prose ("information") is unaffected.
_SENTINELS = ("None", "nan", "NaN", "inf", "Infinity", "undefined", "Undefined")

#: Out-of-scope vocabulary for the closed-form reference profile. Kept in sync
#: with ``tests/test_chair_design_report.py``.
_REFERENCE_BANNED = (
    "FEA",
    "finite element",
    "ANSYS",
    "Abaqus",
    "von Mises",
    "stiffness matrix",
    "DOF",
    "mesh",
    "element analysis",
)

class _ProfileRules(TypedDict):
    """Content policy for one report profile."""

    required: tuple[str, ...]
    required_any: tuple[tuple[str, ...], ...]
    banned: tuple[str, ...]


_PROFILES: dict[str, _ProfileRules] = {
    "core": {
        "required": (),
        "required_any": (("PASS", "FAIL"),),
        "banned": (),
    },
    "academic": {
        "required": ("สารบัญ", "Table of Contents", "Sign-Off"),
        "required_any": (("PASS", "FAIL"),),
        "banned": (),
    },
    "academic_v2": {
        "required": ("Step 1",),
        "required_any": (("PASS", "FAIL"),),
        "banned": ("Tipping", "Finite Element", "FEA"),
    },
    "reference_closed_form": {
        "required": (),
        "required_any": (),
        "banned": _REFERENCE_BANNED,
    },
}


@dataclass(frozen=True)
class ReportIssue:
    """One structural problem found in a rendered report."""

    code: str
    message: str
    severity: Severity = "error"

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code}: {self.message}"


class _StructureParser(HTMLParser):
    """Collect the handful of structural facts the validator needs."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.anchor_targets: list[str] = []
        self.images: list[str] = []
        self.tables: list[dict[str, object]] = []
        self.heading_tags: list[str] = []
        self._table_stack: list[dict[str, object]] = []
        self._row_cells = 0
        self._row_had_th = False

    # -- tables ---------------------------------------------------------
    def _current_table(self) -> dict[str, object] | None:
        return self._table_stack[-1] if self._table_stack else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = dict(attrs)
        if attrs_d.get("id"):
            self.ids.append(attrs_d["id"] or "")
        if tag == "a" and (attrs_d.get("href") or "").startswith("#"):
            self.anchor_targets.append((attrs_d["href"] or "")[1:])
        if tag == "img" and attrs_d.get("src"):
            self.images.append(attrs_d["src"] or "")
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.heading_tags.append(tag)
        if tag == "table":
            table: dict[str, object] = {"header": None, "rows": []}
            self._table_stack.append(table)
            self.tables.append(table)
        elif tag == "tr":
            self._row_cells = 0
            self._row_had_th = False
        elif tag in ("th", "td"):
            try:
                span = int(attrs_d.get("colspan") or 1)
            except ValueError:
                span = 1
            self._row_cells += max(1, span)
            if tag == "th":
                self._row_had_th = True

    def handle_endtag(self, tag: str) -> None:
        table = self._current_table()
        if tag == "tr" and table is not None:
            rows = table["rows"]
            assert isinstance(rows, list)
            if self._row_had_th and table["header"] is None:
                table["header"] = self._row_cells
            else:
                rows.append(self._row_cells)
        elif tag == "table" and self._table_stack:
            self._table_stack.pop()


def _visible_text(document: str) -> str:
    """Strip style/script blocks and tags so sentinel checks see prose only."""
    text = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", " ", document, flags=re.S | re.I)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    return re.sub(r"<[^>]+>", " ", text)


def _profile_rules(profile: str) -> _ProfileRules:
    try:
        return _PROFILES[profile]
    except KeyError as exc:
        available = ", ".join(sorted(_PROFILES))
        raise ValueError(f"unknown report profile {profile!r}; choose one of: {available}") from exc


def validate_html(
    document: str,
    *,
    profile: str = "core",
    base_dir: Path | None = None,
) -> list[ReportIssue]:
    """Validate one rendered HTML report and return every issue found."""
    issues: list[ReportIssue] = []
    parser = _StructureParser()
    parser.feed(document)
    parser.close()

    # 1. Table shape: every body row must match its header's cell count.
    for table_no, table in enumerate(parser.tables, start=1):
        header = table["header"]
        rows = table["rows"]
        assert isinstance(rows, list)
        if header is None and rows:
            header = rows[0]
        for row_no, cells in enumerate(rows, start=1):
            if header is not None and cells != header:
                issues.append(
                    ReportIssue(
                        "table-shape",
                        f"table {table_no} row {row_no} has {cells} cells but the header has {header}",
                    )
                )

    # 2. Every in-page anchor must resolve to an element that exists.
    known_ids = set(parser.ids)
    for target in parser.anchor_targets:
        if target and target not in known_ids:
            issues.append(
                ReportIssue(
                    "broken-anchor",
                    f"link targets #{target}, but no element carries that id",
                )
            )

    # 3. Duplicate ids make anchors ambiguous.
    seen: set[str] = set()
    for element_id in parser.ids:
        if element_id in seen:
            issues.append(
                ReportIssue("duplicate-id", f"id {element_id!r} appears more than once")
            )
        seen.add(element_id)

    # 4. Unrendered placeholders and numeric sentinels.
    text = _visible_text(document)
    for sentinel in _SENTINELS:
        if re.search(rf"(?<![\w.]){re.escape(sentinel)}(?![\w.])", text):
            issues.append(
                ReportIssue(
                    "sentinel-leak",
                    f"rendered document contains the sentinel {sentinel!r}",
                )
            )
    placeholder = re.search(r"\{[A-Za-z_][A-Za-z0-9_]*\}", text)
    if placeholder:
        issues.append(
            ReportIssue(
                "unrendered-placeholder",
                f"unrendered template placeholder {placeholder.group(0)!r}",
            )
        )

    # 5. Profile policy: required and forbidden content.
    rules = _profile_rules(profile)
    lowered = text.lower()
    for marker in rules["required"]:
        if marker.lower() not in lowered:
            issues.append(
                ReportIssue(
                    "missing-section",
                    f"profile {profile!r} requires the marker {marker!r}",
                )
            )
    for alternatives in rules["required_any"]:
        if not any(alt.lower() in lowered for alt in alternatives):
            issues.append(
                ReportIssue(
                    "missing-verdict",
                    f"profile {profile!r} requires one of {alternatives!r}",
                )
            )
    for term in rules["banned"]:
        if term.lower() in lowered:
            issues.append(
                ReportIssue(
                    "out-of-scope-term",
                    f"profile {profile!r} forbids the term {term!r}",
                )
            )

    # 6. Local images must exist next to the report.
    if base_dir is not None:
        for src in parser.images:
            if re.match(r"^(https?:|data:|//)", src):
                continue
            candidate = (base_dir / src).resolve()
            if not candidate.exists():
                issues.append(
                    ReportIssue("missing-image", f"image {src!r} does not exist at {candidate}")
                )

    return issues


def _md_cells(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    # Split on unescaped pipes only.
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", stripped)]


def validate_markdown(document: str, *, profile: str = "core") -> list[ReportIssue]:
    """Validate a Markdown report, chiefly GFM table shape."""
    issues: list[ReportIssue] = []
    lines = document.splitlines()
    index = 0
    separator = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$")
    while index < len(lines):
        if (
            lines[index].strip().startswith("|")
            and index + 1 < len(lines)
            and separator.match(lines[index + 1])
            and "-" in lines[index + 1]
        ):
            header = _md_cells(lines[index])
            divider = _md_cells(lines[index + 1])
            if len(header) != len(divider):
                issues.append(
                    ReportIssue(
                        "table-shape",
                        f"line {index + 1}: header has {len(header)} columns but the divider has {len(divider)}",
                    )
                )
            cursor = index + 2
            while cursor < len(lines) and lines[cursor].strip().startswith("|"):
                cells = _md_cells(lines[cursor])
                if len(cells) != len(header):
                    issues.append(
                        ReportIssue(
                            "table-shape",
                            f"line {cursor + 1}: row has {len(cells)} cells but the header has {len(header)}",
                        )
                    )
                cursor += 1
            index = cursor
            continue
        index += 1

    text = document
    for sentinel in _SENTINELS:
        if re.search(rf"(?<![\w.]){re.escape(sentinel)}(?![\w.])", text):
            issues.append(
                ReportIssue("sentinel-leak", f"rendered document contains the sentinel {sentinel!r}")
            )

    rules = _profile_rules(profile)
    lowered = text.lower()
    for marker in rules["required"]:
        if marker.lower() not in lowered:
            issues.append(
                ReportIssue("missing-section", f"profile {profile!r} requires {marker!r}")
            )
    for alternatives in rules["required_any"]:
        if not any(alt.lower() in lowered for alt in alternatives):
            issues.append(
                ReportIssue("missing-verdict", f"profile {profile!r} requires one of {alternatives!r}")
            )
    for term in rules["banned"]:
        if term.lower() in lowered:
            issues.append(
                ReportIssue("out-of-scope-term", f"profile {profile!r} forbids {term!r}")
            )
    return issues


def infer_profile(path: Path) -> str:
    """Pick a sensible policy from the deliverable's name."""
    name = path.name.lower()
    if "v2" in name and "academic" in name:
        return "academic_v2"
    if "academic" in name:
        return "academic"
    if "chair_design_report" in name:
        return "reference_closed_form"
    return "core"


def validate_file(path: Path, *, profile: str | None = None) -> list[ReportIssue]:
    """Validate a report file, choosing HTML or Markdown by extension."""
    suffix = path.suffix.lower()
    if suffix not in (".html", ".htm", ".md", ".markdown"):
        raise ValueError(f"unsupported report type {suffix!r}; expected .html, .htm, .md")
    document = path.read_text(encoding="utf-8")
    chosen = profile or infer_profile(path)
    if suffix in (".md", ".markdown"):
        return validate_markdown(document, profile=chosen)
    return validate_html(document, profile=chosen, base_dir=path.parent)


class ReportValidationError(RuntimeError):
    """Raised when a report is about to be written but fails structural checks.

    Carrying the issues on the exception lets the CLI print them as a table
    instead of a traceback, and lets tests assert on the individual codes.
    """

    def __init__(self, source: str, issues: list[ReportIssue]) -> None:
        self.source = source
        self.issues = issues
        details = "\n".join(f"  - {issue}" for issue in issues)
        super().__init__(
            f"{source} failed structural validation "
            f"({len(issues)} issue(s)):\n{details}"
        )


def validate_or_raise(
    document: str,
    *,
    profile: str = "core",
    source: str = "report",
    base_dir: Path | None = None,
) -> None:
    """Validate a rendered document, raising instead of returning issues."""
    issues = validate_html(document, profile=profile, base_dir=base_dir)
    if issues:
        raise ReportValidationError(source, issues)


def write_validated(
    path: Path | str,
    document: str,
    *,
    profile: str | None = None,
    allow_invalid: bool = False,
) -> Path:
    """Write a report only after it passes structural validation.

    A malformed deliverable is worse than no deliverable: it gets emailed to a
    supervisor or submitted as coursework with a broken table or a dangling
    TOC link. Refusing to write is the only check the user cannot skip.
    """
    target = Path(path)
    chosen = profile or infer_profile(target)
    suffix = target.suffix.lower()
    if suffix in (".md", ".markdown"):
        issues = validate_markdown(document, profile=chosen)
    else:
        issues = validate_html(document, profile=chosen, base_dir=target.parent)
    if issues and not allow_invalid:
        raise ReportValidationError(str(target), issues)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m reporting.validate",
        description="Check a rendered MDIE report for structural defects.",
    )
    parser.add_argument("paths", nargs="+", type=Path, help="report file(s) to check")
    parser.add_argument(
        "--profile",
        choices=sorted(_PROFILES),
        help="content policy (default: inferred from the file name)",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args(argv)

    exit_code = 0
    for path in args.paths:
        if not path.exists():
            print(f"MISSING {path}")
            exit_code = 1
            continue
        issues = validate_file(path, profile=args.profile)
        blocking = [i for i in issues if i.severity == "error" or args.strict]
        print(f"{path}: {'OK' if not issues else f'{len(issues)} issue(s)'}")
        for issue in issues:
            print(f"  {issue}")
        if blocking:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
