"""
PDF parsing service to extract text from resume PDFs
"""
import PyPDF2
import io
import re
from typing import Dict, Any


class PDFParsingService:
    """Service for parsing PDF resumes"""
    
    def __init__(self):
        pass
    
    def parse_pdf(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Extract text from PDF bytes
        
        Args:
            pdf_bytes: PDF file content as bytes
            
        Returns:
            Dict with parsed data including raw text
        """
        try:
            # Create PDF reader from bytes
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            # Extract text from all pages
            text_content = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
            
            # Combine all text
            raw_text = "\n".join(text_content)
            
            # Clean the text
            cleaned_text = self._clean_text(raw_text)
            
            return {
                "success": True,
                "raw_text": cleaned_text,
                "page_count": len(pdf_reader.pages),
                "error": None
            }
            
        except Exception as e:
            return {
                "success": False,
                "raw_text": "",
                "page_count": 0,
                "error": str(e)
            }
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text
        
        Args:
            text: Raw text from PDF
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep useful punctuation
        text = re.sub(r'[^\w\s@.,;:()\-/+#]', '', text)
        
        # Fix common OCR issues
        text = text.replace('', '')  # Remove null characters
        
        # Normalize line breaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove multiple consecutive newlines
        text = re.sub(r'\n+', '\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def extract_contact_info(self, text: str) -> Dict[str, Any]:
        """
        Extract contact information from text
        
        Args:
            text: Resume text
            
        Returns:
            Dict with email, phone, location
        """
        contact = {
            "email": None,
            "phone": None,
            "location": None
        }
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            contact["email"] = emails[0]
        
        # Extract phone
        phone_patterns = [
            r'\+?\d{1,3}?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US format
            r'\+?\d{1,3}[-.\s]?\d{10}',  # International
            r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}'  # (123) 456-7890
        ]
        for pattern in phone_patterns:
            phones = re.findall(pattern, text)
            if phones:
                contact["phone"] = phones[0]
                break
        
        # Extract location from the header area first to avoid matching tech terms in body
        header_text = text[:400]
        location_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}),\s*([A-Z]{2}|[A-Z][a-z]+)\b'
        locations = re.findall(location_pattern, header_text)
        blacklist_first = {"Chain", "LangChain", "API", "MCP"}
        blacklist_second = {"MC", "MCP", "API", "LLM", "AWS", "GCP", "OCI", "CI", "CD"}
        for city, region in locations:
            if city in blacklist_first or region in blacklist_second:
                continue
            contact["location"] = f"{city}, {region}"
            break

        # Fallback: explicit "City Country" patterns commonly found in resume headers
        if not contact["location"]:
            fallback_patterns = [
                r'\b([A-Z][a-z]+)\s+(Singapore|India|USA|United States|Canada|UK|Australia)\b',
                r'\b(Singapore|India|USA|United States|Canada|UK|Australia)\b'
            ]
            for pattern in fallback_patterns:
                match = re.search(pattern, header_text)
                if not match:
                    continue
                if len(match.groups()) == 2:
                    contact["location"] = f"{match.group(1)}, {match.group(2)}"
                else:
                    contact["location"] = match.group(1)
                break
        
        return contact
    
    def extract_sections(self, text: str) -> Dict[str, str]:
        """
        Split resume into sections
        
        Args:
            text: Resume text
            
        Returns:
            Dict with section names as keys and content as values
        """
        sections = {}
        
        # Common section headers
        section_headers = [
            "experience", "work experience", "professional experience",
            "education", "academic background",
            "skills", "technical skills", "core competencies",
            "projects", "personal projects",
            "certifications", "certificates",
            "summary", "profile", "objective",
            "awards", "honors", "achievements"
        ]
        
        # Create pattern to match section headers
        header_pattern = '|'.join([f"({header})" for header in section_headers])
        pattern = re.compile(f"\\b({header_pattern})\\b", re.IGNORECASE)
        
        # Find all section headers
        matches = list(pattern.finditer(text))
        
        if not matches:
            return {"full_text": text}
        
        # Extract content between headers
        for i, match in enumerate(matches):
            section_name = match.group(0).lower()
            start_pos = match.end()
            
            # End position is start of next section or end of text
            if i < len(matches) - 1:
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(text)
            
            section_content = text[start_pos:end_pos].strip()
            sections[section_name] = section_content
        
        return sections


# Global instance
pdf_parser = PDFParsingService()
