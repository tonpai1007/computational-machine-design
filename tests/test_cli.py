"""Tests for the mdie command line interface."""

from __future__ import annotations

from pathlib import Path

import pytest

from cli import main
from cli.app import SUBCOMMANDS, _design_flags, _resolve_target
from cli.viewers import find_cad_tools, launch_cad_viewer

MD_SAMPLE = "# Sheet\n\nbody\n"


def test_bare_invocation_opens_the_interactive_prompt(monkeypatch):
    called = []
    monkeypatch.setattr("cli.app.interactive_repl", lambda: called.append(True))
    assert main([]) == 0
    assert called == [True]


@pytest.mark.parametrize("flag", ["-h", "--help", "help"])
def test_help_exits_cleanly(flag, capsys):
    assert main([flag]) == 0
    out = capsys.readouterr().out
    assert "MDIE" in out
    assert "convert" in out


def test_info_lists_convertible_formats(capsys):
    assert main(["info"]) == 0
    out = capsys.readouterr().out
    assert "convert formats" in out
    assert "pdf" in out


def test_convert_list_formats_prints_markdown(capsys):
    assert main(["convert", "--list-formats"]) == 0
    assert "Drawing sheets" in capsys.readouterr().out


def test_convert_round_trip_through_the_cli(tmp_path, capsys):
    src = tmp_path / "r.md"
    src.write_text(MD_SAMPLE, encoding="utf-8")
    dst = tmp_path / "r.docx"

    assert main(["convert", str(src), "--to", "docx", "-o", str(dst)]) == 0
    assert dst.exists()
    assert "Wrote" in capsys.readouterr().out


def test_convert_reports_failure_without_a_traceback(tmp_path, capsys):
    src = tmp_path / "r.md"
    src.write_text(MD_SAMPLE, encoding="utf-8")
    assert main(["convert", str(src), "--to", "dwg", "-o", str(tmp_path / "r.dwg")]) == 1
    assert "Conversion failed" in capsys.readouterr().out


def test_legacy_docx_alias_still_works(tmp_path):
    src = tmp_path / "r.html"
    src.write_text("<html><body><h1>Hi</h1></body></html>", encoding="utf-8")
    dst = tmp_path / "r.docx"
    assert main(["docx", str(src), "-o", str(dst)]) == 0
    assert dst.exists()


def test_view_reports_a_missing_target(tmp_path):
    assert main(["view", str(tmp_path / "does_not_exist")]) == 1


def test_design_flags_are_extracted_in_any_order():
    assert _design_flags(["--open", "-o", "Project/x"]) == ("Project/x", True)
    assert _design_flags(["--output-dir", "Project/y"]) == ("Project/y", False)
    assert _design_flags([]) == (None, False)


def test_resolve_target_falls_back_to_the_project_folder():
    resolved = _resolve_target("chair")
    assert isinstance(resolved, Path)
    assert resolved.exists()


def test_known_subcommands_are_declared():
    for name in ("design", "convert", "view", "drawings", "report", "info"):
        assert name in SUBCOMMANDS


def test_legacy_subcommand_aliases_are_preserved():
    for alias in ("docx", "word", "convert-docx", "consolidate", "study", "solve", "optimize"):
        assert alias in SUBCOMMANDS


def test_find_cad_tools_returns_a_mapping():
    tools = find_cad_tools()
    assert isinstance(tools, dict)
    assert set(tools) <= {"openscad", "freecad"}


def test_launching_a_viewer_for_a_missing_file_returns_false(tmp_path):
    assert launch_cad_viewer(tmp_path / "nope.step") is False