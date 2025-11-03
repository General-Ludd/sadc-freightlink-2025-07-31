from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from datetime import datetime
import requests
from fastapi.responses import Response

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

def generate_shipper_invoice_pdf(invoice: dict, logo_url: str = None) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    styles = getSampleStyleSheet()
    normal_style = styles["Normal"]
    normal_style.fontName = "Helvetica"
    normal_style.fontSize = 10
    normal_style.leading = 13

    # === HEADER SECTION ===
    y = height - 50

    # Logo (if provided)
    if logo_url:
        try:
            response = requests.get(logo_url, timeout=5)
            if response.status_code == 200:
                logo = ImageReader(BytesIO(response.content))
                c.drawImage(logo, 40, y - 50, width=95, height=70, preserveAspectRatio=True)
        except Exception as e:
            print(f"Logo load failed: {e}")

    # Platform Name + Invoice Type
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(width - 40, y - 10, invoice["platform_name"].upper())

    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - 40, y - 30, f"{invoice['invoice_type'].upper()} INVOICE")

    # === Invoice Metadata ===
    c.setFont("Helvetica", 10)
    meta_y = y - 70
    c.drawString(40, meta_y, f"Invoice ID: {invoice['id']}")
    c.drawString(40, meta_y - 15, f"Billing Date: {invoice['billing_date']}")
    c.drawString(40, meta_y - 30, f"Due Date: {invoice['due_date']}")
    c.drawString(40, meta_y - 45, f"Payment Reference: {invoice['payment_reference']}")

    # === FROM / BILLED TO ===
    section_y = meta_y - 80
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, section_y, "Billed To:")
    c.drawString(300, section_y, "From:")

    c.setFont("Helvetica", 10)
    billed_to_text = (
        f"{invoice['billed_to']['business_name']}\n"
        f"Reg No: {invoice['billed_to']['registration_no']}\n"
        f"{invoice['billed_to']['billing_address']}\n"
        f"Email: {invoice['billed_to']['business_email']}"
    )
    from_text = (
        f"{invoice['from']['platform_name']}\n"
        f"{invoice['from']['platform_address']}\n"
        f"Bank: {invoice['from']['platform_bank']}\n"
        f"Account: {invoice['from']['platform_bank_account']}"
    )

    # Draw billed_to and from text
    text_obj = c.beginText(40, section_y - 15)
    for line in billed_to_text.split("\n"):
        text_obj.textLine(line)
    c.drawText(text_obj)

    text_obj = c.beginText(300, section_y - 15)
    for line in from_text.split("\n"):
        text_obj.textLine(line)
    c.drawText(text_obj)

    # Leave enough space after addresses
    section_y -= 75

    # === SHIPMENT DETAILS ===
    details_y = section_y - 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, details_y, "Shipment Details")

    shipment_data = [
        ["Origin", invoice["information"]["origin_address"]],
        ["Destination", invoice["information"]["destination_address"]],
        ["Pickup Date", invoice["information"]["pickup_date"]],
        ["Distance", f"{invoice['information']['distance']:,} km"],
        ["Transit Time", invoice["information"]["transit_time"]],
    ]

    table = Table(shipment_data, colWidths=[100, 400])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    table.wrapOn(c, width, height)
    table.drawOn(c, 40, details_y - 80)

    # === CHARGES ===
    charges_y = details_y - 120
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, charges_y, "Charges Summary")

    charge_data = [
        ["Base Amount", f"R{invoice['information']['base_amount']:,}"],
        ["Other Surcharges", f"R{invoice['information']['other_surcharges']:,}"],
        ["Late Fees", f"R{invoice['information']['late_fees']:,}"],
        ["Total", f"R{invoice['information']['total']:,}"],
        ["Amount Due", f"R{invoice['information']['due_amount']:,}"],
    ]

    charge_table = Table(charge_data, colWidths=[150, 150])
    charge_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
            ]
        )
    )
    charge_table.wrapOn(c, width, height)
    charge_table.drawOn(c, 40, charges_y - 100)

    # === FOOTER ===
    c.setFont("Helvetica", 8)
    c.drawString(40, 40, f"Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    c.drawRightString(width - 40, 40, "Thank you for your business.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()