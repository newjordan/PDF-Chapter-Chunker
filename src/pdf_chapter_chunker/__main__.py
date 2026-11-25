"""Allow ``python -m pdf_chapter_chunker``."""

from __future__ import annotations

import sys

from pdf_chapter_chunker.cli import main

if __name__ == "__main__":
    sys.exit(main())
