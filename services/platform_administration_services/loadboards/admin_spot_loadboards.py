from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.loadboard import Dedicated_lanes_LoadBoard, Ftl_Load_Board, Power_Load_Board
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Lane_LoadBoard, Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.carrier import Carrier
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from schemas.brokerage.loadboard import AssignShipmentRequest, FTL_Lane_LoadBoard_Summary_Response, FTL_Lane_Loadboard_Individual_Shipment_Response, Individual_lane_id, IndividualLoadboardShipmentRequest, IndividualSpotPowerLoadboardShipmentResponse, SpotFTLLoadBoardSummaryResponse, SpotPowerLoadBoardSummaryResponse
from schemas.shipment_facility import FacilityContactPersonResponse
from schemas.user import DriverCreate, DriverResponse
from schemas.vehicle import TrailerCreate, TrailerResponse, VehicleCreate, VehicleResponse, VehicleUpdate
from services.brokerage.carrier_loadboard_service import assign_spot_ftl_lane_to_carrier, assign_spot_ftl_shipment_to_carrier, assign_spot_power_shipment_to_carrier
from services.carrier_service import fleet_create_driver
from services.carrier_dashboards import assign_trailer_to_vehicle
from services.vehicle_service import create_trailer, create_vehicle
from utils.administration_auth import get_current_admin
from models.user import CarrierUser, Driver
from models.vehicle import ShipperTrailer, Trailer, Vehicle
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/admin/spot/ftl-loadboard") #UnTested
def admin_get_all_spot_ftl_loadboard_loads(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
): 
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        shipments = db.query(Ftl_Load_Board).filter(Ftl_Load_Board.status == "Available").all()

        return {
            "shipments": [{
                "id": shipment.shipment_id,
                "trip_type": shipment.trip_type,
                "rate": shipment.shipment_rate,
                "distance": shipment.distance,
                "route_preview_embed": shipment.route_preview_embed,
                "rate_per_kilometer": shipment.rate_per_km,
                "origin": shipment.origin_city_province,
                "pickup_date": shipment.pickup_date,
                "pickup_appointment": shipment.pickup_appointment,
                "destination": shipment.destination_city_province,
                "eta_date": shipment.eta_date,
                "eta_window": shipment.eta_window,
                "required_truck_type": shipment.required_truck_type,
                "equipment_type": shipment.equipment_type,
                "trailer_type": shipment.trailer_type,
                "trailer_length": shipment.trailer_length,
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "commodity": shipment.commodity,
                "hazardous_materials": shipment.hazardous_metarials
            } for shipment in shipments]
        }
    except Exception as e:
        return {"error": str(e)}
    
