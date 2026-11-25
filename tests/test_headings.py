"""Heading detection for PDFs that have no outline and no usable TOC."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from pdf_chapter_chunker import PDFChunker
from tests.pdf_factory import make_pdf


def _text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def test_structural_headings_ignore_a_repeated_running_header(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "headed.pdf",
        [
            [
                ("FIELD NOTES", 16),
                ("Chapter 1: Getting Started", 12),
                "ALPHA_MARKER ordinary paragraph",
            ],
            [("FIELD NOTES", 16), "the first chapter continues without a new title"],
            [("FIELD NOTES", 16), ("Chapter 2: Next Steps", 12), "BETA_MARKER ordinary paragraph"],
        ],
    )
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_chapters(source)
    assert chunker.last_detection == "headings"
    assert [path.name for path in written] == [
        "001_Chapter 1_ Getting Started.pdf",
        "002_Chapter 2_ Next Steps.pdf",
    ]
    assert "ALPHA_MARKER" in _text(written[0])
    assert "BETA_MARKER" not in _text(written[0])
    assert "BETA_MARKER" in _text(written[1])
    assert "FIELD NOTES" not in written[0].name


def test_large_type_titles_without_the_word_chapter(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "typed.pdf",
        [
            [("Overview", 20), "ALPHA_MARKER body sentence stays a normal size"],
            ["body continues in the overview portion today"],
            [("Materials", 20), "BETA_MARKER body sentence stays a normal size"],
        ],
    )
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_chapters(source)
    assert chunker.last_detection == "headings"
    assert [path.name for path in written] == ["001_Overview.pdf", "002_Materials.pdf"]
    assert "ALPHA_MARKER" in _text(written[0])
    assert "BETA_MARKER" in _text(written[1])


def test_bare_chapter_number_lines_use_the_page_where_they_appear(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "bare.pdf",
        [
            ["A title page for the notes"],
            [("Chapter 1", 18), "ALPHA_MARKER starts after the title page"],
            ["more of the first chapter"],
            [("Chapter 2", 18), "BETA_MARKER starts the second chapter"],
        ],
    )
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_chapters(source)
    assert chunker.last_detection == "headings"
    assert [path.name for path in written] == ["001_Chapter 1.pdf", "002_Chapter 2.pdf"]
    assert len(PdfReader(str(written[0])).pages) == 2
    assert "ALPHA_MARKER" in _text(written[0])
    assert "A title page" not in _text(written[0])
    assert "BETA_MARKER" in _text(written[1])


def test_split_chapter_title_is_joined(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "split.pdf",
        [
            [("Chapter 1", 18), ("Getting Started", 18), "ALPHA_MARKER body of the chapter"],
            ["the first chapter continues"],
            [("Chapter 2", 18), ("Next Steps", 18), "BETA_MARKER body of the chapter"],
        ],
    )
    written = PDFChunker(verbose=False).split_by_chapters(source)
    assert [path.name for path in written] == [
        "001_Chapter 1_ Getting Started.pdf",
        "002_Chapter 2_ Next Steps.pdf",
    ]


def test_numbered_large_titles_are_chapters_and_lists_are_not(tmp_path: Path) -> None:
    numbered = make_pdf(
        tmp_path / "numbered.pdf",
        [
            [("1 Introduction", 20), "ALPHA_MARKER body under the first number"],
            ["continuation of the introduction"],
            [("2 Methods", 20), "BETA_MARKER body under the second number"],
        ],
    )
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_chapters(numbered)
    assert chunker.last_detection == "headings"
    assert [path.name for path in written] == ["001_1 Introduction.pdf", "002_2 Methods.pdf"]

    listed = make_pdf(
        tmp_path / "listed.pdf",
        [
            ["1. Mix the samples carefully", "2. Heat the tray evenly", "ordinary procedure text"],
            ["3. Cool the tray slowly", "4. Record the result now", "more procedure text"],
        ],
    )
    written = chunker.split_by_chapters(listed)
    assert chunker.last_detection == "pages"
    assert written[0].name == "listed_chunk_001.pdf"
