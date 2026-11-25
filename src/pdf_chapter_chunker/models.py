"""Shared records for a planned chapter chunk."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterChunk:
    """One output chapter, using 1-based inclusive page numbers."""

    index: int
    title: str
    start_page: int
    end_page: int
    filename: str

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1
