#!/usr/bin/env python3
"""Generate test invoice PDFs for extraction testing"""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import os

def create_invoice_1(filename):
    """Standard corporate invoice"""
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "INVOICE")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, "Acme Corporation Inc.")
    c.drawString(50, height - 95, "123 Business Ave")
    c.drawString(50, height - 110, "San Francisco, CA 94102")
    c.drawString(50, height - 125, "billing@acmecorp.com")
    
    # Invoice details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(400, height - 80, "Invoice Details")
    c.setFont("Helvetica", 11)
    c.drawString(400, height - 100, "Invoice #: INV-2024-001")
    c.drawString(400, height - 115, "Date: 03/15/2024")
    c.drawString(400, height - 130, "Due Date: 04/15/2024")
    c.drawString(400, height - 145, "Terms: Net 30")
    
    # Bill To
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 170, "Bill To:")
    c.setFont("Helvetica", 11)
    c.drawString(50, height - 190, "Client Company LLC")
    c.drawString(50, height - 205, "456 Client Street")
    c.drawString(50, height - 220, "New York, NY 10001")
    
    # Line items
    y = height - 280
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Description")
    c.drawString(350, y, "Qty")
    c.drawString(420, y, "Rate")
    c.drawString(500, y, "Amount")
    
    # Line
    c.line(50, y - 10, 550, y - 10)
    
    y -= 30
    c.setFont("Helvetica", 11)
    c.drawString(50, y, "Consulting Services")
    c.drawString(350, y, "10")
    c.drawString(420, y, "$150.00")
    c.drawString(500, y, "$1,500.00")
    
    y -= 25
    c.drawString(50, y, "Software License")
    c.drawString(350, y, "1")
    c.drawString(420, y, "$500.00")
    c.drawString(500, y, "$500.00")
    
    y -= 25
    c.drawString(50, y, "Support Package")
    c.drawString(350, y, "1")
    c.drawString(420, y, "$250.00")
    c.drawString(500, y, "$250.00")
    
    # Totals
    y -= 50
    c.line(400, y + 20, 550, y + 20)
    c.drawString(400, y, "Subtotal:")
    c.drawString(500, y, "$2,250.00")
    
    y -= 20
    c.drawString(400, y, "Tax (8%):")
    c.drawString(500, y, "$180.00")
    
    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(400, y, "Total:")
    c.drawString(500, y, "$2,430.00")
    
    c.save()
    print(f"Created: {filename}")


def create_invoice_2(filename):
    """Simple service invoice"""
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Header - centered
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width/2, height - 50, "SERVICE INVOICE")
    
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height - 80, "Handyman Services LLC")
    c.drawCentredString(width/2, height - 95, "555 Fixit Road, Austin TX 78701")
    
    # Invoice info - simple layout
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, height - 140, "Invoice Number:")
    c.setFont("Helvetica", 12)
    c.drawString(250, height - 140, "HS-2024-445")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, height - 160, "Date:")
    c.setFont("Helvetica", 12)
    c.drawString(250, height - 160, "03/20/2024")
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, height - 180, "Due Date:")
    c.setFont("Helvetica", 12)
    c.drawString(250, height - 180, "04/20/2024")
    
    # Customer
    c.setFont("Helvetica-Bold", 12)
    c.drawString(100, height - 220, "Customer:")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 240, "John Smith")
    c.drawString(100, height - 255, "789 Home Street")
    c.drawString(100, height - 270, "Austin, TX 78702")
    
    # Items - table format
    y = height - 320
    c.setFont("Helvetica-Bold", 11)
    c.drawString(100, y, "Service")
    c.drawString(450, y, "Price")
    c.line(100, y - 10, 500, y - 10)
    
    y -= 30
    c.setFont("Helvetica", 11)
    c.drawString(100, y, "Kitchen faucet repair")
    c.drawString(450, y, "$125.00")
    
    y -= 25
    c.drawString(100, y, "Drywall patch - bedroom")
    c.drawString(450, y, "$85.00")
    
    y -= 25
    c.drawString(100, y, "Light fixture installation")
    c.drawString(450, y, "$95.00")
    
    y -= 25
    c.drawString(100, y, "Materials")
    c.drawString(450, y, "$45.00")
    
    # Total
    y -= 40
    c.line(350, y + 20, 500, y + 20)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(350, y, "Total: $350.00")
    
    # Thank you
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, 100, "Thank you for your business!")
    
    c.save()
    print(f"Created: {filename}")


def create_invoice_3(filename):
    """Minimalist invoice"""
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # Very minimal
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 60, "INVOICE")
    
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 90, "TechStart Inc | 100 Startup Way | Palo Alto, CA 94304")
    
    c.setFont("Helvetica", 11)
    c.drawString(400, height - 60, "Invoice #: TSI-998")
    c.drawString(400, height - 75, "Date: 03/18/2024")
    c.drawString(400, height - 90, "Amount Due: $5,750.00")
    
    c.line(50, height - 120, 550, height - 120)
    
    y = height - 150
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Item")
    c.drawString(450, y, "Amount")
    
    y -= 25
    c.setFont("Helvetica", 11)
    c.drawString(50, y, "Monthly SaaS Subscription - Enterprise Plan")
    c.drawString(450, y, "$5,000.00")
    
    y -= 20
    c.drawString(50, y, "Additional user seats (15 @ $50)")
    c.drawString(450, y, "$750.00")
    
    c.save()
    print(f"Created: {filename}")


def create_invoice_4(filename):
    """International invoice with different currency"""
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "INVOICE / FACTURE")
    
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, "EuroTech Solutions SARL")
    c.drawString(50, height - 95, "45 Rue de Commerce")
    c.drawString(50, height - 110, "75002 Paris, France")
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(380, height - 80, "Invoice #: EUR-2024-55")
    c.setFont("Helvetica", 11)
    c.drawString(380, height - 95, "Date: 20/03/2024")
    c.drawString(380, height - 110, "Due: 20/04/2024")
    
    # Items
    y = height - 160
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Description")
    c.drawString(350, y, "Qty")
    c.drawString(420, y, "Unit Price")
    c.drawString(500, y, "Total")
    c.line(50, y - 5, 550, y - 5)
    
    y -= 25
    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Web Development Services")
    c.drawString(350, y, "40")
    c.drawString(420, y, "€125.00")
    c.drawString(500, y, "€5,000.00")
    
    y -= 20
    c.drawString(50, y, "Hosting & Maintenance")
    c.drawString(350, y, "12")
    c.drawString(420, y, "€75.00")
    c.drawString(500, y, "€900.00")
    
    # Total in EUR
    y -= 40
    c.line(400, y + 15, 550, y + 15)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(400, y, "Total: €5,900.00")
    
    c.save()
    print(f"Created: {filename}")


if __name__ == "__main__":
    os.makedirs("test_invoices", exist_ok=True)
    
    create_invoice_1("test_invoices/invoice_standard.pdf")
    create_invoice_2("test_invoices/invoice_service.pdf")
    create_invoice_3("test_invoices/invoice_minimal.pdf")
    create_invoice_4("test_invoices/invoice_euro.pdf")
    
    print("\n4 test invoices created in test_invoices/")
