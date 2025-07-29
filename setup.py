#!/usr/bin/env python3
"""
Setup script for PDF Chapter Chunker
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="pdf-chapter-chunker",
    version="2.0.0",
    author="newjordan",
    description="An intelligent PDF splitting tool that automatically detects chapters from table of contents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/newjordan/PDF-Chapter-Chunker",
    py_modules=["pdf_chapter_chunker"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business",
        "Topic :: Text Processing",
        "Topic :: Utilities",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "pdf-chunker=pdf_chapter_chunker:main",
        ],
    },
    keywords="pdf, split, chunk, chapter, table-of-contents, document, processing",
    project_urls={
        "Bug Reports": "https://github.com/newjordan/PDF-Chapter-Chunker/issues",
        "Source": "https://github.com/newjordan/PDF-Chapter-Chunker",
        "Documentation": "https://github.com/newjordan/PDF-Chapter-Chunker#readme",
    },
)