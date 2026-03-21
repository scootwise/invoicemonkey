import re
import PyPDF2
from typing import Dict, Any
from io import BytesIO


class LlamaParseExtractor:
    """PDF Invoice extractor using PyPDF2 + pattern matching"""
    
    def extract(self, pdf_bytes: bytes, filename: str = "invoice.pdf") -> Dict[str, Any]:
        """Extract text from PDF and parse invoice data"""
        
        text = self._extract_text_from_pdf(pdf_bytes)
        
        return {
            'raw_text': text[:2000],
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
        pdf_file = BytesIO(pdf_bytes)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    
    def _extract_vendor(self, text: str) -> str:
        lines = text.split('\n')[:40]
        for line in lines:
            line = line.strip()
            if any(x in line.lower() for x in ['inc', 'llc', 'ltd', 'corp']):
                if len(line) > 3 and not line.startswith('$'):
                    return line
        match = re.search(r'(?:from|bill from)[:\s]+(.+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        for line in lines:
            line = line.strip()
            if len(line) > 3 and len(line) < 50:
                return line
        return "Unknown Vendor"
    
    def _extract_invoice_number(self, text: str) -> str:
        match = re.search(r'(?:invoice\s*(?:#|number|no)[:\s]*)([A-Z0-9\-]+)', text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""
    
    def _extract_invoice_date(self, text: str) -> str:
        match = re.search(r'(?:invoice date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""
    
    def _extract_due_date(self, text: str) -> str:
        match = re.search(r'(?:due date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""
    
    def _extract_total(self, text: str) -> float:
        patterns = [
            r'(?:total|amount due|grand total)[:\s]*[$\£\€]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})',
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
        return max(amounts) if amounts else 0.0
    
    def _extract_tax(self, text: str) -> float:
        match = re.search(r'(?:tax|vat|gst)[:\s]*[$\£\€]?\s*(\d{1,3}(?:,\d{3})*\.\d{2})', text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(',', ''))
        return 0.0
    
    def _detect_currency(self, text: str) -> str:
        if '$' in text or 'USD' in text:
            return 'USD'
        if '€' in text or 'EUR' in text:
            return 'EUR'
        if '£' in text or 'GBP' in text:
            return 'GBP'
        return 'USD'
    
    def _extract_line_items(self, text: str) -> list:
        items = []
        lines = text.split('\n')
        for line in lines:
            match = re.search(r'(.+?)\s+(?:[$\£\€])?(\d{1,3}(?:,\d{3})*\.\d{2})\s*$', line)
            if match:
                desc = match.group(1).strip()
                amount = float(match.group(2).replace(',', ''))
                if len(desc) > 5 and not any(x in desc.lower() for x in ['total', 'subtotal', 'tax', 'amount', 'rate', 'qty']):
                    items.append({'description': desc[:100], 'amount': amount})
        return items[:20]


class InvoiceValidator:
    def validate(self, data: Dict) -> tuple:
        errors = []
        if not data.get('vendor_name') or data['vendor_name'] == 'Unknown':
            errors.append("Missing vendor name")
        if not data.get('total') or data['total'] <= 0:
            errors.append("Invalid or missing total amount")
        return (len(errors) == 0, "; ".join(errors))
