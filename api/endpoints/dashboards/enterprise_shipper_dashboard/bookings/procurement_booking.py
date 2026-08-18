from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from utils.auth import get_current_user
from schemas.exchange_bookings.dedicated_ftl_lane import TenderCreate
from services.exchange.tender import create_tender_and_publish

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/procurement-tender-create", status_code=status.HTTP_201_CREATED)
def create_ftl_tender_endpoint(
    tender_data: TenderCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = create_tender_and_publish(
            db,
            tender_data,
            current_user=current_user
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )