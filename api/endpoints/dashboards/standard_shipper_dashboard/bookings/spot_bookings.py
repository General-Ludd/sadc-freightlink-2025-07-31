from datetime import date
from typing import Optional
from enums import Axle_Configuration, EquipmentType, Lorry, Recurrence_Days, Recurrence_Frequency, TrailerLength, TrailerType, TruckType
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import FTL_Lane_Create,  SpotFTLLaneQuoteRequest
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking, FTL_Shipment_docs_create
from schemas.shipment_facility import ShipmentFacilityCreate, FacilityContactCreate
from schemas.spot_bookings.power_shipment import POWER_Shipment_docs_create, Power_Shipment_Booking
from services.finance.finance import calculate_spot_ftl_lane_quote, calculate_spot_ftl_quote, calculate_spot_power_quote
from services.spot_bookings.dedicated_lanes_ftl_shipment import create_dedicated_lane_ftl_shipment
from services.spot_bookings.ftl_shipment import create_ftl_shipment
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from services.spot_bookings.power_shipment import create_spot_power_shipment
from utils.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/spot/ftl-shipment-qoute", status_code=status.HTTP_200_OK)
def get_spot_ftl_shipment_qoute_endpoint(
    origin_address: str,
    destination_address: str,
    minimum_weight_bracket: int,
    required_truck_type: TruckType,
    equipment_type: EquipmentType,
    trailer_type: Optional [TrailerType] = None,
    trailer_length: Optional [TrailerLength] = None,
    db: Session = Depends(get_db),
):
    try:
        result = calculate_spot_ftl_quote(
            db,
            origin_address,
            destination_address,
            required_truck_type,
            equipment_type,
            minimum_weight_bracket,
            trailer_type,
            trailer_length)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/spot/ftl-shipment-create", status_code=status.HTTP_201_CREATED)
def create_spot_ftl_endpoint(
    shipment_data: FTL_Shipment_Booking,
    pickup_facility_data: ShipmentFacilityCreate,
    dropoff_facility_data: ShipmentFacilityCreate,
    pickup_contact_data: FacilityContactCreate,
    dropoff_contact_data: FacilityContactCreate,
    shipment_documents_data: FTL_Shipment_docs_create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = create_ftl_shipment(
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
    
@router.post("/spot/ftl-lane-qoute", status_code=status.HTTP_200_OK)
def get_spot_ftl_lane_quote_endpoint(
    request: SpotFTLLaneQuoteRequest,
    db: Session = Depends(get_db)
):
    try:
        result = calculate_spot_ftl_lane_quote(
            db,
            start_date=request.start_date,
            end_date=request.end_date,
            recurrence_frequency=request.recurrence_frequency,
            skip_weekends=request.skip_weekends,
            recurrence_days=request.recurrence_days,
            shipments_per_interval=request.shipments_per_interval,
            origin_address=request.origin_address,
            destination_address=request.destination_address,
            required_truck_type=request.required_truck_type,
            equipment_type=request.equipment_type,
            trailer_type=request.trailer_type,
            trailer_length=request.trailer_length,
            minimum_weight_bracket=request.minimum_weight_bracket
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/spot/dedicated-ftl-lane-create", status_code=status.HTTP_201_CREATED)
def create_spot_ftl_endpoint(
    shipment_data: FTL_Lane_Create,
    pickup_facility_data: ShipmentFacilityCreate,
    dropoff_facility_data: ShipmentFacilityCreate,
    pickup_contact_data: FacilityContactCreate,
    dropoff_contact_data: FacilityContactCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = create_dedicated_lane_ftl_shipment(
            db,
            shipment_data,
            pickup_facility_data,
            dropoff_facility_data,
            pickup_contact_data,
            dropoff_contact_data,
            current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/spot/power-shipment-qoute", status_code=status.HTTP_200_OK)
def get_spot_power_shipment_qoute_endpoint(
    origin_address: str,
    destination_address: str,
    minimum_weight_bracket: int,
    required_truck_type: Lorry,
    axle_configuration: Axle_Configuration,
    db: Session = Depends(get_db),
):
    try:
        result = calculate_spot_power_quote(
            db,
            origin_address,
            destination_address,
            required_truck_type,
            axle_configuration,
            minimum_weight_bracket)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/spot/power-shipment-create", status_code=status.HTTP_201_CREATED)
def create_spot_power_ftl_endpoint(
    shipment_data: Power_Shipment_Booking,
    pickup_facility_data: ShipmentFacilityCreate,
    dropoff_facility_data: ShipmentFacilityCreate,
    pickup_contact_data: FacilityContactCreate,
    dropoff_contact_data: FacilityContactCreate,
    shipment_documents_data: POWER_Shipment_docs_create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = create_spot_power_shipment(
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