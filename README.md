# PDF Chapter Chunker 📚

An intelligent PDF splitting tool that can automatically detect chapters from a table of contents and split PDFs into digestible, topic-focused chunks.

## ✨ Features

- **🔍 Smart Chapter Detection**: Automatically extracts table of contents and splits by chapters
- **📄 Page-Based Chunking**: Fallback to fixed-page chunks when no TOC is found
- **📁 Organized Output**: Creates clean folder structures with descriptive filenames
- **🏷️ Rich Metadata**: Adds bookmarks and metadata to generated PDFs
- **🛡️ Error Handling**: Robust error handling and graceful fallbacks
- **📋 Multiple TOC Formats**: Supports various table of contents patterns
- **⚡ Fast Processing**: Efficient PDF processing with minimal memory usage

## 🚀 Installation

### Prerequisites
- Python 3.7 or higher
- pip package manager

### Install Dependencies
```bash
pip install pypdf
```

### Download the Script
```bash
# Clone the repository
git clone https://github.com/newjordan/PDF-Chapter-Chunker.git
cd PDF-Chapter-Chunker

# Or download directly
wget https://raw.githubusercontent.com/newjordan/PDF-Chapter-Chunker/main/pdf_chapter_chunker.py
```

## 📖 Usage

### Basic Usage
```bash
# Split by chapters (default mode)
python pdf_chapter_chunker.py book.pdf

# Split by chapters explicitly
python pdf_chapter_chunker.py book.pdf --mode chapters

# Split by pages (99 pages per chunk)
python pdf_chapter_chunker.py book.pdf --mode pages

# Split by pages with custom chunk size
python pdf_chapter_chunker.py book.pdf --mode pages --size 50
```

### Advanced Options
```bash
# Custom output directory
python pdf_chapter_chunker.py book.pdf --output ./my_chunks

# Quiet mode (minimal output)
python pdf_chapter_chunker.py book.pdf --quiet

# Get help
python pdf_chapter_chunker.py --help
```

## 🎯 Examples

### Chapter Mode (Recommended)
```bash
python pdf_chapter_chunker.py "Technical_Manual.pdf"
```

**Output:**
```
Processing Technical_Manual.pdf (450 pages)
Extracting table of contents from first chunk...
Found 23 chapter entries:
  - Introduction (page 5)
  - Chapter 1: Getting Started (page 12)
  - Chapter 2: Advanced Topics (page 45)
  ...

Created: 001_Introduction.pdf (7 pages)
Created: 002_Chapter 1_ Getting Started.pdf (33 pages)
Created: 003_Chapter 2_ Advanced Topics.pdf (28 pages)
...

✅ Successfully split PDF into 23 chunks!
```

### Page Mode
```bash
python pdf_chapter_chunker.py "Large_Document.pdf" --mode pages --size 25
```

**Output:**
```
Processing Large_Document.pdf (300 pages)
Creating 12 chunks of up to 25 pages each

Created: Large_Document_chunk_001.pdf (25 pages)
Created: Large_Document_chunk_002.pdf (25 pages)
...

✅ Successfully split PDF into 12 chunks!
```

## 📂 Output Structure

### Chapter Mode
```
book_name_chapters/
├── 001_Introduction.pdf
├── 002_Chapter 1_ Getting Started.pdf
├── 003_Chapter 2_ Advanced Concepts.pdf
└── ...
```

### Page Mode
```
book_name_pages/
├── book_name_chunk_001.pdf
├── book_name_chunk_002.pdf
├── book_name_chunk_003.pdf
└── ...
```

## 🔧 How It Works

### Chapter Detection
The tool analyzes the first 25 pages of a PDF to find table of contents using multiple patterns:

- `Chapter Title ... Page Number`
- `1.1 Section Title ... 45`
- `Chapter 1: Title 23`
- And more formats...

### Smart Filename Generation
- Removes invalid characters (`<>:"/\\|?*`)
- Limits filename length for compatibility
- Preserves meaningful chapter titles
- Sequential numbering for organization

### Fallback Strategy
If no table of contents is detected:
1. Warns the user
2. Automatically switches to page-based chunking
3. Uses sensible defaults (99 pages per chunk)

## 🎨 Supported TOC Formats

The tool recognizes various table of contents patterns:

```
✅ Chapter 1: Introduction .............. 15
✅ 1.1 Getting Started .................. 23  
✅ Section 2.3 Advanced Topics .......... 67
✅ Appendix A 145
✅ Bibliography ......................... 200
```

## ⚙️ Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `input_pdf` | Path to input PDF file | Required |
| `--mode` | Chunking mode: `chapters` or `pages` | `chapters` |
| `--output, -o` | Output directory | Same as input |
| `--size, -s` | Pages per chunk (page mode only) | `99` |
| `--quiet, -q` | Suppress verbose output | `False` |
| `--help` | Show help message | - |
| `--version` | Show version | - |

## 🐛 Troubleshooting

### Common Issues

**"No table of contents found"**
- The PDF may not have a standard TOC format
- Tool will automatically fall back to page-based chunking
- Try adjusting the search depth or patterns

**"Error reading PDF"**
- Ensure the PDF file is not corrupted
- Check file permissions
- Try with a different PDF

**Memory issues with large PDFs**
- The tool processes pages efficiently
- For extremely large files (>1000 pages), consider splitting first

### Debug Mode
Run with verbose output to see detailed processing:
```bash
python pdf_chapter_chunker.py book.pdf  # Verbose by default
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup
```bash
git clone https://github.com/newjordan/PDF-Chapter-Chunker.git
cd PDF-Chapter-Chunker
pip install -r requirements.txt
```

### Adding New TOC Patterns
Edit the `toc_patterns` list in the `PDFChunker` class to support new formats.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [pypdf](https://github.com/py-pdf/pypdf) for PDF processing
- Inspired by the need for better technical document organization
- Thanks to the open source community for feedback and contributions

## 📊 Performance

- **Speed**: Processes ~100 pages per second on modern hardware
- **Memory**: Minimal RAM usage, suitable for large documents
- **Compatibility**: Works with most PDF versions and formats

---

**Made with ❤️ for better document organization**