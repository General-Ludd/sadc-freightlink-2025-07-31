from typing import List
from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from db.database import SessionLocal
from models.brokerage.finance import FinancialAccounts, Shipment_Invoice
from schemas.brokerage.finance import Individual_Service_Invoice_Response, Individual_Sevice_Invoices_Request, Service_Invoices_Summary_Response, Shipper_Financial_Account_Response
from utils.auth import get_current_user


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/shipper/finance/financial_account", response_model=Shipper_Financial_Account_Response) #UnTested
def get_shipper_financial_account(
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
        financial_account = db.query(FinancialAccounts).filter(
            FinancialAccounts.id == company_id
        ).first()

        if not financial_account:
            raise HTTPException(
                status_code=404,
                detail=f"Shipments linked to carrier ID {id} not found or not authorized"
            )
        
        return financial_account

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


###############################################Invoices Summary Responses############################################
@router.get("/shipper/finance/service-invoices", response_model=List[Service_Invoices_Summary_Response]) #UnTested
def get_all_shipper_service_invoices(
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
            Shipment_Invoice.financial_account_id == company_id
        ).all()

        if not invoices:
            raise HTTPException(
                status_code=404,
                detail=f"Shipments linked to carrier ID {id} not found or not authorized"
            )
        
        return invoices

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
@router.get("/shipper/finance/services-invoice", response_model=Individual_Service_Invoice_Response) #UnTested
def get_individual_shipper_service_invoice(
    invoice_data: Individual_Sevice_Invoices_Request,
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
        invoice = db.query(Shipment_Invoice).filter(
            Shipment_Invoice.id == invoice_data.id,
            Shipment_Invoice.financial_account_id == company_id
        ).first()

        if not invoice:
            raise HTTPException(
                status_code=404,
                detail=f"Shipments linked to carrier ID {id} not found or not authorized"
            )
        
        return invoice

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))