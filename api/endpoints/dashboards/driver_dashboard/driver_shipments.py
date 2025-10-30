from typing import List, Optional
from datetime import date
from sqlalchemy import desc
from fastapi import APIRouter, Depends, HTTPException, Query, status
from utils.auth import get_current_user
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.spot_bookings.ftl_shipment import FTL_Shipment_Docs
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/driver-upcoming-shipments")
def driver_get_all_my_upcoming_shipments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user.get("id")
        today = date.today()

        # Fetch FTL shipments
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.driver_id == user_id,
            Assigned_Spot_Ftl_Shipments.pickup_date >= today,
            Assigned_Spot_Ftl_Shipments.status.in_(["Assigned", "In-Progress", "Awaiting POD"])
        ).all()

        # Fetch Power shipments
        power_shipments = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.driver_id == user_id,
            Assigned_Power_Shipments.pickup_date >= today,
            Assigned_Power_Shipments.status.in_(["Assigned", "In-Progress", "Awaiting POD"])
        ).all()

        # Merge
        shipments = ftl_shipments + power_shipments

        priority_statuses = ["In-Progress", "Awaiting POD"]

        # Sort
        sorted_shipments = sorted(
            shipments,
            key=lambda s: (
                0 if s.status in priority_statuses else 1,   # In-Progress first
                -s.pickup_date.toordinal()               # Newest pickup_date
            )
        )

        # Build response
        result = []
        for shipment in sorted_shipments:
            pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first()
            delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first()

            result.append({
                "id": shipment.shipment_id,
                "type": shipment.type,
                "status": shipment.status,
                "origin": shipment.origin_city_province,
                "pickup_date": shipment.pickup_date,
                "pickup_appointment": f"{pickup_facility.start_time} - {pickup_facility.end_time}" if pickup_facility else None,
                "distance": shipment.distance,
                "destination": shipment.destination_city_province,
                "eta_date": shipment.eta_date,
                "eta_window": shipment.eta_window
            })

        return {"shipments": result}

    except Exception as e:
        return {"error": str(e)}

@router.get("/driver-shipments/split")
def driver_get_all_my_shipments_split(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user.get("id")
        today = date.today()

        # Active (Assigned + In-Progress)
        ftl_active = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.driver_id == user_id,
            Assigned_Spot_Ftl_Shipments.pickup_date >= today,
            Assigned_Spot_Ftl_Shipments.status.in_(["Assigned", "In-Progress", "Awaiting POD"])
        ).all()

        power_active = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.driver_id == user_id,
            Assigned_Power_Shipments.pickup_date >= today,
            Assigned_Power_Shipments.status.in_(["Assigned", "In-Progress", "Awaiting POD"])
        ).all()

        active_shipments = ftl_active + power_active

        # Completed
        ftl_completed = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.driver_id == user_id,
            Assigned_Spot_Ftl_Shipments.in_(["Completed", "Awaiting POD"])
        ).order_by(desc(Assigned_Spot_Ftl_Shipments.pickup_date)).all()

        power_completed = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.driver_id == user_id,
            Assigned_Power_Shipments.in_(["Completed", "Awaiting POD"])
        ).order_by(desc(Assigned_Power_Shipments.pickup_date)).all()

        completed_shipments = ftl_completed + power_completed

        # --- Sort Active Shipments ---
        # Priority: In-Progress first, then Assigned (descending by pickup_date)
        active_sorted = sorted(
            active_shipments,
            key=lambda s: (
                0 if s.status == "In-Progress" else 1,  # In-Progress before Assigned
                -s.pickup_date.toordinal()              # Descending date
            )
        )

        return {
            "assined_shipments": [{
                "id": shipment.shipment_id,
                "type": shipment.type,
                "status": shipment.status,
                "origin": shipment.origin_city_province,
                "pickup_date": shipment.pickup_date,
                "pickup_appointment": shipment.pickup_appointment,
                "distance": shipment.distance,
                "destination": shipment.destination_city_province,
                "eta_date": shipment.eta_date,
                "eta_window": shipment.eta_window
            } for shipment in active_sorted],

            "completed_shipments": [{
                "id": shipment.shipment_id,
                "type": shipment.type,
                "status": shipment.status,
                "origin": shipment.origin_city_province,
                "pickup_date": shipment.pickup_date,
                "pickup_appointment": shipment.pickup_start_time,
                "distance": shipment.distance,
                "destination": shipment.destination_city_province,
                "eta_date": shipment.eta_date,
                "eta_window": shipment.eta_window
            } for shipment in completed_shipments],
        }

    except Exception as e:
        return {"error": str(e)}

