"""Default PDF splitting, including the historical text-TOC path."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from pdf_chapter_chunker import PDFChunker, __version__
from pdf_chapter_chunker.chunker import CREATOR, PRODUCER
from tests.pdf_factory import make_pdf


def _text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _toc_book(path: Path, *, with_outline: bool = False) -> Path:
    pages: list[list[str | tuple[str, float]]] = [
        [
            "Table of Contents",
            "Introduction .............. 3",
            "Methods ................... 5",
        ],
        [("Should Not Win", 20), "EARLY_MARKER is before the first contents entry"],
        ["INTRO_MARKER begins the introduction", "More introduction text without digits"],
        ["Introduction continues on this page"],
        ["METHODS_MARKER begins the methods"],
    ]
    outline = [("Preface", 1), ("Appendix", 4)] if with_outline else None
    return make_pdf(path, pages, outline=outline)


def test_text_toc_splits_pages_and_writes_metadata(tmp_path: Path) -> None:
    source = _toc_book(tmp_path / "manual.pdf", with_outline=True)
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_chapters(source)
    assert chunker.last_detection == "toc"
    assert [path.name for path in written] == ["001_Introduction.pdf", "002_Methods.pdf"]

    intro, methods = written
    assert len(PdfReader(str(intro)).pages) == 2
    assert len(PdfReader(str(methods)).pages) == 1
    assert "INTRO_MARKER" in _text(intro)
    assert "METHODS_MARKER" not in _text(intro)
    assert "EARLY_MARKER" not in _text(intro)
    assert "METHODS_MARKER" in _text(methods)

    meta = PdfReader(str(intro)).metadata
    assert meta is not None
    assert meta.title == "manual - Introduction"
    assert meta.subject == "Chapter 1: Introduction"
    assert meta.creator == CREATOR == f"PDF Chapter Chunker v{__version__}"
    assert meta.producer == PRODUCER
    outline = PdfReader(str(intro)).outline
    assert outline[0].title == "Introduction"
    assert not list(intro.parent.glob("*.json"))
    assert not list(intro.parent.glob("*.md"))


def test_custom_output_directory_nests_chapters_folder(tmp_path: Path) -> None:
    source = _toc_book(tmp_path / "manual.pdf")
    output = tmp_path / "out"
    written = PDFChunker(verbose=False).split_by_chapters(source, output)
    assert written[0].parent == output / "manual_chapters"


def test_in_range_weak_toc_line_still_wins_over_headings(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "weak.pdf",
        [
            ["Chapter notes", "See section 3", ("Real Heading", 20), "PAGE_ONE_MARKER"],
            ["middle page body text"],
            ["PAGE_THREE_MARKER is where the weak entry points"],
        ],
    )
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_chapters(source)
    assert chunker.last_detection == "toc"
    assert [path.name for path in written] == ["001_See section.pdf"]
    assert "PAGE_THREE_MARKER" in _text(written[0])
    assert "PAGE_ONE_MARKER" not in _text(written[0])


def test_out_of_range_toc_without_headings_does_not_page_chunk(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "copyright.pdf",
        [
            ["Chapter notes", "Copyright 2024"],
            ["plain body without a heading line here"],
        ],
    )
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_chapters(source)
    assert chunker.last_detection == "toc"
    assert written == []


def test_missing_structure_falls_back_to_page_chunks(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "notes.pdf",
        [["Just a paragraph of prose without structure here today."]] * 3,
    )
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_chapters(source)
    assert chunker.last_detection == "pages"
    assert len(written) == 1
    assert written[0] == tmp_path / "notes_chapters" / "notes_chunk_001.pdf"
    assert len(PdfReader(str(written[0])).pages) == 3


def test_page_mode_uses_size_and_flat_output_directory(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "notes.pdf", [["Page body text."]] * 5)
    output = tmp_path / "flat"
    chunker = PDFChunker(verbose=False)
    written = chunker.split_by_pages(source, output, 2)
    assert chunker.last_detection == "pages"
    assert [path.name for path in written] == [
        "notes_chunk_001.pdf",
        "notes_chunk_002.pdf",
        "notes_chunk_003.pdf",
    ]
    assert all(path.parent == output for path in written)
    assert [len(PdfReader(str(path)).pages) for path in written] == [2, 2, 1]
    meta = PdfReader(str(written[0])).metadata
    assert meta is not None
    assert meta.subject == "PDF chunk 1 of 3"
    assert meta.title == "notes - Chunk 001 (Pages 1-2)"


def test_page_mode_default_directory(tmp_path: Path) -> None:
    source = make_pdf(tmp_path / "notes.pdf", [["Page body text."]] * 2)
    written = PDFChunker(verbose=False).split_by_pages(source)
    assert written[0].parent == tmp_path / "notes_pages"


def test_missing_file_and_bad_chunk_size(tmp_path: Path) -> None:
    chunker = PDFChunker(verbose=False)
    try:
        chunker.split_by_chapters(tmp_path / "missing.pdf")
    except FileNotFoundError as exc:
        assert "missing.pdf" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")

    source = make_pdf(tmp_path / "notes.pdf", [["Page body text."]])
    try:
        chunker.split_by_pages(source, chunk_size=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected ValueError")
