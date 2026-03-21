# Invoice Monkey - Production Backup

## Date: 2026-03-21 14:34 PM PST
## Status: ✅ END-TO-END WORKING

---

## What's Working

### Landing Page
- URL: https://invoicemonkey.app
- Dark gradient design with animated monkey logo
- "Under Construction" with feature highlights
- Contact email

### Demo Page
- URL: https://invoicemonkey.app/demo
- Drag & drop PDF upload
- Live extraction results display
- Post to QuickBooks button

### API Endpoints

| Endpoint | Method | Status |
|----------|--------|--------|
| / | GET | Landing page |
| /demo | GET | Interactive demo |
| /api/test-extract | POST | PDF extraction ✅ |
| /api/invoice-to-qb | POST | Full pipeline ✅ |
| /api/invoices | GET | List invoices |
| /auth/quickbooks | GET | OAuth flow ✅ |
| /callback/quickbooks | GET | OAuth callback ✅ |

### Database
- Provider: Railway Postgres
- Tables: users, invoices
- Connection: Working

### QuickBooks Integration
- OAuth: Working with state parameter
- Token storage: Encrypted
- Bill posting: Working (Bill ID: 150 created)

---

## Environment Variables (Railway)

```
DATABASE_URL=postgresql://[redacted]
FLASK_SECRET_KEY=7d8a9b2c3e4f5g6h7i8j9k0l1m2n3o4p5q6r7s8t9u0v1w2x3y4z5a6b7c8d9e0f1
QB_REDIRECT_URI=https://invoicemonkey.app/callback/quickbooks
PORT=5000
```

---

## Critical Code Changes

### 1. OAuth State Parameter Fix
File: `auth/quickbooks.py`
- Manually appends state to URL to preserve user_id across redirects
- Required for production OAuth to work

### 2. Railway Deployment Config
File: `railway.json`
- Uses gunicorn with PORT env var
- Binds to 0.0.0.0

### 3. Database Compatibility
File: `models/database.py`
- Added checkfirst=True for Postgres table creation

---

## Test User
- User ID: TKsQ6NyKHPKiTWrWdifawsTHSmWUcO
- QB Connected: Yes
- Successfully posted: Invoice #150

---

## Known Issues
- None - All features working

---

## Restore Instructions

### Database Restore
```bash
# From Railway Postgres backup
pg_restore --dbname=DATABASE_URL backup.sql
```

### Code Restore
```bash
git clone https://github.com/scootwise/invoicemonkey.git
cd invoicemonkey
pip install -r requirements.txt
# Set environment variables
python app.py
```

### Railway Rebuild
1. Delete service
2. New Project → Deploy from GitHub
3. Add environment variables
4. Add custom domain
5. Connect domain + DNS

---

## Verification Commands

```bash
# Test health
curl https://invoicemonkey.app

# Test extraction
curl -X POST https://invoicemonkey.app/api/test-extract \
  -F "file=@invoice.pdf"

# Test full flow (requires QB connection)
curl -X POST "https://invoicemonkey.app/api/invoice-to-qb?user_id=USER_ID" \
  -F "file=@invoice.pdf"
```

---

**Backup created by:** OpenClaw Agent  
**Verified working:** 2026-03-21 14:34 PST
