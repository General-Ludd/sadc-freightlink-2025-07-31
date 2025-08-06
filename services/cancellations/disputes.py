from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from sqlalchemy.orm import Session
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Dispute
from models.spot_bookings.power_shipment import POWER_SHIPMENT, POWER_Shipment_Dispute
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.assigned_shipments import Assigned_Power_Shipments
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Dispute_Create
from schemas.spot_bookings.power_shipment import POWER_Shipment_Dispute_Create
from utils.auth import get_current_user

def shipper_dispute_ftl_shipment(
    dispute_data: FTL_Shipment_Dispute_Create,
    db: Session,
    current_user: dict
):
    user_id = current_user.get("id")
    company_id = current_user.get("company_id")

    # Fetch shipment and check ownership
    shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == dispute_data.shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=400, detail="Shipment not found")
    if not shipment.shipper_company_id == company_id:
        raise HTTPException(status_code=403, detail="Failed to dispute shipment, ou are not authorized to cancel this shipment reason being that this shipment does not belong to your company.")
    if shipment.status == "Disputed":
        raise HTTPException(status_code=400, detail="Shipment already disputed.")

    # Fetch assigned shipment
    assigned_shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
        Assigned_Spot_Ftl_Shipments.shipment_id == shipment.id
    ).first()

    if not assigned_shipment:
        raise HTTPException(status_code=404, detail="Assigned shipment not found.")

    # Create SQLAlchemy dispute instance (not Pydantic schema)
    dispute = FTL_Shipment_Dispute(
        filed_by_shipper=True,
        shipment_id=dispute_data.shipment_id,
        shipper_company_id=company_id,
        carrier_company_id=shipment.carrier_company_id,
        dispute_reason=dispute_data.dispute_reason,
        additional_details=dispute_data.additional_details,
        shipment_status=shipment.shipment_status,
    )

    # Update status and save
    shipment.shipment_status = "Disputed"
    assigned_shipment.status = "Disputed"
    db.add(dispute)
    db.commit()

    return {"message": f"FTL Shipment-{dispute_data.shipment_id} disputed successfully"}

def carrier_dispute_ftl_shipment(
    dispute_data: FTL_Shipment_Dispute_Create,
    db: Session,
    current_user: dict
):
    user_id = current_user.get("id")
    company_id = current_user.get("company_id")

    # Fetch assigned shipment first
    assigned_shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
        Assigned_Spot_Ftl_Shipments.shipment_id == dispute_data.shipment_id
    ).first()

    if not assigned_shipment:
        raise HTTPException(status_code=404, detail="Assigned shipment not found.")

    if assigned_shipment.carrier_company_id != company_id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to dispute this shipment. It does not belong to your company."
        )

    # Now fetch the shipment
    shipment = db.query(FTL_SHIPMENT).filter(
        FTL_SHIPMENT.id == assigned_shipment.shipment_id
    ).first()

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found.")

    if shipment.shipment_status == "Disputed":
        raise HTTPException(status_code=400, detail="Shipment already disputed.")

    # Create the dispute
    dispute = FTL_Shipment_Dispute(
        filed_by_shipper=False,
        shipment_id=dispute_data.shipment_id,
        shipper_company_id=shipment.shipper_company_id,
        carrier_company_id=shipment.carrier_company_id,
        dispute_reason=dispute_data.dispute_reason,
        additional_details=dispute_data.additional_details,
        shipment_status=shipment.shipment_status,
    )

    # Update status
    assigned_shipment.status = "Disputed"
    shipment.shipment_status = "Disputed"

    db.add(dispute)
    db.commit()

    return {"message": f"FTL Shipment-{dispute_data.shipment_id} disputed successfully"}

########################################Power Shipment Dispute##########################################
def shipper_dispute_power_shipment(
    dispute_data: POWER_Shipment_Dispute_Create,
    db: Session,
    current_user: dict
):
    user_id = current_user.get("id")
    company_id = current_user.get("company_id")

    # Fetch shipment and check ownership
    shipment = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.id == dispute_data.shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=400, detail="Shipment not found")
    if not shipment.shipper_company_id == company_id:
        raise HTTPException(status_code=403, detail="Failed to dispute shipment, ou are not authorized to cancel this shipment reason being that this shipment does not belong to your company.")
    if shipment.status == "Disputed":
        raise HTTPException(status_code=400, detail="Shipment already disputed.")

    # Fetch assigned shipment
    assigned_shipment = db.query(Assigned_Power_Shipments).filter(
        Assigned_Power_Shipments.shipment_id == shipment.id
    ).first()

    if not assigned_shipment:
        raise HTTPException(status_code=404, detail="Assigned shipment not found.")

    # Create SQLAlchemy dispute instance (not Pydantic schema)
    dispute = POWER_Shipment_Dispute(
        filed_by_shipper=True,
        shipment_id=dispute_data.shipment_id,
        shipper_company_id=company_id,
        carrier_company_id=shipment.carrier_company_id,
        dispute_reason=dispute_data.dispute_reason,
        additional_details=dispute_data.additional_details,
        shipment_status=shipment.shipment_status,
    )

    # Update status and save
    shipment.shipment_status = "Disputed"
    assigned_shipment.status = "Disputed"
    db.add(dispute)
    db.commit()

    return {"message": f"POWER Shipment-{dispute_data.shipment_id} disputed successfully"}

def carrier_dispute_power_shipment(
    dispute_data: POWER_Shipment_Dispute_Create,
    db: Session,
    current_user: dict
):
    user_id = current_user.get("id")
    company_id = current_user.get("company_id")

    # Fetch assigned shipment first
    assigned_shipment = db.query(Assigned_Power_Shipments).filter(
        Assigned_Power_Shipments.shipment_id == dispute_data.shipment_id
    ).first()

    if not assigned_shipment:
        raise HTTPException(status_code=404, detail="Assigned shipment not found.")

    if assigned_shipment.carrier_company_id != company_id:
        raise HTTPException(
            status_code=403,
            detail="You are not authorized to dispute this shipment. It does not belong to your company."
        )

    # Now fetch the shipment
    shipment = db.query(POWER_SHIPMENT).filter(
        POWER_SHIPMENT.id == assigned_shipment.shipment_id
    ).first()

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found.")

    if shipment.shipment_status == "Disputed":
        raise HTTPException(status_code=400, detail="Shipment already disputed.")

    # Create the dispute
    dispute = POWER_Shipment_Dispute(
        filed_by_shipper=False,
        shipment_id=dispute_data.shipment_id,
        shipper_company_id=shipment.shipper_company_id,
        carrier_company_id=shipment.carrier_company_id,
        dispute_reason=dispute_data.dispute_reason,
        additional_details=dispute_data.additional_details,
        shipment_status=shipment.shipment_status,
    )

    # Update status
    assigned_shipment.status = "Disputed"
    shipment.shipment_status = "Disputed"

    db.add(dispute)
    db.commit()

    return {"message": f"FTL Shipment-{dispute_data.shipment_id} disputed successfully"}