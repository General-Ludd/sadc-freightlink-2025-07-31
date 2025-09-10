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
    - If consignor_id > 0 → link existing consignor
    - If consignor_id == 0 → require valid consignor_data to create a new consignor
    - Else → error
    """

    # Case 1: Use existing consignor
    if shipment_data.consignor_id and shipment_data.consignor_id > 0:
        existing_consignor = (
            db.query(Consignor)
            .filter(Consignor.id == shipment_data.consignor_id)
            .first()
        )
        if not existing_consignor:
            raise HTTPException(status_code=404, detail="Consignor not found by ID.")
        return existing_consignor.id

    # Case 2: Create new consignor if ID == 0
    if shipment_data.consignor_id == 0:
        if not consignor_data:
            raise HTTPException(
                status_code=400,
                detail="Consignor ID is 0 but no consignor data provided."
            )

        # Validate critical required fields are non-empty
        required_fields = ["company_name", "business_address", "contact_person_name", "phone_number", "email"]
        missing_fields = [field for field in required_fields if not getattr(consignor_data, field, "").strip()]

        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required consignor fields: {', '.join(missing_fields)}"
            )

        consignor = Consignor(
            brokerage_firm_id=current_user.get("company_id"),
            status=consignor_data.status or "Active",
            priority_level=consignor_data.priority_level or "Medium",
            company_name=consignor_data.company_name.strip(),
            client_type=consignor_data.client_type,
            business_sector=consignor_data.business_sector,
            company_website=consignor_data.company_website,
            business_address=consignor_data.business_address.strip(),
            contact_person_name=consignor_data.contact_person_name.strip(),
            position=consignor_data.position,
            phone_number=consignor_data.phone_number.strip(),
            email=consignor_data.email.strip(),
            preferred_contact_method=consignor_data.preferred_contact_method,
            client_notes=consignor_data.client_notes,
        )
        db.add(consignor)
        db.commit()
        db.refresh(consignor)
        return consignor.id

    # Case 3: No consignor info at all
    raise HTTPException(
        status_code=400,
        detail="Either provide a valid consignor_id (>0) or complete consignor data to create a new consignor."
    )
