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
######################################Shipments Management###################################################
#############################################################################################################
@router.get("/carrier/all-shipments", response_model=List[Assigned_Shipments_SummaryResponse])
def get_all_carrier_shipments_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")   

    try:
        shipments_summary = []

        # --- 1. Assigned Spot FTL Shipments ---
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.carrier_id == company_id
        ).all()

        for shipment in ftl_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="FTL",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        # --- 2. Assigned Power Shipments ---
        power_shipments = (
            db.query(Assigned_Power_Shipments)
            .filter(Assigned_Power_Shipments.carrier_id == company_id)  # Add this filter!
            .all()
        )

        for shipment in power_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="POWER",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        return shipments_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/carrier/all-assigned-shipments", response_model=List[Assigned_Shipments_SummaryResponse])
def get_all_carrier_assigned_shipments_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")   

    try:
        shipments_summary = []

        # --- 1. Assigned Spot FTL Shipments ---
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.carrier_id == company_id,
            Assigned_Spot_Ftl_Shipments.status != "Assigned"
        ).all()

        for shipment in ftl_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="FTL",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        # --- 2. Assigned Power Shipments ---
        power_shipments = (
            db.query(Assigned_Power_Shipments)
            .filter(Assigned_Power_Shipments.carrier_id == company_id,
                    Assigned_Power_Shipments != "Assigned")  # Add this filter!
            .all()
        )

        for shipment in power_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="POWER",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        return shipments_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/carrier/all-in-progress-shipments", response_model=List[Assigned_Shipments_SummaryResponse])
def get_all_carrier_in_progress_shipments_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")   

    try:
        shipments_summary = []

        # --- 1. Assigned Spot FTL Shipments ---
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.carrier_id == company_id,
            Assigned_Spot_Ftl_Shipments.status != "In-Progress"
        ).all()

        for shipment in ftl_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="FTL",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        # --- 2. Assigned Power Shipments ---
        power_shipments = (
            db.query(Assigned_Power_Shipments)
            .filter(Assigned_Power_Shipments.carrier_id == company_id,
                    Assigned_Power_Shipments != "In-Progress")  # Add this filter!
            .all()
        )

        for shipment in power_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="POWER",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        return shipments_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/all-completed-shipments", response_model=List[Assigned_Shipments_SummaryResponse])
def get_all_carrier_completed_shipments_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")   

    try:
        shipments_summary = []

        # --- 1. Assigned Spot FTL Shipments ---
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.carrier_id == company_id,
            Assigned_Spot_Ftl_Shipments.status != "Completed"
        ).all()

        for shipment in ftl_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="FTL",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        # --- 2. Assigned Power Shipments ---
        power_shipments = (
            db.query(Assigned_Power_Shipments)
            .filter(Assigned_Power_Shipments.carrier_id == company_id,
                    Assigned_Power_Shipments != "Completed")  # Add this filter!
            .all()
        )

        for shipment in power_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="POWER",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        return shipments_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/all-ftl-assigned-shipments", response_model=List[Assigned_Shipments_SummaryResponse])
def get_all_carrier_assigned_ftl_shipments_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")   

    try:
        shipments_summary = []

        # --- 1. Assigned Spot FTL Shipments ---
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.carrier_id == company_id,
            Assigned_Spot_Ftl_Shipments.status.notin_(["Assigned", "In-Progress", "Completed", "Delayed", "Cancelled"])
        ).all()

        for shipment in ftl_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="FTL",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        return shipments_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier/ftl-shipment/id")
