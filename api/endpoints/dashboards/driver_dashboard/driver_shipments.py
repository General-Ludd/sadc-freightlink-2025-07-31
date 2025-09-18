from typing import List, Optional
from datetime import date
from sqlalchemy import desc
from fastapi import APIRouter, Depends, HTTPException, Query, status
from utils.auth import get_current_user
from sqlalchemy.orm import Session
from db.database import SessionLocal
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
            Assigned_Spot_Ftl_Shipments.status.in_(["Assigned", "In-Progress"])
        ).all()

        # Fetch Power shipments
        power_shipments = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.driver_id == user_id,
            Assigned_Power_Shipments.pickup_date >= today,
            Assigned_Power_Shipments.status.in_(["Assigned", "In-Progress"])
        ).all()

        # Merge
        shipments = ftl_shipments + power_shipments

        # Sort
        sorted_shipments = sorted(
            shipments,
            key=lambda s: (
                0 if s.status == "In-Progress" else 1,   # In-Progress first
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
            Assigned_Spot_Ftl_Shipments.status.in_(["Assigned", "In-Progress"])
        ).all()

        power_active = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.driver_id == user_id,
            Assigned_Power_Shipments.pickup_date >= today,
            Assigned_Power_Shipments.status.in_(["Assigned", "In-Progress"])
        ).all()

        active_shipments = ftl_active + power_active

        # Completed
        ftl_completed = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.driver_id == user_id,
            Assigned_Spot_Ftl_Shipments.status == "Completed"
        ).order_by(desc(Assigned_Spot_Ftl_Shipments.pickup_date)).all()

        power_completed = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.driver_id == user_id,
            Assigned_Power_Shipments.status == "Completed"
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
        load = db.query(Assigned_Spot_Ftl_Shipments).filter(Assigned_Spot_Ftl_Shipments.shipment_id == id).first()

        return {
            "load_details": {
                "type": load.type,
                "trip_type": load.trip_type,
                "load_type": load.load_type,
                "lane_id": load.lane_id,
                "status": load.status,
                "trip_status": load.trip_status,
                "origin": load.origin_address_completed,
                "destination": load.destination_address_completed,
                "pickup_date": load.pickup_date,
                "priority": load.priority_level,
                "customer_ref": load.customer_reference_number,
                "pickup_number": load.pickup_number,
                "delivery_number": load.delivery_number,
                "pickup_notes": load.pickup_notes,
                "delivery_notes": load.delivery_notes,
            },
            "load_and_requirements": {
                "required_truck": load.required_truck_type,
                "required_equipment": load.equipment_type,
                "required_trailer_type": load.trailer_type,
                "required_trailer_length": load.trailer_length,
                "min_weight_bracket": load.minimum_weight_bracket,
                "commodity": load.commodity,
                "weight": load.shipment_weight,
                "packaging_type": load.packaging_type,
                "packaging_quantity": load.packaging_quantity,
                "hazardous": load.hazardous_materials,
                "temp_control": load.temperature_control,
            },
        }
    except Exception as e:
        return {"error": str(e)}