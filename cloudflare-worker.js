// Cloudflare Worker for Invoice Monkey Email Webhook
// Receives forwarded emails, extracts PDFs, sends to Railway API

export default {
  async fetch(request, env, ctx) {
    // Only accept POST requests
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    try {
      // Parse the email from Cloudflare Email Routing
      const formData = await request.formData();
      
      // Extract email fields
      const from = formData.get('from') || '';
      const to = formData.get('to') || '';
      const subject = formData.get('subject') || '';
      const text = formData.get('text') || '';
      const html = formData.get('html') || '';
      
      // Extract user ID from email address (e.g., user-123@invoicemonkey.app)
      const userId = extractUserId(to);
      
      if (!userId) {
        return jsonResponse({ status: 'rejected', message: 'Invalid recipient' }, 400);
      }

      // Get attachments
      const attachments = [];
      for (const [key, value] of formData.entries()) {
        if (value instanceof File) {
          const arrayBuffer = await value.arrayBuffer();
          attachments.push({
            filename: value.name,
            type: value.type,
            content: arrayBuffer
          });
        }
      }

      // Filter for PDFs only
      const pdfAttachments = attachments.filter(att => 
        att.type === 'application/pdf' || att.filename.endsWith('.pdf')
      );

      if (pdfAttachments.length === 0) {
        return jsonResponse({ status: 'rejected', message: 'No PDF attachment found' }, 400);
      }

      // Forward each PDF to Railway API
      const results = [];
      for (const pdf of pdfAttachments) {
        const result = await forwardToRailway(pdf, userId, from, subject);
        results.push(result);
      }

      return jsonResponse({
        status: 'processed',
        attachments_processed: results.length,
        results: results
      });

    } catch (error) {
      console.error('Worker error:', error);
      return jsonResponse({ status: 'error', message: error.message }, 500);
    }
  }
};

function extractUserId(email) {
  // Extract user ID from email like "user-123@invoicemonkey.app"
  const match = email.match(/^([^@]+)@/);
  if (match) {
    return match[1];
  }
  return null;
}

async function forwardToRailway(pdf, userId, from, subject) {
  const RAILWAY_API_URL = 'https://invoicemonkey.app/api/invoice-to-qb';
  
  // Create form data for the file upload
  const formData = new FormData();
  const blob = new Blob([pdf.content], { type: 'application/pdf' });
  formData.append('file', blob, pdf.filename);
  formData.append('user_id', userId);
  formData.append('source_email', from);
  formData.append('email_subject', subject);
  
  try {
    const response = await fetch(`${RAILWAY_API_URL}?user_id=${userId}`, {
      method: 'POST',
      body: formData
    });
    
    if (response.ok) {
      const data = await response.json();
      return {
        filename: pdf.filename,
        status: 'success',
        invoice_id: data.invoice_id,
        qb_bill_id: data.qb_bill_id
      };
    } else {
      const errorText = await response.text();
      return {
        filename: pdf.filename,
        status: 'failed',
        error: errorText
      };
    }
  } catch (error) {
    return {
      filename: pdf.filename,
      status: 'error',
      error: error.message
    };
  }
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status: status,
    headers: {
      'Content-Type': 'application/json'
    }
  });
}