@router.get("/driver/ftl-shipment/{id}")
def driver_get_ftl_shipment_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        load = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.shipment_id == id
        ).first()

        if not load:
            return {"error": f"No FTL shipment found with id {id}"}

        # Facilities
        pickup_facility = (
            db.query(ShipmentFacility)
            .filter_by(id=load.pickup_facility_id)
            .first()
            if load.pickup_facility_id else None
        )
        delivery_facility = (
            db.query(ShipmentFacility)
            .filter_by(id=load.delivery_facility_id)
            .first()
            if load.delivery_facility_id else None
        )

        # Contacts
        pickup_contact = (
            db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first()
            if pickup_facility and pickup_facility.contact_person else None
        )
        delivery_contact = (
            db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first()
            if delivery_facility and delivery_facility.contact_person else None
        )

        # Documents
        load_documents = (
            db.query(FTL_Shipment_Docs)
            .filter(FTL_Shipment_Docs.shipment_id == load.shipment_id)
            .first()
        )

        return {
            "load_details": {
                "type": getattr(load, "type", None),
                "trip_type": getattr(load, "trip_type", None),
                "load_type": getattr(load, "load_type", None),
                "lane_Id": getattr(load, "lane_id", None),
                "status": getattr(load, "status", None),
                "trip_status": getattr(load, "trip_status", None),
                "origin": getattr(load, "origin_address_completed", None),
                "destination": getattr(load, "destination_address_completed", None),
                "distance": getattr(load, "distance", None),
                "minimum_transit_time": getattr(load, "estimated_transit_time", None),
                "pickup_date": getattr(load, "pickup_date", None),
                "priority": getattr(load, "priority_level", None),
                "customer_ref": getattr(load, "customer_reference_number", None),
                "pickup_number": getattr(load, "pickup_number", None),
                "delivery_number": getattr(load, "delivery_number", None),
                "pickup_notes": getattr(load, "pickup_notes", None),
                "delivery_notes": getattr(load, "delivery_notes", None),
            },
            "load_and_requirements": {
                "required_truck": getattr(load, "required_truck_type", None),
                "required_equipment": getattr(load, "equipment_type", None),
                "required_trailer_type": getattr(load, "trailer_type", None),
                "required_trailer_length": getattr(load, "trailer_length", None),
                "min_weight_bracket": getattr(load, "minimum_weight_bracket", None),
                "commodity": getattr(load, "commodity", None),
                "weight": getattr(load, "shipment_weight", None),
                "packaging_type": getattr(load, "packaging_type", None),
                "packaging_quantity": getattr(load, "packaging_quantity", None),
                "hazardous": getattr(load, "hazardous_materials", None),
                "temp_control": getattr(load, "temperature_control", None),
            },
            "facilities": {
                "pickup_facility": {
                    "name": getattr(pickup_facility, "name", None),
                    "address": getattr(load, "origin_address_completed", None),
                    "scheduling_type": getattr(pickup_facility, "scheduling_type", None),
                    "operating_hours": f"{getattr(pickup_facility, 'start_time', 'N/A')} - {getattr(pickup_facility, 'end_time', 'N/A')}"
                    if pickup_facility else None,
                    "contact_person": {
                        "first_name": getattr(pickup_contact, "first_name", None),
                        "last_name": getattr(pickup_contact, "last_name", None),
                        "phone_number": getattr(pickup_contact, "phone_number", None),
                        "email": getattr(pickup_contact, "email", None),
                    }
                    if pickup_contact else None,
                    "facility_notes": getattr(pickup_facility, "facility_notes", None),
                }
                if pickup_facility else None,
                "delivery_facility": {
                    "name": getattr(delivery_facility, "name", None),
                    "address": getattr(load, "destination_address_completed", None),
                    "scheduling_type": getattr(delivery_facility, "scheduling_type", None),
                    "operating_hours": f"{getattr(delivery_facility, 'start_time', 'N/A')} - {getattr(delivery_facility, 'end_time', 'N/A')}"
                    if delivery_facility else None,
                    "contact_person": {
                        "first_name": getattr(delivery_contact, "first_name", None),
                        "last_name": getattr(delivery_contact, "last_name", None),
                        "phone_number": getattr(delivery_contact, "phone_number", None),
                        "email": getattr(delivery_contact, "email", None),
                    }
                    if delivery_contact else None,
                    "facility_notes": getattr(delivery_facility, "facility_notes", None),
                }
                if delivery_facility else None,
            },
            "load_documents": {
                "commercial_invoice": getattr(load_documents, "commercial_invoice", None),
                "packaging_list": getattr(load_documents, "packaging_list", None),
                "customs_declaration": getattr(load_documents, "customs_declaration_form", None),
                "import_export_permit": getattr(load_documents, "import_or_export_permits", None),
                "certificate_of_origin": getattr(load_documents, "certificate_of_origin", None),
                "da5501orsad500": getattr(load_documents, "da5501orsad500", None),
            }
            if load_documents else None,
        }
    except Exception as e:
        return {"error": str(e)}
