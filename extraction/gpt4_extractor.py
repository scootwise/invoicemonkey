import os
import base64
import json
from typing import Dict, Any
import requests


class GPT4InvoiceExtractor:
    """Extract invoice data using GPT-4o Vision"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.model = "gpt-4o"
    
    def extract(self, pdf_bytes: bytes, filename: str = "invoice.pdf") -> Dict[str, Any]:
        """Convert PDF to base64 image and extract with GPT-4o"""
        
        # Convert PDF to image (first page)
        from pdf2image import convert_from_bytes
        
        print(f"Converting PDF to image...")
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=150)
        
        if not images:
            raise Exception("Failed to convert PDF to image")
        
        # Save to buffer as PNG
        from io import BytesIO
        img_buffer = BytesIO()
        images[0].save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        # Encode to base64
        base64_image = base64.b64encode(img_buffer.read()).decode('utf-8')
        print(f"Image encoded, size: {len(base64_image)} chars")
        
        # Call GPT-4o Vision
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an invoice data extraction assistant. Extract structured data from invoice images."
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract the following from this invoice and return ONLY a JSON object:\n{\n  \"vendor_name\": \"Company name\",\n  \"invoice_number\": \"INV-123\",\n  \"invoice_date\": \"YYYY-MM-DD\",\n  \"due_date\": \"YYYY-MM-DD\",\n  \"total\": 123.45,\n  \"tax\": 10.00,\n  \"currency\": \"USD\",\n  \"line_items\": [\n    {\"description\": \"Item 1\", \"quantity\": 1, \"unit_price\": 50.00, \"amount\": 50.00}\n  ]\n}\n\nIf any field is not found, use null or empty string. Return ONLY the JSON, no markdown."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 2000,
                "temperature": 0.0
            },
            timeout=60
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Parse JSON from content (might have markdown formatting)
        json_str = content.strip()
        if json_str.startswith('```json'):
            json_str = json_str[7:]
        if json_str.startswith('```'):
            json_str = json_str[3:]
        if json_str.endswith('```'):
            json_str = json_str[:-3]
        
        json_str = json_str.strip()
        extracted = json.loads(json_str)
        
        print(f"Extracted: {json.dumps(extracted, indent=2)}")
        
        # Normalize to standard format
        return {
            'raw_text': content,
            'vendor_name': extracted.get('vendor_name', 'Unknown'),
            'invoice_number': extracted.get('invoice_number', ''),
            'invoice_date': extracted.get('invoice_date', ''),
            'due_date': extracted.get('due_date', ''),
            'total': float(extracted.get('total', 0)) if extracted.get('total') else 0,
            'tax': float(extracted.get('tax', 0)) if extracted.get('tax') else 0,
            'currency': extracted.get('currency', 'USD'),
            'line_items': extracted.get('line_items', [])
        }


class InvoiceValidator:
    def validate(self, data: Dict) -> tuple:
        errors = []
        
        if not data.get('vendor_name') or data['vendor_name'] == 'Unknown':
            errors.append("Missing vendor name")
        
        if not data.get('total') or data['total'] <= 0:
            errors.append("Invalid or missing total amount")
        
        if data.get('line_items'):
            line_sum = sum(item.get('amount', 0) for item in data['line_items'])
            if abs(line_sum - data['total']) > 0.01:
                errors.append(f"Math mismatch: line items sum to {line_sum}, total is {data['total']}")
        
        return (len(errors) == 0, "; ".join(errors))
