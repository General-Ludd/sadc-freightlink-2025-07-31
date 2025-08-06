from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, CarrierFinancialAccounts, FinancialAccounts, Interim_Invoice, Load_Invoice
from models.brokerage.loadboard import Ftl_Load_Board
from models.carrier import Carrier
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.user import Driver
from models.vehicle import ShipperTrailer, Vehicle
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import Ftl_Lanes_Summary_Response, Individual_FTL_Lane_Response, individual_shipment_or_lane_request
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Response, FTL_Shipments_Summary_Response
from schemas.spot_bookings.power_shipment import POWER_SHIPMENT_RESPONSE, Power_Shipments_Summary_Response
from utils.auth import get_current_user
from services.cancellations.spot_cancellations import cancel_spot_ftl_shipment


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/shipper/all-shipments/modes")
def shipper_get_all_shipment_modes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_company_id == company_id).all()
        power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipper_company_id == company_id).all()

        return {
            "ftl_shipments": [{
                "id": ftl_shipment.id,
                "type": ftl_shipment.type,
                "trip_status": ftl_shipment.trip_status,
                "priority_level": ftl_shipment.priority_level,
                "status": ftl_shipment.shipment_status,
                "origin": ftl_shipment.origin_city_province,
                "pickup_date": ftl_shipment.pickup_date,
                "pickup_window": ftl_shipment.pickup_appointment,
                "destination": ftl_shipment.destination_city_province,
                "eta_date": ftl_shipment.eta_date,
                "eta_window": ftl_shipment.eta_window,
            } for ftl_shipment in ftl_shipments],

            "power_shipmnets": [{
                "id": power_shipment.id,
                "type": power_shipment.type,
                "trip_status": power_shipment.trip_status,
                "priority_level": power_shipment.priority_level,
                "status": power_shipment.shipment_status,
                "origin": power_shipment.origin_city_province,
                "pickup_date": power_shipment.pickup_date,
                "pickup_window": power_shipment.pickup_appointment,
                "destination": power_shipment.destination_city_province,
                "eta_date": power_shipment.eta_date,
                "eta_window": power_shipment.eta_window,
            } for power_shipment in power_shipments],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/shipper/all-shipments-modes/booked")
def shipper_get_all_shipment_modes_booked(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_company_id == company_id,
                                                      POWER_SHIPMENT.shipment_status == "Booked").all()
        power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipper_company_id == company_id,
                                                          POWER_SHIPMENT.shipment_status == "Booked").all()

        return {
            "ftl_shipments": [{
                "id": ftl_shipment.id,
                "type": ftl_shipment.type,
                "trip_status": ftl_shipment.trip_status,
                "priority_level": ftl_shipment.priority_level,
                "status": ftl_shipment.shipment_status,
                "origin": ftl_shipment.origin_city_province,
                "pickup_date": ftl_shipment.pickup_date,
                "pickup_window": ftl_shipment.pickup_appointment,
                "destination": ftl_shipment.destination_city_province,
                "eta_date": ftl_shipment.eta_date,
                "eta_window": ftl_shipment.eta_window,
            } for ftl_shipment in ftl_shipments],

            "power_shipmnets": [{
                "id": power_shipment.id,
                "type": power_shipment.type,
                "trip_status": power_shipment.trip_status,
                "priority_level": power_shipment.priority_level,
                "status": power_shipment.shipment_status,
                "origin": power_shipment.origin_city_province,
                "pickup_date": power_shipment.pickup_date,
                "pickup_window": power_shipment.pickup_appointment,
                "destination": power_shipment.destination_city_province,
                "eta_date": power_shipment.eta_date,
                "eta_window": power_shipment.eta_window,
            } for power_shipment in power_shipments],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/shipper/all-shipments-modes/in-progress")
def shipper_get_all_shipment_modes_in_progress(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_company_id == company_id,
                                                      POWER_SHIPMENT.shipment_status == "In-Progress").all()
        power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipper_company_id == company_id,
                                                          POWER_SHIPMENT.shipment_status == "In-Progress").all()

        return {
            "ftl_shipments": [{
                "id": ftl_shipment.id,
                "type": ftl_shipment.type,
                "trip_status": ftl_shipment.trip_status,
                "priority_level": ftl_shipment.priority_level,
                "status": ftl_shipment.shipment_status,
                "origin": ftl_shipment.origin_city_province,
                "pickup_date": ftl_shipment.pickup_date,
                "pickup_window": ftl_shipment.pickup_appointment,
                "destination": ftl_shipment.destination_city_province,
                "eta_date": ftl_shipment.eta_date,
                "eta_window": ftl_shipment.eta_window,
            } for ftl_shipment in ftl_shipments],

            "power_shipmnets": [{
                "id": power_shipment.id,
                "type": power_shipment.type,
                "trip_status": power_shipment.trip_status,
                "priority_level": power_shipment.priority_level,
                "status": power_shipment.shipment_status,
                "origin": power_shipment.origin_city_province,
                "pickup_date": power_shipment.pickup_date,
                "pickup_window": power_shipment.pickup_appointment,
                "destination": power_shipment.destination_city_province,
                "eta_date": power_shipment.eta_date,
                "eta_window": power_shipment.eta_window,
            } for power_shipment in power_shipments],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/shipper/all-shipments-modes/completed")
def shipper_get_all_shipment_modes_completed(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_company_id == company_id,
                                                      POWER_SHIPMENT.shipment_status == "Completed").all()
        power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipper_company_id == company_id,
                                                          POWER_SHIPMENT.shipment_status == "Completed").all()

        return {
            "ftl_shipments": [{
                "id": ftl_shipment.id,
                "type": ftl_shipment.type,
                "trip_status": ftl_shipment.trip_status,
                "priority_level": ftl_shipment.priority_level,
                "status": ftl_shipment.shipment_status,
                "origin": ftl_shipment.origin_city_province,
                "pickup_date": ftl_shipment.pickup_date,
                "pickup_window": ftl_shipment.pickup_appointment,
                "destination": ftl_shipment.destination_city_province,
                "eta_date": ftl_shipment.eta_date,
                "eta_window": ftl_shipment.eta_window,
            } for ftl_shipment in ftl_shipments],

            "power_shipmnets": [{
                "id": power_shipment.id,
                "type": power_shipment.type,
                "trip_status": power_shipment.trip_status,
                "priority_level": power_shipment.priority_level,
                "status": power_shipment.shipment_status,
                "origin": power_shipment.origin_city_province,
                "pickup_date": power_shipment.pickup_date,
                "pickup_window": power_shipment.pickup_appointment,
                "destination": power_shipment.destination_city_province,
                "eta_date": power_shipment.eta_date,
                "eta_window": power_shipment.eta_window,
            } for power_shipment in power_shipments],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/shipper/ftl/all-shipments") #UnTested
def shipper_get_all_ftl_shipments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_company_id == company_id).all()

        return {
            "ftl_shipments": [{
                "id": ftl_shipment.id,
                "type": ftl_shipment.type,
                "trip_status": ftl_shipment.trip_status,
                "priority_level": ftl_shipment.priority_level,
                "status": ftl_shipment.shipment_status,
                "origin": ftl_shipment.origin_city_province,
                "pickup_date": ftl_shipment.pickup_date,
                "pickup_window": ftl_shipment.pickup_appointment,
                "destination": ftl_shipment.destination_city_province,
                "eta_date": ftl_shipment.eta_date,
                "eta_window": ftl_shipment.eta_window,
            } for ftl_shipment in ftl_shipments],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/shipper/ftl-shipment/id")
def shipper_get_individual_ftl_shipment(
    shipment_data: individual_shipment_or_lane_request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == shipment_data.id).first()
        carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
        vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
        driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        return {
            "shipment_details": {
                "id": shipment.id,
                "invoice_id": shipment.invoice_id,
                "status": shipment.shipment_status,
                "trip_status": shipment.trip_status,
                "is_sub_shipment": shipment.is_subshipment,
                "lane_id": shipment.dedicated_lane_id,
                "shipment_type": shipment.type,
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
                "required_truck_type": shipment.required_truck_type,
                "required_equipment_type": shipment.equipment_type,
                "required_trailer_type": shipment.trailer_type,
                "required_trailer_length": shipment.trailer_length,
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "origin_address": shipment.complete_origin_address,
                "destination_address": shipment.complete_destination_address,
                "pickup_date": shipment.pickup_date,
                "priority_level": shipment.priority_level,
                "customer_referece_number": shipment.customer_reference_number,
                "shipment_weight": shipment.shipment_weight,
                "commodity": shipment.commodity,
                "temperature_control": shipment.temperature_control,
                "hazardous_materials": shipment.hazardous_materials,
                "minimum_git_cover_amount": shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": shipment.minimum_liability_cover_amount,
                "packaging_quantity": shipment.packaging_quantity,
                "packaging_type": shipment.packaging_type,
                "pickup_number": shipment.pickup_number,
                "delivery_number": shipment.delivery_number,
                "pickup_notes": shipment.pickup_notes,
                "delivery_notes": shipment.delivery_notes,
                "distance": shipment.distance,
                "estimated_transit_time": shipment.estimated_transit_time,
                "route_preview_embed": shipment.route_preview_embed,
            },

            "carrier_information": {
                "id": carrier.id if carrier else "N/A",
                "carrier_name": f"SADC FREIGHTLINK Carrier-{carrier.id}" if carrier else "N/A",
                "carrier_git_cover": carrier.git_cover_amount if carrier else "N/A",
                "carrier_liability_cover_amount": carrier.liability_insurance_cover_amount if carrier else "N/A",
    
                "assigned_vehicle": {
                    "id": vehicle.id if vehicle else "N/A",
                    "make": vehicle.make if vehicle else "N/A",
                    "model": vehicle.model if vehicle else "N/A",
                    "year": vehicle.color if vehicle else "N/A",
                    "license_plate": vehicle.license_plate if vehicle else "N/A",
                    "vin": vehicle.vin if vehicle else "N/A",
                    "vehicle_type": vehicle.type if vehicle else "N/A",
                    "equipment_type": vehicle.equipment_type if vehicle else "N/A",
                    "trailer_type": vehicle.trailer_type if vehicle else "N/A",
                    "trailer_length": vehicle.trailer_length if vehicle else "N/A",
                    "tare_weight": vehicle.tare_weight if vehicle else "N/A",
                    "gvm_weight": vehicle.gvm_weight if vehicle else "N/A",
                    "payload_capacity": vehicle.payload_capacity if vehicle else "N/A",
                },

                "assigned_driver": {
                    "id": driver.id if driver else "N/A",
                    "first_name": driver.first_name if driver else "N/A",
                    "last_name": driver.last_name if driver else "N/A",
                    "license_number": driver.license_number if driver else "N/A",
                    "email": driver.email if driver else "N/A",
                    "phone_number": driver.phone_number if driver else "N/A",
                },

                "financial": {
                    "price": shipment.quote,
                    "rate_per_kilometer": (shipment.quote/shipment.distance),
                    "rate_per_ton": (shipment.quote / shipment.minimum_weight_bracket),
                    "distance": shipment.distance,
                    "payment_terms": shipment.payment_terms,
                    "invoice_due_date": shipment.invoice_due_date,
                },

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "scheduling_type": pickup_facility.scheduling_type,
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "scheduling_type": delivery_facility.scheduling_type,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            }
    }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/spot/ftl-shipment-cancel/{shipment_id}", status_code=status.HTTP_200_OK)
def cancel_spot_ftl_shipment_endpoint(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Cancels a Spot FTL shipment by ID.
    """
    try:
        result = cancel_spot_ftl_shipment(
            db=db,
            shipment_id=shipment_id,
            cancelled_by_user_id=current_user["user_id"]  # Adjust key if needed
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/shipper/power/all-shipments")
def shipper_get_all_power_shipments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipper_company_id == company_id).all()

        return {
            "power_shipmnets": [{
                "id": power_shipment.id,
                "type": power_shipment.type,
                "trip_status": power_shipment.trip_status,
                "priority_level": power_shipment.priority_level,
                "status": power_shipment.shipment_status,
                "origin": power_shipment.origin_city_province,
                "pickup_date": power_shipment.pickup_date,
                "pickup_window": power_shipment.pickup_appointment,
                "destination": power_shipment.destination_city_province,
                "eta_date": power_shipment.eta_date,
                "eta_window": power_shipment.eta_window,
            } for power_shipment in power_shipments],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/shipper/power-shipment/id")
def shipper_get_individual_power_shipment(
    shipment_data: individual_shipment_or_lane_request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        shipment = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.id == shipment_data.id).first()
        trailer = db.query(ShipperTrailer).filter(ShipperTrailer.id == shipment.trailer_id).first()

        carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
        vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
        driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        return {
            "shipment_details": {
                "id": shipment.id,
                "invoice_id": shipment.invoice_id,
                "status": shipment.shipment_status,
                "trip_status": shipment.trip_status,
                "is_sub_shipment": shipment.is_subshipment,
                "lane_id": shipment.dedicated_lane_id,
                "shipment_type": shipment.type,
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
                "required_truck_type": shipment.required_truck_type,
                "axle_configuration": shipment.axle_configuration,
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "origin_address": shipment.complete_origin_address,
                "destination_address": shipment.complete_destination_address,
                "pickup_date": shipment.pickup_date,
                "priority_level": shipment.priority_level,
                "customer_referece_number": shipment.customer_reference_number,
                "shipment_weight": shipment.shipment_weight,
                "commodity": shipment.commodity,
                "temperature_control": shipment.temperature_control,
                "hazardous_materials": shipment.hazardous_materials,
                "minimum_git_cover_amount": shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": shipment.minimum_liability_cover_amount,
                "packaging_quantity": shipment.packaging_quantity,
                "packaging_type": shipment.packaging_type,
                "pickup_number": shipment.pickup_number,
                "delivery_number": shipment.delivery_number,
                "pickup_notes": shipment.pickup_notes,
                "delivery_notes": shipment.delivery_notes,
                "distance": shipment.distance,
                "estimated_transit_time": shipment.estimated_transit_time,
                "route_preview_embed": shipment.route_preview_embed,
            },

            "shipper_trailer_information": {
                "id": trailer.id,
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.model,
                "color": trailer.color,
                "license_plate": trailer.license_plate,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "tare_weight": trailer.tare_weight,
                "gvm_weight": trailer.gvm_weight,
                "payload_capacity": trailer.payload_capacity,
            },

            "carrier_information": {
                "id": carrier.id if carrier else "N/A",
                "carrier_name": f"SADC FREIGHTLINK Carrier-{carrier.id}" if carrier else "N/A",
                "carrier_git_cover": carrier.git_cover_amount if carrier else "N/A",
                "carrier_liability_cover_amount": carrier.liability_insurance_cover_amount if carrier else "N/A",
    
                "assigned_vehicle": {
                    "id": vehicle.id if vehicle else "N/A",
                    "make": vehicle.make if vehicle else "N/A",
                    "model": vehicle.model if vehicle else "N/A",
                    "year": vehicle.color if vehicle else "N/A",
                    "license_plate": vehicle.license_plate if vehicle else "N/A",
                    "vin": vehicle.vin if vehicle else "N/A",
                    "vehicle_type": vehicle.type if vehicle else "N/A",
                    "axle_configuration": vehicle.axle_configuration,
                    "tare_weight": vehicle.tare_weight if vehicle else "N/A",
                    "gvm_weight": vehicle.gvm_weight if vehicle else "N/A",
                    "payload_capacity": vehicle.payload_capacity if vehicle else "N/A",
                },

                "assigned_driver": {
                    "id": driver.id if driver else "N/A",
                    "first_name": driver.first_name if driver else "N/A",
                    "last_name": driver.last_name if driver else "N/A",
                    "license_number": driver.license_number if driver else "N/A",
                    "email": driver.email if driver else "N/A",
                    "phone_number": driver.phone_number if driver else "N/A",
                },

                "financial": {
                    "price": shipment.quote,
                    "rate_per_kilometer": (shipment.quote/shipment.distance),
                    "distance": shipment.distance,
                    "payment_terms": shipment.payment_terms,
                    "invoice_due_date": shipment.invoice_due_date,
                },

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "scheduling_type": pickup_facility.scheduling_type,
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "scheduling_type": delivery_facility.scheduling_type,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            }
    }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/spot/power-shipment-cancel/{shipment_id}", status_code=status.HTTP_200_OK)
def cancel_spot_power_shipment_endpoint(
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Cancels a Spot POWER shipment by ID.
    """
    try:
        result = cancel_spot_power_shipment(
            db=db,
            shipment_id=shipment_id,
            current_user=current_user,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/shipper/all-lanes/all-modes")
def get_all_shipper_dedicated_lanes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    
    try:
        ftl_lanes = db.query(FTL_Lane).filter(FTL_Lane.shipper_company_id == company_id).all()

        return {
            "ftl_lanes": [{
                "id": ftl_lane.id,
                "type": ftl_lane.type,
                "status": ftl_lane.status,
                "priority_level": ftl_lane.priority_level,
                "progress": ftl_lane.progress,
                "origin": ftl_lane.origin_city_province,
                "destination": ftl_lane.destination_city_province,
                "distance": ftl_lane.distance,
                "contract_rate": ftl_lane.contract_quote,
                "shipment_rate": ftl_lane.qoute_per_shipment,
                "payment_terms": ftl_lane.payment_terms,
                "recurrence_frequency": ftl_lane.recurrence_frequency,
                "recurrnece_days": ftl_lane.recurrence_days,
                "shipments_per_interval": ftl_lane.shipments_per_interval,
                "start_date": ftl_lane.start_date,
                "end_date": ftl_lane.end_date,
            } for ftl_lane in ftl_lanes],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

router.post("shipper/ftl-lane/id")
def shipper_get_individual_ftl_lane(
    lane_data: individual_shipment_or_lane_request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        lane = db.query(FTL_Lane).filter(FTL_Lane.id == lane_data.id).first()
        invoices = db.query(Interim_Invoice).filter(Interim_Invoice.contract_id == lane.id,
                                               Interim_Invoice.contract_type == lane.type).all()
        sub_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.dedicated_lane_id == lane.id).all()

        carrier = db.query(Carrier).filter(Carrier.id == lane.carrier_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=lane.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=lane.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        return {
            "shipment_details": {
                "id": lane.id,
                "status": lane.status,
                "type": lane.type,
                "trip_type": lane.trip_type,
                "load_type": lane.load_type,
                "required_truck_type": lane.required_truck_type,
                "equipment_type": lane.equipment_type,
                "trailer_type": lane.trailer_type,
                "trailer_length": lane.trailer_length,
                "minimum_weight_bracket": lane.minimum_weight_bracket,
                "priority_level": lane.priority_level,
                "average_shipment_weight": lane.average_shipment_weight,
                "commodity": lane.commodity,
                "temperature_control": lane.temperature_control,
                "hazardous_materials": lane.hazardous_materials,
                "minimum_git_cover_amount": lane.minimum_git_cover_amount,
                "minimum_liability_cover_amount": lane.minimum_liability_cover_amount,
                "customer_referece_number": lane.customer_reference_number,
                "packaging_type": lane.packaging_type,
                "packaging_quantity": lane.packaging_quantity,
                "pickup_number": lane.pickup_number,
                "delivery_number": lane.delivery_number,
                "distance": lane.distance,
                "estimated_transit_time": lane.estimated_transit_time,
                "origin_address": lane.complete_origin_address,
                "destination_address": lane.complete_destination_address,
                "pickup_notes": lane.pickup_notes,
                "delivery_notes": lane.delivery_notes,
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "route_preview_embed": lane.route_preview_embed,
            },

            "contract_information": {
                "recurrence_frequency": lane.recurrence_frequency,
                "recurrence_days": lane.recurrence_days,
                "skip_weekends": lane.skip_weekends,
                "shipments_per_interval": lane.shipments_per_interval,
                "total_shipments": lane.total_shipments,
                "per_shipment_rate": lane.qoute_per_shipment,
                "contract_rate": lane.contract_quote,
                "payment_terms": lane.payment_terms,
            },

            "payment_schedule": [{
                "invoice_id": invoice.id,
                "issue_date": invoice.billing_date,
                "due_date": invoice.due_date,
                "status": invoice.status,
                "amount": invoice.due_amount,
            } for invoice in invoices],

            "shipment_schedule": [{
                "id": sub_shipment.id,
                "origin": sub_shipment.origin_city_province,
                "destination": sub_shipment.destination_city_province,
                "pickup_date": sub_shipment.pickup_date,
                "status": sub_shipment.shipment_status,
                "rate": sub_shipment.quote,
                "invoice_status": sub_shipment.invoice_status,
            } for sub_shipment in sub_shipments],

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "scheduling_type": pickup_facility.scheduling_type,
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.address.name if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "scheduling_type": delivery_facility.scheduling_type,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            "carrier_information": {
                "id": carrier.id if carrier else "N/A",
                "carrier_name": f"SADC FREIGHTLINK Carrier-{carrier.id}" if carrier else "N/A",
                "carrier_git_cover": carrier.git_cover_amount if carrier else "N/A",
                "carrier_liability_cover_amount": carrier.liability_insurance_cover_amount if carrier else "N/A",
            }

            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


    