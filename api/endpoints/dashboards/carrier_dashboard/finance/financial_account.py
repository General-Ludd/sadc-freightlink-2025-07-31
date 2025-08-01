from typing import List
from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from db.database import SessionLocal
from models.brokerage.finance import CarrierFinancialAccounts
from schemas.brokerage.finance import CarrierFinancialAccountResponse
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