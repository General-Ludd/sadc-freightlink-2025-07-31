from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import CarrierFinancialAccounts, Lane_Interim_Invoice, Load_Invoice
from models.carrier import Carrier
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from schemas.brokerage.assigned_lanes import Dedicated_Ftl_Lane_Summary_Response
from schemas.brokerage.assigned_shipments import Assigned_Shipments_SummaryResponse, GetAssigned_Spot_Ftl_ShipmentRequest
from schemas.brokerage.finance import CarrierFinancialAccountResponse
from schemas.carrier import CarrierCompanyResponse
from schemas.user import CarrierUserResponse, DriverCreate, DriverResponse
from schemas.vehicle import Fleet_Trailer_Truck_response, TrailerCreate, TrailerResponse, Trailers_Summary_Response, Vehicle_Info, Vehicle_Schedule_Response, VehicleCreate, VehicleResponse, VehicleUpdate, Vehicles_Summary_Response
from services.carrier_service import fleet_create_driver
from services.carrier_dashboards import assign_primary_driver, assign_trailer_to_vehicle
from services.vehicle_service import create_trailer, create_vehicle
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import CarrierUser, Driver
from models.vehicle import ShipperTrailer, Trailer, Vehicle, Vehicle_Schedule
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#############################################################################################################
######################################Contact Lanes Management###############################################
#############################################################################################################
@router.get("/carrier/all-ftl-assigned-lanes", response_model=List[Dedicated_Ftl_Lane_Summary_Response])
def get_all_carrier_assigned_ftl_lanes_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")   

    try:
        shipments_summary = []

        # --- 1. Assigned Spot FTL Shipments ---
        lanes = db.query(Assigned_Ftl_Lanes).filter(
            Assigned_Ftl_Lanes.carrier_id == company_id,
        ).all()

        for lane in lanes:

            shipments_summary.append(Dedicated_Ftl_Lane_Summary_Response(
                id=lane.id,
                lane_id=lane.lane_id,
                type=lane.type,
                status=lane.status,
                contract_rate=lane.contract_rate,
                origin_city_province=lane.origin_city_province,
                destination_city_province=lane.destination_city_province,
                distance=lane.distance,
                recurrence_frequency=lane.recurrence_frequency,
                shipments_per_interval=lane.shipments_per_interval,
                start_date=lane.start_date,
                end_date=lane.end_date,
                total_shipments_completed=lane.total_shipment_completed
            ))

        return shipments_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/carrier/ftl-lane/id")
def carrier_get_ftl_lane_details(
    lane_data: GetAssigned_Spot_Ftl_ShipmentRequest,
    db: Session = Depends(get_db)
):
    try:
        lane = db.query(Assigned_Ftl_Lanes).filter_by(lane_id=lane_data.id).first()
        if not lane:
            raise HTTPException(status_code=404, detail="Contract lane not found")

        pickup_facility = db.query(ShipmentFacility).filter_by(id=lane.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=lane.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        lane_sub_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter_by(lane_id=lane.lane_id).all()
        lane_interim_invoices = db.query(Lane_Interim_Invoice).filter_by(contract_id=lane.lane_id).all()

        return {
            "id": lane.lane_id,
            "type": lane.type,
            "trip_type": lane.trip_type,
            "load_type": lane.load_type,
            "required_truck_type": lane.required_truck_type,
            "equipment_type": lane.equipment_type,
            "trailer_type": lane.trailer_type,
            "trailer_length": lane.trailer_length,
            "minimum_weight_bracket": lane.minimum_weight_bracket,
            "shipment_weight": lane.average_shipment_weight,
            "origin_address": lane.origin_address,
            "destination_address": lane.destination_address,
            "start_date": lane.start_date,
            "end_date": lane.end_date,
            "priority_level": lane.priority_level,
            "customer_reference_number": lane.customer_reference_number,
            "commodity": lane.commodity,
            "temperature_control": lane.temperature_control,
            "min_git_cover": lane.minimum_git_cover_amount,
            "min_liability_cover": lane.minimum_liability_cover_amount,
            "packaging_quantity": lane.packaging_quantity,
            "packaging_type": lane.packaging_type,
            "hazardous_material": lane.hazardous_materials,
            "pickup_number": lane.pickup_number,
            "delivery_number": lane.delivery_number,
            "distance": lane.distance,
            "estimated_transit_time": lane.estimated_transit_time,
            "pickup_notes": lane.pickup_notes,
            "delivery_notes": lane.delivery_notes,
            "payment_terms": lane.payment_terms,
            "contract_progress": lane.total_shipment_completed,
            "route_preview_embed": lane.route_preview_embed,

            "pickup_facility": {
                "location": lane.origin_city_province if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "location": lane.destination_city_province if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            "contract_details": {
                "recurrence_frequency": lane.recurrence_frequency,
                "recurrence_days": lane.recurrence_days,
                "shipments_per_interval": lane.shipments_per_interval,
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "total_shipments": lane.total_shipments,
                "contract_rate": lane.contract_rate,
                "per_shipment_rate": lane.rate_per_shipment,
                "payment_terms": lane.payment_terms,
            },

            "payment_schedule": [{
                "due_date": lane_interim_invoice.due_date,
                "amount": lane_interim_invoice.due_amount,
                "status": lane_interim_invoice.status,
            } for lane_interim_invoice in lane_interim_invoices],

            "lane_sub_shipments": [{
                "shipment_id": lane_sub_shipment.shipment_id,
                "date": lane_sub_shipment.pickup_date,
                "route": f"{lane_sub_shipment.origin_city_province} to {lane_sub_shipment.destination_city_province}",
                "status": lane_sub_shipment.status,
            } for lane_sub_shipment in lane_sub_shipments],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

