from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.vehicle import ShipperTrailer

def check_trailer_equipment_info(
    db: Session,
    trailer_id: int,
    shipment_weight: int,
):
    # Step 1: Retrieve the trailer from the DB
    trailer = db.query(ShipperTrailer).filter(ShipperTrailer.id == trailer_id).first()

    # Step 2: Check if the trailer exists
    if not trailer:
        raise HTTPException(
            status_code=404,
            detail=f"Trailer with ID {trailer_id} not found."
        )

    # Step 3: Check if trailer is verified
    if not trailer.is_verified:
        raise HTTPException(
            status_code=403,
            detail=f"Trailer with ID {trailer_id} is not verified."
        )
    
    try:
        assert trailer.payload_capacity >= shipment_weight, "Trailer Payload capacity too low to satisfy this shipment's weight"
    except AssertionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # If everything checks out
    return trailer
