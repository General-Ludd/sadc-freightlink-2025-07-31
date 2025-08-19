from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from db.database import SessionLocal
from models.vehicle import ShipperTrailer, Vehicle
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from schemas.brokerage.finance import Individual_Sevice_Invoices_Request
from schemas.vehicle import Individual_Shipper_Trailer_Response, Shipper_Trailers_Summary_Response, ShipperTrailerCreate, TrailerUpdate
from services.vehicle_service import create_shipper_trailer, update_shipper_trailer
from utils.auth import get_current_user
from enums import TrailerAvailabilityStatus


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
    
@router.get("/all-company-trailers")
def get_all_company_trailers(
    status: Optional[TrailerAvailabilityStatus] = None,
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
        query = db.query(ShipperTrailer).filter(
            ShipperTrailer.owner_id == company_id
        )
        if status:
            query = query.filter(ShipperTrailer.availability_status == status.value)

        trailers = query.all()

        return {
            "trailers": [{
                "id": trailer.id,
                "availability_status": trailer.availability_status,
                "make_model_and_year": f"{trailer.make}-{trailer.model} ~ {trailer.year}",
                "license_plate": trailer.license_plate,
                "equipment_type": trailer.equipment_type,
                "trailer_length": trailer.trailer_length,
                "trailer_type": trailer.trailer_type,
                "verification": trailer.is_verified,
                "payload_capacity": trailer.payload_capacity,

                "current_shipment":{
                    "id": f"SHP-{trailer.current_shipment_id}" if trailer.current_shipment_id else None,
                    "status": trailer.current_shipment.status if trailer.current_shipment.status else None,
                }
            } for trailer in trailers]
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/company-trailer/{id}")  # Tested
def get_single_shipper_trailer(
    id: int,
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
            ShipperTrailer.id == id,
            ShipperTrailer.owner_id == company_id
        ).first()

        if not trailer:
            raise HTTPException(
                status_code=404,
                detail=f"Trailer with ID {id} not found or User not authorized"
            )

        # --- Truck lookup ---
        truck = None
        if trailer.truck_id:
            truck = db.query(Vehicle).filter(Vehicle.id == trailer.truck_id).first()

        # --- Shipment lookup ---
        shipment = None
        if truck and truck.current_shipment_id:
            if truck.current_shipment_type == "FTL":
                shipment = db.query(FTL_SHIPMENT).filter(
                    FTL_SHIPMENT.id == truck.current_shipment_id
                ).first()
            else:
                shipment = db.query(POWER_SHIPMENT).filter(
                    POWER_SHIPMENT.id == truck.current_shipment_id
                ).first()

        return {
            "trailer_information": {
                "id": trailer.id,
                "owned_by": f"SADC FREIGHTLINK Client-{trailer.owner_id}",
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.year,
                "color": trailer.color,
                "vin": trailer.vin,
                "license_plate": trailer.license_plate,
                "license_expiry_date": trailer.license_expiry_date,
                "tare_weight": trailer.tare_weight,
                "gvm_weight": trailer.gvm_weight,
                "equipment_type": trailer.equipment_type,
                "trailer_length": trailer.trailer_length,
                "trailer_type": trailer.trailer_type,
                "connected_truck_id": trailer.truck_id or "N/A"
            },

            "trailer_documents": {
                "registration_certificate": trailer.vrc_leasing,
                "license_disc": trailer.license_disk,
                "road_worthy_certificate": trailer.road_worthy_certificate
            },

            "trailer_pictures": {
                "front_angle_image": trailer.front_angle_image,
                "rear_angle_image": trailer.rear_angle_image,
                "left_angle_image": trailer.left_angle_image,
                "right_angle_image": trailer.right_angle_image
            },

            "attached_truck_information": {
                "truck_id": truck.id if truck else "N/A",
                "verification_status": truck.is_verified if truck else "N/A",
                "owned_by": f"SADC FREIGHTLINK Carrier-{truck.owner_id}" if truck else "N/A",
                "make": truck.make if truck else "N/A",
                "model": truck.model if truck else "N/A",
                "year": truck.year if truck else "N/A",
                "color": truck.color if truck else "N/A",
                "vin": truck.vin if truck else "N/A",
                "license_plate": truck.license_plate if truck else "N/A",
                "license_expiry_date": truck.license_expiry_date if truck else "N/A",
                "tare_weight": truck.tare_weight if truck else "N/A",
                "gvm_weight": truck.gvm_weight if truck else "N/A",
                "payload_capacity": truck.payload_capacity if truck else "N/A",
                "last_known_location": truck.location_description if truck else "N/A",
            },

            "current_shipment_information": {
                "shipment_id": shipment.id if shipment else "N/A",
                "shipment_status": shipment.shipment_status if shipment else "N/A",
                "origin": shipment.origin_city_province if shipment else "N/A",
                "destination": shipment.destination_city_province if shipment else "N/A"
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/equipment-update/{trailer_id}")
def shipper_broker_update_trailer_information(
    trailer_id: int,
    trailer_data: TrailerUpdate,
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

    return update_shipper_trailer(db, trailer_id, trailer_data, current_user=current_user)
