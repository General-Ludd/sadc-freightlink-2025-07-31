from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.shipper import Consignor
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking
from schemas.shipper import ConsignorCreate
from typing import Optional

def get_or_create_consignor(
    db: Session,
    shipment_data: FTL_Shipment_Booking,
    consignor_data: Optional[ConsignorCreate],
    current_user: dict,
) -> int:
    """
    Decide which consignor_id to use:
      - If shipment_data.consignor_id exists and is valid → return it
      - Else, if consignor_data is provided → create a new consignor and return its ID
      - Else → raise error
    """
    if shipment_data.consignor_id and shipment_data.consignor_id != 0:
        existing_consignor = db.query(Consignor).filter(Consignor.id == shipment_data.consignor_id).first()
        if not existing_consignor:
            raise HTTPException(status_code=404, detail="Consignor not found by ID.")
        return existing_consignor.id

    if consignor_data:
        consignor = Consignor(
            brokerage_firm_id=current_user.get("company_id"),
            status=consignor_data.status,
            priority_level=consignor_data.priority_level,
            company_name=consignor_data.company_name,
            client_type=consignor_data.client_type,
            business_sector=consignor_data.business_sector,
            company_website=consignor_data.company_website,
            business_address=consignor_data.business_address,
            contact_person_name=consignor_data.contact_person_name,
            position=consignor_data.position,
            phone_number=consignor_data.phone_number,
            email=consignor_data.email,
            preferred_contact_method=consignor_data.preferred_contact_method,
            client_notes=consignor_data.client_notes,
        )
        db.add(consignor)
        db.commit()
        db.refresh(consignor)
        return consignor.id

    raise HTTPException(
        status_code=400,
        detail="Either a consignor_id must be provided or consignor_data to create a new one."
    )