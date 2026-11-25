"""Command-line interface for PDF Chapter Chunker."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from pdf_chapter_chunker._version import __version__
from pdf_chapter_chunker.chunker import PDFChunker


def build_parser() -> argparse.ArgumentParser:
    """Return the command-line parser. Defaults match the historical tool."""
    parser = argparse.ArgumentParser(
        prog="pdf-chunker",
        description="PDF Chapter Chunker - Intelligent PDF splitting tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s book.pdf                          # Split by chapters into PDFs
  %(prog)s book.pdf --mode chapters          # Same as the default
  %(prog)s book.pdf --mode pages             # Split by pages (99 per chunk)
  %(prog)s book.pdf --mode pages --size 50   # Split by pages (50 per chunk)
  %(prog)s book.pdf --output ./chunks        # Custom output directory
  %(prog)s book.pdf --format json            # Chapter metadata and text as JSON
  %(prog)s book.pdf --format markdown -o book.md
  %(prog)s book.pdf --quiet                  # Run without verbose output
        """,
    )
    parser.add_argument("input_pdf", help="Path to input PDF file")
    parser.add_argument(
        "--mode",
        choices=["chapters", "pages"],
        default="chapters",
        help="Chunking mode: chapters (default) or pages",
    )
    parser.add_argument("--output", "-o", help="Output directory, or a .json/.md file path")
    parser.add_argument(
        "--format",
        choices=["pdf", "json", "markdown"],
        default="pdf",
        help="Output format (default: pdf)",
    )
    parser.add_argument(
        "--size",
        "-s",
        type=int,
        default=99,
        help="Pages per chunk (pages mode only, default: 99)",
    )
    parser.add_argument("--quiet", "-q", action="store_true", help="Run without verbose output")
    parser.add_argument("--version", action="version", version=f"PDF Chapter Chunker {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Split a PDF from command-line arguments.

    Args:
        argv: Arguments, excluding the program name. Defaults to ``sys.argv``.

    Returns:
        Process exit code. ``0`` on success, ``1`` on a handled error.
    """
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        chunker = PDFChunker(verbose=not args.quiet)
        if args.mode == "chapters":
            chunks = chunker.split_by_chapters(args.input_pdf, args.output, args.format)
        else:
            chunks = chunker.split_by_pages(args.input_pdf, args.output, args.size, args.format)

        if not args.quiet:
            if args.format == "pdf":
                print(f"\n✅ Successfully split PDF into {len(chunks)} chunks!")
            elif chunks:
                print(f"\n✅ Wrote {args.format} output to {chunks[0]}")
        return 0
    except FileNotFoundError as exc:
        print(f"❌ Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"❌ Error: {exc}", file=sys.stderr)
        return 1
