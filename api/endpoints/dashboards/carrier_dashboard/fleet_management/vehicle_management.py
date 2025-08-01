from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import CarrierFinancialAccounts, Lane_Interim_Invoice, Load_Invoice
from models.carrier import Carrier
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from schemas.brokerage.assigned_lanes import Dedicated_Ftl_Lane_Summary_Response
from schemas.brokerage.assigned_shipments import Assigned_Shipments_SummaryResponse, GetAssigned_Spot_Ftl_ShipmentRequest
from schemas.brokerage.finance import CarrierFinancialAccountResponse
from schemas.carrier import CarrierCompanyResponse
from schemas.user import CarrierUserResponse, DriverCreate, DriverResponse
from schemas.vehicle import Fleet_Trailer_Truck_response, TrailerCreate, TrailerResponse, Trailers_Summary_Response, Vehicle_Info, Vehicle_Schedule_Response, VehicleCreate, VehicleResponse, VehicleUpdate, Vehicles_Summary_Response
from services.carrier_service import fleet_create_driver
from services.carrier_dashboards import assign_primary_driver, assign_trailer_to_vehicle
from services.vehicle_service import create_trailer, create_vehicle
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import CarrierUser, Driver
from models.vehicle import ShipperTrailer, Trailer, Vehicle, Vehicle_Schedule
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#################################VEHICLES###################################################################################
@router.post("/carrier/vehicle-create", status_code=status.HTTP_201_CREATED) #Untested
def create_truck_endpoint(
    vehicle_data: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    print(f"Vehicle data: {vehicle_data.dict()}")  # Debugging
    print(f"Current user: {current_user}")  # Debugging
    try:
        result = create_vehicle(db, vehicle_data, current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/all-fleet-vehicles", response_model=List[Vehicles_Summary_Response])
def get_all_fleet_vehicles(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
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
        vehicles = db.query(Vehicle).filter(Vehicle.owner_id == company_id).all()
        results = []

        for vehicle in vehicles:
            driver = None
            if vehicle.primary_driver_id:
                driver = db.query(Driver).filter(Driver.id == vehicle.primary_driver_id).first()

            vehicle_summary = Vehicles_Summary_Response(
                id=vehicle.id,
                status=vehicle.status,
                current_shipment_id=vehicle.current_shipment_id,
                location_description=vehicle.location_description,
                make=vehicle.make,
                model=vehicle.model,
                year=vehicle.year,
                color=vehicle.color,
                license_plate=vehicle.license_plate,
                axle_configuration=vehicle.axle_configuration,
                license_expiry_date=vehicle.license_expiry_date,
                type=vehicle.type,
                equipment_type=vehicle.equipment_type,
                trailer_type=vehicle.trailer_type,
                trailer_length=vehicle.trailer_length,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None
            )
            results.append(vehicle_summary)

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/vehicle/id", response_model=VehicleResponse) #Tested
def get_single_truck(
    vehicle_data: Vehicle_Info,
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
        truck = db.query(Vehicle).filter(
            Vehicle.id == vehicle_data.id,
            Vehicle.owner_id == company_id
        ).first()

        if not truck:
            raise HTTPException(
                status_code=404,
                detail=f"Truck with ID {vehicle_data.id} not found or not authorized"
            )

        return truck

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.patch("/update-vehicle/{vehicle_id}", response_model=VehicleResponse) #UnTested
def partial_update_truck(
    vehicle_id: int,
    vehicle_data: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    truck = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.owner_id == company_id
    ).first()

    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found or not authorized")

    for key, value in vehicle_data.dict(exclude_unset=True).items():
        setattr(truck, key, value)

    db.commit()
    db.refresh(truck)
    return truck

@router.delete("delete-vehicle/{vehicle_id}", response_model=VehicleResponse) #UnTested
def deactivate_truck(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    truck = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.owner_id == company_id
    ).first()

    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found or not authorized")

    truck.status = "Deleted"
    db.commit()
    db.refresh(truck)
    return truck

@router.post("/vehicle-id/schedule", response_model=List[Vehicle_Schedule_Response]) #UnTested
def get_vehicle_schedule(
    vehicle_data: Vehicle_Info,
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
        schedule = db.query(Vehicle_Schedule).filter(
            Vehicle_Schedule.vehicle_id == vehicle_data.id,
            Vehicle_Schedule.past != False
        ).all()

        if not schedule:
            raise HTTPException(
                status_code=404,
                detail=f"No schedule found for vehicle with ID {vehicle_data.id}"
            )

        return schedule

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#################################TRAILERS###################################################################################
@router.post("/carrier/trailer-create", status_code=status.HTTP_201_CREATED) #Tested
def create_trailer_endpoint(
    trailer_data: TrailerCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = create_trailer(db, trailer_data, current_user=current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/all-fleet-trailers", response_model=List[Trailers_Summary_Response]) #UnTested
def get_all_fleet_trailers(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
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
        trailers = db.query(Trailer).filter(Trailer.owner_id == company_id).all()
        results = []

        for trailer in trailers:
            truck = None
            if trailer.truck_id:
                truck = db.query(Vehicle).filter(Vehicle.id == trailer.truck_id).first()

            trailer_summary = Trailers_Summary_Response(
                id=trailer.id,
                status=trailer.status,
                make=trailer.make,
                model=trailer.model,
                year=trailer.year,
                license_plate=trailer.license_plate,
                license_expiry_date=trailer.license_expiry_date,
                equipment_type=trailer.equipment_type,
                trailer_type=trailer.trailer_type,
                trailer_length=trailer.trailer_length,
                tare_weight=trailer.tare_weight,
                gvm_weight=trailer.gvm_weight,
                payload_capacity=trailer.payload_capacity,
                truck_id=trailer.truck_id,
                truck_status=truck.status if truck else None,
                truck_make=truck.make if truck else None,
                truck_model=truck.model if truck else None,
                truck_year=truck.year if truck else None,
                truck_color=truck.color if truck else None,
                truck_license_plate=truck.license_plate if truck else None,
                truck_license_expiry_date=truck.license_expiry_date if truck else None,
                truck_tare_weight=truck.tare_weight if truck else None,
                truck_payload_capacity=truck.payload_capacity if truck else None,
            )
            results.append(trailer_summary)

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/fleet-trailers/id", response_model=TrailerResponse) #Tested
def get_single_trailer(
    vehicle_data: Vehicle_Info,
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
        trailer = db.query(Trailer).filter(
            Trailer.id == vehicle_data.id,
            Trailer.owner_id == company_id
        ).first()

        if not trailer:
            raise HTTPException(
                status_code=404,
                detail=f"Trailer with ID {vehicle_data.id} not found or not authorized"
            )

        return trailer

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trailer/truck-id", response_model=Fleet_Trailer_Truck_response)
def get_vehicle_with_shipment_info(
    vehicle_data: Vehicle_Info,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        # Step 1: Get the vehicle
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == vehicle_data.id,
            Vehicle.owner_id == company_id
        ).first()

        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found or not authorized")

        # Step 2: Initialize shipment fields
        shipment_id = None
        shipment_status = None
        origin = None
        destination = None

        # Step 3: Check for shipment
        if vehicle.current_shipment_id and vehicle.current_shipment_type:
            if vehicle.current_shipment_type == "FTL":
                shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
                    Assigned_Spot_Ftl_Shipments.shipment_id == vehicle.current_shipment_id
                ).first()
            elif vehicle.current_shipment_type == "POWER":
                shipment = db.query(Assigned_Power_Shipments).filter(
                    Assigned_Power_Shipments.shipment_id == vehicle.current_shipment_id
                ).first()
            else:
                shipment = None

            if shipment:
                shipment_id = shipment.shipment_id
                shipment_type = shipment.type
                shipment_status = shipment.status
                origin = shipment.origin_city_province
                destination = shipment.destination_city_province

        # Step 4: Return the full response
        return Fleet_Trailer_Truck_response(
            id=vehicle.id,
            is_verified=vehicle.is_verified,
            company_name=vehicle.company_name,
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
            color=vehicle.color,
            vin=vehicle.vin,
            license_plate=vehicle.license_plate,
            license_expiry_date=vehicle.license_expiry_date,
            tare_weight=vehicle.tare_weight,
            gvm_weight=vehicle.gvm_weight,
            payload_capacity=vehicle.payload_capacity,
            location_description=vehicle.location_description,
            shipment_id=shipment_id,
            shipment_type=shipment_type,
            shipment_status=shipment_status,
            origin=origin,
            destination=destination
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/assign-trailer-to-vehicle", status_code=status.HTTP_201_CREATED) #UnTested
def assign_trailer(
    vehicle_id: int,
    trailer_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = assign_trailer_to_vehicle(db, trailer_id, vehicle_id, current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/available-carrier-shipment-for-vehicle-assignement")
def carrier_get_all_assigned_scheduled_shipment(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(Assigned_Spot_Ftl_Shipments.carrier_id == company_id).all()
        power_shipments = db.query(Assigned_Power_Shipments).filter(Assigned_Power_Shipments.carrier_id == company_id).all()

        return {
            "ftl_shipments": [{
                "id": ftl_shipment.id,
                "type": ftl_shipment.type,
                "status": ftl_shipment.status,
                "pickup_date": ftl_shipment.pickup_date,
                "origin": ftl_shipment.origin_city_province,
                "distance": ftl_shipment.distance,
                "destination": ftl_shipment.destination_city_province,
                "min_weight_bracket": ftl_shipment.minimum_weight_bracket,
                "truck_type": ftl_shipment.required_truck_type,
                "equipment_type": ftl_shipment.equipment_type,
                "trailer_type": ftl_shipment.trailer_type,
                "trailer_length": ftl_shipment.trailer_length,
                "assigned_vehicle": ftl_shipment.vehicle_id,
            } for ftl_shipment in ftl_shipments],

            "power_shipments": [{
                "id": power_shipment.id,
                "type": power_shipment.type,
                "status": power_shipment.status,
                "pickup_date": power_shipment.pickup_date,
                "origin": power_shipment.origin_city_province,
                "distance": power_shipment.distance,
                "destination": power_shipment.destination_city_province,
                "min_weight_bracket": power_shipment.minimum_weight_bracket,
                "truck_type": power_shipment.required_truck_type,
                "equipment_type": power_shipment.equipment_type,
                "trailer_type": power_shipment.trailer_type,
                "trailer_length": power_shipment.trailer_length,
                "assigned_vehicle": power_shipment.vehicle_id,
            } for power_shipment in power_shipments],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

from sqlalchemy.orm import joinedload
