from typing import List
from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from db.database import SessionLocal
from models.brokerage.finance import FinancialAccounts, Shipment_Invoice
from schemas.brokerage.finance import Individual_Service_Invoice_Response, Individual_Sevice_Invoices_Request, Service_Invoices_Summary_Response, Shipper_Financial_Account_Response
from utils.auth import get_current_user
from utils.pdf_generator import generate_shipper_invoice_pdf
from fastapi.responses import Response

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/shipper/shipment-invoice/{shipment_id}-{shipment_type}")
def get_shipper_shipment_invoice(
    shipment_id: int,
    shipment_type: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    invoice = db.query(Shipment_Invoice).filter(
        Shipment_Invoice.shipment_id == shipment_id,
        Shipment_Invoice.shipment_type == shipment_type
    ).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == invoice.company_id).first()

    if not financial_account:
        raise HTTPException(status_code=404, detail="Linked financial account not found")

    invoice_dict = {
        "id": invoice.id,
        "invoice_type": invoice.invoice_type,
        "billing_date": str(invoice.billing_date),
        "due_date": str(invoice.due_date),
        "payment_reference": invoice.payment_reference,
        "platform_name": "SADC FREIGHTLINK",
        "billed_to": {
            "business_name": financial_account.company_name,
            "registration_no": financial_account.business_registration_number,
            "billing_address": financial_account.business_address,
            "business_email": financial_account.business_email,
        },
        "from": {
            "platform_name": "SADC FREIGHTLINK ",
            "platform_address": "2 Bridgeway, Century City, Cape Town, 7441",
            "platform_bank": "Nedbank Ltd",
            "platform_bank_account": "1317232429",
        },
        "information": {
            "origin_address": invoice.origin_address,
            "destination_address": invoice.destination_address,
            "pickup_date": str(invoice.pickup_date),
            "distance": invoice.distance,
            "transit_time": invoice.transit_time,
            "base_amount": invoice.base_amount,
            "other_surcharges": invoice.other_surcharges,
            "late_fees": invoice.late_fees,
            "total": invoice.total,
            "due_amount": invoice.due_amount,
        },
    }

    logo_url = "https://ik.imagekit.io/0bf9ktdig/ChatGPT%20Image%20Sep%202,%202025,%2009_28_10%20PM.png?updatedAt=1759309497595"  # Replace with your real URL
    pdf_bytes = generate_shipper_invoice_pdf(invoice_dict, logo_url)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="shipper_invoice_{invoice.id}.pdf"'}
    )

@router.get("/shipper/shipment-invoice/{invoice_id}")
def get_shipper_shipment_invoice_by_id(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    invoice = db.query(Shipment_Invoice).filter(Shipment_Invoice.id == invoice_id).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == invoice.company_id).first()

    if not financial_account:
        raise HTTPException(status_code=404, detail="Linked financial account not found")

    invoice_dict = {
        "id": invoice.id,
        "invoice_type": invoice.invoice_type,
        "billing_date": str(invoice.billing_date),
        "due_date": str(invoice.due_date),
        "payment_reference": invoice.payment_reference,
        "platform_name": "SADC FREIGHTLINK",
        "billed_to": {
            "business_name": financial_account.company_name,
            "registration_no": financial_account.business_registration_number,
            "billing_address": financial_account.business_address,
            "business_email": financial_account.business_email,
        },
        "from": {
            "platform_name": "SADC FREIGHTLINK ",
            "platform_address": "2 Bridgeway, Century City, Cape Town, 7441",
            "platform_bank": "Nedbank Ltd",
            "platform_bank_account": "1317232429",
        },
        "information": {
            "origin_address": invoice.origin_address,
            "destination_address": invoice.destination_address,
            "pickup_date": str(invoice.pickup_date),
            "distance": invoice.distance,
            "transit_time": invoice.transit_time,
            "base_amount": invoice.base_amount,
            "other_surcharges": invoice.other_surcharges,
            "late_fees": invoice.late_fees,
            "total": invoice.total,
            "due_amount": invoice.due_amount,
        },
    }

    logo_url = "https://ik.imagekit.io/0bf9ktdig/ChatGPT%20Image%20Sep%202,%202025,%2009_28_10%20PM.png?updatedAt=1759309497595"  # Replace with your real URL
    pdf_bytes = generate_shipper_invoice_pdf(invoice_dict, logo_url)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="shipper_invoice_{invoice.id}.pdf"'}
    )


@router.get("/shipper/interim-invoice/{invoice_id}")
def get_shipper_interim_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # === 1️⃣ Fetch Invoice ===
    invoice = db.query(Interim_Invoice).filter(Interim_Invoice.id == invoice_id).first()

    if not invoice:
        raise HTTPException(status_code=404, detail="Interim invoice not found")

    # === 2️⃣ Fetch Financial Account ===
    financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == invoice.financial_account_id).first()

    if not financial_account:
        raise HTTPException(status_code=404, detail="Linked financial account not found")

    # === 3️⃣ Build Invoice Dictionary ===
    invoice_dict = {
        "id": invoice.id,
        "invoice_type": invoice.invoice_type,
        "billing_date": str(invoice.billing_date),
        "due_date": str(invoice.due_date),
        "payment_reference": invoice.payment_reference,
        "platform_name": invoice.platform_name,
        "status": invoice.status,
        "description": invoice.description,
        "from": {
            "platform_name": invoice.platform_name,
            "platform_address": invoice.platform_address,
            "platform_bank": invoice.platform_bank,
            "platform_bank_account": invoice.platform_bank_account,
        },
        "billed_to": {
            "business_name": financial_account.company_name,
            "registration_no": financial_account.business_registration_number,
            "billing_address": financial_account.business_address,
            "business_email": financial_account.business_email,
        },
        "information": {
            "contract_id": invoice.contract_id,
            "contract_type": invoice.contract_type,
            "billing_period": invoice.payment_terms or "N/A",
            "base_amount": invoice.base_amount,
            "other_surcharges": invoice.other_surcharges,
            "late_fees": invoice.late_fees,
            "total": invoice.total,
            "due_amount": invoice.due_amount,
        },
    }

    # === 4️⃣ Generate PDF ===
    logo_url = "https://ik.imagekit.io/0bf9ktdig/ChatGPT%20Image%20Sep%202,%202025,%2009_25_07%20PM.png?updatedAt=1762145054656"
    pdf_bytes = generate_interim_invoice_pdf(invoice_dict, logo_url)

    # === 5️⃣ Return Response ===
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="interim_invoice_{invoice.id}.pdf"'}
    )