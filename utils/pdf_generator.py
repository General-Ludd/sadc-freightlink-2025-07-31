from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from datetime import datetime

def generate_invoice_pdf(invoice: dict) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # === Styles for Paragraphs ===
    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    normal_style.fontName = "Helvetica"
    normal_style.fontSize = 10
    normal_style.leading = 12

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

    # === From & Billed To ===
    title_y = height - 220
    content_y = title_y - 15

    # Titles
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, title_y, "From:")
    c.drawString(300, title_y, "Billed To:")

    # Content using Paragraph for wrapping
    from_text = f"{invoice['from']['company_name']}<br/>{invoice['from']['address']}<br/>Bank: {invoice['from']['bank_name']}<br/>Account: {invoice['from']['account_number']}"
    billed_to_text = f"{invoice['billed_to']['platform_name']}<br/>Reg No: {invoice['billed_to']['registration_number']}<br/>Email: {invoice['billed_to']['platform_email']}"

    from_para = Paragraph(from_text, normal_style)
    billed_para = Paragraph(billed_to_text, normal_style)

    from_para.wrapOn(c, 200, 100)   # width, height
    from_para.drawOn(c, 60, content_y - 45)  # start slightly below the title

    billed_para.wrapOn(c, 200, 100)
    billed_para.drawOn(c, 310, content_y - 45)

    # === Service Details ===
    service_y = content_y - 90
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, service_y, "Service Details:")

    service_text_y = service_y - 15
    description_para = Paragraph(f"Description: {invoice['description']}", normal_style)
    services_para = Paragraph(f"Services: {invoice['information']['services']}", normal_style)
    description_para.wrapOn(c, 480, 50)
    services_para.wrapOn(c, 480, 50)
    description_para.drawOn(c, 60, service_text_y)
    services_para.drawOn(c, 60, service_text_y - 15)

    # Pickup date and distance
    c.setFont("Helvetica", 10)
    c.drawString(60, service_text_y - 40, f"Pickup Date: {invoice['information']['pickup_date']}")
    c.drawString(60, service_text_y - 55, f"Distance: {invoice['information']['distance']:,} km")

    # === Charges ===
    charges_y = service_text_y - 85
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, charges_y, "Charges:")

    c.setFont("Helvetica", 10)
    c.drawString(60, charges_y - 15, f"Base Amount: R{invoice['information']['base_amount']:,}")
    c.drawString(60, charges_y - 30, f"Detention Fees: R{invoice['information']['detention_fees']:,}")
    c.drawString(60, charges_y - 45, f"Other Surcharges: R{invoice['information']['other_surcharges']:,}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(60, charges_y - 70, f"Total Due: R{invoice['information']['due_amount']:,}")

    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(50, 40, f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")

    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()