from typing import List
from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from db.database import SessionLocal
from models.brokerage.finance import CarrierFinancialAccounts
from schemas.brokerage.finance import CarrierFinancialAccountResponse
from schemas.brokerage.finance import Withdrawal_Request
from utils.auth import get_current_user


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/carrier/finance/financial-account", response_model=CarrierFinancialAccountResponse) #UnTested
def get_carrier_financial_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        financial_account = db.query(CarrierFinancialAccounts).filter(
            CarrierFinancialAccounts.id == company_id
        ).first()

        if not financial_account:
            raise HTTPException(
                status_code=404,
                detail=f"Shipments linked to carrier ID {id} not found or not authorized"
            )
        
        return financial_account

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

###############################################Invoices Summary Responses############################################
@router.get("/carrier/finance/service-invoices") #UnTested
def get_carrier_service_invoices(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:

        invoices = db.query(Load_Invoice).filter(
            Load_Invoice.carrier_financial_account_id == company_id
        ).all()

        return {
            "load_invoices": [{
                "id": invoice.id,
                "billing_date": invoice.billing_date,
                "due_date": invoice.due_date,
                "status": invoice.status,
                "service": f"{invoice.origin_address} - {invoice.destination_address} ({invoice.distance})",
                "due_amount": invoice.due_amount
                } for invoice in invoices]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/finance/shipment-invoices/{status}") #UnTested
def get_carrier_shipment_invoices_by_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:

        invoices = db.query(Load_Invoice).filter(
            Load_Invoice.carrier_financial_account_id == company_id,
            Load_Invoice.status == status
        ).all()

        return {
            "service_invoices": [{
                "id": invoice.id,
                "billing_date": invoice.billing_date,
                "due_date": invoice.due_date,
                "status": invoice.status,
                "service": f"{invoice.origin_address} - {invoice.destination_address} ({invoice.distance})",
                "due_amount": invoice.due_amount
                } for invoice in invoices]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/finance/interim-invoices") #UnTested
def get_carrier_interim_invoices(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:

        invoices = db.query(Lane_Interim_Invoice).filter(
            Lane_Interim_Invoice.carrier_financial_account_id == company_id
        ).all()

        return {
            "lane_interim_invoices": [{
                "id": invoice.id,
                "lane_id": invoice.contract_id,
                "lane_type": invoice.contract_type,
                "billing_period": f"{invoice.billing_date} - {invoice.due_date}",
                "due_date": invoice.billing_date,
                "status": invoice.status,
                "due_amount": invoice.due_amount,
                "settled_amount": invoice.settled_amount
                } for invoice in invoices]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/finance/interim-invoices/{status}") #UnTested
def get_carrier_interim_invoices(
    status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:

        invoices = db.query(Lane_Interim_Invoice).filter(
            Lane_Interim_Invoice.carrier_financial_account_id == company_id,
            Lane_Interim_Invoice.status == status
        ).all()

        return {
            "lane_interim_invoices": [{
                "id": invoice.id,
                "lane_id": invoice.contract_id,
                "lane_type": invoice.contract_type,
                "billing_period": f"{invoice.billing_date} - {invoice.due_date}",
                "due_date": invoice.billing_date,
                "status": invoice.status,
                "due_amount": invoice.due_amount,
                "settled_amount": invoice.settled_amount
                } for invoice in invoices]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/finance/interim-invoices/{lane_type}-{lane_id}") #UnTested
def get_carrier_interim_invoices(
    lane_type: str,
    lane_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        invoices = db.query(Lane_Interim_Invoice).filter(
            Lane_Interim_Invoice.carrier_financial_account_id == company_id,
            Lane_Invoice.contract_type == lane_type,
            Lane_Interim_Invoice.contract_id == lane_id,
        ).all()

        return {
            "lane_interim_invoices": [{
                "id": invoice.id,
                "lane_id": invoice.contract_id,
                "lane_type": invoice.contract_type,
                "billing_period": f"{invoice.billing_date} - {invoice.due_date}",
                "due_date": invoice.billing_date,
                "status": invoice.status,
                "due_amount": invoice.due_amount,
                "settled_amount": invoice.settled_amount
                } for invoice in invoices]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/finance/lanes-invoices") #UnTested
def get_carrier_lanes_invoices(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:

        invoices = db.query(Lane_Invoice).filter(
            Lane_Invoice.financial_account_id == company_id
        ).all()

        return {
            "lanes_invoices": [{
                "id": invoice.id,
                "lane_id": invoice.contract_id,
                "lane_type": invoice.lane_type,
                "billing_period": f"{invoice.billing_date} - {invoice.due_date}",
                "due_date": invoice.billing_date,
                "status": invoice.status,
                "due_amount": invoice.due_amount,
                "settled_amount": invoice.paid_amount
                } for invoice in invoices]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/finance/lanes-invoices/{status}") #UnTested
def get_carrier_lanes_invoices_status(
    status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:

        invoices = db.query(Lane_Invoice).filter(
            Lane_Invoices.financial_account_id == company_id,
            Lane_Invoices.status == status
        ).all()

        return {
            "lanes_invoices": [{
                "id": invoice.id,
                "lane_id": invoice.contract_id,
                "lane_type": invoice.lane_type,
                "billing_period": f"{invoice.billing_date} - {invoice.due_date}",
                "due_date": invoice.billing_date,
                "status": invoice.status,
                "due_amount": invoice.due_amount,
                "settled_amount": invoice.paid_amount
                } for invoice in invoices]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shipper/finance/Overdue/service-invoices", response_model=List[Service_Invoices_Summary_Response]) #UnTested
def get_all_shipper_overdue_service_invoices(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        invoices = db.query(Shipment_Invoice).filter(
            Shipment_Invoice.financial_account_id == company_id,
            Shipment_Invoice.status == "Overdue"
        ).all()

        if not invoices:
            raise HTTPException(
                status_code=404,
                detail=f"Shipments linked to carrier ID {id} not found or not authorized"
            )
        
        return invoices

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#########################################Individual Invoice#############################################
@router.get("/carrier/finance/shipment-invoice/{invoice_id}") #UnTested
def get_carrier_shipment_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        company = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.id == company_id).first()

        invoice = db.query(Load_Invoice).filter(
            Load_Invoice.id == invoice_id
        ).first()

        return {
            "service_invoice": {
                "id": invoice.id,
                "invoice_type": invoice.invoice_type,
                "billing_date": invoice.billing_date,
                "due_date": invoice.due_date,
                "status": invoice.status,
                "payment_terms": invoice.payment_terms,

                "service_details": {
                    "shipment_id": invoice.shipment_id,
                    "shipment_type": invoice.shipment_type,
                    "origin_address": invoice.origin_address,
                    "destination_address": invoice.destination_address,
                    "pickup_date": invoice.pickup_date,
                    "distance": invoice.distance,
                },

                "base_amount": invoice.base_amount,
                "detention_fees": invoice.other_surcharges,
                "total_due": invoice.due_amount,
                "settled_amount": invoice.paid_amount
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/finance/interim-invoice/{invoice_id}") #UnTested
def get_carrier_interim_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        company = db.query(FinancialAccounts).filter(FinancialAccounts.id == company_id).first()

        invoice = db.query(Lane_Interim_Invoice).filter(
            Lane_Interim_Invoice.id == invoice_id
        ).first()

        return {
            "lane_interim_invoice": {
                "id": invoice.id,
                "invoice_type": invoice.invoice_type,
                "billing_date": invoice.billing_date,
                "due_date": invoice.due_date,
                "status": invoice.status,
                "payment_terms": invoice.payment_terms,

                "base_amount": invoice.base_amount,
                "detention_fees": invoice.other_surcharges,
                "total_due": invoice.due_amount,
                "settled_amount": invoice.paid_amount
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/finance/lane-invoice/{invoice_id}") #UnTested
def get_carrier_lane_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        company = db.query(FinancialAccounts).filter(FinancialAccounts.id == company_id).first()

        invoice = db.query(Lane_Invoice).filter(
            Lane_Invoice.id == invoice_id
        ).first()

        return {
            "lane_invoice": {
                "id": invoice.id,
                "invoice_type": invoice.invoice_type,
                "billing_period": f"{invoice.billing_date} - {invoice.due_date}",
                "billing_date": invoice.billing_date,
                "due_date": invoice.due_date,
                "status": invoice.status,
                "payment_terms": invoice.payment_terms,

                "base_amount": invoice.base_amount,
                "detention_fees": invoice.other_surcharges,
                "total_due": invoice.due_amount,
                "settled_amount": invoice.paid_amount
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))