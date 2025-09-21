from typing import List
from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from db.database import SessionLocal
from models.brokerage.finance import CarrierFinancialAccounts, Load_Invoice, Lane_Interim_Invoice, Lane_Invoice
from schemas.brokerage.finance import CarrierFinancialAccountResponse
from schemas.brokerage.finance import Withdrawal_Request
from utils.auth import get_current_user
from utils.pdf_generator import generate_invoice_pdf


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/carrier/shipment-invoice/{shipment_id}-{shipment_type}")
def carrier_get_carrier_shipment_invoice(
    shipment_id: int,
    shipment_type: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        invoice = db.query(Load_Invoice).filter(
            Load_Invoice.shipment_id == shipment_id,
            Load_Invoice.shipment_type == shipment_type
        ).first()

        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")

        invoice_dict = {
            "id": invoice.id,
            "shipment_id": invoice.shipment_type,
            "description": invoice.description,
            "invoice_type": invoice.invoice_type,
            "billing_date": str(invoice.billing_date),
            "due_date": str(invoice.due_date),
            "from": {
                "company_name": invoice.carrier_company_name,
                "address": invoice.carrier_address,
                "bank_name": invoice.carrier_bank,
                "account_number": invoice.carrier_bank_account,
            },
            "billed_to": {
                "platform_name": "SADC FREIGHTLINK PTY LTD",
                "registration_number": "2024/452702/07",
                "platform_email": "finance.sadcfreightlink.co.za",
            },
            "information": {
                "services": f"Shipment from {invoice.origin_address} to {invoice.destination_address}",
                "pickup_date": str(invoice.pickup_date),
                "distance": invoice.distance,
                "base_amount": invoice.base_amount,
                "detention_fees": invoice.detention_fees,
                "other_surcharges": invoice.other_surcharges,
                "due_amount": invoice.due_amount,
            },
        }

        # ✅ Generate PDF
        pdf_bytes = generate_invoice_pdf(invoice_dict)

        return Response(content=pdf_bytes, media_type="application/pdf")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("carrier/financial/withdrawal-request")
def submit_carrier_financial_account_withdrawal_request(
    withdrawal_request_data: Withdrawal_Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        results = create_withdral_request(
            db,
            withdral_request_data,
            current_user=current_user
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

