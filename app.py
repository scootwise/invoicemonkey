# Invoice Monkey - Railway deployment triggered after DNS outage
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
def landing():
    """Landing page with demo features"""
    return send_file('templates/index.html')

@app.route('/demo')
def demo():
    """Interactive demo page - v1"""
    return send_file('templates/demo.html')

@app.route('/api/ping', methods=['POST'])
def ping():
    """Simple test endpoint"""
    return jsonify({'status': 'ok', 'message': 'pong'})

@app.route('/api/debug-extract', methods=['POST'])
def debug_extract():
    """Debug extraction - shows raw data"""
    from extraction.engine import LlamaParseExtractor
    
    if 'file' not in request.files:
        return {'error': 'No file'}, 400
    
    file = request.files['file']
    pdf_bytes = file.read()
    
    extractor = LlamaParseExtractor()
    extracted = extractor.extract(pdf_bytes, file.filename)
    
    return jsonify({
        'extracted': extracted,
        'raw_text_preview': extracted.get('raw_text', '')[:500]
    })

@app.route('/api/signup', methods=['POST'])
def signup():
    """Handle free trial signup from landing page"""
    try:
        name = request.form.get('name')
        business = request.form.get('business')
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        if not email:
            return jsonify({'status': 'error', 'message': 'Email required'}), 400
        
        # Generate unique user_id from email
        user_id = email.replace('@', '-').replace('.', '-')
        
        # Check if user exists
        db_session = Session()
        user = db_session.query(User).filter_by(id=user_id).first()
        
        if not user:
            # Create trial user
            user = User(
                id=user_id,
                email=email
            )
            db_session.add(user)
            db_session.commit()
            
            # In production: Send welcome email, create QB setup link
            # For now: Redirect to demo with user connected
            return jsonify({
                'status': 'success',
                'message': 'Trial started! Redirecting to setup...',
                'user_id': user_id,
                'next_step': '/auth/quickbooks?user_id=' + user_id
            })
        
        return jsonify({
            'status': 'exists',
            'message': 'You already have an account!',
            'user_id': user_id
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/auth/quickbooks')
def auth_quickbooks():
    """Start OAuth flow"""
    user_id = request.args.get('user_id', 'test-user-123')
    # NOTE: OAuth session issue - user_id gets lost in production
    # For now, OAuth creates user 'unknown'. Use manual QB connect endpoint instead.
    session['user_id'] = user_id
    auth_url = qb_auth.get_auth_url(state=user_id)
    return redirect(auth_url)

@app.route('/callback/quickbooks')
def callback_quickbooks():
    """OAuth callback"""
    auth_code = request.args.get('code')
    realm_id = request.args.get('realmId')
    # Extract user_id from OAuth state parameter (reliable across redirects)
    user_id = request.args.get('state', 'unknown')
    
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
        
        return {'status': 'success', 'message': 'QuickBooks connected', 'user_id': user_id}
        
    except Exception as e:
        return {'status': 'error', 'message': str(e)}, 500

@app.route('/api/create-user', methods=['POST'])
def create_user():
    """Create a test user directly"""
    user_id = request.json.get('user_id', 'test123')
    email = request.json.get('email', f"user-{user_id}@example.com")
    
    db_session = Session()
    user = db_session.query(User).filter_by(id=user_id).first()
    
    if not user:
        user = User(id=user_id, email=email)
        db_session.add(user)
        db_session.commit()
        return {'status': 'created', 'user_id': user_id, 'email': email}
    
    return {'status': 'exists', 'user_id': user_id, 'email': email}

@app.route('/api/connect-qb', methods=['POST'])
def connect_qb_manual():
    """Manually set QB credentials for testing"""
    user_id = request.json.get('user_id')
    realm_id = request.json.get('realm_id')
    access_token = request.json.get('access_token')
    refresh_token = request.json.get('refresh_token')
    
    if not user_id:
        return {'error': 'user_id required'}, 400
    
    db_session = Session()
    user = db_session.query(User).filter_by(id=user_id).first()
    
    if not user:
        return {'error': 'User not found'}, 404
    
    # Encrypt tokens
    access_enc, refresh_enc = qb_auth.encrypt_tokens(access_token, refresh_token)
    
    user.qb_connected = True
    user.qb_realm_id = realm_id
    user.qb_access_token_enc = access_enc
    user.qb_refresh_token_enc = refresh_enc
    user.qb_expires_in = 3600
    user.qb_token_updated_at = datetime.utcnow()
    db_session.commit()
    
    return {'status': 'success', 'message': 'QB connected manually', 'user_id': user_id}

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
    """Full pipeline: PDF -> Archive -> Extraction -> QuickBooks (or Queue)"""
    from extraction.engine import LlamaParseExtractor, InvoiceValidator
    from posting.quickbooks import QuickBooksPoster
    
    # Get review mode: 'direct' (post immediately) or 'queue' (hold for approval)
    review_mode = request.args.get('review_mode', 'direct')
    
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
        
        # Check review mode
        if review_mode == 'queue':
            # Save to approval queue
            invoice.status = 'pending_approval'
            invoice.review_mode = 'queue'
            db_session.commit()
            
            return {
                'status': 'pending_approval',
                'invoice_id': invoice.id,
                'extracted': extracted,
                'archive_url': archive_result.get('url'),
                'message': 'Invoice saved for review. Approve in dashboard to post to QuickBooks.'
            }
        
        # Direct mode: Post immediately
        invoice.status = 'extracted'
        invoice.review_mode = 'direct'
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

@app.route('/api/approvals', methods=['GET'])
def list_pending_approvals():
    """List invoices pending approval for a user"""
    user_id = request.args.get('user_id', 'test123')
    
    db_session = Session()
    invoices = db_session.query(Invoice).filter_by(
        user_id=user_id,
        status='pending_approval'
    ).all()
    
    return {
        'invoices': [{
            'id': inv.id,
            'vendor': inv.vendor_name,
            'total': inv.total_amount,
            'filename': inv.filename,
            'created_at': inv.created_at.isoformat() if inv.created_at else None,
            'line_items': inv.line_items
        } for inv in invoices]
    }

@app.route('/api/approve', methods=['POST'])
def approve_invoice():
    """Approve pending invoice and post to QuickBooks"""
    from posting.quickbooks import QuickBooksPoster
    
    invoice_id = request.json.get('invoice_id')
    user_id = request.json.get('user_id', 'test123')
    
    if not invoice_id:
        return {'error': 'invoice_id required'}, 400
    
    db_session = Session()
    invoice = db_session.query(Invoice).filter_by(id=invoice_id, user_id=user_id).first()
    
    if not invoice:
        return {'error': 'Invoice not found'}, 404
    
    if invoice.status != 'pending_approval':
        return {'error': 'Invoice not in pending approval status'}, 400
    
    user = db_session.query(User).filter_by(id=user_id).first()
    if not user or not user.qb_connected:
        return {'error': 'QuickBooks not connected'}, 400
    
    # Build extracted data from invoice record
    extracted = {
        'vendor_name': invoice.vendor_name,
        'total': invoice.total_amount,
        'invoice_date': invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else None,
        'due_date': invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else None,
        'line_items': invoice.line_items
    }
    
    # Post to QuickBooks
    poster = QuickBooksPoster(user)
    result = poster.post_bill(extracted)
    
    if result['status'] == 'posted':
        invoice.status = 'posted'
        invoice.qb_bill_id = result['qb_bill_id']
        invoice.qb_posted_at = datetime.utcnow()
        db_session.commit()
        
        return {
            'status': 'approved_and_posted',
            'invoice_id': invoice.id,
            'qb_bill_id': result['qb_bill_id'],
            'message': 'Invoice approved and posted to QuickBooks'
        }
    else:
        return {
            'status': 'error',
            'message': result['message']
        }, 500

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


@app.route('/api/email-webhook', methods=['POST'])
def email_webhook():
    """Receive forwarded emails from Cloudflare Worker"""
    try:
        data = request.get_json() or {}
        
        user_id = data.get('userId')
        from_email = data.get('from')
        subject = data.get('subject')
        attachments = data.get('attachments', [])
        
        if not user_id:
            return {'error': 'userId required'}, 400
        
        # Find PDF attachments
        pdf_attachments = [att for att in attachments if att.get('filename', '').endswith('.pdf')]
        
        if not pdf_attachments:
            return {'error': 'No PDF attachment found'}, 400
        
        # Process first PDF
        pdf = pdf_attachments[0]
        pdf_content = pdf.get('content')  # Base64 encoded
        filename = pdf.get('filename', 'invoice.pdf')
        
        if not pdf_content:
            return {'error': 'Empty PDF content'}, 400
        
        # Decode base64 content
        import base64
        try:
            pdf_bytes = base64.b64decode(pdf_content)
        except Exception:
            return {'error': 'Invalid PDF encoding'}, 400
        
        # Get or create user
        db_session = Session()
        user = db_session.query(User).filter_by(id=user_id).first()
        
        if not user:
            # Auto-create user from email
            user = User(
                id=user_id,
                email=from_email or f"{user_id}@invoicemonkey.app"
            )
            db_session.add(user)
            db_session.commit()
        
        # Create invoice record
        invoice = Invoice(
            id=str(uuid.uuid4()),
            user_id=user_id,
            filename=filename,
            file_size=len(pdf_bytes),
            status='processing'
        )
        db_session.add(invoice)
        db_session.commit()
        
        # Store PDF
        archive_result = archive.store_pdf(user_id, invoice.id, pdf_bytes, filename)
        invoice.storage_key = archive_result['key']
        invoice.storage_type = archive_result.get('storage_type', 'local')
        db_session.commit()
        
        # Extract data
        from extraction.engine import LlamaParseExtractor, InvoiceValidator
        extractor = LlamaParseExtractor()
        validator = InvoiceValidator()
        
        extracted = extractor.extract(pdf_bytes, filename)
        is_valid, error = validator.validate(extracted)
        
        if not is_valid:
            invoice.status = 'error'
            invoice.error_message = error
            db_session.commit()
            return {'status': 'error', 'message': error}, 422
        
        # Update invoice
        invoice.vendor_name = extracted.get('vendor_name')
        invoice.total_amount = extracted.get('total')
        invoice.invoice_date = _parse_date(extracted.get('invoice_date'))
        invoice.due_date = _parse_date(extracted.get('due_date'))
        invoice.status = 'extracted'
        db_session.commit()
        
        # If QB connected, auto-post
        if user.qb_connected:
            from posting.quickbooks import QuickBooksPoster
            poster = QuickBooksPoster()
            
            # Get decrypted token
            access_token = qb_auth.decrypt_tokens(user.qb_access_token_enc, user.qb_refresh_token_enc)
            
            result = poster.create_bill(
                access_token=access_token,
                realm_id=user.qb_realm_id,
                invoice_data=extracted,
                pdf_attachment=pdf_bytes
            )
            
            if result['success']:
                invoice.qb_bill_id = result['qb_bill_id']
                invoice.status = 'posted'
                invoice.qb_posted_at = datetime.utcnow()
                db_session.commit()
                
                return {
                    'status': 'success',
                    'invoice_id': invoice.id,
                    'qb_bill_id': result['qb_bill_id'],
                    'message': 'Invoice extracted and posted to QuickBooks'
                }
            else:
                invoice.status = 'error'
                invoice.error_message = result.get('message', 'QB posting failed')
                db_session.commit()
                return {'status': 'error', 'message': invoice.error_message}, 500
        else:
            return {
                'status': 'success',
                'invoice_id': invoice.id,
                'message': 'Invoice extracted. QB not connected - manual review needed.',
                'needs_qb_setup': True
            }
            
    except Exception as e:
        import traceback
        print(f"Email webhook error: {str(e)}\n{traceback.format_exc()}")
        return {'error': str(e)}, 500


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
    app.run(host='0.0.0.0', port=port, debug=False)  # Railway requires 0.0.0.0
