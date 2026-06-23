from datetime import date
from typing import Optional
from enums import Axle_Configuration, EquipmentType, Lorry, Recurrence_Days, Recurrence_Frequency, TrailerLength, TrailerType, TruckType
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import FTL_Lane_Create,  SpotFTLLaneQuoteRequest
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking, Admin_Client_FTL_Shipment_Booking, FTL_Shipment_docs_create
from schemas.shipment_facility import ShipmentFacilityCreate, FacilityContactCreate
from schemas.spot_bookings.power_shipment import POWER_Shipment_docs_create, Power_Shipment_Booking
from services.finance.finance import calculate_spot_ftl_lane_quote, calculate_spot_ftl_quote, calculate_spot_power_quote
from services.spot_bookings.dedicated_lanes_ftl_shipment import create_dedicated_lane_ftl_shipment
from services.spot_bookings.ftl_shipment import create_ftl_shipment, admin_create_client_ftl_shipment
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from services.spot_bookings.power_shipment import create_spot_power_shipment
from utils.auth import get_current_user
from utils.administration_auth import get_current_admin


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/admin/spot/client-ftl-shipment-create", status_code=status.HTTP_201_CREATED)
def admin_create_client_spot_ftl_endpoint(
    shipment_data: Admin_Client_FTL_Shipment_Booking,
    pickup_facility_data: ShipmentFacilityCreate,
    dropoff_facility_data: ShipmentFacilityCreate,
    pickup_contact_data: FacilityContactCreate,
    dropoff_contact_data: FacilityContactCreate,
    shipment_documents_data: FTL_Shipment_docs_create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        result = admin_create_client_ftl_shipment(
            db,
            shipment_data,
            pickup_facility_data,
            dropoff_facility_data,
            pickup_contact_data,
            dropoff_contact_data,
            shipment_documents_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))