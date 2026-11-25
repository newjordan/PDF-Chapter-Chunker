"""Split a PDF into chapter chunks and optional JSON or Markdown metadata."""

from __future__ import annotations

from typing import Any

from pdf_chapter_chunker._version import __version__

__all__ = ["PDFChunker", "main", "__version__"]


def __getattr__(name: str) -> Any:
    """Import the chunker and CLI lazily so packaging can read the version."""
    if name == "PDFChunker":
        from pdf_chapter_chunker.chunker import PDFChunker

        return PDFChunker
    if name == "main":
        from pdf_chapter_chunker.cli import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
