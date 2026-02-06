"""
File parsers for various document formats (PDF, DOCX, CSV, TXT, PPTX, XLSX).
"""

import os
from typing import List, Dict, Any
from pathlib import Path

import pandas as pd
from pypdf import PdfReader
from docx import Document
from pptx import Presentation

from src.utils.logging import get_logger, trace_function

logger = get_logger(__name__)


class DocumentParser:
    """
    Universal document parser supporting multiple file formats.
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf": "parse_pdf",
        ".txt": "parse_txt",
        ".docx": "parse_docx",
        ".doc": "parse_docx",
        ".csv": "parse_csv",
        ".xlsx": "parse_excel",
        ".xls": "parse_excel",
        ".pptx": "parse_pptx",
        ".ppt": "parse_pptx",
    }

    @trace_function("parse_document")
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a document and extract its content.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with parsed content and metadata
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        extension = path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type: {extension}. "
                f"Supported: {list(self.SUPPORTED_EXTENSIONS.keys())}"
            )

        parser_method = getattr(self, self.SUPPORTED_EXTENSIONS[extension])

        try:
            content = parser_method(file_path)
            metadata = self._extract_metadata(path)

            result = {
                "content": content,
                "metadata": metadata,
                "file_path": str(path),
                "file_type": extension,
            }

            logger.info(
                f"Successfully parsed {extension} file",
                file_path=str(path),
                content_length=len(content),
            )

            return result

        except Exception as e:
            logger.error(f"Failed to parse file: {e}", file_path=str(path))
            raise

    @staticmethod
    def parse_pdf(file_path: str) -> str:
        """Parse PDF file"""
        reader = PdfReader(file_path)
        text_parts = []

        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text.strip():
                text_parts.append(f"[Page {page_num + 1}]\n{text}")

        return "\n\n".join(text_parts)

    @staticmethod
    def parse_txt(file_path: str) -> str:
        """Parse text file"""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    @staticmethod
    def parse_docx(file_path: str) -> str:
        """Parse DOCX file"""
        doc = Document(file_path)
        text_parts = []

        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)

        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells)
                if row_text.strip():
                    text_parts.append(row_text)

        return "\n\n".join(text_parts)

    @staticmethod
    def parse_csv(file_path: str) -> str:
        """Parse CSV file"""
        df = pd.read_csv(file_path)

        # Convert to readable text format
        text_parts = [
            f"CSV File Summary:",
            f"Rows: {len(df)}",
            f"Columns: {', '.join(df.columns)}",
            "",
            "Data Preview:",
            df.head(10).to_string(index=False),
        ]

        # Add column statistics for numeric columns
        numeric_cols = df.select_dtypes(include=["number"]).columns
        if len(numeric_cols) > 0:
            text_parts.extend(["", "Numeric Column Statistics:"])
            text_parts.append(df[numeric_cols].describe().to_string())

        return "\n".join(text_parts)

    @staticmethod
    def parse_excel(file_path: str) -> str:
        """Parse Excel file"""
        excel_file = pd.ExcelFile(file_path)
        text_parts = [f"Excel File: {len(excel_file.sheet_names)} sheets"]

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            text_parts.extend(
                [
                    "",
                    f"[Sheet: {sheet_name}]",
                    f"Rows: {len(df)}",
                    f"Columns: {', '.join(df.columns)}",
                    "",
                    "Data Preview:",
                    df.head(10).to_string(index=False),
                ]
            )

        return "\n".join(text_parts)

    @staticmethod
    def parse_pptx(file_path: str) -> str:
        """Parse PowerPoint file"""
        prs = Presentation(file_path)
        text_parts = []

        for slide_num, slide in enumerate(prs.slides):
            slide_text = [f"[Slide {slide_num + 1}]"]

            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_text.append(shape.text)

            if len(slide_text) > 1:  # Has content beyond header
                text_parts.append("\n".join(slide_text))

        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_metadata(path: Path) -> Dict[str, Any]:
        """Extract file metadata"""
        stat = path.stat()
        return {
            "file_name": path.name,
            "file_size": stat.st_size,
            "created_time": stat.st_ctime,
            "modified_time": stat.st_mtime,
            "extension": path.suffix,
        }

    @trace_function("chunk_text")
    def chunk_text(
        self, text: str, chunk_size: int = 1000, chunk_overlap: int = 200
    ) -> List[str]:
        """
        Split text into chunks for embedding.

        Args:
            text: Text to chunk
            chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between chunks

        Returns:
            List of text chunks
        """
        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind(".")
                last_newline = chunk.rfind("\n")
                break_point = max(last_period, last_newline)

                if break_point > chunk_size * 0.5:  # Only if reasonable
                    end = start + break_point + 1
                    chunk = text[start:end]

            chunks.append(chunk.strip())
            start = end - chunk_overlap

        logger.debug(f"Split text into {len(chunks)} chunks")
        return chunks


# Global parser instance
_document_parser = None


def get_document_parser() -> DocumentParser:
    """Get global document parser instance"""
    global _document_parser
    if _document_parser is None:
        _document_parser = DocumentParser()
    return _document_parser


def load_documents_from_directory(directory: str) -> List:
    """
    Load all supported documents from a directory.

    Returns list of LangChain Document objects.
    """
    from langchain_core.documents import Document

    if not os.path.exists(directory):
        logger.warning(f"Directory does not exist: {directory}")
        return []

    parser = get_document_parser()
    documents = []

    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = Path(file_path).suffix.lower()

            if file_ext in DocumentParser.SUPPORTED_EXTENSIONS:
                try:
                    parsed = parser.parse(file_path)
                    doc = Document(
                        page_content=parsed["text"],
                        metadata=parsed["metadata"]
                    )
                    documents.append(doc)
                    logger.debug(f"Loaded: {file}")
                except Exception as e:
                    logger.warning(f"Failed to parse {file}: {e}")

    logger.info(f"Loaded {len(documents)} documents from {directory}")
    return documents
