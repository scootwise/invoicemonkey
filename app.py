from flask import Flask, request, redirect, jsonify, session, send_file
import sys
import os
import secrets
import uuid

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth.quickbooks import QuickBooksAuth
from models.database import Session, User, Invoice
from datetime import datetime
from storage.archive import PDFArchive

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(16))
archive = PDFArchive()

qb_auth = QuickBooksAuth()

@app.route('/')
def health():
    return {'status': 'Invoice Parser API', 'version': '0.1.0'}

@app.route('/auth/quickbooks')
def auth_quickbooks():
    """Start OAuth flow"""
    user_id = request.args.get('user_id', 'test-user-123')
    session['user_id'] = user_id  # Store in Flask session
    auth_url = qb_auth.get_auth_url()
    return redirect(auth_url)

@app.route('/callback/quickbooks')
def callback_quickbooks():
    """OAuth callback"""
    auth_code = request.args.get('code')
    realm_id = request.args.get('realmId')
    user_id = session.get('user_id', 'unknown')
    
    try:
        tokens = qb_auth.exchange_code(auth_code, realm_id)
        access_enc, refresh_enc = qb_auth.encrypt_tokens(
            tokens['access_token'], 
            tokens['refresh_token']
        )
        
        db_session = Session()
        user = db_session.query(User).filter_by(id=user_id).first()
        
        if not user:
            user = User(id=user_id, email=f"user-{user_id}@example.com")
            db_session.add(user)
        
        user.qb_connected = True
        user.qb_realm_id = realm_id
        user.qb_access_token_enc = access_enc
        user.qb_refresh_token_enc = refresh_enc
        user.qb_expires_in = tokens['expires_in']
        user.qb_token_updated_at = datetime.utcnow()
        db_session.commit()
        
        # Clear session user_id
        session.pop('user_id', None)
        
        return {'status': 'success', 'message': 'QuickBooks connected', 'user_id': user_id}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/api/test-extract', methods=['POST'])
def test_extract():
    """Test extraction without QB posting"""
    from extraction.engine import LlamaParseExtractor, InvoiceValidator
    
    if 'file' not in request.files:
        return {'error': 'No file'}, 400
    
    file = request.files['file']
    pdf_bytes = file.read()
    
    extractor = LlamaParseExtractor()
    validator = InvoiceValidator()
    
    try:
        extracted = extractor.extract(pdf_bytes, file.filename)
        is_valid, error = validator.validate(extracted)
        
        return {
            'extracted': extracted,
            'valid': is_valid,
            'error': error if not is_valid else None
        }
    except Exception as e:
        return {'error': str(e)}, 500

@app.route('/api/invoices')
def list_invoices():
    """Get user's invoices"""
    user_id = request.args.get('user_id', 'test-user-123')
    
    db_session = Session()
    invoices = db_session.query(Invoice).filter_by(user_id=user_id).all()
    
    return {
        'invoices': [{
            'id': inv.id,
            'vendor': inv.vendor_name,
            'total': inv.total_amount,
            'status': inv.status,
            'created_at': inv.created_at.isoformat() if inv.created_at else None
        } for inv in invoices]
    }

