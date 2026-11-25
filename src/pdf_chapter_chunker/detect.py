"""Outline reading and heading heuristics for PDFs that lack a text TOC."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pypdf import PdfReader

_BARE_TOC_TITLE = re.compile(
    r"^(?:chapter|chap\.?|part|section|appendix|book)$",
    re.IGNORECASE,
)
_STRUCTURAL = re.compile(
    r"^(?:"
    r"(?:chapter|chap\.?)\s+(?:\d+|[ivxlcdm]+)\b.*|"
    r"part\s+(?:\d+|[ivxlcdm]+)\b.*|"
    r"appendix\s+[a-z0-9]+\b.*|"
    r"section\s+\d+(?:\.\d+)*\b.*"
    r")$",
    re.IGNORECASE,
)
_BARE_HEADING = re.compile(
    r"^(?:(?:chapter|chap\.?|part|section)\s+(?:\d+|[ivxlcdm]+)|appendix\s+[a-z0-9]+):?$",
    re.IGNORECASE,
)
_NUMBERED = re.compile(
    r"^(?P<num>\d{1,2}(?:\.\d{1,2}){0,3})[.)]?\s+(?P<title>[A-Z][\w][^\n]{0,80})$"
)
_LIST_ITEM = re.compile(r"^\d{1,3}[.)]\s+\S")
_DOT_LEADER = re.compile(r"\.{4,}")
_ONLY_DIGITS = re.compile(r"^\d+$")


@dataclass(frozen=True)
class TextLine:
    """One visual line of text and the font size used to draw it."""

    text: str
    size: float
    y: float


def toc_is_usable(entries: list[tuple[str, int]], total_pages: int) -> bool:
    """Return True when scanned TOC entries can drive the historical splitter.

    Entries whose page numbers fall outside the document, and entries that are
    only the word "Chapter" (the following number was the chapter number, not
    a page), do not count. Any other in-range hit keeps the previous behaviour.
    """
    in_range = [(title, page) for title, page in entries if 1 <= page <= total_pages]
    if not in_range:
        return False
    return not all(_BARE_TOC_TITLE.fullmatch(title.strip()) for title, _page in in_range)


def outline_entries(reader: PdfReader) -> list[tuple[str, int]]:
    """Return top-level bookmark titles and 1-based page numbers.

    Nested bookmarks stay inside the parent chapter. When the outline is a
    single root with several children, the children are the chapters.
    """
    try:
        outline = reader.outline
    except Exception:
        return []
    if not isinstance(outline, list) or not outline:
        return []

    selected = _selected_outline_nodes(outline)
    entries: list[tuple[str, int]] = []
    for item in selected:
        title = _outline_title(item)
        if not title:
            continue
        try:
            page_index = reader.get_destination_page_number(item)
        except Exception:
            continue
        if page_index is None or page_index < 0:
            continue
        entries.append((title, page_index + 1))
    return _dedupe_by_page(entries)


def detect_headings(reader: PdfReader) -> list[tuple[str, int]]:
    """Find chapter starts from page text when the PDF has no outline.

    A heading is a short line near the top of a page that looks like
    "Chapter 1", "Appendix A", a numbered title in a larger font, or other
    short large type. Running headers that repeat on every page are ignored.
    At least two headings are required; otherwise the caller falls back.
    """
    pages = list(reader.pages)
    if len(pages) < 2:
        return []

    lines_by_page = [_page_lines(page) for page in pages]
    running = _running_header_norms(lines_by_page)
    body_size = _body_size(lines_by_page, running)

    found: list[tuple[str, int]] = []
    for page_number, lines in enumerate(lines_by_page, start=1):
        heading = _heading_on_page(lines, running, body_size)
        if heading:
            found.append((heading, page_number))

    if len(found) < 2:
        return []
    return _dedupe_by_page(found)


def _selected_outline_nodes(outline: list[Any]) -> list[Any]:
    nodes: list[tuple[Any, list[Any]]] = []
    index = 0
    while index < len(outline):
        item = outline[index]
        if isinstance(item, list):
            index += 1
            continue
        children: list[Any] = []
        if index + 1 < len(outline) and isinstance(outline[index + 1], list):
            children = [child for child in outline[index + 1] if not isinstance(child, list)]
        nodes.append((item, children))
        index += 1

    if len(nodes) == 1 and len(nodes[0][1]) >= 2:
        return nodes[0][1]
    return [node for node, _children in nodes]


def _outline_title(item: Any) -> str:
    title = getattr(item, "title", None)
    if title is None and isinstance(item, dict):
        title = item.get("/Title")
    if title is None:
        return ""
    return re.sub(r"\s+", " ", str(title)).strip()


def _dedupe_by_page(entries: list[tuple[str, int]]) -> list[tuple[str, int]]:
    seen: set[tuple[str, int]] = set()
    unique: list[tuple[str, int]] = []
    for title, page in entries:
        key = (title, page)
        if key in seen:
            continue
        seen.add(key)
        unique.append((title, page))
    return sorted(unique, key=lambda item: item[1])


def _page_lines(page: Any) -> list[TextLine]:
    spans: list[tuple[float, float, str, float]] = []

    def visitor(
        text: object,
        cm: object,
        tm: object,
        font_dict: object,
        font_size: object,
    ) -> None:
        del cm, font_dict
        if text is None:
            return
        raw = str(text).replace("\n", "")
        if not raw.strip():
            return
        x_pos, y_pos = _text_position(tm)
        size = float(font_size) if isinstance(font_size, (int, float)) else 0.0
        spans.append((x_pos, y_pos, raw, size))

    try:
        page.extract_text(visitor_text=visitor)
    except Exception:
        spans = []

    grouped = _group_spans(spans)
    if grouped:
        return grouped

    try:
        plain = page.extract_text() or ""
    except Exception:
        return []
    fallback: list[TextLine] = []
    for raw_line in plain.splitlines():
        cleaned = raw_line.strip()
        if cleaned:
            fallback.append(TextLine(cleaned, 0.0, 0.0))
    return fallback


def _text_position(tm: object) -> tuple[float, float]:
    if isinstance(tm, (list, tuple)) and len(tm) >= 6:
        try:
            return float(tm[4]), float(tm[5])
        except (TypeError, ValueError):
            return 0.0, 0.0
    return 0.0, 0.0


def _group_spans(spans: list[tuple[float, float, str, float]]) -> list[TextLine]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda span: (-round(span[1], 1), span[0]))
    groups: list[list[tuple[float, float, str, float]]] = []
    current: list[tuple[float, float, str, float]] = []
    current_y: float | None = None
    for span in ordered:
        y_pos = span[1]
        if current_y is None or abs(y_pos - current_y) > 2.5:
            if current:
                groups.append(current)
            current = [span]
            current_y = y_pos
        else:
            current.append(span)
    if current:
        groups.append(current)

    lines: list[TextLine] = []
    for group in groups:
        text, size, y_pos = _merge_group(group)
        if text:
            lines.append(TextLine(text, size, y_pos))
    return lines


def _merge_group(parts: list[tuple[float, float, str, float]]) -> tuple[str, float, float]:
    ordered = sorted(parts, key=lambda part: part[0])
    pieces: list[str] = []
    previous_end: float | None = None
    size = 0.0
    for x_pos, _y_pos, text, span_size in ordered:
        gap = max(span_size * 0.3, 2.0)
        if (
            previous_end is not None
            and x_pos - previous_end > gap
            and pieces
            and not pieces[-1].endswith(" ")
        ):
            pieces.append(" ")
        pieces.append(text)
        previous_end = x_pos + max(len(text), 1) * max(span_size, 1.0) * 0.45
        size = max(size, span_size)
    return "".join(pieces).strip(), size, ordered[0][1]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def _running_header_norms(lines_by_page: list[list[TextLine]]) -> set[str]:
    counts: Counter[str] = Counter()
    page_count = len(lines_by_page)
    for lines in lines_by_page:
        counts.update({_norm(line.text) for line in lines if _norm(line.text)})

    ignored: set[str] = set()
    for text, count in counts.items():
        if page_count >= 2 and count >= page_count:
            ignored.add(text)
        elif page_count >= 5 and count >= 3 and count / page_count >= 0.6:
            ignored.add(text)
    return ignored


def _body_size(lines_by_page: list[list[TextLine]], running: set[str]) -> float:
    sizes = [
        round(line.size, 1)
        for lines in lines_by_page
        for line in lines
        if line.size > 0 and _norm(line.text) not in running and len(line.text) >= 15
    ]
    if len(sizes) < 2:
        sizes = [
            round(line.size, 1)
            for lines in lines_by_page
            for line in lines
            if line.size > 0 and _norm(line.text) not in running
        ]
    if not sizes:
        return 0.0
    counts = Counter(sizes)
    most = max(counts.values())
    return min(size for size, count in counts.items() if count == most)


def _heading_on_page(lines: list[TextLine], running: set[str], body_size: float) -> str | None:
    visible = [line for line in lines if _norm(line.text) not in running]
    if not visible or _looks_like_toc_page(visible):
        return None

    window = visible[:8]
    for index, line in enumerate(window):
        title = _heading_title(line, window[index + 1 : index + 5], body_size)
        if title:
            return title
    return None


def _looks_like_toc_page(lines: list[TextLine]) -> bool:
    leaders = sum(1 for line in lines[:12] if _DOT_LEADER.search(line.text))
    return leaders >= 3


def _heading_title(line: TextLine, following: list[TextLine], body_size: float) -> str | None:
    text = line.text.strip()
    if not text or _DOT_LEADER.search(text) or _ONLY_DIGITS.fullmatch(text):
        return None

    structural = _STRUCTURAL.fullmatch(text) is not None
    numbered = _numbered_heading(text, line.size, body_size, following)
    display = _is_large(line.size, body_size) and _looks_like_title(text)
    if not structural and not numbered and not display:
        return None

    title = _join_subtitle(text, line.size, following) if structural else text
    if not _looks_like_title(title):
        return None
    return title


def _join_subtitle(text: str, heading_size: float, following: list[TextLine]) -> str:
    if _BARE_HEADING.fullmatch(text) is None and not text.endswith(":"):
        return text
    if not following:
        return text
    nxt_line = following[0]
    nxt = nxt_line.text.strip()
    if len(nxt) > 40 or len(nxt.split()) > 6:
        return text
    # A body paragraph under a large "Chapter N" line is not the subtitle.
    if heading_size >= 14 and nxt_line.size + 1 < heading_size:
        return text
    if not _looks_like_title(nxt) or _STRUCTURAL.fullmatch(nxt):
        return text
    if text.endswith(":"):
        return f"{text} {nxt}"
    return f"{text}: {nxt}"


def _numbered_heading(text: str, size: float, body_size: float, following: list[TextLine]) -> bool:
    match = _NUMBERED.fullmatch(text)
    if match is None:
        return False
    if body_size > 0 and not _is_large(size, body_size):
        return False
    if len(match.group("title").split()) > 8:
        return False
    for line in following[:4]:
        candidate = line.text.strip()
        if _LIST_ITEM.match(candidate) or _NUMBERED.fullmatch(candidate):
            return False
    return True


def _is_large(size: float, body_size: float) -> bool:
    if size <= 0 or body_size <= 0:
        return False
    return size >= body_size + 4 and size >= 14


def _looks_like_title(text: str) -> bool:
    cleaned = text.strip()
    if not (3 <= len(cleaned) <= 90):
        return False
    words = cleaned.split()
    if not (1 <= len(words) <= 12):
        return False
    if not any(char.isalpha() for char in cleaned):
        return False
    if cleaned.endswith((",", ";")):
        return False
    if ". " in cleaned or _DOT_LEADER.search(cleaned) or _ONLY_DIGITS.fullmatch(cleaned):
        return False
    return True
