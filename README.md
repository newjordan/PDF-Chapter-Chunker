# PDF Chapter Chunker

Split a PDF into one file per chapter. The tool reads top-level bookmarks when the file has them, otherwise it looks for a table of contents in the first 25 pages. If it finds neither, it falls back to fixed-size page chunks.

## Install

Python 3.8 or newer.

Install the `pdf-chunker` command from a checkout:

```bash
git clone https://github.com/newjordan/PDF-Chapter-Chunker.git
cd PDF-Chapter-Chunker
pip install .
```

To run the script without installing the command:

```bash
pip install -r requirements.txt
python pdf_chapter_chunker.py --help
```

## Quickstart

```bash
pdf-chunker book.pdf
pdf-chunker book.pdf --mode pages --size 50
pdf-chunker book.pdf --output ./chunks
pdf-chunker book.pdf --quiet
```

The same flags work with `python pdf_chapter_chunker.py`.

## What it does

Chapter mode, in order:

1. **Bookmarks.** Top-level PDF bookmarks become chapters. Each chunk starts on the page that bookmark opens. Nested bookmarks stay inside the parent chapter.
2. **Table-of-contents text.** If there are no usable bookmarks, the first 25 pages are scanned for lines like these:
   - `Introduction .......... 15`
   - `Chapter 1: Getting Started 23`
   - `Appendix A 145`
   - `1.2 Methods 40` (only when the page text contains the word "contents")
3. **Page chunks.** If that scan finds nothing, the PDF is split into fixed chunks (default 99 pages) in `<name>_pages/`. `--size` applies to this fallback as well as to `--mode pages`.

Pages before the first chapter are written to `001_Front matter.pdf`, so the split still covers the whole file. Other chapters run from their start page up to the page before the next chapter. The last chapter runs through the end of the file.

Each output PDF gets a bookmark and document info (`Title`, `Subject`, `Creator`) for that chapter or chunk. Filenames are numbered, stripped of characters that are illegal on common filesystems, and truncated.

Default folders, created next to the input file:

```text
manual_chapters/
├── 001_Front matter.pdf
├── 002_Introduction.pdf
└── 003_Chapter 1_ Getting Started.pdf

manual_pages/
├── manual_chunk_001.pdf
└── manual_chunk_002.pdf
```

`--output DIR` writes those files directly into `DIR`.

## What it does not do

- It does not OCR scanned pages. A scan with no text layer and no bookmarks falls back to page chunks.
- Text table-of-contents numbers are used as PDF page numbers. If printed page 1 is not PDF page 1, add bookmarks or the split will land on the wrong pages. Bookmark mode uses the destination page stored in the file, so it does not have this problem.
- It does not split on nested bookmarks.
- It does not open password-protected PDFs.
- `--size` does not shorten a chapter that is already longer than that many pages. It only affects page mode and the chapter-mode fallback.

## CLI

| Option | Description | Default |
| --- | --- | --- |
| `input_pdf` | PDF to split | required |
| `--mode` | `chapters` or `pages` | `chapters` |
| `--output`, `-o` | Directory that receives the chunk files | `<name>_chapters` or `<name>_pages` next to the input |
| `--size`, `-s` | Pages per chunk in page mode, and when chapter mode falls back | `99` |
| `--quiet`, `-q` | Suppress progress output | off |
| `--version` | Print the version | |

`--size` must be a positive integer.

## Examples

Chapter mode when the PDF has bookmarks:

```bash
pdf-chunker Technical_Manual.pdf
```

```text
Processing Technical_Manual.pdf (120 pages)
Splitting on top-level bookmarks:
  - Front matter (page 1)
  - Introduction (page 5)
  - Chapter 1: Getting Started (page 12)
  - Chapter 2: Advanced Topics (page 40)
Created: 001_Front matter.pdf (4 pages)
Created: 002_Introduction.pdf (7 pages)
Created: 003_Chapter 1_ Getting Started.pdf (28 pages)
Created: 004_Chapter 2_ Advanced Topics.pdf (81 pages)

Successfully created 4 chapter chunks in: Technical_Manual_chapters

✅ Successfully split PDF into 4 chunks!
```

Page mode:

```bash
pdf-chunker Large_Document.pdf --mode pages --size 25
```

```text
Processing Large_Document.pdf (300 pages)
Creating 12 chunks of up to 25 pages each
Created: Large_Document_chunk_001.pdf (25 pages)
...

✅ Successfully split PDF into 12 chunks!
```

## Development

```bash
pip install -e .
python -m unittest discover -s tests -t .
```

TOC line patterns live in `pdf_chapter_chunker.py` (`_DOT_LEADER`, `_CHAPTER_LINE`, `_NUMBERED_LINE`).

## License

MIT. See [LICENSE](LICENSE).
