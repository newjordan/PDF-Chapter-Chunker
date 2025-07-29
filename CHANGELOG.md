# Changelog

All notable changes to PDF Chapter Chunker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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