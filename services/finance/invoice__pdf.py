"""
invoice_pdf.py
Basic PDF generation placeholders for invoices.
Replace rendering with reportlab templates in production.
"""
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

styles=getSampleStyleSheet()

class InvoicePDFService:
    def generate_invoice_pdf(self, invoice:dict, output_path:str):
        doc=SimpleDocTemplate(output_path)
        elems=[
            Paragraph(f"Invoice: {invoice.get('invoice_number','')}",styles["Heading1"]),
            Paragraph(f"Type: {invoice.get('invoice_type','')}",styles["Normal"]),
            Paragraph(f"Reference: {invoice.get('reference','')}",styles["Normal"]),
            Paragraph(f"Subtotal: {invoice.get('subtotal','')}",styles["Normal"]),
            Paragraph(f"VAT: {invoice.get('vat','')}",styles["Normal"]),
            Paragraph(f"Total: {invoice.get('total','')}",styles["Normal"]),
        ]
        doc.build(elems)
        return output_path

    def merge_supporting_documents(self, invoice_pdf:str, supporting_files:list):
        return {"invoice_pdf":invoice_pdf,"attachments":supporting_files}

invoice_pdf_service=InvoicePDFService()