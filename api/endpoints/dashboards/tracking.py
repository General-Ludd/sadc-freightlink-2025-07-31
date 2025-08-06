from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.vehicle import Vehicle
from app.models.shipment import FTLShipment, PowerShipment
from app.schemas.tracking import VehicleLocationResponse
from app.dependencies import get_db, get_current_user

router = APIRouter()

@router.get("/tracking/vehicle/{vehicle_id}")
def get_vehicle_location(vehicle_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
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
def get_shipment_location(shipment_id: int, shipment_type: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        shipment = None
        if shipment_type.upper() == "FTL":
            shipment = db.query(FTLShipment).filter(
                FTLShipment.id == shipment_id,
                FTLShipment.company_id == user.company_id
            ).first()
        elif shipment_type.upper() == "POWER":
            shipment = db.query(PowerShipment).filter(
                PowerShipment.id == shipment_id,
                PowerShipment.company_id == user.company_id
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