@app.route('/api/invoice-to-qb', methods=['POST'])
def invoice_to_qb():
    """Full pipeline: PDF -> Archive -> Extraction -> QuickBooks"""
    from extraction.engine import LlamaParseExtractor, InvoiceValidator
    from posting.quickbooks import QuickBooksPoster
    
    user_id = request.args.get('user_id', 'test123')
    
    if 'file' not in request.files:
        return {'error': 'No file provided'}, 400
    
    file = request.files['file']
    pdf_bytes = file.read()
    
    # Get user
    db_session = Session()
    user = db_session.query(User).filter_by(id=user_id).first()
    
    if not user:
        return {'error': 'User not found'}, 404
    
    if not user.qb_connected:
        return {'error': 'QuickBooks not connected'}, 400
    
    # Create invoice record
    invoice = Invoice(
        id=str(uuid.uuid4()),
        user_id=user_id,
        filename=file.filename,
        file_size=len(pdf_bytes),
        status='processing'
    )
    db_session.add(invoice)
    db_session.commit()
    
    try:
        # Store PDF in encrypted archive
        archive_result = archive.store_pdf(user_id, invoice.id, pdf_bytes, file.filename)
        invoice.storage_key = archive_result['key']
        invoice.storage_type = archive_result.get('storage_type', 'local')
        db_session.commit()
        
        # Extract
        extractor = LlamaParseExtractor()
        validator = InvoiceValidator()
        
        extracted = extractor.extract(pdf_bytes, file.filename)
        is_valid, error = validator.validate(extracted)
        
        if not is_valid:
            invoice.status = 'error'
            invoice.error_message = error
            db_session.commit()
            return {'error': error}, 422
        
        # Update invoice with extracted data
        invoice.vendor_name = extracted.get('vendor_name')
        invoice.total_amount = extracted.get('total')
        invoice.invoice_date = _parse_date(extracted.get('invoice_date'))
        invoice.due_date = _parse_date(extracted.get('due_date'))
        invoice.line_items = extracted.get('line_items')
        invoice.status = 'extracted'
        db_session.commit()
        
        # Post to QuickBooks
        poster = QuickBooksPoster(user)
        result = poster.post_bill(extracted)
        
        if result['status'] == 'posted':
            invoice.status = 'posted'
            invoice.qb_bill_id = result['qb_bill_id']
            invoice.qb_posted_at = datetime.utcnow()
            db_session.commit()
            
            return {
                'status': 'success',
                'invoice_id': invoice.id,
                'qb_bill_id': result['qb_bill_id'],
                'extracted': extracted,
                'archive_url': archive_result.get('url'),
                'message': result['message']
            }
        else:
            invoice.status = 'qb_error'
            invoice.error_message = result['message']
            db_session.commit()
            return {
                'status': 'error',
                'invoice_id': invoice.id,
                'message': result['message'],
                'extracted': extracted
            }, 500
            
    except Exception as e:
        invoice.status = 'error'
        invoice.error_message = str(e)
        db_session.commit()
        return {'error': str(e)}, 500

@app.route('/api/archive', methods=['GET'])
def list_archive():
    """List user's archived PDFs"""
    user_id = request.args.get('user_id', 'test123')
    
    db_session = Session()
    invoices = db_session.query(Invoice).filter_by(user_id=user_id).filter(Invoice.storage_key != None).all()
    
    results = []
    for inv in invoices:
        # Generate fresh download URL
        download_url = None
        if inv.storage_key:
            download_url = archive.get_download_url(inv.storage_key)
        
        results.append({
            'invoice_id': inv.id,
            'filename': inv.filename,
            'vendor': inv.vendor_name,
            'total': inv.total_amount,
            'status': inv.status,
            'created_at': inv.created_at.isoformat() if inv.created_at else None,
            'download_url': download_url
        })
    
    return {'invoices': results}


@app.route('/api/archive/download/<invoice_id>', methods=['GET'])
def download_pdf(invoice_id):
    """Download archived PDF"""
    user_id = request.args.get('user_id', 'test123')
    
    db_session = Session()
    invoice = db_session.query(Invoice).filter_by(id=invoice_id, user_id=user_id).first()
    
    if not invoice or not invoice.storage_key:
        return {'error': 'PDF not found'}, 404
    
    # Generate fresh presigned URL
    url = archive.get_download_url(invoice.storage_key)
    
    return {'download_url': url, 'filename': invoice.filename}


