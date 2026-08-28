from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
from sqlalchemy.orm import Session
from db.database import SessionLocal
from schemas.exchange_bookings.dedicated_ftl_lane import Broker_Exchange_FTL_Lane_Booking
from schemas.exchange_bookings.ftl_shipment import Broker_Exchange_FTL_Shipment_Booking
from schemas.exchange_bookings.power_shipment import Exchange_Power_Shipment_Booking
from schemas.shipment_facility import FacilityContactCreate, ShipmentFacilityCreate
from schemas.shipper import ConsignorCreate
from services.exchange.dedicated_ftl_lane import broker_access_create_dedicated_ftl_lane_exchange
from services.exchange.power_shipment import create_power_shipment_exchange
from utils.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/broker-access/exchange/ftl-shipment-create", status_code=status.HTTP_201_CREATED)
def create_broker_ftl_exchange_endpoint(
    shipment_data: Broker_Exchange_FTL_Shipment_Booking,
    pickup_facility_data: ShipmentFacilityCreate,
    dropoff_facility_data: ShipmentFacilityCreate,
    pickup_contact_data: FacilityContactCreate,
    dropoff_contact_data: FacilityContactCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    consignor_data: Optional[ConsignorCreate] = None,
):
    try:
        result = broker_access_create_ftl_shipment_exchange(
            db,
            shipment_data,
            pickup_facility_data,
            dropoff_facility_data,
            pickup_contact_data,
            dropoff_contact_data,
            consignor_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/broker-access/exchange/ftl-lane-create", status_code=status.HTTP_201_CREATED)
def create_broker_exchange_ftl_lane_endpoint(
    shipment_data: Broker_Exchange_FTL_Lane_Booking,
    pickup_facility_data: ShipmentFacilityCreate,
    dropoff_facility_data: ShipmentFacilityCreate,
    pickup_contact_data: FacilityContactCreate,
    dropoff_contact_data: FacilityContactCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    consignor_data: Optional[ConsignorCreate] = None,
):
    try:
        result = broker_access_create_dedicated_ftl_lane_exchange(
            db,
            shipment_data,
            pickup_facility_data,
            dropoff_facility_data,
            pickup_contact_data,
            dropoff_contact_data,
            consignor_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))