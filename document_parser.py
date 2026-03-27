import PyPDF2
import pdfplumber
from docx import Document
from typing import Optional
import io
import logging

logger = logging.getLogger(__name__)

class DocumentParser:
    @staticmethod
    async def parse_pdf(file_bytes: bytes) -> str:
        """Extract text from PDF with layout preservation"""
        text_content = []
        
        try:
            # First try pdfplumber (better for tables/layout)
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_content.append(text)
                
                full_text = "\n".join(text_content)
                
                # Quality check - if too little text, might be scanned image
                if len(full_text.strip()) < 100:
                    logger.warning("PDF might be scanned image - text extraction poor")
                    # Here you could integrate OCR (tesseract) as fallback
                    
                return full_text
                
        except Exception as e:
            logger.error(f"pdfplumber failed: {e}, trying PyPDF2")
            # Fallback to PyPDF2
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as e2:
                raise Exception(f"PDF parsing failed: {e2}")

    @staticmethod
    async def parse_docx(file_bytes: bytes) -> str:
        """Extract text from Word document"""
        try:
            doc = Document(io.BytesIO(file_bytes))
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            return "\n".join(paragraphs)
        except Exception as e:
            raise Exception(f"DOCX parsing failed: {e}")

    @staticmethod
    def detect_quality_issues(text: str) -> list:
        """Detect if document quality is insufficient for AI extraction"""
        issues = []
        
        if len(text) < 200:
            issues.append("Dokument scheint leer oder gescannt zu sein (zu wenig Text)")
        
        if text.count('@') < 1:
            issues.append("Keine E-Mail-Adresse erkannt - möglicherweise Bild-basiertes PDF")
            
        # Check for German characters (indicates encoding issues if missing)
        german_chars = sum(1 for c in text if c in 'äöüÄÖÜß')
        if german_chars == 0 and len(text) > 1000:
            issues.append("Keine deutschen Umlaute gefunden - möglicherweise Kodierungsfehler")
            
        return issues
