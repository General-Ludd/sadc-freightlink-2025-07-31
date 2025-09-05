from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.finance import BrokerageLedger, Dedicated_Lane_BrokerageLedger
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Dispute_Create
from schemas.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane_Dispute_Create
from models.spot_bookings.ftl_shipment import FTL_Shipment_Dispute
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane, FTL_Lane_Dispute
from sqlalchemy.orm import Session
from db.database import SessionLocal

def shipper_dispute_ftl_shipment(
    db: Session,
    dispute_data: FTL_Shipment_Dispute_Create,
    current_user: dict,
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    
    shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == dispute_data.shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    # 🚨 Check if status allows disputes
    if shipment.shipment_status == "Booked":
        raise HTTPException(
            status_code=400,
            detail="Booked shipments cannot be disputed, but they can be cancelled."
        )

    if shipment.shipment_status not in ["In-Progress", "Completed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Shipments with status '{shipment.shipment_status}' cannot be disputed."
        )

    carrier_shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(Assigned_Spot_Ftl_Shipments.shipment_id == dispute_data.shipment_id).first()
    if not carrier_shipment:
        raise HTTPException(
            status_code=404,
            detail="Carrier shipment not found"
        )

    brokerage_ledger = db.query(BrokerageLedger).filter(BrokerageLedger.shipment_type == "FTL",
                                                        BrokerageLedger.shipment_id == dispute_data.shipment_id).first()
    if not brokerage_ledger:
        raise HTTPException(
            status_code=404,
            detail="Brokerage ledger not found"
        )

    # 🚨 Check if dispute already exists
    existing_dispute = db.query(FTL_Shipment_Dispute).filter(
        FTL_Shipment_Dispute.shipment_id == dispute_data.shipment_id,
        FTL_Shipment_Dispute.status == "Open"  # Only block if there's an open dispute
    ).first()

    if existing_dispute:
        raise HTTPException(
            status_code=400,
            detail=f"FTL Shipment-{dispute_data.lane_id} is already disputed"
        )

    dispute = FTL_Shipment_Dispute(
        filed_by_shipper=True,
        shipment_id=dispute_data.shipment_id,
        shipment_status=dispute_data.shipment_status,
        shipper_company_id=company_id,
        carrier_company_id=carrier_shipment.carrier_id,
        dispute_reason=dispute_data.dispute_reason,
        additional_details=dispute_data.additional_details,
        status="Open",
    )
    shipment.shipment_status = "Disputed"
    carrier_shipment.status = "Disputed"
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return {f"dispute for shipment FTL-{dispute.shipment_id} successfully filed"}

def carrier_dispute_ftl_shipment(
    db: Session,
    dispute_data: FTL_Shipment_Dispute_Create,
    current_user: dict,
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    
    shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == dispute_data.shipment_id).first()
    if not shipment:
        raise HTTPException(
            status_code=404,
            detail="Shipment not found"
        )

    # 🚨 Check if status allows disputes
    if shipment.shipment_status == "Assigned":
        raise HTTPException(
            status_code=400,
            detail="Assigned shipments cannot be disputed, but they can be cancelled."
        )

    if shipment.shipment_status not in ["In-Progress", "Completed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Shipments with status '{shipment.shipment_status}' cannot be disputed."
        )

    carrier_shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(Assigned_Spot_Ftl_Shipments.shipment_id == dispute_data.shipment_id).first()
    if not carrier_shipment:
        raise HTTPException(
            status_code=404,
            detail="Carrier shipment not found"
        )
    
    brokerage_ledger = db.query(BrokerageLedger).filter(BrokerageLedger.shipment_type == "FTL",
                                                        BrokerageLedger.shipment_id == dispute_data.shipment_id).first()
    if not brokerage_ledger:
        raise HTTPException(
            status_code=404,
            detail="Brokerage ledger not found"
        )

    # 🚨 Check if dispute already exists
    existing_dispute = db.query(FTL_Shipment_Dispute).filter(
        FTL_Shipment_Dispute.shipment_id == dispute_data.shipment_id,
        FTL_Shipment_Dispute.status == "Open"  # Only block if there's an open dispute
    ).first()

    if existing_dispute:
        raise HTTPException(
            status_code=400,
            detail=f"FTL Shipment-{dispute_data.lane_id} is already disputed"
        )

    dispute = FTL_Shipment_Dispute(
        filed_by_shipper=False,
        shipment_id=dispute_data.shipment_id,
        shipment_status=dispute_data.shipment_status,
        shipper_company_id=shipment.shipper_company_id,
        carrier_company_id=carrier_company_id,
        dispute_reason=dispute_data.dispute_reason,
        additional_details=dispute_data.additional_details,
        status="Open",
    )
    shipment.shipment_status = "Disputed"
    brokerage_ledger.shipment_status = "Disputed"
    carrier_shipment.status = "Disputed"
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return {f"dispute for shipment FTL-{dispute.shipment_id} successfully filed"}

def shipper_dispute_ftl_lane(
    db: Session,
    dispute_data: FTL_Lane_Dispute_Create,
    current_user: dict,
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    lane = db.query(FTL_Lane).filter(FTL_Lane.id == dispute_data.lane_id).first()
    if not lane:
        raise HTTPException(
            status_code=404,
            detail="Lane not found"
        )

    # 🚨 Check if status allows disputes
    if lane._status == "Booked":
        raise HTTPException(
            status_code=400,
            detail="Booked Lanes cannot be disputed, but they can be cancelled up to 48 hours prior to the comemencement date."
        )

    if shipment.shipment_status not in ["In-Progress", "Completed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Lanes with status '{lane.status}' cannot be disputed."
        )

    carrier_lane = db.query(Assigned_Ftl_Lanes).filter(Assigned_Ftl_Lanes.lane_id == dispute_data.lane_id).first()
    if not carrier_lane:
        raise HTTPException(
            status_code=404,
            detail="Carrier lane not found"
        )
    
    brokerage_ledger = db.query(Dedicated_Lane_BrokerageLedger).filter(Dedicated_Lane_BrokerageLedger.contract_id = lane.id,
                                                                        Dedicated_Lane_BrokerageLedger.lane_type == lane.type).first()

    # 🚨 Check if dispute already exists
    existing_dispute = db.query(FTL_Lane_Dispute).filter(
        FTL_Lane_Dispute.lane_id == dispute_data.lane_id,
        FTL_Lane_Dispute.status == "Open"  # Only block if there's an open dispute
    ).first()

    if existing_dispute:
        raise HTTPException(
            status_code=400,
            detail=f"Lane FTL-{dispute_data.lane_id} is already disputed"
        )

    dispute = FTL_Lane_Dispute(
        filed_by_shipper=True,
        lane_id=dispute_data.lane_id,
        lane_status=dispute_data.lane_status,
        shipper_company_id=company_id,
        carrier_company_id=carrier_lane.carrier_id,
        dispute_reason=dispute_data.dispute_reason,
        additional_details=dispute_data.additional_details,
        status="Open",
    )
    lane.status = "Disputed"
    brokerage_ledger.lane_status = "Disputed"
    carrier_lane.status = "Disputed"
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    return {f"dispute for lane FTL-{dispute.lane_id} successfully filed"}

def carrier_dispute_ftl_lane(
    db: Session,
    dispute_data: FTL_Lane_Dispute_Create,
    current_user: dict,
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    lane = db.query(FTL_Lane).filter(FTL_Lane.id == dispute_data.lane_id).first()
    if not lane:
        raise HTTPException(
            status_code=404,
            detail="Lane not found"
        )

    # 🚨 Check if status allows disputes
    if lane._status == "Assigned":
        raise HTTPException(
            status_code=400,
            detail="Assigned Lanes cannot be disputed, but they can be cancelled up to 48 hours prior to the comemencement date."
        )

    if shipment.shipment_status not in ["In-Progress", "Completed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Lanes with status '{lane.status}' cannot be disputed."
        )

    carrier_lane = db.query(Assigned_Ftl_Lanes).filter(Assigned_Ftl_Lanes.lane_id == dispute_data.lane_id).first()
    if not carrier_lane:
        raise HTTPException(
            status_code=404,
            detail="Carrier lane not found"
        )
    
    brokerage_ledger = db.query(Dedicated_Lane_BrokerageLedger).filter(Dedicated_Lane_BrokerageLedger.contract_id = lane.id,
                                                                        Dedicated_Lane_BrokerageLedger.lane_type == lane.type).first()

    # 🚨 Check if dispute already exists
    existing_dispute = db.query(FTL_Lane_Dispute).filter(
        FTL_Lane_Dispute.lane_id == dispute_data.lane_id,
        FTL_Lane_Dispute.status == "Open"  # Only block if there's an open dispute
    ).first()

    if existing_dispute:
        raise HTTPException(
            status_code=400,
            detail=f"Lane FTL-{dispute_data.lane_id} is already disputed"
        )

    dispute = FTL_Lane_Dispute(
        filed_by_shipper=False,
        lane_id=dispute_data.lane_id,
        lane_status=dispute_data.lane_status,
        shipper_company_id=lane.shipper_company_id,
        carrier_company_id=company_id,
        dispute_reason=dispute_data.dispute_reason,
        additional_details=dispute_data.additional_details,
        status="Open",
    )
    lane.status = "Disputed"
    brokerage_ledger.lane_status = "Disputed"
    carrier_lane.status = "Disputed"
    db.add(dispute)
    db.commit()
    db.refresh(dispute)

    return {f"dispute for lane FTL-{dispute.lane_id} successfully filed"}