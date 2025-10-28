from fastapi import APIRouter, Depends, HTTPException, Query, status
from utils.auth import get_current_user
from sqlalchemy.orm import Session
from db.database import SessionLocal
from sqlalchemy.orm import Session
from typing import Literal
from schemas.user import UploadPODRequest
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

@router.get("/driver/get-shipment-status/{shipment_id}-{shipment_type}")
def driver_get_shipment_status(
    shipment_id: int,
    shipment_type: Literal["FTL", "POWER"],
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
            "Carrier at delivery facility",
            "Off-loading",
            "Completed"
        ]

        # Determine next possible trip status
        try:
            current_index = trip_status_flow.index(carrier_shipment.trip_status)
            next_trip_status = trip_status_flow[current_index + 1] if current_index + 1 < len(trip_status_flow) else None
        except ValueError:
            next_trip_status = None  # current status not in flow

        return {
            "message": "Shipment status retrieved successfully",
            "shipment_id": shipment_id,
            "shipment_type": shipment_type,
            "shipment_status": carrier_shipment.status,
            "trip_status": carrier_shipment.trip_status,
            "next_possible_trip_status": next_trip_status
        }

    except Exception as e:
        return {"error": str(e)}

@router.put("/driver/update-shipment-status/{shipment_id}-{shipment_type}/{new_trip_status}")
def driver_update_shipment_status(
    shipment_id: int,
    shipment_type: Literal["FTL", "POWER"],
    new_trip_status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # Select correct shipment models
        if shipment_type == "FTL":
            carrier_shipment = db.query(Assigned_Spot_Ftl_Shipments).filter_by(shipment_id=shipment_id).first()
            shipment = db.query(FTL_SHIPMENT).filter_by(id=shipment_id).first()
        elif shipment_type == "POWER":
            carrier_shipment = db.query(Assigned_Power_Shipments).filter_by(shipment_id=shipment_id).first()
            shipment = db.query(POWER_SHIPMENT).filter_by(id=shipment_id).first()
        else:
            raise HTTPException(status_code=400, detail="Invalid shipment type")

        if not carrier_shipment or not shipment:
            raise HTTPException(status_code=404, detail=f"No {shipment_type} shipment found with id {shipment_id}")

        # Define valid progression
        trip_status_flow = [
            "Scheduled",
            "Carrier en route to pickup",
            "Carrier at pickup facility",
            "Loading",
            "Carrier in transit",
            "Carrier at delivery facility",
            "Off-loading",
            "Completed"
        ]

        if new_trip_status not in trip_status_flow:
            raise HTTPException(status_code=400, detail=f"Invalid trip status: {new_trip_status}")

        # Default to "Scheduled" if not set
        current_trip_status = shipment.trip_status or "Scheduled"

        current_index = trip_status_flow.index(current_trip_status)
        new_index = trip_status_flow.index(new_trip_status)

        # Enforce logical progression
        if new_index < current_index or new_index > current_index + 1:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status transition from '{current_trip_status}' to '{new_trip_status}'"
            )

        # Update both shipment sides
        carrier_shipment.trip_status = new_trip_status
        shipment.trip_status = new_trip_status

        # Carrier-side logic
        if carrier_shipment.status == "Assigned" and new_trip_status == "Carrier en route to pickup":
            carrier_shipment.status = "In-Progress"
        elif new_trip_status == "Completed":
            carrier_shipment.status = "Awaiting POD"

        # Shipper-side logic
        if hasattr(shipment, "shipment_status"):
            if shipment.shipment_status == "Assigned" and new_trip_status == "Carrier en route to pickup":
                shipment.shipment_status = "In-Progress"
            elif new_trip_status == "Completed":
                shipment.shipment_status = "Awaiting POD"

        db.commit()
        db.refresh(carrier_shipment)
        db.refresh(shipment)

        return {
            "message": "Shipment status updated successfully",
            "shipment_id": shipment_id,
            "shipment_type": shipment_type,
            "carrier_status": carrier_shipment.status,
            "carrier_trip_status": carrier_shipment.trip_status,
            "shipper_status": getattr(shipment, "shipment_status", None),
            "shipper_trip_status": shipment.trip_status,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/driver/upload-pod", status_code=status.HTTP_200_OK)
def upload_pod(
    request: UploadPODRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    shipment_id = request.shipment_id
    shipment_type = request.shipment_type
    pod_link = request.pod_link

    try:
        # Select correct models
        if shipment_type == "FTL":
            shipment = db.query(FTL_SHIPMENT).filter_by(id=shipment_id).first()
            carrier_shipment = db.query(Assigned_Spot_Ftl_Shipments).filter_by(shipment_id=shipment_id).first()
        elif shipment_type == "POWER":
            shipment = db.query(POWER_SHIPMENT).filter_by(id=shipment_id).first()
            carrier_shipment = db.query(Assigned_Power_Shipments).filter_by(shipment_id=shipment_id).first()

        if not shipment or not carrier_shipment:
            raise HTTPException(status_code=404, detail=f"No {shipment_type} shipment found with id {shipment_id}")

        # Validate status
        if shipment.trip_status != "Completed" or shipment.shipment_status != "Awaiting POD":
            raise HTTPException(status_code=400, detail="Shipment not ready for POD upload")

        # Save POD link
        shipment.pod_document = str(pod_link)
        carrier_shipment.pod = str(pod_link)
        shipment.shipment_status = "Completed"
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
        if not shipper_account:
            raise HTTPException(status_code=404, detail="Shipper financial account not found")

        shipper_account.total_outstanding = (shipper_account.total_outstanding or 0) + shipment.quote
        db.add(shipper_account)

        # Update related shipment invoice (if exists) to "Due"
        shipment_invoice = db.query(Shipment_Invoice).filter_by(
            shipment_id=shipment.id,
            shipment_type=shipment.type
        ).first()
        if shipment_invoice:
            shipment_invoice.status = "Due"
            shipment_invoice.is_paid = False
            db.add(shipment_invoice)

        # --- CARRIER: financial account ---
        carrier_account = db.query(CarrierFinancialAccount).filter_by(carrier_id=shipment.carrier_id).first()
        if not carrier_account:
            raise HTTPException(status_code=404, detail="Carrier financial account not found")

        rate = carrier_shipment.shipment_rate
        carrier_account.holding_balance = (carrier_account.holding_balance or 0) + rate
        db.add(carrier_account)

        # Update carrier invoice
        carrier_invoice = db.query(Load_Invoice).filter_by(
            shipment_id=shipment.id,
            shipment_type=shipment.type
        ).first()
        if carrier_invoice:
            carrier_invoice.status = "Unpaid"
            carrier_invoice.is_paid = False
            db.add(carrier_invoice)

        # Commit all changes
        db.commit()

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
