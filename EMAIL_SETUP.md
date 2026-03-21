# Email Ingestion Setup Guide

## Overview
Users forward invoice emails to your domain, webhook receives them, auto-processes.

## SendGrid Inbound Parse Setup

### 1. Create SendGrid Account
- Sign up at https://sendgrid.com/
- Free tier: 100 emails/day

### 2. Configure Inbound Parse

**A. Add Domain**
```
Settings > Inbound Parse > Add Host & URL
```

**B. Point MX Record**
In your DNS (Cloudflare, Namecheap, etc):
```
Type: MX
Name: process
Value: mx.sendgrid.net
Priority: 10
```

**C. Configure Webhook URL**
```
URL: https://yourdomain.com/webhook/email
Check: "Check incoming emails for spam"
```

### 3. Test Email Address
Once MX propagates (~5 min), user emails:
```
process+user123@yourdomain.com
```

## Alternative: Manual Testing (No SendGrid)

For local testing, simulate webhook:

```bash
curl -X POST http://localhost:5000/webhook/email \
  -F "from=sender@example.com" \
  -F "to=process+test123@localhost" \
  -F "subject=Invoice from Vendor" \
  -F "text=Please see attached invoice" \
  -F "attachment-1=@/path/to/invoice.pdf"
```

## Production Checklist

- [ ] Domain registered
- [ ] SendGrid account created
- [ ] MX records configured
- [ ] Webhook URL set
- [ ] SSL certificate (for webhook)
- [ ] Test email sent

## How It Works

1. User forwards invoice email to `process+user123@yourdomain.com`
2. SendGrid receives email, POSTs to your webhook
3. Webhook extracts PDF, runs extraction, posts to QB
4. PDF archived with presigned download URL
5. Response sent back (200 OK = processed)

## Troubleshooting

**Email not received:**
- Check MX record: `dig MX yourdomain.com`
- Verify webhook URL is public (not localhost)
- Check SendGrid activity log

**PDF not processing:**
- Check attachment field name in payload
- Verify PDF is under 25MB
- Check Flask logs for errors
