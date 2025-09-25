from fastapi import APIRouter, Depends, HTTPException, Query, status
from utils.auth import get_current_user
from sqlalchemy.orm import Session
from db.database import SessionLocal
from sqlalchemy.orm import Session
from typing import Literal
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.put("/driver/update-shipment-status")
def driver_update_shipment_status(
    shipment_id: int,
    shipment_type: Literal["FTL", "POWER"],
    new_trip_status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # Select the correct carrier-side model
        if shipment_type == "FTL":
            carrier_shipment = (
                db.query(Assigned_Spot_Ftl_Shipments)
                .filter_by(shipment_id=shipment_id)
                .first()
            )
            shipment = db.query(FTL_SHIPMENT).filter_by(id=shipment_id).first()
        elif shipment_type == "POWER":
            carrier_shipment = (
                db.query(Assigned_Power_Shipments)
                .filter_by(shipment_id=shipment_id)
                .first()
            )
            shipment = db.query(POWER_SHIPMENT).filter_by(id=shipment_id).first()
        else:
            return {"error": "Invalid shipment type"}

        if not carrier_shipment or not shipment:
            return {"error": f"No {shipment_type} shipment found with id {shipment_id}"}

        # Define allowed trip status progression
        trip_status_flow = [
            "Scheduled",
            "Carrier en route to pickup",
            "Carrier at pickup facility",
            "Loading",
            "Carrier in transit",
            "Carrier at delivery",
            "Off-loading",
            "Completed"
        ]

        # Validate requested status
        if new_trip_status not in trip_status_flow:
            return {"error": f"Invalid trip status: {new_trip_status}"}

        # Get indexes for progression validation
        current_index = trip_status_flow.index(shipment.trip_status)
        new_index = trip_status_flow.index(new_trip_status)

        # Prevent invalid jumps
        if new_index < current_index or new_index > current_index + 1:
            return {
                "error": f"Invalid status transition from {shipment.trip_status} to {new_trip_status}"
            }

        # Update trip statuses
        carrier_shipment.trip_status = new_trip_status
        shipment.trip_status = new_trip_status

        # Business rules for carrier side
        if carrier_shipment.status == "Assigned" and new_trip_status == "Carrier en route to pickup":
            carrier_shipment.status = "In-Progress"

        if new_trip_status == "Completed":
            carrier_shipment.status = "Awating POD"

        # Business rules for shipper side
        if shipment.shipment_status == "Assigned" and new_trip_status == "Carrier en route to pickup":
            shipment.shipment_status = "In-Progress"

        if new_trip_status == "Completed":
            shipment.shipment_status = "Awaiting POD"

        # Commit and refresh
        db.commit()
        db.refresh(carrier_shipment)
        db.refresh(shipment)

        return {
            "message": "Shipment status updated successfully",
            "shipment_id": shipment_id,
            "shipment_type": shipment_type,
            "carrier_status": carrier_shipment.status,
            "carrier_trip_status": carrier_shipment.trip_status,
            "shipper_status": shipment.shipment_status,
            "shipper_trip_status": shipment.trip_status,
        }

    except Exception as e:
        return {"error": str(e)}



@router.post("/driver/upload-pod/{shipment_id}-{shipment_type}/{pod_link}")
def upload_pod(
    shipment_id: int,
    shipment_type: Literal["FTL", "POWER"],
    pod_link: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # Select correct models
        if shipment_type == "FTL":
            shipment = db.query(FTL_SHIPMENT).filter_by(id=shipment_id).first()
            carrier_shipment = db.query(Assigned_Spot_Ftl_Shipments).filter_by(shipment_id=shipment_id).first()
        elif shipment_type == "POWER":
            shipment = db.query(POWER_SHIPMENT).filter_by(id=shipment_id).first()
            carrier_shipment = db.query(Assigned_Power_Shipments).filter_by(shipment_id=shipment_id).first()
        else:
            return {"error": "Invalid shipment type"}

        if not shipment or not carrier_shipment:
            return {"error": f"No {shipment_type} shipment found with id {shipment_id}"}

        # Validate status
        if shipment.trip_status != "Completed" or shipment.shipment_status != "Awaiting POD":
            return {"error": "Shipment not ready for POD upload"}

        # Save POD link
        shipment.pod_document = pod_link
        carrier_shipment.pod = pod_link
        shipment.shipment_status = "Completed"   # Finalize after POD is uploaded
        carrier_shipment.status = "Completed"

        # Handle sub-shipment case
        if shipment.is_sub_shipment:
            lane = db.query(FTL_Lane).filter_by(id=shipment.lane_id).first()
            carrier_lane = db.query(Assigned_Ftl_Lanes).filter_by(id=shipment.lane_id).first()
            if lane and carrier_lane:
                lane.progress = (lane.progress or 0) + 1
                carrier_lane.progress = (carrier_lane.total_shipment_completed or 0) + 1

        # --- SHIPPER: financial account ---
        shipper_account = db.query(FinancialAccounts).filter_by(id=shipment.shipper_company_id).first()

        if shipper_account:
            shipper_account.total_outstanding = (shipper_account.total_outstanding or 0) + shipment.quote
            db.add(shipper_account)
        else:
            raise HTTPException(status_code=404, detail="Shipper financial account not found")

        # Update related shipment invoice (if exists) to "Due"
        shipment_invoice = db.query(Shipment_Invoice).filter_by(shipment_id=shipment.id,
                                                            shipment_type=shipment.type).first()
        if shipment_invoice:
            shipment_invoice.status = "Due",        # mark as due for payment
            shipment_invoice.is_paid = False
            db.add(shipment_invoice)

        # --- CARRIER: financial account ---
        carrier_account = db.query(CarrierFinancialAccount).filter_by(carrier_id=shipment.carrier_id).first()
        if not carrier_account:
            raise HTTPException(status_code=404, detail="Carrier financial account not found")

        # Rate is on the assigned carrier_shipment record
        rate = carrier_shipment.shipment_rate
        carrier_account.holding_balance = (carrier_account.holding_balance or 0) + rate
        db.add(carrier_account)

        # Find carrier invoice (Load_Invoice) for the shipment and mark unpaid
        carrier_invoice = db.query(Load_Invoice).filter_by(
            shipment_id=shipment.id,
            shipment_type=shipment.type
        ).first()

        if carrier_invoice:
            carrier_invoice.status = "Unpaid",
            carrier_invoice.is_paid = False
            db.add(carrier_invoice)

        # --- persist everything in one transaction ---
        db.commit()

        # refresh objects for return
        db.refresh(shipment)
        db.refresh(carrier_shipment)
        db.refresh(shipper_account)
        db.refresh(carrier_account)

        return {
            "message": "POD uploaded and financials updated successfully",
            "shipment_id": shipment_id,
            "shipment_status": shipment.shipment_status,
            "shipper_total_outstanding": shipper_account.total_outstanding,
            "carrier_holding_balance": carrier_account.holding_balance,
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
