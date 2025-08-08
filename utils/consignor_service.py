from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.shipper import Consignor
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking
from schemas.shipper import ConsignorCreate
from typing import Optional

def get_or_create_consignor(
    db: Session,
    shipment_data: FTL_Shipment_Booking,
    quote_per_shipment: int,
    consignor_billable: Optional[int] = None,
    consignor_data: Optional[ConsignorCreate] = None,
) -> int:
    """
    Get existing consignor by ID, email or phone — or create new one.
    Returns the consignor ID.
    """
    profit = (consignor_billable or 0) - quote_per_shipment
    # Use provided consignor_id directly if it exists
    if shipment_data.consignor_id:
        existing_consignor = db.query(Consignor).filter(Consignor.id == shipment_data.consignor_id).first()
        if not existing_consignor:
            raise HTTPException(status_code=404, detail="Consignor not found by ID.")
        
        existing_consignor.shipments += 1
        existing_consignor.revenue_generated += quote_per_shipment
        existing_consignor.profit_generated += profit
        db.add(existing_consignor)
        db.flush()
        db.commit()
        return existing_consignor.id

    # Handle consignor_data (lookup or create)
    elif consignor_data:
        data = consignor_data

        # Try to find consignor by email or phone
        existing_consignor = db.query(Consignor).filter(
            (Consignor.email == data.email) | (Consignor.phone_number == data.phone_number) | (Consignor.company_website == data.company_website)
        ).first()

        if existing_consignor:
            existing_consignor.shipments += 1
            existing_consignor.revenue_generated += quote_per_shipment
            existing_consignor.profit_generated += profit
            db.add(existing_consignor)
            db.flush()
            db.commit()
            return existing_consignor.id

        # Create a new consignor
        new_consignor = Consignor(
            status=data.status,
            priority_level=data.priority_level,
            company_name=data.company_name,
            client_type=data.client_type,
            business_sector=data.business_sector,
            company_website=data.company_website,
            business_address=data.business_address,
            contact_person_name=data.contact_person_name,
            position=data.position,
            phone_number=data.phone_number,
            email=data.email,
            preferred_contact_method=data.preferred_contact_method,
            client_notes=data.client_notes,
            shipments=1,
            contract_lanes=0,
            revenue_generated=quote_per_shipment,
            profit_generated=profit,
        )
        db.add(new_consignor)
        db.commit()
        db.refresh(new_consignor)
        return new_consignor.id

    # If neither ID nor data is provided
    raise HTTPException(status_code=400, detail="Consignor information is required.")
