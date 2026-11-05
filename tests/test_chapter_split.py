"""Tests for chapter detection and PDF splitting."""

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pypdf import PdfReader, PdfWriter

from pdf_chapter_chunker import PDFChunker, __version__, main


def write_text_pdf(path, pages):
    """Write a tiny text PDF. ``pages`` is a list of page strings."""

    def escape(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def content_stream(text):
        ops = ["BT /F1 12 Tf 72 740 Td"]
        for index, line in enumerate(text.split("\n")):
            if index:
                ops.append("0 -16 Td")
            ops.append(f"({escape(line)}) Tj")
        ops.append("ET")
        stream = "\n".join(ops)
        return f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"

    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        3: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids = []
    next_id = 4
    for text in pages:
        page_id = next_id
        content_id = next_id + 1
        next_id += 2
        objects[page_id] = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        )
        objects[content_id] = content_stream(text)
        kids.append(f"{page_id} 0 R")
    objects[2] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(kids)}] >>"

    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for obj_id in range(1, next_id):
        offsets[obj_id] = len(out)
        out += f"{obj_id} 0 obj\n{objects[obj_id]}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {next_id}\n".encode()
    out += b"0000000000 65535 f \n"
    for obj_id in range(1, next_id):
        out += f"{offsets[obj_id]:010d} 00000 n \n".encode()
    out += (
        f"trailer << /Size {next_id} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ).encode()
    Path(path).write_bytes(out)


def write_blank_pdf(path, page_count, outlines=None):
    """Create a blank PDF.

    ``outlines`` items are ``(title, page_index)`` or
    ``(title, page_index, parent_title)`` for a nested bookmark.
    """
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=200, height=200)
    parents = {}
    for spec in outlines or []:
        parent = parents[spec[2]] if len(spec) == 3 else None
        parents[spec[0]] = writer.add_outline_item(spec[0], spec[1], parent=parent)
    with open(path, "wb") as handle:
        writer.write(handle)


def page_counts(paths):
    counts = []
    for path in paths:
        counts.append(len(PdfReader(str(path)).pages))
    return counts


class TocParseTests(unittest.TestCase):
    def setUp(self):
        self.chunker = PDFChunker(verbose=False)

    def test_parses_common_toc_lines(self):
        text = "\n".join([
            "Table of Contents",
            "Introduction .......... 1",
            "Chapter 1: Getting Started ..... 3",
            "1.2 Advanced Topics .......... 5",
            "Chapter 2 Advanced 10",
            "Appendix A 145",
            "Part II Further Reading 200",
        ])
        self.assertEqual(
            self.chunker.extract_toc_from_text(text),
            [
                ("Introduction", 1),
                ("Chapter 1: Getting Started", 3),
                ("1.2 Advanced Topics", 5),
                ("Chapter 2 Advanced", 10),
                ("Appendix A", 145),
                ("Part II Further Reading", 200),
            ],
        )

    def test_numbered_sections_require_a_contents_heading(self):
        without = "1.2 Getting Started 23\n2 Methods 40"
        self.assertEqual(self.chunker.extract_toc_from_text(without), [])
        with_heading = "Contents\n" + without
        self.assertEqual(
            self.chunker.extract_toc_from_text(with_heading),
            [("1.2 Getting Started", 23), ("2 Methods", 40)],
        )

    def test_prose_and_years_are_not_chapters(self):
        text = "\n".join([
            "This chapter explains widgets on page 3",
            "Copyright 2024",
            "See section 12",
            "Introduction to the material 4",
            "part of the story 8",
        ])
        self.assertEqual(self.chunker.extract_toc_from_text(text), [])

    def test_duplicate_lines_are_collapsed(self):
        text = "Introduction .......... 4\nIntroduction .......... 4"
        self.assertEqual(
            self.chunker.extract_toc_from_text(text),
            [("Introduction", 4)],
        )


