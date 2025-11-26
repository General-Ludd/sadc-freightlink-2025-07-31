from sqlalchemy.orm import Session
from datetime import datetime
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, shipment_status_Update
from models.spot_bookings.shipment_facility import ShipmentFacility

def get_shipment_kpis(db: Session, shipment_id: int):
    shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == shipment_id).first()
    if not shipment:
        return None

    # Fetch pickup & delivery facility details
    pickup_fac = db.query(ShipmentFacility).filter(
        ShipmentFacility.id == shipment.pickup_facility_id
    ).first()

    delivery_fac = db.query(ShipmentFacility).filter(
        ShipmentFacility.id == shipment.delivery_facility_id
    ).first()

    # Fetch all status updates for this shipment
    updates = db.query(shipment_status_Update).filter(
        shipment_status_Update.shipment_id == shipment_id
    ).order_by(shipment_status_Update.created_at.asc()).all()

    # Helper to get timestamp of a specific trip status
    def get_time(status):
        for u in updates:
            if u.trip_status == status:
                return u.created_at
        return None

    # ----------------------
    # KPI CALCULATIONS
    # ----------------------

    actual_pickup_time = get_time("Carrier at Pickup Facility")
    loading_start = get_time("Loading")
    in_transit_time = get_time("In-transit")
    arrival_delivery_time = get_time("Carrier at delivery facility")
    unloading_end = get_time("Awaiting POD") or get_time("Completed")

    # Pickup on-time calculation
    pickup_on_time = None
    if pickup_fac and actual_pickup_time:
        pickup_window_start = datetime.combine(actual_pickup_time.date(), pickup_fac.start_time)
        pickup_window_end = datetime.combine(actual_pickup_time.date(), pickup_fac.end_time)
        pickup_on_time = pickup_window_start <= actual_pickup_time <= pickup_window_end

    # Pickup dwell
    pickup_dwell_minutes = None
    if actual_pickup_time and loading_start:
        pickup_dwell_minutes = int((loading_start - actual_pickup_time).total_seconds() / 60)

    # Transit duration
    transit_duration_minutes = None
    if in_transit_time and arrival_delivery_time:
        transit_duration_minutes = int((arrival_delivery_time - in_transit_time).total_seconds() / 60)

    # Delivery delay
    delivery_late_by_minutes = None
    if delivery_fac and arrival_delivery_time:
        delivery_window_start = datetime.combine(arrival_delivery_time.date(), delivery_fac.start_time)
        delivery_window_end = datetime.combine(arrival_delivery_time.date(), delivery_fac.end_time)

        if arrival_delivery_time > delivery_window_end:
            delivery_late_by_minutes = int((arrival_delivery_time - delivery_window_end).total_seconds() / 60)
        else:
            delivery_late_by_minutes = 0

    # Delivery dwell
    delivery_dwell_minutes = None
    if arrival_delivery_time and unloading_end:
        delivery_dwell_minutes = int((unloading_end - arrival_delivery_time).total_seconds() / 60)

    # Total shipment duration
    total_shipment_duration_minutes = None
    if actual_pickup_time and unloading_end:
        total_shipment_duration_minutes = int((unloading_end - actual_pickup_time).total_seconds() / 60)

    # Build response
    return {
        "shipment_id": shipment_id,
        "kpis": {
            "actual_pickup_time": actual_pickup_time,
            "pickup_on_time": pickup_on_time,
            "pickup_dwell_minutes": pickup_dwell_minutes,
            "estimated_transit_time": shipment.estimated_transit_time,
            "transit_duration_minutes": transit_duration_minutes,
            "actual_delivery_time": arrival_delivery_time,
            "delivery_late_by_minutes": delivery_late_by_minutes,
            "delivery_dwell_minutes": delivery_dwell_minutes,
            "total_shipment_duration_minutes": total_shipment_duration_minutes,
            "total_status_updates": len(updates)
        }
    }
