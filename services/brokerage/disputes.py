from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Dispute_Create
from models.spot_bookings.ftl_shipment import FTL_Shipment_Dispute
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