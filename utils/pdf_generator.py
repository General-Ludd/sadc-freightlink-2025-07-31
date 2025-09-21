from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime

def generate_invoice_pdf(invoice: dict) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # === "LOGO" / Platform Name at Top Center ===
    c.setFont("Helvetica-Bold", 22)
    platform_name = invoice['billed_to']['platform_name']
    text_width = c.stringWidth(platform_name, "Helvetica-Bold", 22)
    c.setFillColorRGB(0, 0, 0)
    c.drawString((width - text_width) / 2, height - 60, platform_name)

    # Invoice Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(260, height - 100, "INVOICE")

    # Invoice meta
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 140, f"Invoice ID: {invoice['id']}")
    c.drawString(50, height - 155, f"Invoice Type: {invoice['invoice_type']}")
    c.drawString(50, height - 170, f"Billing Date: {invoice['billing_date']}")
    c.drawString(50, height - 185, f"Due Date: {invoice['due_date']}")

    # From
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 220, "From:")
    c.setFont("Helvetica", 10)
    c.drawString(60, height - 235, invoice['from']['company_name'])
    c.drawString(60, height - 250, invoice['from']['address'])
    c.drawString(60, height - 265, f"Bank: {invoice['from']['bank_name']}")
    c.drawString(60, height - 280, f"Account: {invoice['from']['account_number']}")

    # Billed To
    c.setFont("Helvetica-Bold", 12)
    c.drawString(300, height - 220, "Billed To:")
    c.setFont("Helvetica", 10)
    c.drawString(310, height - 235, invoice['billed_to']['platform_name'])
    c.drawString(310, height - 250, f"Reg No: {invoice['billed_to']['registration_number']}")
    c.drawString(310, height - 265, f"Email: {invoice['billed_to']['platform_email']}")

    # Service details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 310, "Service Details:")
    c.setFont("Helvetica", 10)
    c.drawString(60, height - 325, f"Description: {invoice['description']}")
    c.drawString(60, height - 340, f"Services: {invoice['information']['services']}")
    c.drawString(60, height - 355, f"Pickup Date: {invoice['information']['pickup_date']}")
    c.drawString(60, height - 370, f"Distance: {invoice['information']['distance']:,} km")

    # Charges
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 410, "Charges:")
    c.setFont("Helvetica", 10)
    c.drawString(60, height - 425, f"Base Amount: R{invoice['information']['base_amount']:,}")
    c.drawString(60, height - 440, f"Detention Fees: R{invoice['information']['detention_fees']:,}")
    c.drawString(60, height - 455, f"Other Surcharges: R{invoice['information']['other_surcharges']:,}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, height - 480, f"Total Due: R{invoice['information']['due_amount']:,}")

    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(50, 40, f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()
