# PDF Chapter Chunker

[![CI](https://github.com/newjordan/PDF-Chapter-Chunker/actions/workflows/ci.yml/badge.svg)](https://github.com/newjordan/PDF-Chapter-Chunker/actions/workflows/ci.yml)

Split a PDF into chapters. The default is still one PDF file per chapter, with a bookmark and document metadata on each file. The same split can be written as JSON or Markdown instead.

Chapter mode looks for structure in this order:

1. **Text table of contents** in the first 25 pages, using the same patterns as v2.0. When a contents line points at a real page, that split is used.
2. **PDF outline** (the bookmark tree) when the text contents do not match. Top-level bookmarks are chapters. Nested bookmarks stay inside the parent. A single root bookmark with several children uses the children.
3. **Heading detection** when the file has no outline. The detector looks for lines such as `Chapter 1`, `Chapter 1` followed by a short title, `Appendix A`, numbered titles in a larger font, and other short large-type lines at the top of a page. Repeated running headers are ignored.
4. **99-page chunks** when none of the above find chapters. In chapter mode those PDFs are still written to `<name>_chapters/`.

A line that is only `Chapter 1` is not treated as a contents entry. The number is the chapter number, so heading detection uses the page where that line actually appears.

Pages before the first chapter are omitted, matching previous versions.

## Install

Python 3.10 or newer.

```bash
git clone https://github.com/newjordan/PDF-Chapter-Chunker.git
cd PDF-Chapter-Chunker
pip install .
```

That installs the `pdf-chunker` command. From a checkout you can also run:

```bash
python -m pdf_chapter_chunker --help
```

Development tools (pytest, reportlab for generated fixtures, Ruff, and mypy):

```bash
pip install -e ".[dev]"
pytest
```

Tests build small PDFs in memory. They do not download books.

## Usage

PDF output is the default.

```bash
# Split by chapters into PDFs
pdf-chunker book.pdf

# Same thing, explicit mode
pdf-chunker book.pdf --mode chapters

# Fixed page chunks (99 pages, or pass --size)
pdf-chunker book.pdf --mode pages
pdf-chunker book.pdf --mode pages --size 50

# Choose the output directory
pdf-chunker book.pdf --output ./chunks

# One JSON document with titles, page ranges, and extracted text
pdf-chunker book.pdf --format json

# One Markdown document
pdf-chunker book.pdf --format markdown -o book.md

# Suppress progress logs
pdf-chunker book.pdf --quiet
```

`python -m pdf_chapter_chunker` accepts the same arguments.

### Chapter PDFs

```bash
pdf-chunker Technical_Manual.pdf
```

```text
Processing Technical_Manual.pdf (450 pages)
Extracting table of contents from first chunk...
Found 23 chapter entries:
  - Introduction (page 5)
  - Chapter 1: Getting Started (page 12)
  ...

Created: 001_Introduction.pdf (7 pages)
Created: 002_Chapter 1_ Getting Started.pdf (33 pages)

Successfully created 23 chapter chunks in: Technical_Manual_chapters

✅ Successfully split PDF into 23 chunks!
```

```text
Technical_Manual_chapters/
├── 001_Introduction.pdf
├── 002_Chapter 1_ Getting Started.pdf
└── ...
```

Each file's title is `<stem> - <chapter>`, the subject is `Chapter N: <chapter>`, and the PDF outline contains the chapter title. The creator is `PDF Chapter Chunker v2.1.0`.

When you pass `--output`, chapter PDFs go in `<output>/<stem>_chapters/`. Page-mode PDFs go directly in `--output`, or in `<stem>_pages/` when you omit it.

### Page PDFs

```bash
pdf-chunker Large_Document.pdf --mode pages --size 25
```

```text
Large_Document_pages/
├── Large_Document_chunk_001.pdf
├── Large_Document_chunk_002.pdf
└── ...
```

### JSON

```bash
pdf-chunker book.pdf --format json -o book.json
```

```json
{
  "tool": "pdf-chapter-chunker",
  "version": "2.1.0",
  "source": "book.pdf",
  "page_count": 120,
  "mode": "chapters",
  "detection": "toc",
  "pages_per_chunk": null,
  "chapters": [
    {
      "index": 1,
      "title": "Introduction",
      "filename": "001_Introduction.pdf",
      "start_page": 5,
      "end_page": 11,
      "page_count": 7,
      "text": "..."
    }
  ]
}
```

`detection` is `toc`, `outline`, `headings`, or `pages`. `filename` is the PDF name that chapter mode would have used. With no `--output`, the file is `<stem>_chapters.json` or `<stem>_pages.json`.

### Markdown

```bash
pdf-chunker book.pdf --format markdown
```

```markdown
# book

- Source: book.pdf
- Pages: 120
- Mode: chapters
- Detection: headings
- Tool: pdf-chapter-chunker 2.1.0

## 1. Introduction

Pages 5-11.

...
```

## Options

| Option | Description | Default |
| --- | --- | --- |
| `input_pdf` | Input PDF | Required |
| `--mode` | `chapters` or `pages` | `chapters` |
| `--format` | `pdf`, `json`, or `markdown` | `pdf` |
| `--output`, `-o` | Directory, or a `.json` / `.md` file | Beside the input |
| `--size`, `-s` | Pages per chunk in page mode | `99` |
| `--quiet`, `-q` | Suppress progress logs | Off |
| `--version` | Print the version | |

`--size` must be a positive integer. It applies to `--mode pages`. The chapter-mode page fallback stays at 99 pages.

## Contents patterns

These lines still match when the first 25 pages contain `contents`, `table of contents`, `index`, or `chapter`:

```text
Chapter 1: Introduction .............. 15
1.1 Getting Started .................. 23
Section 2.3 Advanced Topics .......... 67
Appendix A 145
Bibliography ......................... 200
```

The page number is used as a PDF page number, not a printed page number. A contents hit inside the document wins over bookmarks and over heading detection.

Lines that only say `Chapter 1` or `Chapter 2` are left for heading detection, because that pattern used to read the chapter number as a page number.

## Library

```python
from pdf_chapter_chunker import PDFChunker

chunker = PDFChunker()
paths = chunker.split_by_chapters("book.pdf")
print(chunker.last_detection)  # toc, outline, headings, or pages

chunker.split_by_chapters("book.pdf", output_format="json")
chunker.split_by_pages("book.pdf", chunk_size=50)
```

`split_by_chapters` and `split_by_pages` default to `output_format="pdf"`.

## Troubleshooting

**No table of contents found.** The tool tries bookmarks, then headings, then 99-page chunks. A scanned PDF with no text layer cannot yield headings.

**Contents points at the wrong pages.** The text scanner uses the number printed on the contents line as the PDF page index. Bookmarks are more reliable. They are used when that contents scan does not produce an in-range chapter.

**Encrypted PDFs.** The reader error is reported and the command exits with status 1.

**Filenames.** `<>:"/\|?*` are replaced, whitespace is collapsed, and long titles are cut on a word boundary.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
mypy src
```

CI runs those checks on Python 3.10, 3.11, 3.12, and 3.13. New contents patterns belong on `PDFChunker.toc_patterns`.

## License

MIT. See [LICENSE](LICENSE).

Built with [pypdf](https://github.com/py-pdf/pypdf).
