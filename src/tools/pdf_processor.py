"""
PDF Processor using pymupdf4llm

This module extracts content from PDF files in a format optimized for LLMs.
pymupdf4llm is specifically designed to produce markdown that LLMs can understand,
including proper handling of:
- Tables (converted to markdown tables)
- Images (extracted and embedded as base64 or saved to files)
- Multi-column layouts
- Headers and footings detection

Why pymupdf4llm over alternatives?
- pdfplumber: Good for tables, but no LLM-optimized output
- PyPDF2: Text only, loses structure
- marker-pdf: Great for complex PDFs but slower
- pymupdf4llm: Best balance of speed, accuracy, and LLM-ready output
"""

import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import hashlib


@dataclass
class ExtractedContent:
    """Standardized output from content processors"""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    images: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    source_hash: str = ""
    extraction_timestamp: datetime = field(default_factory=datetime.now)


class PDFProcessor:
    """
    Process PDF files and extract LLM-ready content.

    Usage:
        processor = PDFProcessor()
        content = processor.process("document.pdf")
        print(content.text)  # Markdown formatted text
        print(content.images)  # List of extracted images
    """

    def __init__(
        self,
        extract_images: bool = True,
        embed_images_as_base64: bool = True,
        image_dpi: int = 150,
        max_pages: Optional[int] = None
    ):
        """
        Initialize the PDF processor.

        Args:
            extract_images: Whether to extract images from the PDF
            embed_images_as_base64: If True, embed images as base64 in markdown
                                    If False, save to files and reference
            image_dpi: Resolution for image extraction
            max_pages: Maximum pages to process (None = all)
        """
        self.extract_images = extract_images
        self.embed_images = embed_images_as_base64
        self.image_dpi = image_dpi
        self.max_pages = max_pages
        self._pymupdf4llm = None

    def _ensure_pymupdf(self):
        """Lazy import pymupdf4llm"""
        if self._pymupdf4llm is None:
            try:
                import pymupdf4llm
                self._pymupdf4llm = pymupdf4llm
            except ImportError:
                raise ImportError(
                    "pymupdf4llm is not installed. "
                    "Install with: pip install pymupdf4llm"
                )

    def process(self, file_path: str, output_dir: Optional[str] = None) -> ExtractedContent:
        """
        Process a PDF file and extract content.

        Args:
            file_path: Path to the PDF file
            output_dir: Directory to save extracted images (if not embedding)

        Returns:
            ExtractedContent with markdown text and metadata
        """
        self._ensure_pymupdf()

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        # Calculate file hash for deduplication
        with open(file_path, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        # Extract content using pymupdf4llm
        try:
            if self.extract_images and self.embed_images:
                # Embed images as base64 in markdown
                md_text = self._pymupdf4llm.to_markdown(
                    doc=file_path,
                    embed_images=True,
                    dpi=self.image_dpi,
                    pages=list(range(self.max_pages)) if self.max_pages else None
                )
                images = []  # Images are embedded in the markdown
            elif self.extract_images:
                # Save images to files
                if output_dir is None:
                    output_dir = os.path.dirname(file_path)
                os.makedirs(output_dir, exist_ok=True)

                md_text = self._pymupdf4llm.to_markdown(
                    doc=file_path,
                    write_images=True,
                    image_path=output_dir,
                    image_format="png",
                    dpi=self.image_dpi,
                    pages=list(range(self.max_pages)) if self.max_pages else None
                )
                # Find extracted images
                images = self._find_extracted_images(output_dir, file_path)
            else:
                # Text only
                md_text = self._pymupdf4llm.to_markdown(
                    doc=file_path,
                    pages=list(range(self.max_pages)) if self.max_pages else None
                )
                images = []

            # Extract metadata
            import pymupdf
            doc = pymupdf.open(file_path)
            metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "keywords": doc.metadata.get("keywords", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "page_count": doc.page_count,
                "file_path": file_path,
                "file_name": os.path.basename(file_path)
            }
            doc.close()

            # Extract tables (pymupdf4llm converts them to markdown tables)
            tables = self._extract_tables_from_markdown(md_text)

            return ExtractedContent(
                text=md_text,
                metadata=metadata,
                images=images,
                tables=tables,
                source_hash=file_hash
            )

        except Exception as e:
            raise RuntimeError(f"Failed to process PDF: {e}")

    def _find_extracted_images(self, output_dir: str, source_file: str) -> List[Dict[str, Any]]:
        """Find images extracted from the PDF"""
        images = []
        base_name = os.path.splitext(os.path.basename(source_file))[0]

        for filename in os.listdir(output_dir):
            if filename.startswith(base_name) and filename.endswith(('.png', '.jpg', '.jpeg')):
                images.append({
                    "path": os.path.join(output_dir, filename),
                    "filename": filename,
                    "format": os.path.splitext(filename)[1][1:]
                })

        return images

    def _extract_tables_from_markdown(self, md_text: str) -> List[Dict[str, Any]]:
        """
        Find markdown tables in the extracted text.

        Tables in markdown look like:
        | Header 1 | Header 2 |
        |----------|----------|
        | Cell 1   | Cell 2   |
        """
        tables = []
        lines = md_text.split('\n')
        current_table = []
        in_table = False

        for line in lines:
            if '|' in line and line.strip().startswith('|'):
                in_table = True
                current_table.append(line)
            elif in_table and line.strip() == '':
                # End of table
                if len(current_table) > 1:
                    tables.append({
                        "markdown": '\n'.join(current_table),
                        "row_count": len(current_table) - 2  # Exclude header and separator
                    })
                current_table = []
                in_table = False
            elif in_table:
                # Line doesn't look like a table row, end table
                if len(current_table) > 1:
                    tables.append({
                        "markdown": '\n'.join(current_table),
                        "row_count": len(current_table) - 2
                    })
                current_table = []
                in_table = False

        # Don't forget the last table if file ends with one
        if current_table and len(current_table) > 1:
            tables.append({
                "markdown": '\n'.join(current_table),
                "row_count": len(current_table) - 2
            })

        return tables

    def extract_text_only(self, file_path: str) -> str:
        """
        Quick extraction of text only (no images, no structure).

        Useful for quick content analysis or when you don't need
        the full markdown output.
        """
        self._ensure_pymupdf()

        import pymupdf
        doc = pymupdf.open(file_path)
        text_parts = []

        for page_num, page in enumerate(doc):
            if self.max_pages and page_num >= self.max_pages:
                break
            text_parts.append(page.get_text())

        doc.close()
        return '\n\n'.join(text_parts)
