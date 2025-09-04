from fastapi import APIRouter, Request, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from services.brokerage.payment_processor import process_deposit
import os

router = APIRouter()

NEDBANK_SECRET_KEY = os.getenv("NEDBANK_WEBHOOK_KEY")

@router.post("/nedbank-deposit")
async def nedbank_deposit(request: Request):
    body = await request.json()

    amount = body.get("deposit_amount")
    reference = body.get("reference")
    timestamp = body.get("timestamp")
    key = body.get("key")

    # Security check
    if key != NEDBANK_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key")

    if not amount or not reference:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required fields")

    db: Session = SessionLocal()
    try:
        result = process_deposit(db, float(amount), reference, timestamp)
    finally:
        db.close()

    return result
