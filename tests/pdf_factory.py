"""Build small PDFs in tests.

Fixtures are generated at runtime from these helpers. Do not download or commit
copyrighted books.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

Line = str | tuple[str, float]


def make_pdf(
    path: Path,
    pages: list[list[Line]],
    *,
    outline: list[tuple[str, int]] | None = None,
    outline_root: str | None = None,
    outline_children: dict[int, list[tuple[str, int]]] | None = None,
) -> Path:
    """Write a text PDF and optionally attach bookmarks.

    ``outline`` items are ``(title, zero-based page index)``. ``outline_root``
    wraps those items under a single top-level bookmark. ``outline_children``
    maps a top-level outline index to nested bookmarks.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=letter)
    for page in pages:
        y_pos = 750.0
        for item in page:
            if isinstance(item, str):
                text, size = item, 12.0
            else:
                text, size = item
            font = "Times-Bold" if size >= 14 else "Times-Roman"
            pdf.setFont(font, size)
            pdf.drawString(72, y_pos, text)
            y_pos -= max(size + 8, 16)
        pdf.showPage()
    pdf.save()

    if outline is not None or outline_root is not None or outline_children:
        _attach_outline(path, outline or [], outline_root, outline_children or {})
    return path


def _attach_outline(
    path: Path,
    items: list[tuple[str, int]],
    root: str | None,
    children: dict[int, list[tuple[str, int]]],
) -> None:
    reader = PdfReader(str(path))
    writer = PdfWriter()
    writer.append(reader)
    if root is not None:
        parent = writer.add_outline_item(title=root, page_number=0)
        for title, page in items:
            writer.add_outline_item(title=title, page_number=page, parent=parent)
    else:
        parents = []
        for title, page in items:
            parents.append(writer.add_outline_item(title=title, page_number=page))
        for parent_index, kids in children.items():
            for title, page in kids:
                writer.add_outline_item(title=title, page_number=page, parent=parents[parent_index])
    with path.open("wb") as handle:
        writer.write(handle)
