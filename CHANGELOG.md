# Changelog

All notable changes to PDF Chapter Chunker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-11-25

### Added
- `pyproject.toml` packaging and the `pdf-chunker` console script (`python -m pdf_chapter_chunker` works too)
- Type hints across the package
- PDF outline (bookmark) splitting when the text table of contents does not match
- Heading detection for PDFs that have no outline: "Chapter 1" lines, split titles, and short large-type titles
- `--format json` and `--format markdown` (PDF remains the default)
- Pytest suite that generates small PDFs in `tests/` (no downloaded books)
- GitHub Actions CI for Python 3.10–3.13, Ruff, and mypy

### Changed
- Runtime dependency is now `pypdf>=6` and Python `>=3.10`
- `setup.py` and `requirements.txt` are replaced by `pyproject.toml`

### Unchanged by default
- Chapter mode, 99-page chunks, output folder names, and PDF metadata layout
- Text table-of-contents patterns. An in-range contents hit still wins over outlines and headings
- When chapter mode finds nothing, PDF chunks are still written under `<name>_chapters/`

## [2.0.0] - 2025-01-29

### Added
- **Smart Chapter Detection**: Automatically extracts table of contents using multiple regex patterns
- **Object-Oriented Architecture**: Clean `PDFChunker` class for better maintainability
- **Command Line Interface**: Full argparse integration with comprehensive options
- **Multiple TOC Formats**: Support for various table of contents patterns and numbering systems
- **Intelligent Filename Sanitization**: Safe filename generation from chapter titles
- **Rich Metadata**: Bookmarks and metadata in generated PDF chunks
- **Quiet Mode**: Option to suppress verbose output
- **Fallback Strategy**: Automatic switch to page-based chunking when no TOC found
- **Comprehensive Documentation**: Detailed README with examples and troubleshooting
- **Open Source Structure**: MIT license, setup.py, requirements.txt

### Improved
- **Error Handling**: Robust error handling with graceful degradation
- **Performance**: Efficient memory usage for large documents
- **User Experience**: Clear progress indicators and informative output
- **Code Quality**: Clean, documented, and maintainable codebase

### Technical Details
- Searches first 25 pages for table of contents (configurable)
- Supports 5+ different TOC patterns including numbered and titled chapters
- Creates organized folder structures (`{book_name}_chapters/` or `{book_name}_pages/`)
- Sequential numbering with descriptive filenames
- Maximum filename length protection for cross-platform compatibility

### Breaking Changes
- Complete rewrite from original script
- New command line interface (backward compatibility maintained)
- Changed default behavior to chapter-based chunking

## [1.0.0] - Initial Release

### Added
- Basic PDF chunking functionality
- Page-based splitting
- Simple command line interface
