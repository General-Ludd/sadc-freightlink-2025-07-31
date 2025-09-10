from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from db.database import SessionLocal
from services.brokerage.payment_processor import process_deposit
import os
from pydantic import BaseModel
from datetime import date, datetime

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class DepositWebhook(BaseModel):
    transaction_id: str
    unique_transaction_key: str
    deposit_amount: float
    reference: str
    timestamp: datetime
    key: str

class DepositResponse(BaseModel):
    status: str
    account_id: int | None = None
    new_credit_balance: int | None = None
    new_total_outstanding: int | None = None
    new_total_paid: int | None = None
    message: str | None = None

NEDBANK_SECRET_KEY = os.getenv("NEDBANK_WEBHOOK_KEY")

@router.post("/nedbank/deposit", response_model=DepositResponse)
def nedbank_deposit(payload: DepositWebhook, db: Session = Depends(get_db)):
    # Validate secret key
    if payload.key != NEDBANK_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid key"
        )

    result = process_deposit(
        db=db,
        transaction_id=payload.transaction_id,
        unique_transaction_key=payload.unique_transaction_key,
        amount=payload.deposit_amount,
        reference=payload.reference,
        timestamp=payload.timestamp
    )
    return result