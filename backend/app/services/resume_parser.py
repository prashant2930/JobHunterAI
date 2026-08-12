from abc import ABC, abstractmethod
import io
import os
import tempfile
import logging
from pypdf import PdfReader
import docx2txt

logger = logging.getLogger("jobhunter")

class BaseExtractor(ABC):
    """
    Interface for document text extraction.
    """
    @abstractmethod
    def extract_text(self, file_bytes: bytes) -> str:
        pass


class PDFExtractor(BaseExtractor):
    """
    Extracts text from PDF documents using pypdf locally.
    """
    def extract_text(self, file_bytes: bytes) -> str:
        try:
            pdf_file = io.BytesIO(file_bytes)
            reader = PdfReader(pdf_file)
            text_parts = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"pypdf extraction failed: {e}", exc_info=True)
            raise ValueError(f"Unreadable PDF document: {e}")


class DOCXExtractor(BaseExtractor):
    """
    Extracts text from DOCX documents using docx2txt locally.
    """
    def extract_text(self, file_bytes: bytes) -> str:
        temp_file_path = None
        try:
            # docx2txt requires a file path on disk, we save to a secure temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
                temp_file.write(file_bytes)
                temp_file_path = temp_file.name
            
            text = docx2txt.process(temp_file_path)
            return text or ""
        except Exception as e:
            logger.error(f"docx2txt extraction failed: {e}", exc_info=True)
            raise ValueError(f"Unreadable DOCX document: {e}")
        finally:
            # Securely clean up the temporary file immediately
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception as ex:
                    logger.warning(f"Failed to remove temporary file {temp_file_path}: {ex}")


class DocumentExtractor:
    """
    Unified manager to coordinate file validation and text extraction.
    """
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        Cleans extracted text by removing excessive whitespaces and structural noise.
        """
        if not text:
            return ""
        # Split into lines, clean whitespace, skip completely empty lines
        lines = [line.strip() for line in text.splitlines()]
        cleaned_lines = [line for line in lines if line]
        return "\n".join(cleaned_lines)

    @classmethod
    def extract(cls, filename: str, file_bytes: bytes) -> str:
        """
        Validates file type and extracts raw text.
        """
        # Determine file type based on extension
        ext = os.path.splitext(filename)[1].lower()
        
        if ext == ".pdf":
            extractor = PDFExtractor()
        elif ext in [".docx", ".doc"]:
            extractor = DOCXExtractor()
        else:
            logger.error(f"File upload attempt with unsupported extension: {ext}")
            raise ValueError(f"Unsupported file type '{ext}'. Only PDF and DOCX files are permitted.")
            
        logger.info(f"Extracting text locally from uploaded file: {filename}")
        raw_text = extractor.extract_text(file_bytes)
        
        cleaned_text = cls.clean_text(raw_text)
        
        if not cleaned_text.strip():
            logger.error(f"Extracted text was empty for file: {filename}")
            raise ValueError("The uploaded document is empty or unreadable.")
            
        return cleaned_text
