from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board
from models.carrier import Carrier
from schemas.brokerage.loadboard import IndividualLoadboardShipmentRequest
from schemas.brokerage.exchange_loadboards import Exchange_Ftl_Load_Board_Response, Exchange_Ftl_Loadboard_Summary_Response
from schemas.exchange_bookings.auction import Exchange_FTL_Lane_Bid_Create, Exchange_FTL_Shipment_Bid_Create, Exchange_FTL_Exchange_Loadboard_BidResponse, Exchange_POWER_Shipment_Bid_Create, Exchange_Power_Exchange_Loadboard_BidResponse
from schemas.exchange_bookings.ftl_shipment import Exchange_Ftl_Shipments_Summary_Response
from services.exchange.auction import place_ftl_lane_bid, place_ftl_shipment_bid, place_power_shipment_bid
from utils.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/exchange/ftl-loadboard", response_model=List[Exchange_Ftl_Loadboard_Summary_Response]) #UnTested
def get_all_ftl_loads_exchanges(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        exchanges = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.status == "Open").all()
        return exchanges
    except Exception as e:
        return {"error": str(e)}
    
@router.get("/exchange/ftl-loadboard/id", response_model=Exchange_Ftl_Load_Board_Response) #UnTested
def loadboard_get_individual_ftl_shipment_exchange(
    loadboard_data: IndividualLoadboardShipmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")
        
    try:
        # Query all records from the "Exchange Ftl Shipments loadboard" table
        shipment = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.exchange_id == loadboard_data.id).first()
        return shipment
    except Exception as e:
        return {"error": str(e)}

@router.post("/exchange/ftl-loadboard/id/bid", status_code=status.HTTP_201_CREATED) #UnTested
def place_ftl_shipment_exchange_bid(
    bid_data: Exchange_FTL_Shipment_Bid_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):

    try:
        result = place_ftl_shipment_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/exchange/ftl-loadboard/id/all-bids", response_model=List[Exchange_FTL_Exchange_Loadboard_BidResponse]) #UnTested
def get_all_ftl_load_exchange_bids(
    bid_data: IndividualLoadboardShipmentRequest,
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(
        Carrier.id == company_id).first()
    if not carrier:
        raise ValueError("Carrier Not found")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == bid_data.id).all()
        return bids
    except Exception as e:
        return {"error": str(e)}
    

###########################   ONCE-OFF POWER   #############################################
@router.post("/exchange/power-loadboard/id/bid", status_code=status.HTTP_201_CREATED) #UnTested
def place_power_shipment_exchange_bid(
    bid_data: Exchange_POWER_Shipment_Bid_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):

    try:
        result = place_power_shipment_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/exchange/power-loadboard/id/all-bids", response_model=List[Exchange_Power_Exchange_Loadboard_BidResponse]) #UnTested
def get_all_power_load_exchange_bids(
    bid_data: IndividualLoadboardShipmentRequest,
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    carrier = db.query(Carrier).filter(
        Carrier.id == company_id).first()
    if not carrier:
        raise ValueError("Carrier Not found")
        
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        bids = db.query(Exchange_POWER_Shipment_Bid).filter(Exchange_POWER_Shipment_Bid.exchange_id == bid_data.id).all()
        return bids
    except Exception as e:
        return {"error": str(e)}
    
@router.post("/exchange/ftl-lane-loadboard/id/bid", status_code=status.HTTP_201_CREATED) #UnTested
def place_ftl_lane_exchange_bid(
    bid_data: Exchange_FTL_Lane_Bid_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)):

    try:
        result = place_ftl_lane_bid(
            db,
            bid_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
