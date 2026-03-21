"""Email webhook handler for SendGrid Inbound Parse"""
import os
import json
import base64
from typing import Dict, Any, List
from werkzeug.utils import secure_filename


class EmailWebhookHandler:
    """Handle incoming emails with invoice attachments"""
    
    def __init__(self):
        self.webhook_secret = os.getenv('EMAIL_WEBHOOK_SECRET')
    
    def parse_sendgrid_payload(self, request_data: Dict) -> Dict[str, Any]:
        """Parse SendGrid Inbound Parse webhook payload"""
        
        # Extract email metadata
        headers = json.loads(request_data.get('headers', '{}'))
        
        return {
            'from': request_data.get('from', ''),
            'to': request_data.get('to', ''),
            'subject': request_data.get('subject', ''),
            'text': request_data.get('text', ''),
            'html': request_data.get('html', ''),
            'attachments': self._parse_attachments(request_data),
            'headers': headers
        }
    
    def _parse_attachments(self, request_data: Dict) -> List[Dict]:
        """Extract attachments from SendGrid payload or multipart upload"""
        attachments = []
        
        # SendGrid sends attachments as separate fields: attachment-info, attachment-1, etc.
        attachment_info = request_data.get('attachment-info', '{}')
        if isinstance(attachment_info, str):
            try:
                attachment_info = json.loads(attachment_info)
            except:
                attachment_info = {}
        
        for att_name, att_info in attachment_info.items():
            # Check if this is a file upload (werkzeug FileStorage) or raw content
            file_obj = request_data.get(att_name)
            
            if hasattr(file_obj, 'read'):
                # This is a werkzeug FileStorage (multipart upload)
                file_obj.seek(0)
                file_bytes = file_obj.read()
                filename = secure_filename(file_obj.filename or att_info.get('filename', 'attachment.pdf'))
                content_type = file_obj.content_type or att_info.get('type', 'application/pdf')
            elif isinstance(file_obj, str):
                # Raw content (base64 or string)
                try:
                    file_bytes = base64.b64decode(file_obj)
                except:
                    file_bytes = file_obj.encode()
                filename = secure_filename(att_info.get('filename', 'attachment.pdf'))
                content_type = att_info.get('type', 'application/pdf')
            else:
                continue
            
            if file_bytes:
                attachments.append({
                    'filename': filename,
                    'content': file_bytes,
                    'type': content_type,
                    'size': len(file_bytes)
                })
        
        return attachments
    
    def extract_user_from_email(self, to_address: str) -> str:
        """Extract user ID from recipient email address"""
        # Support: process+user123@yourdomain.com or process@yourdomain.com with default user
        
        if '+' in to_address:
            # process+user123@domain.com -> user123
            local_part = to_address.split('@')[0]
            if '+' in local_part:
                return local_part.split('+')[1]
        
        # Check for X-User-ID header or default
        return 'default'
    
    def is_invoice_email(self, subject: str, text: str) -> bool:
        """Check if email appears to be an invoice"""
        subject_lower = subject.lower()
        text_lower = text.lower()
        
        invoice_keywords = ['invoice', 'bill', 'payment due', 'receipt', 'order']
        
        for keyword in invoice_keywords:
            if keyword in subject_lower or keyword in text_lower:
                return True
        
        return False


class SimpleSMTPHandler:
    """Alternative: Handle raw SMTP/email data for custom setups"""
    
    def parse_raw_email(self, raw_email_bytes: bytes) -> Dict[str, Any]:
        """Parse raw email data (for custom SMTP servers)"""
        from email import message_from_bytes
        from email.policy import default
        
        msg = message_from_bytes(raw_email_bytes, policy=default)
        
        result = {
            'from': msg.get('From', ''),
            'to': msg.get('To', ''),
            'subject': msg.get('Subject', ''),
            'text': '',
            'html': '',
            'attachments': []
        }
        
        # Extract body
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                
                if content_type == 'text/plain':
                    result['text'] = part.get_content()
                elif content_type == 'text/html':
                    result['html'] = part.get_content()
                elif part.get_filename():
                    # Attachment
                    result['attachments'].append({
                        'filename': secure_filename(part.get_filename()),
                        'content': part.get_payload(decode=True),
                        'type': content_type,
                        'size': len(part.get_payload(decode=True) or b'')
                    })
        else:
            result['text'] = msg.get_content()
        
        return result
