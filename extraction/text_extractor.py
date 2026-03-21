import os
import re
import json
from typing import Dict, Any
import PyPDF2


class TextInvoiceExtractor:
    """Extract invoice data using PyPDF2 + pattern matching"""
    
    def __init__(self):
        pass
    
    def extract(self, pdf_bytes: bytes, filename: str = "invoice.pdf") -> Dict[str, Any]:
        """Extract text from PDF and parse invoice data"""
        
        # Extract text from PDF
        text = self._extract_text_from_pdf(pdf_bytes)
        
        print(f"Extracted {len(text)} chars from PDF")
        
        # Parse invoice data
        return {
            'raw_text': text[:2000],  # First 2000 chars
            'full_text': text,
            'vendor_name': self._extract_vendor(text),
            'invoice_number': self._extract_invoice_number(text),
            'invoice_date': self._extract_invoice_date(text),
            'due_date': self._extract_due_date(text),
            'total': self._extract_total(text),
            'tax': self._extract_tax(text),
            'currency': self._detect_currency(text),
            'line_items': self._extract_line_items(text)
        }
    
    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF using PyPDF2"""
        try:
            from io import BytesIO
            pdf_file = BytesIO(pdf_bytes)
            reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            return text
        except Exception as e:
            print(f"PDF extraction error: {e}")
            return ""
    
    def _extract_vendor(self, text: str) -> str:
        """Find vendor/company name"""
        lines = text.split('\n')[:40]
        
        # Pattern 1: Lines with company indicators
        for line in lines:
            line = line.strip()
            if any(x in line.lower() for x in ['inc', 'llc', 'ltd', 'corp', 'company']):
                if len(line) > 3 and not line.startswith('$'):
                    return line
        
        # Pattern 2: "From:" or "Sold By:"
        match = re.search(r'(?:from|sold by|bill from)[:\s]+(.+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Pattern 3: First non-empty line that looks like a name
        for line in lines:
            line = line.strip()
            if len(line) > 3 and len(line) < 50 and not any(x in line for x in ['$', 'date', 'invoice']):
                return line
        
        return "Unknown Vendor"
    
    def _extract_invoice_number(self, text: str) -> str:
        """Find invoice number"""
        patterns = [
            r'(?:invoice\s*(?:#|number|no)[:\s]*)([A-Z0-9\-]+)',
            r'(?:inv\.?\s*#?\s*)([A-Z0-9\-]+)',
            r'(?:order\s*(?:#|number)[:\s]*)([A-Z0-9\-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""
    
    def _extract_invoice_date(self, text: str) -> str:
        """Find invoice date"""
        patterns = [
            r'(?:invoice date|date issued)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(?:date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ""
    
    def _extract_due_date(self, text: str) -> str:
        """Find due date"""
        patterns = [
            r'(?:due date|payment due)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(?:due)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return ""
    
    def _extract_total(self, text: str) -> float:
        """Find total amount"""
        patterns = [
            r'(?:total|amount due|balance due|grand total)[:\s]*[$\£\€]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})',
            r'(?:total)[:\s]*[$\£\€]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})'
        ]
        
        amounts = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    amount = float(match.replace(',', ''))
                    if amount > 0:
                        amounts.append(amount)
                except:
                    pass
        
        if amounts:
            return max(amounts)  # Usually total is largest
        
        return 0.0
    
    def _extract_tax(self, text: str) -> float:
        """Find tax amount"""
        patterns = [
            r'(?:tax|vat|gst)[:\s]*[$\£\€]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})',
            r'(?:sales tax)[:\s]*[$\£\€]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except:
                    pass
        
        return 0.0
    
    def _detect_currency(self, text: str) -> str:
        """Detect currency"""
        if '$' in text or 'USD' in text:
            return 'USD'
        if '€' in text or 'EUR' in text:
            return 'EUR'
        if '£' in text or 'GBP' in text:
            return 'GBP'
        return 'USD'
    
    def _extract_line_items(self, text: str) -> list:
        """Extract line items from tables or lists"""
        items = []
        lines = text.split('\n')
        
        # Look for table rows with amounts
        for line in lines:
            # Match patterns like: Description ... $XX.XX or XX.XX
            match = re.search(r'(.+?)\s+(?:[$\£\€])?(\d{1,3}(?:,\d{3})*\.\d{2})\s*$', line)
            if match:
                desc = match.group(1).strip()
                amount = float(match.group(2).replace(',', ''))
                
                # Filter out header/footer lines
                if len(desc) > 5 and not any(x in desc.lower() for x in ['total', 'subtotal', 'tax', 'balance']):
                    items.append({
                        'description': desc[:100],
                        'amount': amount
                    })
        
        return items[:20]


class InvoiceValidator:
    def validate(self, data: Dict) -> tuple:
        errors = []
        
        if not data.get('vendor_name') or data['vendor_name'] == 'Unknown':
            errors.append("Missing vendor name")
        
        if not data.get('total') or data['total'] <= 0:
            errors.append("Invalid or missing total amount")
        
        return (len(errors) == 0, "; ".join(errors))
