#!/usr/bin/env python3
"""
PDF Chapter Chunker - Intelligent PDF splitting tool
Splits PDFs into chapters based on table of contents or fixed page chunks

Repository: https://github.com/newjordan/PDF-Chapter-Chunker
License: MIT
Version: 2.0.0
"""

import os
import sys
import re
import argparse
from pypdf import PdfReader, PdfWriter
from pathlib import Path


class PDFChunker:
    """Main PDF chunking class with chapter detection and splitting capabilities."""
    
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.toc_patterns = [
            r'(.+?)\s+\.{2,}\s*(\d+)',  # Chapter title ... page_number
            r'(.+?)\s+(\d+)$',          # Chapter title page_number (end of line)
            r'(\d+\.?\d*)\s+(.+?)\s+(\d+)',  # Number Chapter title page_number
            r'Chapter\s+(\d+)[:\s]+(.+?)\s+(\d+)',  # Chapter X: Title page_number
            r'(\d+\.\d+)\s+(.+?)\s+(\d+)',  # 1.1 Chapter title page_number
        ]
        self.toc_indicators = ['table of contents', 'contents', 'index', 'chapter']
    
    def log(self, message):
        """Print message if verbose mode is enabled."""
        if self.verbose:
            print(message)
    
    def extract_toc_from_text(self, text):
        """
        Extract table of contents from text using common patterns.
        
        Args:
            text (str): Raw text extracted from PDF pages
            
        Returns:
            list: List of (chapter_title, page_number) tuples
        """
        toc_entries = []
        
        lines = text.split('\n')
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
        seen = set()
        unique_entries = []
        for title, page in toc_entries:
            if (title, page) not in seen:
                seen.add((title, page))
                unique_entries.append((title, page))
        
        return sorted(unique_entries, key=lambda x: x[1])
    
    def extract_toc_from_pdf(self, pdf_path, max_pages=25):
        """
        Extract table of contents from the first chunk of a PDF.
        
        Args:
            pdf_path (Path): Path to the PDF file
            max_pages (int): Maximum pages to search for TOC
            
        Returns:
            list: List of (chapter_title, page_number) tuples
        """
        reader = PdfReader(str(pdf_path))
        toc_text = ""
        
        # Extract text from first few pages to find TOC
        search_pages = min(max_pages, len(reader.pages))
        
        for page_num in range(search_pages):
            try:
                page_text = reader.pages[page_num].extract_text()
                toc_text += f"\n--- Page {page_num + 1} ---\n{page_text}\n"
            except Exception as e:
                self.log(f"Warning: Could not extract text from page {page_num + 1}: {e}")
                continue
        
        # Look for TOC indicators
        toc_found = any(indicator in toc_text.lower() for indicator in self.toc_indicators)
        
        if not toc_found:
            self.log("Warning: No clear table of contents found in first chunk")
            return []
        
        return self.extract_toc_from_text(toc_text)
    
    def sanitize_filename(self, title, max_length=50):
        """
        Clean chapter title for use as filename.
        
        Args:
            title (str): Chapter title
            max_length (int): Maximum filename length
            
        Returns:
            str: Sanitized filename
        """
        # Remove invalid filename characters
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)
        # Remove extra whitespace and dots
        safe_title = re.sub(r'\s+', ' ', safe_title).strip()
        safe_title = safe_title.replace('..', '.')
        # Limit length
        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length].rsplit(' ', 1)[0]
        return safe_title
    
    def split_by_chapters(self, input_path, output_dir=None):
        """
        Split a PDF into chapters based on table of contents.
        
        Args:
            input_path (str): Path to input PDF file
            output_dir (str): Directory to save chunks
            
        Returns:
            list: List of created chunk file paths
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Set output directory with chapters subfolder
        if output_dir is None:
            output_dir = input_path.parent / f"{input_path.stem}_chapters"
        else:
            output_dir = Path(output_dir) / f"{input_path.stem}_chapters"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Read the PDF
        try:
            reader = PdfReader(str(input_path))
            total_pages = len(reader.pages)
            self.log(f"Processing {input_path.name} ({total_pages} pages)")
        except Exception as e:
            raise Exception(f"Error reading PDF: {e}")
        
        # Extract table of contents
        self.log("Extracting table of contents from first chunk...")
        toc_entries = self.extract_toc_from_pdf(input_path)
        
        if not toc_entries:
            self.log("No table of contents found, falling back to page-based chunking")
            return self.split_by_pages(input_path, output_dir, 99)
        
        self.log(f"Found {len(toc_entries)} chapter entries:")
        for title, page in toc_entries[:10]:  # Show first 10
            self.log(f"  - {title} (page {page})")
        
        if len(toc_entries) > 10:
            self.log(f"  ... and {len(toc_entries) - 10} more")
        
        # Create chapter chunks
        chunks_created = []
        base_name = input_path.stem
        
        for i, (chapter_title, start_page) in enumerate(toc_entries):
            # Determine end page (start of next chapter or end of book)
            if i + 1 < len(toc_entries):
                end_page = toc_entries[i + 1][1] - 1
            else:
                end_page = total_pages
            
            # Adjust for 0-indexing
            start_page_idx = max(0, start_page - 1)
            end_page_idx = min(total_pages, end_page)
            
            if start_page_idx >= end_page_idx:
                continue
            
            # Create new PDF writer for this chapter
            writer = PdfWriter()
            
            # Add pages to chapter
            for page_num in range(start_page_idx, end_page_idx):
                writer.add_page(reader.pages[page_num])
            
            # Clean chapter title for filename
            safe_title = self.sanitize_filename(chapter_title)
            
            # Add bookmark for this chapter
            writer.add_outline_item(chapter_title, 0)
            
            # Add metadata
            writer.add_metadata({
                '/Title': f"{base_name} - {chapter_title}",
                '/Subject': f"Chapter {i + 1}: {chapter_title}",
                '/Creator': 'PDF Chapter Chunker v2.0',
                '/Producer': 'PDF Chapter Chunker'
            })
            
            # Generate output filename
            output_filename = f"{i + 1:03d}_{safe_title}.pdf"
            output_path = output_dir / output_filename
            
            # Write the chapter
            try:
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
                
                chunks_created.append(output_path)
                pages_in_chapter = end_page_idx - start_page_idx
                self.log(f"Created: {output_filename} ({pages_in_chapter} pages)")
                
            except Exception as e:
                self.log(f"Error writing chapter {i + 1}: {e}")
                continue
        
        self.log(f"\nSuccessfully created {len(chunks_created)} chapter chunks in: {output_dir}")
        return chunks_created
    
    def split_by_pages(self, input_path, output_dir=None, chunk_size=99):
        """
        Split a PDF into fixed-size page chunks.
        
        Args:
            input_path (str): Path to input PDF file
            output_dir (str): Directory to save chunks
            chunk_size (int): Number of pages per chunk
            
        Returns:
            list: List of created chunk file paths
        """
        input_path = Path(input_path)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Set output directory
        if output_dir is None:
            output_dir = input_path.parent / f"{input_path.stem}_pages"
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Read the input PDF
        try:
            reader = PdfReader(str(input_path))
            total_pages = len(reader.pages)
            self.log(f"Processing {input_path.name} ({total_pages} pages)")
        except Exception as e:
            raise Exception(f"Error reading PDF: {e}")
        
        # Calculate number of chunks
        num_chunks = (total_pages + chunk_size - 1) // chunk_size
        self.log(f"Creating {num_chunks} chunks of up to {chunk_size} pages each")
        
        base_name = input_path.stem
        chunks_created = []
        
        for chunk_num in range(num_chunks):
            start_page = chunk_num * chunk_size
            end_page = min(start_page + chunk_size, total_pages)
            
            # Create new PDF writer for this chunk
            writer = PdfWriter()
            
            # Add pages to chunk
            for page_num in range(start_page, end_page):
                writer.add_page(reader.pages[page_num])
            
            # Add bookmark for this chunk
            chunk_title = f"Chunk {chunk_num + 1:03d} (Pages {start_page + 1}-{end_page})"
            writer.add_outline_item(chunk_title, 0)
            
            # Add metadata
            writer.add_metadata({
                '/Title': f"{base_name} - {chunk_title}",
                '/Subject': f"PDF chunk {chunk_num + 1} of {num_chunks}",
                '/Creator': 'PDF Chapter Chunker v2.0',
                '/Producer': 'PDF Chapter Chunker'
            })
            
            # Generate output filename
            output_filename = f"{base_name}_chunk_{chunk_num + 1:03d}.pdf"
            output_path = output_dir / output_filename
            
            # Write the chunk
            try:
                with open(output_path, 'wb') as output_file:
                    writer.write(output_file)
                
                chunks_created.append(output_path)
                self.log(f"Created: {output_filename} ({end_page - start_page} pages)")
                
            except Exception as e:
                self.log(f"Error writing chunk {chunk_num + 1}: {e}")
                continue
        
        self.log(f"\nSuccessfully created {len(chunks_created)} chunks in: {output_dir}")
        return chunks_created


def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(
        description='PDF Chapter Chunker - Intelligent PDF splitting tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s book.pdf                          # Split by chapters (default)
  %(prog)s book.pdf --mode chapters          # Split by chapters explicitly
  %(prog)s book.pdf --mode pages             # Split by pages (99 per chunk)
  %(prog)s book.pdf --mode pages --size 50   # Split by pages (50 per chunk)
  %(prog)s book.pdf --output ./chunks        # Custom output directory
  %(prog)s book.pdf --quiet                  # Run without verbose output
        """
    )
    
    parser.add_argument('input_pdf', help='Path to input PDF file')
    parser.add_argument('--mode', choices=['chapters', 'pages'], default='chapters',
                       help='Chunking mode: chapters (default) or pages')
    parser.add_argument('--output', '-o', help='Output directory for chunks')
    parser.add_argument('--size', '-s', type=int, default=99,
                       help='Pages per chunk (pages mode only, default: 99)')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Run without verbose output')
    parser.add_argument('--version', action='version', version='PDF Chapter Chunker 2.0.0')
    
    args = parser.parse_args()
    
    try:
        chunker = PDFChunker(verbose=not args.quiet)
        
        if args.mode == 'chapters':
            chunks = chunker.split_by_chapters(args.input_pdf, args.output)
        else:
            chunks = chunker.split_by_pages(args.input_pdf, args.output, args.size)
        
        if not args.quiet:
            print(f"\n✅ Successfully split PDF into {len(chunks)} chunks!")
        
        return 0
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())