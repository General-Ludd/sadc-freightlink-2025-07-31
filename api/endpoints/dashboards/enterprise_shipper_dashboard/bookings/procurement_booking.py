from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from utils.auth import get_current_user
from schemas.exchange_bookings.dedicated_ftl_lane import TenderCreate, TenderBatchCreate
from schemas.exchange_bookings.ftl_shipment import ClientShipmentAuctionCreate
from services.exchange.tender import create_tender_and_publish
from services.exchange.load_auction import create_auction_and_publish

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post(
    "/procurement-tender-create-debug"
)
async def debug_tender_request(request: Request):

    body = await request.body()

    print("\n========== TENDER DEBUG ==========")
    print("CONTENT-TYPE:", request.headers.get("content-type"))
    print("BODY TYPE:", type(body))
    print("BODY BYTES:", body[:500])
    print("BODY DECODED:", body.decode("utf-8", errors="replace"))
    print("==================================\n")

    return {
        "content_type": request.headers.get("content-type"),
        "body_type": str(type(body)),
        "body": body.decode("utf-8", errors="replace")
    }

@router.post("/procurement-tender-create", status_code=status.HTTP_201_CREATED)
def create_ftl_tender_endpoint(
    batch_data: TenderBatchCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = create_tender_and_publish(
            db,
            batch_data,
            current_user=current_user
        )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@router.post("/procurement-exchange-create", status_code=status.HTTP_201_CREATED)
def create_shipment_auction_endpoint(
    auction_data: ClientShipmentAuctionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = create_auction_and_publish(
            db,
            auction_data,
            current_user=current_user
        )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )