"""Bookmark outlines are used only when the text TOC does not match."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from pdf_chapter_chunker import PDFChunker
from tests.pdf_factory import make_pdf


def _text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_outline_splits_when_there_is_no_text_toc(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "outlined.pdf",
        [
            [("WRONG HEADING", 20), "ALPHA_MARKER in the opening"],
            ["still opening body text here"],
            [("ANOTHER HEADING", 20), "BETA_MARKER in the later part"],
            ["later body continues"],
        ],
        outline=[("Opening", 0), ("Later", 2)],
    )
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_chapters(source)
    assert chunker.last_detection == "outline"
    assert [path.name for path in written] == ["001_Opening.pdf", "002_Later.pdf"]
    assert "ALPHA_MARKER" in _text(written[0])
    assert "WRONG HEADING" in _text(written[0])
    assert "BETA_MARKER" not in _text(written[0])
    assert "BETA_MARKER" in _text(written[1])


def test_nested_outline_items_stay_inside_the_parent(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "nested.pdf",
        [
            ["ALPHA_MARKER opening"],
            ["INNER_MARKER inside the first chapter"],
            ["BETA_MARKER second chapter"],
        ],
        outline=[("First", 0), ("Second", 2)],
        outline_children={0: [("Inner", 1)]},
    )
    written = PDFChunker(verbose=False).split_by_chapters(source)
    assert [path.name for path in written] == ["001_First.pdf", "002_Second.pdf"]
    assert "INNER_MARKER" in _text(written[0])
    assert "BETA_MARKER" not in _text(written[0])


def test_single_root_outline_uses_its_children(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "rooted.pdf",
        [
            ["ALPHA_MARKER first child"],
            ["bridge page"],
            ["BETA_MARKER second child"],
        ],
        outline=[("First", 0), ("Second", 2)],
        outline_root="Whole Book",
    )
    written = PDFChunker(verbose=False).split_by_chapters(source)
    names = [path.name for path in written]
    assert names == ["001_First.pdf", "002_Second.pdf"]
    assert "Whole" not in " ".join(names)
    assert "ALPHA_MARKER" in _text(written[0])
    assert "BETA_MARKER" in _text(written[1])
