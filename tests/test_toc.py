"""Historical table-of-contents parsing and filename rules."""

from __future__ import annotations

from pathlib import Path

from pdf_chapter_chunker import PDFChunker
from pdf_chapter_chunker.detect import toc_is_usable
from tests.pdf_factory import make_pdf


def test_extract_toc_from_text_keeps_historical_matches() -> None:
    text = "\n".join(
        [
            "Chapter 1: Introduction .............. 15",
            "1.1 Getting Started .................. 23",
            "Section 2.3 Advanced Topics .......... 67",
            "Appendix A 145",
            "Bibliography ......................... 200",
            "short",
            "Copyright 2024",
            "See section 12",
            "A 1",
        ]
    )
    entries = PDFChunker(verbose=False).extract_toc_from_text(text)
    assert entries == [
        ("See section", 12),
        ("Chapter 1: Introduction", 15),
        ("1.1 Getting Started", 23),
        ("Section 2.3 Advanced Topics", 67),
        ("Appendix A", 145),
        ("Bibliography", 200),
        ("Copyright", 2024),
    ]


def test_extract_toc_deduplicates_and_sorts() -> None:
    text = "\n".join(
        [
            "Methods .......... 8",
            "Intro ............ 2",
            "Intro ............ 2",
        ]
    )
    assert PDFChunker(verbose=False).extract_toc_from_text(text) == [
        ("Intro", 2),
        ("Methods", 8),
    ]


def test_chapter_line_uses_the_earlier_end_of_line_pattern() -> None:
    text = "Chapter 4: Storage layout 88"
    assert PDFChunker(verbose=False).extract_toc_from_text(text) == [
        ("Chapter 4: Storage layout", 88)
    ]


def test_chapter_pattern_when_the_page_number_is_not_at_the_end() -> None:
    text = "Chapter 4: Storage layout 88 (draft)"
    assert PDFChunker(verbose=False).extract_toc_from_text(text) == [("4 Storage layout", 88)]


def test_toc_page_requires_an_indicator(tmp_path: Path) -> None:
    pdf = make_pdf(
        tmp_path / "no_indicator.pdf",
        [["Introduction .............. 2", "Methods .............. 3"]],
    )
    assert PDFChunker(verbose=False).extract_toc_from_pdf(pdf) == []


def test_toc_page_with_contents_indicator(tmp_path: Path) -> None:
    pdf = make_pdf(
        tmp_path / "contents.pdf",
        [["Table of Contents", "Introduction .............. 2", "Methods .............. 3"]],
    )
    assert PDFChunker(verbose=False).extract_toc_from_pdf(pdf) == [
        ("Introduction", 2),
        ("Methods", 3),
    ]


def test_toc_is_usable_rejects_bare_labels_and_out_of_range_pages() -> None:
    assert toc_is_usable([("Introduction", 2), ("Methods", 4)], 10)
    assert not toc_is_usable([("Chapter", 1), ("Chapter", 2)], 10)
    assert not toc_is_usable([("Copyright", 2024)], 10)
    assert toc_is_usable([("Appendix A", 4)], 10)


def test_sanitize_filename() -> None:
    chunker = PDFChunker(verbose=False)
    assert chunker.sanitize_filename('A<B>C:"D/E\\F|G?H*I') == "A_B_C__D_E_F_G_H_I"
    assert chunker.sanitize_filename("Hello    World") == "Hello World"
    assert chunker.sanitize_filename("foo..bar") == "foo.bar"
    long_title = "word " * 30
    safe = chunker.sanitize_filename(long_title, max_length=50)
    assert len(safe) <= 50
    assert safe.endswith("word")
