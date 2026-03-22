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
        
        # Look for business name patterns in first 40 lines
        for i, line in enumerate(lines):
            line = line.strip()
            # Skip obvious non-vendor lines
            if any(skip in line.lower() for skip in ['intuit', 'payment', 'inc (ipi)', 'license', 'www.', 'page 1']):
                continue
            # Look for business indicators
            if any(x in line.lower() for x in ['inc', 'llc', 'ltd', 'corp', 'control', 'services']):
                if len(line) > 5 and len(line) < 60 and not line.startswith('$') and not line.startswith('---'):
                    # Verify it's not just "Control" by checking surrounding context
                    if 'termite' in line.lower() or 'pest' in line.lower() or i > 5:
                        return line
        
        # Look for patterns like email addresses with business names
        match = re.search(r'([A-Z][A-Za-z0-9\s&]+(?:Inc|LLC|Ltd|Corp|Control|Services))\s+[\d,]+', text)
        if match:
            return match.group(1).strip()
            
        # Look for lines before @email
        match = re.search(r'([A-Z][A-Za-z0-9\s&]+)\s+[A-Z][A-Za-z0-9\s,]+USA\s*[a-z]+@[a-z]+', text)
        if match:
            return match.group(1).strip()
        
        # Fallback: Return first substantial line that looks like a name
        for line in lines[10:]:  # Skip first 10 lines (headers)
            line = line.strip()
            if len(line) > 10 and len(line) < 50 and not any(skip in line.lower() for skip in ['intuit', 'payment', 'terms', 'conditions', 'page', '---']):
                if re.search(r'[A-Z]', line) and not line.startswith('$'):
                    return line
        
        return "Unknown Vendor"
    
    def _extract_invoice_number(self, text: str) -> str:
        patterns = [
            r'(?:invoice|receipt|sales)\s*(?:#|number|no)[:\s]*([A-Z0-9\-]+)',
            r'(?:receipt|sales)\s*[:\s]*([A-Z0-9\-]+)\s*(?:date|payment)',
            r'(?:#|no)[:\s]*([A-Z0-9\-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""
    
    def _extract_invoice_date(self, text: str) -> str:
        # Look for various date patterns
        patterns = [
            r'(?:date|invoice date|sales date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'date[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'(\d{2}[/-]\d{2}[/-]\d{4})\s+(?:payment|method|total)',
            r'date\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
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
            r'(?:total|amount due|grand total|balance|sum)[:\s]*[$\£\€]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})',
            r'(?:^|\n)\s*(?:Total)[:\s]*[$\£\€]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})',
            r'Total\s+[$\£\€]?(\d{1,3}(?:,\d{3})*\.\d{2})',
            r'[$\£\€]?(\d{1,3}(?:,\d{3})*\.\d{2})\s*(?:Total|USD)?\s*$',
        ]
        amounts = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                try:
                    amount = float(match.replace(',', ''))
                    if amount > 0.01:  # Filter out tiny amounts
                        amounts.append(amount)
                except:
                    pass
        # Return largest amount (usually the total)
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
        
        # Look for table-like sections with amounts
        in_items_section = False
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip header/footer lines
            if any(skip in line.lower() for skip in ['total', 'subtotal', 'tax', 'balance due', 'payment method', 'amount']):
                continue
            
            # Pattern 1: Description followed by amount at end
            match = re.search(r'(.+?)\s+(?:[$\£\€])?(\d{1,3}(?:,\d{3})*\.\d{2})\s*$', line)
            if match:
                desc = match.group(1).strip()
                amount = float(match.group(2).replace(',', ''))
                # Filter out totals and headers
                if len(desc) > 5 and amount > 0 and not any(x in desc.lower() for x in ['total', 'subtotal', 'tax', 'amount', 'rate', 'qty', 'description', 'service']):
                    items.append({'description': desc[:100], 'amount': amount})
                    continue
            
            # Pattern 2: Lines with "Custom Amount" or similar
            match = re.search(r'(custom amount|service|description)\s*(.+?)\s*(?:[$\£\€])?(\d{1,3}(?:,\d{3})*\.?\d{0,2})\s*(?:[$\£\€])?(\d{1,3}(?:,\d{3})*\.\d{2})', line, re.IGNORECASE)
            if match:
                desc = match.group(2).strip() if len(match.group(2).strip()) > 3 else match.group(1)
                amount = float(match.group(4).replace(',', ''))
                if amount > 0 and 'total' not in desc.lower():
                    items.append({'description': desc[:100], 'amount': amount})
        
        # Remove duplicates and limit
        seen = set()
        unique_items = []
        for item in items:
            key = (item['description'][:50], item['amount'])
            if key not in seen:
                seen.add(key)
                unique_items.append(item)
        
        return unique_items[:20]


class InvoiceValidator:
    def validate(self, data: Dict) -> tuple:
        errors = []
        if not data.get('vendor_name') or data['vendor_name'] == 'Unknown':
            errors.append("Missing vendor name")
        if not data.get('total') or data['total'] <= 0:
            errors.append("Invalid or missing total amount")
        return (len(errors) == 0, "; ".join(errors))
