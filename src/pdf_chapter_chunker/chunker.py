"""Split PDFs into chapter files, JSON, or Markdown."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pypdf import PdfReader, PdfWriter

from pdf_chapter_chunker._version import __version__
from pdf_chapter_chunker.detect import detect_headings, outline_entries, toc_is_usable
from pdf_chapter_chunker.models import ChapterChunk

OutputFormat = Literal["pdf", "json", "markdown"]
DetectionMethod = Literal["toc", "outline", "headings", "pages"]

PRODUCER = "PDF Chapter Chunker"
CREATOR = f"PDF Chapter Chunker v{__version__}"
OUTPUT_FORMATS = ("pdf", "json", "markdown")


class PDFChunker:
    """Split a PDF on its table of contents, outline, headings, or page count."""

    def __init__(self, verbose: bool = True) -> None:
        self.verbose = verbose
        self.last_detection: DetectionMethod | None = None
        self.toc_patterns = [
            r"(.+?)\s+\.{2,}\s*(\d+)",  # Chapter title ... page_number
            r"(.+?)\s+(\d+)$",  # Chapter title page_number (end of line)
            r"(\d+\.?\d*)\s+(.+?)\s+(\d+)",  # Number Chapter title page_number
            r"Chapter\s+(\d+)[:\s]+(.+?)\s+(\d+)",  # Chapter X: Title page_number
            r"(\d+\.\d+)\s+(.+?)\s+(\d+)",  # 1.1 Chapter title page_number
        ]
        self.toc_indicators = ["table of contents", "contents", "index", "chapter"]

    def log(self, message: str) -> None:
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def extract_toc_from_text(self, text: str) -> list[tuple[str, int]]:
        """Extract table of contents entries from text using common patterns.

        Args:
            text: Raw text extracted from PDF pages.

        Returns:
            ``(chapter_title, page_number)`` pairs sorted by page.
        """
        toc_entries: list[tuple[str, int]] = []

        lines = text.split("\n")
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5:
                continue

            for pattern in self.toc_patterns:
                match = re.search(pattern, line)
                if match:
                    if len(match.groups()) == 2:
                        title, page = match.groups()
                        try:
                            page_num = int(page)
                            if 1 <= page_num <= 10000:  # Reasonable page range
                                toc_entries.append((title.strip(), page_num))
                                break
                        except ValueError:
                            continue
                    elif len(match.groups()) == 3:
                        # Handle numbered chapters
                        num, title, page = match.groups()
                        try:
                            page_num = int(page)
                            if 1 <= page_num <= 10000:
                                full_title = f"{num} {title}".strip()
                                toc_entries.append((full_title, page_num))
                                break
                        except ValueError:
                            continue

        # Remove duplicates and sort by page number
        seen: set[tuple[str, int]] = set()
        unique_entries: list[tuple[str, int]] = []
        for title, page in toc_entries:
            if (title, page) not in seen:
                seen.add((title, page))
                unique_entries.append((title, page))

        return sorted(unique_entries, key=lambda item: item[1])

    def extract_toc_from_pdf(
        self, pdf_path: str | Path, max_pages: int = 25
    ) -> list[tuple[str, int]]:
        """Extract a table of contents from the first pages of a PDF.

        Args:
            pdf_path: Path to the PDF file.
            max_pages: Maximum pages to search for a table of contents.

        Returns:
            ``(chapter_title, page_number)`` pairs, or an empty list.
        """
        reader = PdfReader(str(pdf_path))
        return self._extract_toc_from_reader(reader, max_pages=max_pages)

    def _extract_toc_from_reader(
        self, reader: PdfReader, max_pages: int = 25
    ) -> list[tuple[str, int]]:
        toc_text = ""
        search_pages = min(max_pages, len(reader.pages))

        for page_num in range(search_pages):
            try:
                page_text = reader.pages[page_num].extract_text()
                toc_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            except Exception as exc:
                self.log(f"Warning: Could not extract text from page {page_num + 1}: {exc}")
                continue

        toc_found = any(indicator in toc_text.lower() for indicator in self.toc_indicators)
        if not toc_found:
            self.log("Warning: No clear table of contents found in first chunk")
            return []

        return self.extract_toc_from_text(toc_text)

    def sanitize_filename(self, title: str, max_length: int = 50) -> str:
        """Clean a chapter title for use as a filename.

        Args:
            title: Chapter title.
            max_length: Maximum filename length.

        Returns:
            Sanitized filename stem.
        """
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)
        safe_title = re.sub(r"\s+", " ", safe_title).strip()
        safe_title = safe_title.replace("..", ".")
        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length].rsplit(" ", 1)[0]
        return safe_title

    def split_by_chapters(
        self,
        input_path: str | Path,
        output_dir: str | Path | None = None,
        output_format: OutputFormat = "pdf",
    ) -> list[Path]:
        """Split a PDF into chapters.

        A text table of contents in the first 25 pages is used when it points
        at real pages. Otherwise a PDF outline is used, then heading detection
        for documents with no outline. Page chunks remain the last resort.

        Args:
            input_path: Path to the input PDF.
            output_dir: Directory or, for JSON/Markdown, a file path.
            output_format: ``pdf`` (default), ``json``, or ``markdown``.

        Returns:
            Paths of files written.
        """
        self._check_format(output_format)
        source = self._existing_pdf(input_path)
        pdf_dir = self._chapters_directory(source, output_dir)
        if output_format == "pdf":
            pdf_dir.mkdir(parents=True, exist_ok=True)

        reader = self._open_reader(source)
        total_pages = len(reader.pages)
        self.log(f"Processing {source.name} ({total_pages} pages)")
        self.log("Extracting table of contents from first chunk...")
        toc_entries = self._extract_toc_from_reader(reader)

        entries: list[tuple[str, int]] | None = None
        detection: DetectionMethod = "toc"
        if toc_entries and toc_is_usable(toc_entries, total_pages):
            entries = toc_entries
            detection = "toc"
        else:
            bookmarks = outline_entries(reader)
            headings = [] if bookmarks else detect_headings(reader)
            if bookmarks:
                self.log("No usable table of contents found, using PDF outline")
                entries = bookmarks
                detection = "outline"
            elif headings:
                self.log("No usable table of contents found, detecting chapter headings...")
                entries = headings
                detection = "headings"
            elif toc_entries:
                entries = toc_entries
                detection = "toc"
            else:
                self.log("No table of contents found, falling back to page-based chunking")
                if output_format == "pdf":
                    return self.split_by_pages(source, pdf_dir, 99, "pdf")
                plans = self._page_plans(total_pages, 99, source.stem)
                self.log(f"Creating {len(plans)} chunks of up to 99 pages each")
                return self._emit(
                    reader,
                    source,
                    plans,
                    output_format=output_format,
                    detection="pages",
                    mode="chapters",
                    pdf_dir=pdf_dir,
                    output=Path(output_dir) if output_dir is not None else None,
                    chunk_size=99,
                )

        assert entries is not None
        self._log_entries(entries)
        plans = self._plans_from_entries(entries, total_pages)
        return self._emit(
            reader,
            source,
            plans,
            output_format=output_format,
            detection=detection,
            mode="chapters",
            pdf_dir=pdf_dir,
            output=Path(output_dir) if output_dir is not None else None,
            chunk_size=None,
        )

    def split_by_pages(
        self,
        input_path: str | Path,
        output_dir: str | Path | None = None,
        chunk_size: int = 99,
        output_format: OutputFormat = "pdf",
    ) -> list[Path]:
        """Split a PDF into fixed-size page chunks.

        Args:
            input_path: Path to the input PDF.
            output_dir: Directory for PDF chunks, or a JSON/Markdown path.
            chunk_size: Number of pages per chunk.
            output_format: ``pdf`` (default), ``json``, or ``markdown``.

        Returns:
            Paths of files written.
        """
        self._check_format(output_format)
        if chunk_size < 1:
            raise ValueError("Pages per chunk must be a positive integer")

        source = self._existing_pdf(input_path)
        if output_dir is None:
            pdf_dir = source.parent / f"{source.stem}_pages"
        else:
            pdf_dir = Path(output_dir)
        if output_format == "pdf":
            pdf_dir.mkdir(parents=True, exist_ok=True)

        reader = self._open_reader(source)
        total_pages = len(reader.pages)
        self.log(f"Processing {source.name} ({total_pages} pages)")

        plans = self._page_plans(total_pages, chunk_size, source.stem)
        self.log(f"Creating {len(plans)} chunks of up to {chunk_size} pages each")
        return self._emit(
            reader,
            source,
            plans,
            output_format=output_format,
            detection="pages",
            mode="pages",
            pdf_dir=pdf_dir,
            output=Path(output_dir) if output_dir is not None else None,
            chunk_size=chunk_size,
        )

    def _emit(
        self,
        reader: PdfReader,
        source: Path,
        plans: list[ChapterChunk],
        output_format: OutputFormat,
        detection: DetectionMethod,
        mode: Literal["chapters", "pages"],
        pdf_dir: Path,
        output: Path | None,
        chunk_size: int | None,
    ) -> list[Path]:
        self.last_detection = detection
        if output_format == "pdf":
            written = self._write_pdfs(reader, source, plans, pdf_dir, mode, len(plans))
            noun = "chapter chunks" if mode == "chapters" else "chunks"
            self.log(f"\nSuccessfully created {len(written)} {noun} in: {pdf_dir}")
            return written

        payload_chapters = [self._chapter_record(reader, plan) for plan in plans]
        destination = self._single_file_path(source, output, output_format, mode)
        page_count = len(reader.pages)
        if output_format == "json":
            self._write_json(
                destination, source, page_count, mode, detection, chunk_size, payload_chapters
            )
        else:
            self._write_markdown(
                destination, source, page_count, mode, detection, chunk_size, payload_chapters
            )
        self.log(f"\nSuccessfully wrote {len(plans)} chapters to: {destination}")
        return [destination]

    def _write_pdfs(
        self,
        reader: PdfReader,
        source: Path,
        plans: list[ChapterChunk],
        pdf_dir: Path,
        mode: Literal["chapters", "pages"],
        total_chunks: int,
    ) -> list[Path]:
        written: list[Path] = []
        label = "chapter" if mode == "chapters" else "chunk"
        for plan in plans:
            writer = PdfWriter()
            for page_index in range(plan.start_page - 1, plan.end_page):
                writer.add_page(reader.pages[page_index])
            writer.add_outline_item(title=plan.title, page_number=0)
            if mode == "chapters":
                subject = f"Chapter {plan.index}: {plan.title}"
            else:
                subject = f"PDF chunk {plan.index} of {total_chunks}"
            writer.add_metadata(
                {
                    "/Title": f"{source.stem} - {plan.title}",
                    "/Subject": subject,
                    "/Creator": CREATOR,
                    "/Producer": PRODUCER,
                }
            )
            output_path = pdf_dir / plan.filename
            try:
                with output_path.open("wb") as output_file:
                    writer.write(output_file)
            except Exception as exc:
                self.log(f"Error writing {label} {plan.index}: {exc}")
                continue
            written.append(output_path)
            self.log(f"Created: {plan.filename} ({plan.page_count} pages)")
        return written

    def _write_json(
        self,
        destination: Path,
        source: Path,
        page_count: int,
        mode: str,
        detection: str,
        chunk_size: int | None,
        chapters: list[dict[str, Any]],
    ) -> None:
        payload = {
            "tool": "pdf-chapter-chunker",
            "version": __version__,
            "source": source.name,
            "page_count": page_count,
            "mode": mode,
            "detection": detection,
            "pages_per_chunk": chunk_size if detection == "pages" else None,
            "chapters": chapters,
        }
        destination.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _write_markdown(
        self,
        destination: Path,
        source: Path,
        page_count: int,
        mode: str,
        detection: str,
        chunk_size: int | None,
        chapters: list[dict[str, Any]],
    ) -> None:
        lines = [
            f"# {source.stem}",
            "",
            f"- Source: {source.name}",
            f"- Pages: {page_count}",
            f"- Mode: {mode}",
            f"- Detection: {detection}",
            f"- Tool: pdf-chapter-chunker {__version__}",
        ]
        if detection == "pages" and chunk_size is not None:
            lines.append(f"- Pages per chunk: {chunk_size}")
        lines.extend(["", ""])
        parts = ["\n".join(lines).rstrip() + "\n"]
        for chapter in chapters:
            title = str(chapter["title"]).replace("\n", " ")
            start_page = chapter["start_page"]
            end_page = chapter["end_page"]
            if start_page == end_page:
                page_line = f"Page {start_page}."
            else:
                page_line = f"Pages {start_page}-{end_page}."
            parts.append(
                "\n".join(
                    [
                        f"## {chapter['index']}. {title}",
                        "",
                        page_line,
                        "",
                        str(chapter["text"]),
                        "",
                    ]
                )
            )
        destination.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")

    def _chapter_record(self, reader: PdfReader, plan: ChapterChunk) -> dict[str, Any]:
        texts: list[str] = []
        for page_index in range(plan.start_page - 1, plan.end_page):
            try:
                extracted = reader.pages[page_index].extract_text() or ""
            except Exception:
                extracted = ""
            cleaned = extracted.strip()
            if cleaned:
                texts.append(cleaned)
        return {
            "index": plan.index,
            "title": plan.title,
            "filename": plan.filename,
            "start_page": plan.start_page,
            "end_page": plan.end_page,
            "page_count": plan.page_count,
            "text": "\n\n".join(texts),
        }

    def _plans_from_entries(
        self, entries: list[tuple[str, int]], total_pages: int
    ) -> list[ChapterChunk]:
        plans: list[ChapterChunk] = []
        for index, (title, start_page) in enumerate(entries):
            if index + 1 < len(entries):
                end_page_number = entries[index + 1][1] - 1
            else:
                end_page_number = total_pages
            start_idx = max(0, start_page - 1)
            end_idx = min(total_pages, end_page_number)
            if start_idx >= end_idx:
                continue
            plans.append(
                ChapterChunk(
                    index=index + 1,
                    title=title,
                    start_page=start_idx + 1,
                    end_page=end_idx,
                    filename=f"{index + 1:03d}_{self.sanitize_filename(title)}.pdf",
                )
            )
        return plans

    def _page_plans(self, total_pages: int, chunk_size: int, base_name: str) -> list[ChapterChunk]:
        plans: list[ChapterChunk] = []
        start = 0
        chunk_num = 1
        while start < total_pages:
            end = min(start + chunk_size, total_pages)
            title = f"Chunk {chunk_num:03d} (Pages {start + 1}-{end})"
            plans.append(
                ChapterChunk(
                    index=chunk_num,
                    title=title,
                    start_page=start + 1,
                    end_page=end,
                    filename=f"{base_name}_chunk_{chunk_num:03d}.pdf",
                )
            )
            start = end
            chunk_num += 1
        return plans

    def _single_file_path(
        self,
        source: Path,
        output: Path | None,
        output_format: OutputFormat,
        mode: Literal["chapters", "pages"],
    ) -> Path:
        suffix = ".json" if output_format == "json" else ".md"
        filename = f"{source.stem}_{mode}{suffix}"
        if output is None:
            return source.parent / filename
        allowed = {suffix}
        if output_format == "markdown":
            allowed.add(".markdown")
        if output.suffix.lower() in allowed:
            output.parent.mkdir(parents=True, exist_ok=True)
            return output
        output.mkdir(parents=True, exist_ok=True)
        return output / filename

    def _chapters_directory(self, source: Path, output_dir: str | Path | None) -> Path:
        if output_dir is None:
            return source.parent / f"{source.stem}_chapters"
        return Path(output_dir) / f"{source.stem}_chapters"

    def _existing_pdf(self, input_path: str | Path) -> Path:
        source = Path(input_path)
        if not source.exists():
            raise FileNotFoundError(f"Input file not found: {source}")
        return source

    def _open_reader(self, source: Path) -> PdfReader:
        try:
            return PdfReader(str(source))
        except Exception as exc:
            raise Exception(f"Error reading PDF: {exc}") from exc

    def _log_entries(self, entries: list[tuple[str, int]]) -> None:
        self.log(f"Found {len(entries)} chapter entries:")
        for title, page in entries[:10]:
            self.log(f"  - {title} (page {page})")
        if len(entries) > 10:
            self.log(f"  ... and {len(entries) - 10} more")

    @staticmethod
    def _check_format(output_format: str) -> None:
        if output_format not in OUTPUT_FORMATS:
            raise ValueError(f"Unsupported output format: {output_format}")