@router.get("/admin/spot/ftl-loadboard/{id}")
def admin_get_individual_spot_ftl_loadboard_shipment(
    id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        shipment = db.query(Ftl_Load_Board).filter(Ftl_Load_Board.shipment_id == id).first()

        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        return {
            "shipment_details": {
                "id": shipment.shipment_id,
                "type": shipment.type,
                "load_type": shipment.load_type,
                "trip_type": shipment.trip_type,
                "status": shipment.status,
                "required_truck_type": shipment.required_truck_type,
                "equipment_type": shipment.equipment_type,
                "trailer_type": shipment.trailer_type if shipment.trailer_type else "N/A",
                "trailer_length": shipment.trailer_length if shipment.trailer_length else "N/A",
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "minimum_git_cover_amount": shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": shipment.minimum_liability_cover_amount,
                "origin": shipment.origin_city_province,
                "destination": shipment.destination_city_province,
                "distance": shipment.distance,
                "rate": shipment.shipment_rate,
                "rate_per_km": shipment.rate_per_km,
                "rate_per_ton": shipment.rate_per_ton,
                "pickup_date": shipment.pickup_date,
                "eta_data": shipment.eta_date,
                "payment_terms": shipment.payment_terms,
                "payment_date": shipment.payment_date,
                "minimum_transit_time": shipment.estimated_transit_time,
                "route_preview": shipment.route_preview_embed,
                "commodity": shipment.commodity,
                "temperature_control": shipment.temperature_control,
                "hazardous_materails": shipment.hazardous_metarials,
                "packaging_quantity": shipment.packaging_quantity,
                "packaging_type": shipment.packaging_type,
                "pickup_number": shipment.pickup_number,
                "pickup_notes": shipment.pickup_notes,
                "delivery_number": shipment.delivery_number,
                "delivery_notes": shipment.delivery_notes,
            },
            "pickup_facility": {
                "name": shipment.pickup_facility_name,
                "address": shipment.origin_address,
                "scheduling_type": shipment.pickup_scheduling_type,
                "operating_hours": f"{shipment.pickup_start_time} - {shipment.pickup_end_time}",
                "contact_person": f"{shipment.pickup_first_name} {shipment.pickup_last_name}",
                "phone_number": shipment.pickup_phone_number,
                "email": shipment.pickup_email,
            },
            "delivery_facility": {
                "name": shipment.delivery_facility_name,
                "address": shipment.destination_address,
                "scheduling_type": shipment.delivery_scheduling_type,
                "operating_hours": f"{shipment.delivery_start_time} - {shipment.delivery_end_time}",
                "contact_person": f"{shipment.delivery_first_name} {shipment.delivery_last_name}",
                "phone_number": shipment.delivery_phone_number,
                "email": shipment.delivery_email,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
#####################################################################################################
############################################FTL Lane Loadboard#######################################
#####################################################################################################
@router.get("/admin/dedicated-ftl-lane-loadboard") #UnTested
def admin_get_all_spot_ftl_lanes_loads(
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin)
):
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        ftl_lanes = db.query(Dedicated_lanes_LoadBoard).filter(Dedicated_lanes_LoadBoard.status == "Available").all()
        return {
            "lanes": [{
                "id": ftl_lane.shipment_id,
                "status": ftl_lane.status,
                "trip_type": ftl_lane.trip_type,
                "load_type": ftl_lane.load_type,
                "origin": ftl_lane.origin_city_province,
                "destination": ftl_lane.destination_city_province,
                "distance": ftl_lane.distance,
                "full_route": ftl_lane.route_preview_embed,
                "truck_type": ftl_lane.required_truck_type,
                "equipment_type": ftl_lane.equipment_type if ftl_lane.equipment_type else "N/A",
                "trailer_type": ftl_lane.trailer_type if ftl_lane.trailer_type else "N/A",
                "trailer_length": ftl_lane.trailer_length if ftl_lane.trailer_length else "N/A",
                "minimum_weight_bracket": ftl_lane.minimum_weight_bracket,
                "commodity": ftl_lane.commodity,
                "packaging_type": ftl_lane.packaging_type,
                "average_shipment_weight": ftl_lane.average_shipment_weight,
                "start_date": ftl_lane.start_date,
                "end_date": ftl_lane.end_date,
                "frequency": ftl_lane.recurrence_frequency,
                "recurrence_days": ftl_lane.recurrence_days,
                "shipment_per_interval": ftl_lane.shipments_per_interval,
                "total_shipments": ftl_lane.total_shipments,
                "per_shipment_rate": ftl_lane.rate_per_shipment,
                "contract_rate": ftl_lane.contract_rate,
            } for ftl_lane in ftl_lanes]
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/admin/spot/ftl-lane-loadboard/{id}")
def admin_get_individual_loadboard_ftl_lane(
    id: int,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        lane = db.query(Dedicated_lanes_LoadBoard).filter(Dedicated_lanes_LoadBoard.shipment_id == id).first()
        if not lane:
            raise HTTPException(status_code=404, detail="Lane not found")
            
        return {
            "lane_information": {
                "id": lane.shipment_id,
                "status": lane.status,
                "type": lane.type,
                "load_type": lane.load_type,
                "trip_type": lane.trip_type,
                "origin": lane.origin_city_province,
                "destination": lane.destination_city_province,
                "distance": lane.distance,
                "minimum_transit_time": lane.estimated_transit_time,
                "route_preview": lane.route_preview_embed,
                "required_truck_type": lane.required_truck_type,
                "equipment_type": lane.equipment_type,
                "trailer_type": lane.trailer_type if lane.trailer_type else "N/A",
                "trailer_length": lane.trailer_length if lane.trailer_length else "N/A",
                "minimum_weight_bracket": lane.minimum_weight_bracket,
                "average_shipment_weight": lane.average_shipment_weight,
                "minimum_git_cover_amount": lane.minimum_git_cover_amount,
                "minimum_liability_cover_amount": lane.minimum_liability_cover_amount,
                "commodity": lane.commodity,
                "temperature_control": lane.temperature_control,
                "hazardous_materials": lane.hazardous_materials,
                "packaging_quantity": lane.packaging_quantity,
                "packaging_type": lane.packaging_type,
                "pickup_number": lane.pickup_number,
                "pickup_notes": lane.pickup_notes,
                "delivery_number": lane.delivery_number,
                "delivery_notes": lane.delivery_notes,
            },
            "contract_information": {
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "recurrence_frequency": lane.recurrence_frequency,
                "recurrence_days": lane.recurrence_days,
                "shipments_per_interval": lane.shipments_per_interval,
                "total_shipments": lane.total_shipments,
                "per_shipment_rate": lane.rate_per_shipment,
                "total_contract_rate": lane.contract_rate,
                "distance_per_shipment": lane.distance,
                "rate_per_km": lane.rate_per_km,
                "rate_per_ton": lane.rate_per_ton,
                "shipment_dates": lane.shipment_dates,
                "payment_dates": lane.payment_dates,
            },
            "pickup_facility": {
                "name": lane.pickup_facility_name,
                "address": lane.origin_address,
                "scheduling_type": lane.pickup_scheduling_type,
                "operating_hours": f"{lane.pickup_start_time} - {lane.pickup_end_time}",
                "contact_person": f"{lane.pickup_first_name} {lane.pickup_last_name}",
                "phone_number": lane.pickup_phone_number,
                "email": lane.pickup_email,
            },
            "delivery_facility": {
                "name": lane.delivery_facility_name,
                "address": lane.destination_address,
                "scheduling_type": lane.delivery_scheduling_type,
                "operating_hours": f"{lane.delivery_start_time} - {lane.delivery_end_time}",
                "contact_person": f"{lane.delivery_first_name} {lane.delivery_last_name}",
                "phone_number": lane.delivery_phone_number,
                "email": lane.delivery_email,
            },
        }
    except Exception as e:
        return {"error": str(e)}
