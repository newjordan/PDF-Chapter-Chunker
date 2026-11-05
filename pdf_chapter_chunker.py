#!/usr/bin/env python3
"""
PDF Chapter Chunker - split a PDF into chapters or fixed-size page chunks.

Repository: https://github.com/newjordan/PDF-Chapter-Chunker
License: MIT
"""

import argparse
import re
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

__version__ = "2.0.1"


def _count_label(count, singular, plural=None):
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {word}"

_DOT_LEADER = re.compile(
    r"^(?P<title>.+?)\s*(?:\.{2,}|·{2,}|…+)\s*(?P<page>\d+)\s*$"
)
_CHAPTER_LINE = re.compile(
    r"^(?P<title>(?:chapter|appendix|part)\s+"
    r"(?:\d+|[IVXLCDM]+|[A-Z])\b.*?)\s+(?P<page>\d+)\s*$",
    re.IGNORECASE,
)
_NUMBERED_LINE = re.compile(
    r"^(?P<num>\d{1,3}(?:\.\d+){0,4})\.?\s+"
    r"(?P<title>[A-Za-z].+?)\s+(?P<page>\d+)\s*$"
)
_CONTENTS_WORD = re.compile(r"\bcontents\b", re.IGNORECASE)
_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
}


class PDFChunker:
    """Split PDFs by bookmark, table-of-contents text, or fixed page counts."""

    def __init__(self, verbose=True):
        self.verbose = verbose

    def log(self, message):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def extract_outline_entries(self, reader):
        """
        Read top-level PDF bookmarks as (title, page_number) pairs.

        Page numbers are 1-based PDF pages (the page the bookmark opens),
        not printed page numbers. Nested bookmarks are ignored so subsections
        stay inside the parent chapter.
        """
        try:
            outline = reader.outline or []
        except Exception as e:
            self.log(f"Warning: Could not read bookmarks: {e}")
            return []

        entries = []
        for item in outline:
            if isinstance(item, list):
                continue
            title = getattr(item, "title", None)
            if title is None:
                continue
            title = re.sub(r"\s+", " ", str(title)).strip()
            if not title:
                continue
            try:
                page_index = reader.get_destination_page_number(item)
            except Exception:
                continue
            if page_index is None or page_index < 0:
                continue
            entries.append((title, page_index + 1))
        return entries

    def _parse_toc_line(self, line, allow_numbered):
        """Return (title, page) when a line looks like a TOC entry."""
        match = _DOT_LEADER.match(line)
        if match:
            title = match.group("title").strip(" .\t")
            return self._accept_toc_title(title, match.group("page"))

        match = _CHAPTER_LINE.match(line)
        if match:
            title = match.group("title").strip()
            return self._accept_toc_title(title, match.group("page"))

        if allow_numbered:
            match = _NUMBERED_LINE.match(line)
            if match:
                num = match.group("num")
                # A 4-digit bare number is usually a year, not a section.
                if "." not in num and int(num) > 200:
                    return None
                title = f"{num} {match.group('title').strip()}"
                return self._accept_toc_title(title, match.group("page"))
        return None

    def _accept_toc_title(self, title, page):
        if not title or not re.search(r"[A-Za-z]", title) or len(title) > 120:
            return None
        try:
            page_num = int(page)
        except ValueError:
            return None
        if 1 <= page_num <= 10000:
            return (title, page_num)
        return None

    def extract_toc_from_text(self, text):
        """
        Extract table-of-contents entries from plain text.

        Accepts dot-leader lines and Chapter/Appendix/Part lines. Numbered
        section lines (``1.2 Title 23``) count only when the text contains
        the word "contents", so ordinary sentences that end in a number are
        not treated as chapters.

        Args:
            text (str): Raw text extracted from PDF pages

        Returns:
            list: (chapter_title, page_number) tuples sorted by page
        """
        allow_numbered = _CONTENTS_WORD.search(text) is not None
        entries = []
        seen = set()
        for line in text.splitlines():
            line = line.strip()
            if len(line) < 5:
                continue
            parsed = self._parse_toc_line(line, allow_numbered)
            if parsed and parsed not in seen:
                seen.add(parsed)
                entries.append(parsed)
        return sorted(entries, key=lambda item: item[1])

    def extract_toc_from_pdf(self, pdf_path, max_pages=25):
        """
        Scan the first pages of a PDF for a textual table of contents.

        Args:
            pdf_path (Path): Path to the PDF file
            max_pages (int): Maximum pages to search for TOC

        Returns:
            list: (chapter_title, page_number) tuples
        """
        reader = PdfReader(str(pdf_path))
        return self._toc_entries_from_reader(reader, max_pages)

    def _toc_entries_from_reader(self, reader, max_pages=25):
        search_pages = min(max_pages, len(reader.pages))
        chunks = []
        for page_num in range(search_pages):
            try:
                page_text = reader.pages[page_num].extract_text() or ""
            except Exception as e:
                self.log(f"Warning: Could not extract text from page {page_num + 1}: {e}")
                continue
            chunks.append(page_text)
        return self.extract_toc_from_text("\n".join(chunks))

    def sanitize_filename(self, title, max_length=50):
        """
        Clean a chapter title for use as a filename.

        Args:
            title (str): Chapter title
            max_length (int): Maximum filename length

        Returns:
            str: Sanitized filename stem
        """
        safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(title))
        safe_title = re.sub(r"\s+", " ", safe_title).strip(" .")
        safe_title = re.sub(r"\.{2,}", ".", safe_title)
        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length].rsplit(" ", 1)[0].strip(" .")
        if not safe_title:
            safe_title = "chapter"
        if safe_title.split(".", 1)[0].upper() in _RESERVED_NAMES:
            safe_title = f"chapter_{safe_title}"
        return safe_title

    def _open_reader(self, input_path):
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        try:
            reader = PdfReader(str(input_path))
        except Exception as e:
            raise Exception(f"Error reading PDF: {e}") from e
        if reader.is_encrypted:
            raise ValueError(
                "This PDF is encrypted. Password-protected files are not supported."
            )
        return input_path, reader

    def _prepare_entries(self, entries, total_pages):
        """Drop impossible pages, keep the first title for each page, and sort."""
        prepared = []
        seen_pages = set()
        for title, page in entries:
            if not isinstance(page, int) or page < 1 or page > total_pages:
                continue
            if page in seen_pages:
                continue
            title = re.sub(r"\s+", " ", str(title)).strip()
            if not title:
                continue
            seen_pages.add(page)
            prepared.append((title, page))
        prepared.sort(key=lambda item: item[1])
        if prepared and prepared[0][1] > 1:
            prepared.insert(0, ("Front matter", 1))
        return prepared

    def _chapter_output_dir(self, input_path, output_dir):
        if output_dir is None:
            return input_path.parent / f"{input_path.stem}_chapters"
        return Path(output_dir)

    def split_by_chapters(self, input_path, output_dir=None, chunk_size=99):
        """
        Split a PDF into chapters.

        Uses top-level bookmarks when the PDF has them. Otherwise scans the
        first pages for a table of contents. Page numbers in that text are
        treated as PDF page numbers. If neither source yields chapters, falls
        back to :meth:`split_by_pages`.

        Args:
            input_path (str): Path to input PDF file
            output_dir (str): Directory to save chunks. Defaults to
                ``<stem>_chapters`` next to the input file. When provided,
                chunk files are written directly into this directory.
            chunk_size (int): Page size used only if chapter detection fails

        Returns:
            list: Paths of created chunk files
        """
        if chunk_size < 1:
            raise ValueError("chunk size must be a positive integer")

        input_path, reader = self._open_reader(input_path)
        total_pages = len(reader.pages)
        self.log(f"Processing {input_path.name} ({total_pages} pages)")

        outline_entries = self.extract_outline_entries(reader)
        toc_entries = self._prepare_entries(outline_entries, total_pages)
        from_bookmarks = bool(toc_entries)
        if not toc_entries:
            if outline_entries:
                self.log("Bookmarks did not point at pages in this file; scanning the first 25 pages for a table of contents...")
            else:
                self.log("No bookmarks found; scanning the first 25 pages for a table of contents...")
            toc_entries = self._prepare_entries(
                self._toc_entries_from_reader(reader), total_pages
            )
        if not toc_entries:
            self.log("No table of contents found; falling back to page-based chunking")
            return self.split_by_pages(
                input_path, output_dir, chunk_size, reader=reader
            )

        if from_bookmarks:
            self.log("Splitting on top-level bookmarks:")
        else:
            self.log("Splitting on the table of contents:")
        for title, page in toc_entries[:10]:
            self.log(f"  - {title} (page {page})")
        extra = len(toc_entries) - 10
        if extra > 0:
            self.log(f"  ... and {extra} more")

        output_dir = self._chapter_output_dir(input_path, output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        return self._write_chapters(reader, input_path.stem, toc_entries, total_pages, output_dir)

    def _write_chapters(self, reader, base_name, toc_entries, total_pages, output_dir):
        chunks_created = []
        for i, (chapter_title, start_page) in enumerate(toc_entries):
            if i + 1 < len(toc_entries):
                end_page = toc_entries[i + 1][1] - 1
            else:
                end_page = total_pages

            start_page_idx = start_page - 1
            end_page_idx = min(total_pages, end_page)
            if start_page_idx >= end_page_idx:
                continue

            writer = PdfWriter()
            for page_num in range(start_page_idx, end_page_idx):
                writer.add_page(reader.pages[page_num])

            safe_title = self.sanitize_filename(chapter_title)
            writer.add_outline_item(chapter_title, 0)
            writer.add_metadata({
                "/Title": f"{base_name} - {chapter_title}",
                "/Subject": f"Chapter {i + 1}: {chapter_title}",
                "/Creator": f"PDF Chapter Chunker v{__version__}",
                "/Producer": "PDF Chapter Chunker",
            })

            output_filename = f"{i + 1:03d}_{safe_title}.pdf"
            output_path = output_dir / output_filename
            try:
                with open(output_path, "wb") as output_file:
                    writer.write(output_file)
            except Exception as e:
                self.log(f"Error writing chapter {i + 1}: {e}")
                continue

            chunks_created.append(output_path)
            pages_in_chapter = end_page_idx - start_page_idx
            self.log(f"Created: {output_filename} ({_count_label(pages_in_chapter, 'page')})")

        self.log(
            f"\nSuccessfully created {_count_label(len(chunks_created), 'chapter chunk')} in: {output_dir}"
        )
        return chunks_created

    def split_by_pages(self, input_path, output_dir=None, chunk_size=99, reader=None):
        """
        Split a PDF into fixed-size page chunks.

        Args:
            input_path (str): Path to input PDF file
            output_dir (str): Directory to save chunks. Defaults to
                ``<stem>_pages`` next to the input file.
            chunk_size (int): Number of pages per chunk
            reader: Optional already-opened PdfReader

        Returns:
            list: Paths of created chunk files
        """
        if chunk_size < 1:
            raise ValueError("chunk size must be a positive integer")

        input_path = Path(input_path)
        if reader is None:
            input_path, reader = self._open_reader(input_path)
            total_pages = len(reader.pages)
            self.log(f"Processing {input_path.name} ({total_pages} pages)")
        else:
            if not input_path.exists():
                raise FileNotFoundError(f"Input file not found: {input_path}")
            total_pages = len(reader.pages)

        if output_dir is None:
            output_dir = input_path.parent / f"{input_path.stem}_pages"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        num_chunks = (total_pages + chunk_size - 1) // chunk_size if total_pages else 0
        self.log(f"Creating {num_chunks} chunks of up to {chunk_size} pages each")

        base_name = input_path.stem
        chunks_created = []
        for chunk_num in range(num_chunks):
            start_page = chunk_num * chunk_size
            end_page = min(start_page + chunk_size, total_pages)

            writer = PdfWriter()
            for page_num in range(start_page, end_page):
                writer.add_page(reader.pages[page_num])

            chunk_title = f"Chunk {chunk_num + 1:03d} (Pages {start_page + 1}-{end_page})"
            writer.add_outline_item(chunk_title, 0)
            writer.add_metadata({
                "/Title": f"{base_name} - {chunk_title}",
                "/Subject": f"PDF chunk {chunk_num + 1} of {num_chunks}",
                "/Creator": f"PDF Chapter Chunker v{__version__}",
                "/Producer": "PDF Chapter Chunker",
            })

            output_filename = f"{base_name}_chunk_{chunk_num + 1:03d}.pdf"
            output_path = output_dir / output_filename
            try:
                with open(output_path, "wb") as output_file:
                    writer.write(output_file)
            except Exception as e:
                self.log(f"Error writing chunk {chunk_num + 1}: {e}")
                continue

            chunks_created.append(output_path)
            self.log(f"Created: {output_filename} ({_count_label(end_page - start_page, 'page')})")

        self.log(
            f"\nSuccessfully created {_count_label(len(chunks_created), 'chunk')} in: {output_dir}"
        )
        return chunks_created


def _positive_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("size must be a positive integer")
    if parsed < 1:
        raise argparse.ArgumentTypeError("size must be a positive integer")
    return parsed


def main(argv=None):
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(
        description="PDF Chapter Chunker - split a PDF into chapters or page chunks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s book.pdf                          # Chapters from bookmarks or a TOC
  %(prog)s book.pdf --mode pages             # Fixed chunks of 99 pages
  %(prog)s book.pdf --mode pages --size 50   # Fixed chunks of 50 pages
  %(prog)s book.pdf --output ./chunks        # Write chunk files into ./chunks
  %(prog)s book.pdf --quiet                  # Errors only
        """,
    )

    parser.add_argument("input_pdf", help="Path to input PDF file")
    parser.add_argument(
        "--mode",
        choices=["chapters", "pages"],
        default="chapters",
        help="Chunking mode: chapters (default) or pages",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Directory to write chunk files into (default: <name>_chapters or <name>_pages)",
    )
    parser.add_argument(
        "--size",
        "-s",
        type=_positive_int,
        default=99,
        help="Pages per chunk for page mode and for the chapter-mode fallback (default: 99)",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Run without verbose output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"PDF Chapter Chunker {__version__}",
    )

    args = parser.parse_args(argv)

    try:
        chunker = PDFChunker(verbose=not args.quiet)
        if args.mode == "chapters":
            chunks = chunker.split_by_chapters(args.input_pdf, args.output, args.size)
        else:
            chunks = chunker.split_by_pages(args.input_pdf, args.output, args.size)

        if not args.quiet:
            print(f"\n✅ Successfully split PDF into {_count_label(len(chunks), 'chunk')}!")
        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
