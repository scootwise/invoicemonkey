#!/bin/bash

# Invoice Parser Setup Script
# Run this once to initialize everything

set -e

echo "=== Invoice Parser Setup ==="
echo ""

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: Run this script from the invoice-parser directory"
    exit 1
fi

# Generate encryption key
echo "[1/4] Generating encryption key..."
KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || python3 -m pip install cryptography -q && python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Create .env file with the key
echo "[2/4] Creating .env file..."
cat > .env << EOF
# Auto-generated encryption key
ENCRYPTION_KEY=$KEY

# QuickBooks Developer Account: https://developer.intuit.com/
# Create app → Keys tab → Copy Client ID and Secret below
QB_CLIENT_ID=
QB_CLIENT_SECRET=
QB_REDIRECT_URI=http://localhost:5000/callback/quickbooks
QB_ENVIRONMENT=sandbox

# LlamaParse: https://cloud.llamaindex.ai/
# Sign up → API Keys → Create Key
LLAMAPARSE_API_KEY=

# Database (default SQLite)
DATABASE_URL=sqlite:///invoice_parser.db
EOF

# Install dependencies
echo "[3/4] Installing dependencies..."
pip3 install -q -r requirements.txt

echo "[4/4] Verifying installation..."
python3 -c "from auth.quickbooks import QuickBooksAuth; print('✓ QuickBooks auth module loaded')" 2>/dev/null || echo "⚠ Module import failed - may need to run: cd ~/invoice-parser && pip3 install -r requirements.txt"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Get QuickBooks credentials:"
echo "   → https://developer.intuit.com/"
echo "   → My Apps → Create App → Keys tab"
echo "   → Copy Client ID and Secret to .env file"
echo ""
echo "2. Get LlamaParse API key:"
echo "   → https://cloud.llamaindex.ai/"
echo "   → Sign up → API Keys → Create Key"
echo "   → Paste into .env file"
echo ""
echo "3. Run the app:"
echo "   python3 app.py"
echo ""
echo "4. Test: http://localhost:5000/"
