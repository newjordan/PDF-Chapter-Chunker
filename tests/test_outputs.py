"""JSON and Markdown output. PDF remains the default."""

from __future__ import annotations

import json
from pathlib import Path

from pdf_chapter_chunker import PDFChunker, __version__
from tests.pdf_factory import make_pdf


def _book(path: Path) -> Path:
    return make_pdf(
        path,
        [
            ["Table of Contents", "Introduction .............. 2", "Methods .............. 4"],
            ["INTRO_MARKER opening text"],
            ["introduction continues"],
            ["METHODS_MARKER closing text"],
        ],
    )


def test_json_contains_chapter_text_and_detection(tmp_path: Path) -> None:
    source = _book(tmp_path / "manual.pdf")
    output = tmp_path / "out"
    written = PDFChunker(verbose=False).split_by_chapters(source, output, "json")
    assert written == [output / "manual_chapters.json"]
    assert not (output / "manual_chapters").exists()

    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["tool"] == "pdf-chapter-chunker"
    assert payload["version"] == __version__
    assert payload["source"] == "manual.pdf"
    assert payload["page_count"] == 4
    assert payload["mode"] == "chapters"
    assert payload["detection"] == "toc"
    assert payload["pages_per_chunk"] is None
    assert [chapter["title"] for chapter in payload["chapters"]] == ["Introduction", "Methods"]
    intro, methods = payload["chapters"]
    assert intro["start_page"] == 2
    assert intro["end_page"] == 3
    assert intro["filename"] == "001_Introduction.pdf"
    assert "INTRO_MARKER" in intro["text"]
    assert "METHODS_MARKER" not in intro["text"]
    assert "METHODS_MARKER" in methods["text"]


def test_markdown_and_explicit_file_path(tmp_path: Path) -> None:
    source = _book(tmp_path / "manual.pdf")
    destination = tmp_path / "notes" / "manual.md"
    written = PDFChunker(verbose=False).split_by_chapters(source, destination, "markdown")
    assert written == [destination]
    text = destination.read_text(encoding="utf-8")
    assert text.startswith("# manual\n")
    assert "- Detection: toc" in text
    assert "- Mode: chapters" in text
    assert "## 1. Introduction" in text
    assert "Pages 2-3." in text
    assert "INTRO_MARKER" in text
    assert "## 2. Methods" in text
    assert "Page 4." in text
    assert "METHODS_MARKER" in text


def test_heading_detection_is_reported_in_json(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "typed.pdf",
        [
            [("Overview", 20), "ALPHA_MARKER body sentence stays a normal size"],
            [("Materials", 20), "BETA_MARKER body sentence stays a normal size"],
        ],
    )
    written = PDFChunker(verbose=False).split_by_chapters(source, output_format="json")
    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["detection"] == "headings"
    assert payload["chapters"][0]["title"] == "Overview"
    assert "ALPHA_MARKER" in payload["chapters"][0]["text"]


def test_page_mode_json_records_chunk_size(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "notes.pdf", [["Sentence one."], ["Sentence two."], ["Sentence three."]]
    )
    destination = tmp_path / "notes.json"
    written = PDFChunker(verbose=False).split_by_pages(source, destination, 2, "json")
    assert written == [destination]
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["mode"] == "pages"
    assert payload["detection"] == "pages"
    assert payload["pages_per_chunk"] == 2
    assert [chapter["page_count"] for chapter in payload["chapters"]] == [2, 1]
    assert payload["chapters"][0]["title"] == "Chunk 001 (Pages 1-2)"


def test_chapter_fallback_json_keeps_the_chapters_name(tmp_path: Path) -> None:
    source = make_pdf(
        tmp_path / "notes.pdf",
        [["Just a paragraph of prose without structure here today."]] * 2,
    )
    written = PDFChunker(verbose=False).split_by_chapters(source, output_format="markdown")
    assert written == [tmp_path / "notes_chapters.md"]
    text = written[0].read_text(encoding="utf-8")
    assert "- Mode: chapters" in text
    assert "- Detection: pages" in text
    assert "- Pages per chunk: 99" in text
