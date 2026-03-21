import os
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

# Generate once: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', '').encode()

# QuickBooks
QB_CLIENT_ID = os.getenv('QB_CLIENT_ID', '')
QB_CLIENT_SECRET = os.getenv('QB_CLIENT_SECRET', '')
QB_REDIRECT_URI = os.getenv('QB_REDIRECT_URI', 'http://localhost:5000/callback/quickbooks')
QB_ENVIRONMENT = os.getenv('QB_ENVIRONMENT', 'sandbox')

# LlamaParse
LLAMAPARSE_API_KEY = os.getenv('LLAMAPARSE_API_KEY', '')

# Database
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///invoice_parser.db')

# Email
EMAIL_WEBHOOK_SECRET = os.getenv('EMAIL_WEBHOOK_SECRET', '')
NYLAS_API_KEY = os.getenv('NYLAS_API_KEY', '')

# R2 Storage (for PDF archive)
R2_ACCOUNT_ID = os.getenv('R2_ACCOUNT_ID', '')
R2_ACCESS_KEY_ID = os.getenv('R2_ACCESS_KEY_ID', '')
R2_SECRET_ACCESS_KEY = os.getenv('R2_SECRET_ACCESS_KEY', '')
R2_BUCKET_NAME = os.getenv('R2_BUCKET_NAME', 'invoice-parser-pdfs')
R2_PUBLIC_URL = os.getenv('R2_PUBLIC_URL', '')