class FilenameTests(unittest.TestCase):
    def setUp(self):
        self.chunker = PDFChunker(verbose=False)

    def test_replaces_invalid_characters_and_limits_length(self):
        title = 'Report: Q1 <draft> ' + ("very long " * 10)
        safe = self.chunker.sanitize_filename(title, max_length=30)
        self.assertNotIn(":", safe)
        self.assertNotIn("<", safe)
        self.assertLessEqual(len(safe), 30)
        self.assertFalse(safe.endswith(" ") or safe.endswith("."))

    def test_reserved_windows_names_are_prefixed(self):
        self.assertEqual(self.chunker.sanitize_filename("CON"), "chapter_CON")

    def test_empty_title_gets_a_fallback_name(self):
        self.assertEqual(self.chunker.sanitize_filename("..."), "chapter")


class SplitTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)
        self.chunker = PDFChunker(verbose=False)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_bookmarks_define_chapter_ranges_and_keep_front_matter(self):
        source = self.dir / "manual.pdf"
        write_blank_pdf(
            source,
            6,
            outlines=[
                ("Chapter 1: Getting Started", 2),
                ("1.1 Nested detail", 3, "Chapter 1: Getting Started"),
                ("Chapter 2: Advanced", 4),
            ],
        )
        chunks = self.chunker.split_by_chapters(source)
        names = [path.name for path in chunks]
        self.assertEqual(
            names,
            [
                "001_Front matter.pdf",
                "002_Chapter 1_ Getting Started.pdf",
                "003_Chapter 2_ Advanced.pdf",
            ],
        )
        self.assertEqual(page_counts(chunks), [2, 2, 2])
        self.assertTrue(str(chunks[0]).endswith("manual_chapters/001_Front matter.pdf"))
        # Nested bookmark is not its own file.
        self.assertFalse(any("Nested" in name for name in names))
        first = PdfReader(str(chunks[1]))
        self.assertIn("Chapter 1: Getting Started", str(first.outline))

    def test_bookmarks_win_over_conflicting_text(self):
        source = self.dir / "book.pdf"
        write_text_pdf(source, [
            "Table of Contents\nWrong Chapter ..... 1",
            "body",
            "body",
            "body",
        ])
        reader = PdfReader(str(source))
        writer = PdfWriter()
        writer.append(reader)
        writer.add_outline_item("Real Start", 0)
        writer.add_outline_item("Real Middle", 2)
        with open(source, "wb") as handle:
            writer.write(handle)

        chunks = self.chunker.split_by_chapters(source)
        self.assertEqual(
            [path.name for path in chunks],
            ["001_Real Start.pdf", "002_Real Middle.pdf"],
        )
        self.assertEqual(page_counts(chunks), [2, 2])

    def test_unusable_bookmarks_fall_through_to_the_text_toc(self):
        source = self.dir / "notes.pdf"
        write_text_pdf(source, [
            "Contents\nIntroduction .......... 1\nResults ..... 3",
            "page two",
            "page three",
            "page four",
        ])

        class StaleBookmarks(PDFChunker):
            def extract_outline_entries(self, reader):
                return [("Ghost", 9999)]

        chunks = StaleBookmarks(verbose=False).split_by_chapters(source)
        self.assertEqual(
            [path.name for path in chunks],
            ["001_Introduction.pdf", "002_Results.pdf"],
        )

    def test_text_toc_splits_when_the_pdf_has_no_bookmarks(self):
        source = self.dir / "notes.pdf"
        write_text_pdf(source, [
            "Contents\nIntroduction .......... 1\nMethods ..... 3\nResults ..... 5",
            "page two",
            "page three",
            "page four",
            "page five",
            "page six",
        ])
        chunks = self.chunker.split_by_chapters(source)
        self.assertEqual(
            [path.name for path in chunks],
            ["001_Introduction.pdf", "002_Methods.pdf", "003_Results.pdf"],
        )
        self.assertEqual(page_counts(chunks), [2, 2, 2])
        self.assertEqual(sum(page_counts(chunks)), 6)

    def test_prose_falls_back_to_page_chunks_outside_the_chapters_folder(self):
        source = self.dir / "essay.pdf"
        write_text_pdf(source, [
            "This chapter explains widgets on page 3",
            "Copyright 2024",
            "See section 12",
            "Introduction to the material 4",
        ])
        chunks = self.chunker.split_by_chapters(source, chunk_size=3)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(all(path.parent.name == "essay_pages" for path in chunks))
        self.assertFalse((self.dir / "essay_chapters").exists())
        self.assertEqual(page_counts(chunks), [3, 1])
        self.assertEqual(chunks[0].name, "essay_chunk_001.pdf")

    def test_explicit_output_directory_is_not_nested(self):
        source = self.dir / "book.pdf"
        write_blank_pdf(source, 3, outlines=[("Intro", 0), ("Next", 2)])
        target = self.dir / "my_chunks"
        chunks = self.chunker.split_by_chapters(source, output_dir=target)
        self.assertTrue(all(path.parent == target for path in chunks))
        self.assertEqual(page_counts(chunks), [2, 1])

    def test_page_mode_remainder_and_custom_directory(self):
        source = self.dir / "long.pdf"
        write_blank_pdf(source, 5)
        target = self.dir / "out"
        chunks = self.chunker.split_by_pages(source, output_dir=target, chunk_size=2)
        self.assertEqual(page_counts(chunks), [2, 2, 1])
        self.assertEqual(
            [path.name for path in chunks],
            ["long_chunk_001.pdf", "long_chunk_002.pdf", "long_chunk_003.pdf"],
        )

    def test_rejects_non_positive_chunk_size(self):
        source = self.dir / "book.pdf"
        write_blank_pdf(source, 1)
        with self.assertRaises(ValueError):
            self.chunker.split_by_pages(source, chunk_size=0)

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            self.chunker.split_by_chapters(self.dir / "missing.pdf")

    def test_encrypted_pdf_has_a_clear_error(self):
        source = self.dir / "secret.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.encrypt("secret")
        with open(source, "wb") as handle:
            writer.write(handle)
        with self.assertRaises(ValueError) as caught:
            self.chunker.split_by_chapters(source)
        self.assertIn("encrypted", str(caught.exception).lower())

    def test_same_page_bookmarks_do_not_emit_empty_chapters(self):
        source = self.dir / "dup.pdf"
        write_blank_pdf(source, 4, outlines=[("First", 0), ("Also first", 0), ("Later", 2)])
        chunks = self.chunker.split_by_chapters(source)
        self.assertEqual([path.name for path in chunks], ["001_First.pdf", "002_Later.pdf"])
        self.assertEqual(page_counts(chunks), [2, 2])


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_version_matches_package_version(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "pdf_chapter_chunker.py"), "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(__version__, result.stdout)

    def test_size_must_be_positive(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "pdf_chapter_chunker.py"), "book.pdf", "--size", "0"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("positive", result.stderr.lower())

    def test_quiet_success_prints_nothing(self):
        source = self.dir / "book.pdf"
        write_blank_pdf(source, 2, outlines=[("Only", 0)])
        buffer = io.StringIO()
        stdout = sys.stdout
        sys.stdout = buffer
        try:
            code = main([str(source), "--quiet", "--output", str(self.dir / "out")])
        finally:
            sys.stdout = stdout
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue(), "")
        self.assertEqual(len(list((self.dir / "out").glob("*.pdf"))), 1)

    def test_missing_file_returns_one(self):
        stderr = sys.stderr
        sys.stderr = io.StringIO()
        try:
            code = main([str(self.dir / "nope.pdf")])
        finally:
            sys.stderr = stderr
        self.assertEqual(code, 1)

    def test_pyproject_entry_point(self):
        try:
            import tomllib
        except ModuleNotFoundError:
            self.skipTest("tomllib unavailable")
        with open(ROOT / "pyproject.toml", "rb") as handle:
            project = tomllib.load(handle)["project"]
        self.assertEqual(project["scripts"]["pdf-chunker"], "pdf_chapter_chunker:main")
        self.assertIn("pypdf", " ".join(project["dependencies"]))


if __name__ == "__main__":
    unittest.main()
