from fastapi import APIRouter, Depends, HTTPException
from datetime import date, datetime
from sqlalchemy.orm import Session
from models.vehicle import Vehicle
from models.user import Driver
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from utils.auth import get_current_user
from db.database import SessionLocal
from schemas.vehicle import Driver_Location_Update

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/tracking/driver-location-update")
def update_vehicle_location(
    location_data: Driver_Location_Update,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")

    user_id = current_user.get("id")
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    # Find driver record
    driver = db.query(Driver).filter(Driver.id == user_id).first()
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")

    # ✅ Update driver's location
    driver.latitude = location_data.latitude
    driver.longitude = location_data.longitude
    driver.speed = location_data.speed
    driver.heading = location_data.heading
    driver.location_description = location_data.location_description
    driver.time_stamp = datetime.utcnow()

    # If driver has a vehicle, update vehicle location too
    if driver.current_vehicle_id:
        vehicle = db.query(Vehicle).filter(Vehicle.id == driver.current_vehicle_id).first()
        if vehicle:
            vehicle.latitude = location_data.latitude
            vehicle.longitude = location_data.longitude
            vehicle.speed = location_data.speed
            vehicle.heading = location_data.heading
            vehicle.location_description = location_data.location_description
            vehicle.time_stamp = datetime.utcnow()

    db.commit()

    return {
        "status": "success",
        "message": "Location updated successfully",
    }

@router.get("/tracking/vehicle/{vehicle_id}")
def get_vehicle_location(vehicle_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        
        if vehicle.owner_id != user.company_id:
            raise HTTPException(status_code=403, detail="Unauthorized to access this vehicle")

        return {
            "vehicle_location_data": {
                "latitude": vehicle.latitude,
                "longitude": vehicle.longitude,
                "speed": vehicle.speed,
                "heading": vehicle.heading,
                "location_description": vehicle.location_description
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tracking/shipment/{shipment_id}/{shipment_type}")
def get_shipment_location(shipment_id: int, shipment_type: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        shipment = None
        if shipment_type.upper() == "FTL":
            shipment = db.query(FTL_SHIPMENT).filter(
                FTL_SHIPMENT.id == shipment_id,
                FTL_SHIPMENT.shipper_company_id == current_user["company_id"]
            ).first()
        elif shipment_type.upper() == "POWER":
            shipment = db.query(POWER_SHIPMENT).filter(
                POWER_SHIPMENT.id == shipment_id,
                POWER_SHIPMENT.shipper_company_id == current_user["company_id"]
            ).first()
        else:
            raise HTTPException(status_code=400, detail="Invalid shipment type")

        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found or does not belong to user's company")
        
        if shipment.shipment_status != "In-Progress":
            raise HTTPException(status_code=403, detail="Tracking only available for in-progress shipments")

        vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found for this shipment")

        return {
            "vehicle_location_data": {
                "latitude": vehicle.latitude,
                "longitude": vehicle.longitude,
                "speed": vehicle.speed,
                "heading": vehicle.heading,
                "location_description": vehicle.location_description
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tracking/carrier-shipment/{shipment_id}/{shipment_type}")
def carrier_get_shipment_location(shipment_id: int, shipment_type: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        shipment = None
        if shipment_type.upper() == "FTL":
            shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
                Assigned_Spot_Ftl_Shipments.shipment_id == shipment_id,
                Assigned_Spot_Ftl_Shipments.carrier_id == user.company_id
            ).first()
        elif shipment_type.upper() == "POWER":
            shipment = db.query(Assigned_Power_Shipments).filter(
                Assigned_Power_Shipments.shipment_id == shipment_id,
                Assigned_Power_Shipments.carrier_id == user.company_id
            ).first()
        else:
            raise HTTPException(status_code=400, detail="Invalid shipment type")

        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found or does not belong to user's company")
        
        if shipment.status != "In-Progress":
            raise HTTPException(status_code=403, detail="Tracking only available for in-progress shipments")

        vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found for this shipment")

        return {
            "vehicle_location_data": {
                "latitude": vehicle.latitude,
                "longitude": vehicle.longitude,
                "speed": vehicle.speed,
                "heading": vehicle.heading,
                "location_description": vehicle.location_description
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))