@app.route('/webhook/email', methods=['POST'])
def webhook_email():
    """Receive invoice emails via SendGrid Inbound Parse"""
    from extraction.engine import LlamaParseExtractor, InvoiceValidator
    from posting.quickbooks import QuickBooksPoster
    from email_webhook.handler import EmailWebhookHandler
    import uuid
    
    handler = EmailWebhookHandler()
    
    try:
        # Merge request.form and request.files for processing
        combined_data = {}
        combined_data.update(request.form.to_dict())
        for key, file in request.files.items():
            combined_data[key] = file
        
        # Parse SendGrid webhook payload
        email_data = handler.parse_sendgrid_payload(combined_data)
        
        user_id = handler.extract_user_from_email(email_data['to'])
        
        # Get user
        db_session = Session()
        user = db_session.query(User).filter_by(id=user_id).first()
        
        if not user or not user.qb_connected:
            # User not found or no QB connected - send notification
            return {'status': 'rejected', 'message': 'User not configured'}, 400
        
        # Process attachments
        attachments = email_data['attachments']
        pdf_attachments = [att for att in attachments if att['type'] == 'application/pdf' or att['filename'].endswith('.pdf')]
        
        if not pdf_attachments:
            return {'status': 'rejected', 'message': 'No PDF attachment found'}, 400
        
        results = []
        
        for attachment in pdf_attachments:
            pdf_bytes = attachment['content']
            filename = attachment['filename']
            
            # Create invoice record
            invoice = Invoice(
                id=str(uuid.uuid4()),
                user_id=user_id,
                email_id=email_data.get('headers', {}).get('Message-Id', ''),
                filename=filename,
                file_size=len(pdf_bytes),
                status='processing'
            )
            db_session.add(invoice)
            db_session.commit()
            
            try:
                # Store in archive
                archive_result = archive.store_pdf(user_id, invoice.id, pdf_bytes, filename)
                invoice.storage_key = archive_result['key']
                invoice.storage_type = archive_result.get('storage_type', 'local')
                db_session.commit()
                
                # Extract
                extractor = LlamaParseExtractor()
                validator = InvoiceValidator()
                
                extracted = extractor.extract(pdf_bytes, filename)
                is_valid, error = validator.validate(extracted)
                
                if not is_valid:
                    invoice.status = 'error'
                    invoice.error_message = error
                    invoice.vendor_name = extracted.get('vendor_name', 'Unknown')
                    db_session.commit()
                    results.append({'filename': filename, 'status': 'extraction_failed', 'error': error})
                    continue
                
                # Update invoice
                invoice.vendor_name = extracted.get('vendor_name')
                invoice.total_amount = extracted.get('total')
                invoice.invoice_date = _parse_date(extracted.get('invoice_date'))
                invoice.due_date = _parse_date(extracted.get('due_date'))
                invoice.line_items = extracted.get('line_items')
                invoice.status = 'extracted'
                db_session.commit()
                
                # Post to QuickBooks
                poster = QuickBooksPoster(user)
                result = poster.post_bill(extracted)
                
                if result['status'] == 'posted':
                    invoice.status = 'posted'
                    invoice.qb_bill_id = result['qb_bill_id']
                    invoice.qb_posted_at = datetime.utcnow()
                    db_session.commit()
                    
                    results.append({
                        'filename': filename,
                        'status': 'success',
                        'invoice_id': invoice.id,
                        'qb_bill_id': result['qb_bill_id'],
                        'vendor': extracted.get('vendor_name'),
                        'total': extracted.get('total')
                    })
                else:
                    invoice.status = 'qb_error'
                    invoice.error_message = result['message']
                    db_session.commit()
                    results.append({
                        'filename': filename,
                        'status': 'qb_failed',
                        'error': result['message']
                    })
                
            except Exception as e:
                invoice.status = 'error'
                invoice.error_message = str(e)
                db_session.commit()
                results.append({'filename': filename, 'status': 'error', 'error': str(e)})
        
        return {
            'status': 'processed',
            'attachments_processed': len(results),
            'results': results
        }
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500


def _parse_date(date_str):
    """Parse date from various formats"""
    if not date_str:
        return None
    formats = ['%m/%d/%Y', '%Y-%m-%d', '%d/%m/%Y', '%m-%d-%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
