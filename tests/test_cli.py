"""Command-line defaults and the console entry point."""

from __future__ import annotations

import json
import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

import pytest

from pdf_chapter_chunker import __version__
from pdf_chapter_chunker.cli import main
from tests.pdf_factory import make_pdf


def _book(path: Path) -> Path:
    return make_pdf(
        path,
        [
            ["Table of Contents", "Introduction .............. 2"],
            ["INTRO_MARKER body text"],
        ],
    )


def test_default_invocation_writes_pdfs_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _book(tmp_path / "manual.pdf")
    output = tmp_path / "out"
    assert main([str(source), "--output", str(output)]) == 0
    captured = capsys.readouterr()
    assert "Successfully split PDF into 1 chunks!" in captured.out
    assert "Found 1 chapter entries:" in captured.out
    assert "using PDF outline" not in captured.out
    assert "detecting chapter headings" not in captured.out
    pdfs = list((output / "manual_chapters").glob("*.pdf"))
    assert len(pdfs) == 1
    assert not list(output.rglob("*.json"))
    assert not list(output.rglob("*.md"))


def test_quiet_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _book(tmp_path / "manual.pdf")
    destination = tmp_path / "manual.json"
    assert main([str(source), "--format", "json", "-o", str(destination), "--quiet"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["detection"] == "toc"
    assert "INTRO_MARKER" in payload["chapters"][0]["text"]


def test_version_and_unknown_format(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out

    with pytest.raises(SystemExit) as exc:
        main(["book.pdf", "--format", "xml"])
    assert exc.value.code == 2


def test_missing_file_returns_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    missing = tmp_path / "missing.pdf"
    assert main([str(missing), "--quiet"]) == 1
    captured = capsys.readouterr()
    assert "missing.pdf" in captured.err
    assert captured.out == ""


def test_page_size_must_be_positive(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = _book(tmp_path / "manual.pdf")
    assert main([str(source), "--mode", "pages", "--size", "0"]) == 1
    assert "positive" in capsys.readouterr().err


def test_module_and_console_entry_point() -> None:
    module = subprocess.run(
        [sys.executable, "-m", "pdf_chapter_chunker", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert module.returncode == 0
    assert __version__ in module.stdout

    scripts = {item.name: item.value for item in entry_points(group="console_scripts")}
    assert scripts.get("pdf-chunker") == "pdf_chapter_chunker:main"
