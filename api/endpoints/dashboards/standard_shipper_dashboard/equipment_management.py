from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from db.database import SessionLocal
from models.vehicle import ShipperTrailer
from schemas.brokerage.finance import Individual_Sevice_Invoices_Request
from schemas.vehicle import Individual_Shipper_Trailer_Response, Shipper_Trailers_Summary_Response, ShipperTrailerCreate
from services.vehicle_service import create_shipper_trailer
from utils.auth import get_current_user


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/shipper/equipment/trailer-create", status_code=status.HTTP_201_CREATED) #Tested
def create_shipper_trailer_endpoint(
    trailer_data: ShipperTrailerCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = create_shipper_trailer(db, trailer_data, current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/all-company-trailers", response_model=List[Shipper_Trailers_Summary_Response]) #Tested
def get_all_company_trailers(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        trailers = db.query(ShipperTrailer).filter(ShipperTrailer.owner_id == company_id).all()
        return trailers
    except Exception as e:
        return {"error": str(e)}
    

@router.get("/company-trailer/id", response_model=Individual_Shipper_Trailer_Response) #Tested
def get_single_trailer(
    vehicle_data: Individual_Sevice_Invoices_Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        trailer = db.query(ShipperTrailer).filter(
            ShipperTrailer.id == vehicle_data.id,
            ShipperTrailer.owner_id == company_id
        ).first()

        if not trailer:
            raise HTTPException(
                status_code=404,
                detail=f"Trailer with ID {vehicle_data.id} not found or User not authorized"
            )

        return trailer

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))