def carrier_get_ftl_shipment_details(
    shipment_data: GetAssigned_Spot_Ftl_ShipmentRequest,
    db: Session = Depends(get_db)
):
    try:
        shipment = db.query(Assigned_Spot_Ftl_Shipments).filter_by(shipment_id=shipment_data.id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        vehicle = db.query(Vehicle).filter_by(id=shipment.vehicle_id).first() if shipment.vehicle_id else None
        driver = db.query(Driver).filter_by(id=shipment.driver_id).first() if shipment.driver_id else None
        documents = db.query(FTL_Shipment_Docs).filter_by(shipment_id=shipment.shipment_id).all()
        invoice = db.query(Load_Invoice).filter_by(id=shipment.invoice_id).first()

        return {
            "id": shipment.shipment_id,
            "is_subshipment": shipment.is_subshipment,
            "lane_id": shipment.lane_id,
            "type": shipment.type,
            "trip_type": shipment.trip_type,
            "load_type": shipment.load_type,
            "required_truck_type": shipment.required_truck_type,
            "equipment_type": shipment.equipment_type,
            "trailer_type": shipment.trailer_type,
            "trailer_length": shipment.trailer_length,
            "minimum_weight_bracket": shipment.minimum_weight_bracket,
            "shipment_weight": shipment.shipment_weight,
            "origin_address": shipment.origin_address_completed,
            "destination_address": shipment.destination_address_completed,
            "pickup_date": shipment.pickup_date,
            "priority_level": shipment.priority_level,
            "customer_reference_number": shipment.customer_reference_number,
            "commodity": shipment.commodity,
            "temperature_control": shipment.temperature_control,
            "min_git_cover": shipment.minimum_git_cover_amount,
            "min_liability_cover": shipment.minimum_liability_cover_amount,
            "packaging_quantity": shipment.packaging_quantity,
            "packaging_type": shipment.packaging_type,
            "hazardous_material": shipment.hazardous_materials,
            "pickup_number": shipment.pickup_number,
            "delivery_number": shipment.delivery_number,
            "distance": shipment.distance,
            "estimated_transit_time": shipment.estimated_transit_time,
            "pickup_notes": shipment.pickup_notes,
            "delivery_notes": shipment.delivery_notes,
            "payment_terms": shipment.payment_terms,

            "pickup_facility": {
                "location": shipment.origin_city_province if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "date": shipment.pickup_date,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "location": shipment.destination_city_province if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "date": shipment.eta_date,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "eta": shipment.eta_window,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            "vehicle": {
                "id": vehicle.id,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "license_plate": vehicle.license_plate,
                "color": vehicle.color,
                "vin": vehicle.vin,
                "axle_config": vehicle.axle_configuration,
                "license_expiry": vehicle.license_expiry_date,
                "vehicle_type": vehicle.type,
                "equipment_type": vehicle.equipment_type,
                "trailer_type": vehicle.trailer_type,
                "trailer_length": vehicle.trailer_length,
            } if vehicle else None,

            "driver": {
                "id": driver.id,
                "full_name": f"{driver.first_name} {driver.last_name}",
                "phone": driver.phone_number,
                "email": driver.email,
                "license_number": driver.license_number,
                "license_expiry": driver.license_expiry_date,
                "address": driver.address,
            } if driver else None,

            "documents": [{
                "id": doc.id,
                "commercial_invoice": doc.commercial_invoice,
                "packaging_list": doc.packaging_list,
                "customs_declaration_form": doc.customs_declaration_form,
                "import_or_export_permits": doc.import_or_export_permits,
                "certificate_of_origin": doc.certificate_of_origin,
                "da5501orsad500": doc.da5501orsad500,
                "pod": shipment.pod_document,
            } for doc in documents],

            "invoice": {
                "id": invoice.id,
                "status": invoice.status,
                "issued": invoice.billing_date,
                "due_date": invoice.due_date,
                "subtotal": invoice.base_amount,
                "total": invoice.due_amount,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/carrier/all-power-assigned-shipments", response_model=List[Assigned_Shipments_SummaryResponse])
def get_all_carrier_assigned_power_shipments_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")   

    try:
        shipments_summary = []

        # --- 1. Assigned Spot FTL Shipments ---
        ftl_shipments = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.carrier_id == company_id,
            Assigned_Power_Shipments.status.notin_(["Assigned", "In-Progress", "Completed", "Delayed", "Cancelled"])
        ).all()

        for shipment in ftl_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="FTL",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        return shipments_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/carrier/power-shipment/id")
def carrier_get_power_shipment_details(
    shipment_data: GetAssigned_Spot_Ftl_ShipmentRequest,
    db: Session = Depends(get_db)
):
    try:
        shipment = db.query(Assigned_Power_Shipments).filter_by(shipment_id=shipment_data.id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        trailer = db.query(ShipperTrailer).filter_by(id=shipment.trailer_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        vehicle = db.query(Vehicle).filter_by(id=shipment.vehicle_id).first() if shipment.vehicle_id else None
        driver = db.query(Driver).filter_by(id=shipment.driver_id).first() if shipment.driver_id else None
        documents = db.query(FTL_Shipment_Docs).filter_by(shipment_id=shipment.shipment_id).all()
        invoice = db.query(Load_Invoice).filter_by(id=shipment.invoice_id).first()

        return {
            "id": shipment.shipment_id,
            "is_subshipment": shipment.is_subshipment,
            "lane_id": shipment.lane_id,
            "type": shipment.type,
            "trip_type": shipment.trip_type,
            "load_type": shipment.load_type,
            "required_truck_type": shipment.required_truck_type,
            "axle_configuration": shipment.axle_configuration,
            "minimum_weight_bracket": shipment.minimum_weight_bracket,
            "shipment_weight": shipment.shipment_weight,
            "origin_address": shipment.origin_address_completed,
            "destination_address": shipment.destination_address_completed,
            "pickup_date": shipment.pickup_date,
            "priority_level": shipment.priority_level,
            "customer_reference_number": shipment.customer_reference_number,
            "commodity": shipment.commodity,
            "temperature_control": shipment.temperature_control,
            "min_git_cover": shipment.minimum_git_cover_amount,
            "min_liability_cover": shipment.minimum_liability_cover_amount,
            "packaging_quantity": shipment.packaging_quantity,
            "packaging_type": shipment.packaging_type,
            "hazardous_material": shipment.hazardous_materials,
            "pickup_number": shipment.pickup_number,
            "delivery_number": shipment.delivery_number,
            "distance": shipment.distance,
            "estimated_transit_time": shipment.estimated_transit_time,
            "is_trailer_loaded": shipment.is_trailer_loaded,
            "pickup_notes": shipment.pickup_notes,
            "delivery_notes": shipment.delivery_notes,
            "payment_terms": shipment.payment_terms,

            "trailer": {
                "id": trailer.id,
                "is_verified": trailer.is_verified,
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.year,
                "color": trailer.color,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "vin": trailer.vin,
                "license_plate": trailer.license_plate,
                "tare_weight": trailer.tare_weight,
                "gvm_weight": trailer.gvm_weight,
                "payload_capacity": trailer.payload_capacity,
            },

            "pickup_facility": {
                "location": shipment.origin_city_province if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "date": shipment.pickup_date,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "location": shipment.destination_city_province if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "date": shipment.eta_date,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "eta": shipment.eta_window,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            "vehicle": {
                "id": vehicle.id,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "license_plate": vehicle.license_plate,
                "color": vehicle.color,
                "vin": vehicle.vin,
                "axle_config": vehicle.axle_configuration,
                "license_expiry": vehicle.license_expiry_date,
                "vehicle_type": vehicle.type,
                "payload_capacity": vehicle.payload_capacity,
            } if vehicle else None,

            "driver": {
                "id": driver.id,
                "full_name": f"{driver.first_name} {driver.last_name}",
                "phone": driver.phone_number,
                "email": driver.email,
                "license_number": driver.license_number,
                "license_expiry": driver.license_expiry_date,
                "address": driver.address,
            } if driver else None,

            "documents": [{
                "id": doc.id,
                "commercial_invoice": doc.commercial_invoice,
                "packaging_list": doc.packaging_list,
                "customs_declaration_form": doc.customs_declaration_form,
                "import_or_export_permits": doc.import_or_export_permits,
                "certificate_of_origin": doc.certificate_of_origin,
                "da5501orsad500": doc.da5501orsad500,
                "pod": shipment.pod_document,
            } for doc in documents],

            "invoice": {
                "id": invoice.id,
                "status": invoice.status,
                "issued": invoice.billing_date,
                "due_date": invoice.due_date,
                "subtotal": invoice.base_amount,
                "total": invoice.due_amount,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
