import os
import sys
import requests
import time
from typing import Dict, Any

# Load .env
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

class LlamaParseExtractor:
    """Real LlamaParse integration with proper async polling"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('LLAMAPARSE_API_KEY')
        if not self.api_key:
            raise ValueError("LLAMAPARSE_API_KEY not set")
        self.base_url = "https://api.cloud.llamaindex.ai/api/parsing"
    
    def extract(self, pdf_bytes: bytes, filename: str = "invoice.pdf") -> Dict[str, Any]:
        """Upload PDF and poll for results"""
        
        # Step 1: Upload
        upload_url = f"{self.base_url}/upload"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        print(f"Uploading {filename} to LlamaParse...")
        
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        upload_resp = requests.post(upload_url, headers=headers, files=files, timeout=30)
        
        if upload_resp.status_code != 200:
            raise Exception(f"Upload failed: {upload_resp.status_code} - {upload_resp.text}")
        
        upload_data = upload_resp.json()
        job_id = upload_data.get("id")
        
        if not job_id:
            raise Exception(f"No job ID in response: {upload_data}")
        
        print(f"Job created: {job_id}")
        
        # Step 2: Poll for completion
        result_url = f"{self.base_url}/job/{job_id}/result/json"
        
        max_retries = 60  # 60 seconds
        for attempt in range(max_retries):
            time.sleep(1)
            
            result_resp = requests.get(result_url, headers=headers, timeout=10)
            
            if result_resp.status_code == 200:
                data = result_resp.json()
                status = data.get("status")
                
                print(f"Poll {attempt + 1}: status = {status}")
                
                if status == "SUCCESS":
                    return self._normalize(data)
                elif status == "FAILED":
                    raise Exception(f"LlamaParse processing failed: {data.get('error', 'Unknown error')}")
                elif status == "PENDING":
                    continue
            else:
                print(f"Poll {attempt + 1}: HTTP {result_resp.status_code}")
        
        raise Exception(f"Timeout waiting for LlamaParse after {max_retries} seconds")
    
    def _normalize(self, llamaparse_output: Dict) -> Dict[str, Any]:
        """Convert LlamaParse output to standardized format"""
        
        # Get markdown text from response
        markdown = llamaparse_output.get("markdown", "")
        text = llamaparse_output.get("text", markdown)
        
        print(f"Extracted text length: {len(text)}")
        
        return {
            'raw_text': text[:1000],  # First 1000 chars for debugging
            'full_text': text,
            'vendor_name': self._extract_vendor(text),
            'total': self._extract_total(text),
            'invoice_date': self._extract_date(text),
            'line_items': self._extract_line_items(text)
        }
    
    def _extract_vendor(self, text: str) -> str:
        lines = text.split('\n')[:30]  # Check first 30 lines
        for line in lines:
            line_stripped = line.strip()
            if any(word in line_stripped.lower() for word in ['inc', 'llc', 'ltd', 'corp', 'company']):
                if len(line_stripped) > 3 and not line_stripped.startswith('$'):
                    return line_stripped
        return "Unknown Vendor"
    
    def _extract_total(self, text: str) -> float:
        import re
        
        # Look for total patterns
        patterns = [
            r'(?:total|amount|balance|due)[^\d]{0,20}(\d{1,3}(?:,\d{3})*\.\d{2})',
            r'[\$\£\€]\s*(\d{1,3}(?:,\d{3})*\.\d{2})',
            r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*(?:USD|EUR|GBP)?'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Return largest amount (usually the total)
                amounts = [float(m.replace(',', '')) for m in matches]
                return max(amounts)
        
        return 0.0
    
    def _extract_date(self, text: str) -> str:
        from datetime import datetime
        import re
        
        patterns = [
            r'(?:invoice date|date|issued)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            r'(\d{1,2}[/-]\d{1,2}[/-]\d{4})',
            r'(\d{4}[/-]\d{2}[/-]\d{2})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return datetime.now().strftime("%Y-%m-%d")
    
    def _extract_line_items(self, text: str) -> list:
        """Extract line items from tables or structured text"""
        import re
        
        items = []
        
        # Try to find table rows (markdown format)
        lines = text.split('\n')
        for line in lines:
            # Look for lines with | (markdown table)
            if '|' in line and not line.strip().startswith('|--'):
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if len(cells) >= 2:
                    # Last cell might be amount
                    last_cell = cells[-1]
                    amount_match = re.search(r'[\$\£\€]?\s*(\d+(?:,\d{3})*\.\d{2})', last_cell)
                    if amount_match:
                        amount = float(amount_match.group(1).replace(',', ''))
                        desc = cells[0] if len(cells) > 1 else "Item"
                        items.append({
                            'description': desc[:100],
                            'amount': amount
                        })
        
        # If no table found, look for numbered lines with amounts
        if not items:
            for line in lines:
                match = re.search(r'^(?:\d+\.?\s*)?(.+?)[\s\.]+[\$\£\€]?(\d+(?:,\d{3})*\.\d{2})', line)
                if match:
                    items.append({
                        'description': match.group(1).strip()[:100],
                        'amount': float(match.group(2).replace(',', ''))
                    })
        
        return items[:20]  # Limit to 20 items


# Test function
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python llamaparse_real.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    with open(pdf_path, 'rb') as f:
        pdf_bytes = f.read()
    
    extractor = LlamaParseExtractor()
    result = extractor.extract(pdf_bytes, os.path.basename(pdf_path))
    
    print("\n=== EXTRACTION RESULT ===")
    print(f"Vendor: {result['vendor_name']}")
    print(f"Total: ${result['total']}")
    print(f"Date: {result['invoice_date']}")
    print(f"Line items: {len(result['line_items'])}")
    print(f"\nPreview:\n{result['raw_text'][:500]}")
