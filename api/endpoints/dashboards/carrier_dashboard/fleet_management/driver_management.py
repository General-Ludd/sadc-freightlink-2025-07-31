from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import CarrierFinancialAccounts
from models.carrier import Carrier
from schemas.brokerage.finance import CarrierFinancialAccountResponse
from schemas.carrier import CarrierCompanyResponse
from schemas.user import CarrierUserResponse, Driver_Info, DriverCreate, DriverResponse, Drivers_Summary_Response
from schemas.vehicle import DriverVehicleSummaryResponse, TrailerCreate, TrailerResponse, VehicleCreate, VehicleResponse, VehicleUpdate
from services.carrier_service import fleet_create_driver
from services.carrier_dashboards import assign_primary_driver, assign_trailer_to_vehicle
from services.vehicle_service import create_trailer, create_vehicle
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import CarrierUser, Driver
from models.vehicle import Trailer, Vehicle
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#################################DRIVERS###################################################################################    
@router.post("/carrier/create-driver", status_code=status.HTTP_201_CREATED) #Untested
def fleet_create_driver_endpoint(
    driver_data: DriverCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = fleet_create_driver(db, driver_data, current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/all-fleet-drivers")  # tested
def get_all_fleet_drivers(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Ensure company_id exists
    if "company_id" not in current_user:
        raise HTTPException(status_code=400, detail="Missing company_id in current_user")

    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        # Query all drivers for the current user's company
        drivers = db.query(Driver).filter(Driver.company_id == company_id).all()
        results = []

        for driver in drivers:
            vehicle = None
            if driver.current_vehicle_id:
                vehicle = db.query(Vehicle).filter(Vehicle.id == driver.current_vehicle_id).first()

        return {
            "drivers": [{
                "id": driver.id,
                "verification_status": driver.is_verified,
                "status": driver.status,
                "service_status": driver.service_status,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "nationality": driver.nationality,
                "id_number": driver.id_number,
                "license_number": driver.license_number,
                "license_expiry_date": driver.license_expiry_date,
                "current_vehicle": {
                    "make": vehicle.make if vehicle else None,
                    "model": vehicle.model if vehicle else None,
                    "year": vehicle.year if vehicle else None,
                    "license_plate": vehicle.license_plate if vehicle else None,
                    "type": vehicle.type if vehicle else None,
                    "equipment_type": vehicle.equipment_type if vehicle else None,
                    "trailer_type": vehicle.trailer_type if vehicle else None,
                    "trailer_length": vehicle.trailer_length if vehicle else None,
                } if vehicle else None
            } for driver in drivers]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fleet-driver/{id}")
def get_driver_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if "company_id" not in current_user:
        raise HTTPException(status_code=400, detail="Missing company_id in current_user")
    
    company_id = current_user["company_id"]

    try:
        # 1. Get the driver
        driver = db.query(Driver).filter(Driver.id == id, Driver.company_id == company_id).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")

        # 2. Initialize
        vehicle = None
        shipment = None

        # 3. Get driver's current vehicle (if exists)
        if driver.current_vehicle_id:
            vehicle = db.query(Vehicle).filter(Vehicle.id == driver.current_vehicle_id).first()

            # 4. If vehicle has active shipment, fetch it
            if vehicle and vehicle.current_shipment_id and vehicle.current_shipment_type:
                if vehicle.current_shipment_type.upper() == "FTL":
                    shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
                        Assigned_Spot_Ftl_Shipments.id == vehicle.current_shipment_id
                    ).first()
                elif vehicle.current_shipment_type.upper() == "POWER":
                    shipment = db.query(Assigned_Power_Shipments).filter(
                        Assigned_Power_Shipments.id == vehicle.current_shipment_id
                    ).first()

        return {
            "driver_information": {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "nationality": driver.nationality,
                "id_number": driver.id_number,
                "license_number": driver.license_number,
                "license_expiry_date": driver.license_expiry_date,
                "prdp_number": driver.prdp_number,
                "prdp_expiry_date": driver.prdp_expiry_date,
                "passport_number": driver.passport_number,
                "address": driver.address,
                "email": driver.email,
                "phone_number": driver.phone_number,
                "company_id": driver.company_id,
                "company_name": driver.company_name,
                "company_type": driver.company_type,
                "current_vehicle_id": driver.current_vehicle_id,
                "id_document": driver.id_document,
                "license_document": driver.license_document,
                "prdp_document": driver.prdp_document,
                "passport_document": driver.passport_document,
                "proof_of_address": driver.proof_of_address,
                "is_verified": driver.is_verified,
                "status": driver.status,
                "service_status": driver.service_status,
                "total_shipments_completed": driver.total_shipments_completed,
                "total_distance_driven": driver.total_distance_driven
            },
            "assigned_vehicle_information": {
                "id": vehicle.id,
                "verification_status": vehicle.is_verified,
                "status": vehicle.status,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "color": vehicle.color,
                "vin": vehicle.vin,
                "license_plate": vehicle.license_plate,
                "license_expiry_date": vehicle.license_expiry_date,
                "type": vehicle.type,
                "equipment_type": vehicle.equipment_type,
                "trailer_type": vehicle.trailer_type,
                "trailer_length": vehicle.trailer_length,
                "tare_weight": vehicle.tare_weight,
                "gvm_weight": vehicle.gvm_weight,
                "payload_capacity": vehicle.payload_capacity,
            } if vehicle else None,
            "current_shipment_information": {
                "id": shipment.id,
                "status": shipment.status,
                "trip_status": shipment.trip_status,
                "type": shipment.type,
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
                "origin": shipment.origin_city_province,
                "destination": shipment.destination_city_province,
                "pickup_date": shipment.pickup_date,
                "distance": shipment.distance,
                "minimum_transit_time": shipment.estimated_transit_time,
                "shipment_weight": shipment.shipment_weight,
                "temperature_control": shipment.temperature_control,
            } if shipment else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/driver/assignd-vehicle-summary", response_model=DriverVehicleSummaryResponse)
def get_driver_vehicle_summary(
    driver_request: Driver_Info,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        # Step 1: Get the Driver
        driver = db.query(Driver).filter(
            Driver.id == driver_request.id,
            Driver.company_id == company_id
        ).first()

        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")

        if not driver.current_vehicle_id:
            raise HTTPException(status_code=404, detail="Driver has no assigned vehicle")

        # Step 2: Get the Vehicle
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == driver.current_vehicle_id
        ).first()

        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        # Step 3: Get the Trailer if attached
        trailer_id = None
        trailer_length = None
        trailer_type = None
        if vehicle.trailer_id:
            trailer = db.query(Trailer).filter(Trailer.id == vehicle.trailer_id).first()
            if trailer:
                trailer_id = trailer.id
                trailer_length = trailer.trailer_length
                trailer_type = trailer.trailer_type

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/assign/primary-driver", status_code=status.HTTP_201_CREATED) #Untested
def assign_driver(
    driver_id: int,
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = assign_primary_driver(db, driver_id, vehicle_id, current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))