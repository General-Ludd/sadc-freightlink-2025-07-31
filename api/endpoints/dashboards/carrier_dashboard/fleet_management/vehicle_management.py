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

@router.get("/carrier/vehicle/{id}") #Tested
def carrier_get_single_truck(
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
        truck = db.query(Vehicle).filter(
            Vehicle.id == id,
            Vehicle.owner_id == company_id
        ).first()
        if not truck:
            raise HTTPException(
                status_code=404,
                detail=f"Truck with ID {vehicle_data.id} not found or not authorized"
            )
        vehicle_schedules = db.query(Vehicle_Schedule).filter(Vehicle_Schedule.vehicle_id == truck.id).all()

        trailer = db.query(Trailer).filter(Trailer.id == truck.trailer_id).first()
        driver = db.query(Driver).filter(Driver.id == truck.primary_driver_id).first()

        shipment = None
        if truck.current_shipment_id and truck.current_shipment_type:
            if truck.current_shipment_type.lower() == "ftl":
                shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
                    FTL_Shipment.id == truck.current_shipment_id
                ).first()
            elif truck.current_shipment_type.lower() == "power":
                shipment = db.query(Assigned_Power_Shipments).filter(
                    Power_Shipment.id == truck.current_shipment_id
                ).first()

        return {
            "vehicle information": {
                "id": truck.id,
                "verification_status": truck.is_verified,
                "status": truck.status,
                "availability_status": truck.service_status,
                "type": truck.type,
                "axle_configuration": truck.axle_configuration,
                "equipment_type": truck.equipment_type,
                "trailer_type": truck.trailer_type if truck.trailer_type else "N/A",
                "trailer_length": truck.trailer_length if truck.trailer_length else "N/A",
                "make": truck.make,
                "model": truck.model,
                "year": truck.year,
                "color": truck.color,
                "license_plate": truck.license_plate,
                "license_expiry_date": truck.license_expiry_date,
                "tare_weight": truck.tare_weight,
                "gvm_weight": truck.gvm_weight,
                "payload_capacity": truck.payload_capacity,
            },
            "tracker_details": {
                "tracker_company_name": truck.tracker_providers_name,
                "tracker_company_country": truck.tracker_providers_country,
                "tracker_device_id": truck.tracker_id,
                "tracking_account_login_username": truck.tracker_login_username,
                "tracking_account_login_password": truck.tracker_login_password,
            },
            "vehicle_documents": {
                "vehicle_registration_or_leasing_certificate": truck.vrc_or_leasing,
                "vehicle_license_disc": truck.vehicle_license_disk,
                "vehicle_roadworthy_certificate": truck.vehicle_road_worthy_certificate,
                "vehicle_tracking_certificate": truck.vehicle_tracking_certificate,
            },
            "vehicle_images": {
                "front_angle": truck.front_angle_image,
                "rear_angle": truck.rear_angle_image,
                "left_angle": truck.left_angle_image,
                "right_angle": truck.right_angle_image,
            },
            "vehicle_schedule": [{
                "shipment_id": schedule.shipment_id,
                "shipment_type": schedule.shipment_type,
                "status": schedule.status,
                "origin": schedule.origin,
                "destination": schedule.destination,
                "pickup_date": schedule.pickup_date,
                "pickup_appointment": schedule.pickup_appointment,
                "eta": schedule.eta,
                "distance": schedule.distance,
                "rate": schedule.rate,
            }for schedule in vehicle_schedules],
            "trailer_information": {
                "id": trailer.id if trailer else "N/A",
                "verification_status": trailer.is_verified if trailer else "N/A",
                "status": trailer.status if trailer else "N/A",
                "make": trailer.make if trailer else "N/A",
                "model": trailer.model if trailer else "N/A",
                "year": trailer.year if trailer else "N/A",
                "color": trailer.color if trailer else "N/A",
                "equipment_type": trailer.equipment_type if trailer else "N/A",
                "trailer_type": trailer.trailer_type if trailer else "N/A",
                "trailer_length": trailer.trailer_length if trailer else "N/A",
                "license_plate": trailer.license_plate if trailer else "N/A",
                "license_expiry_date": trailer.license_expiry_date if trailer else "N/A",
                "tare_weight": trailer.tare_weight if trailer else "N/A",
                "gvm_weight": trailer.gvm_weight if trailer else "N/A",
                "payload_capacity": trailer.payload_capacity if trailer else "N/A",
            },
            "driver_information": {
                "id": driver.id,
                "verification_status": driver.is_verified,
                "status": driver.status,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "nationality": driver.nationality,
                "id_number": driver.id_number,
                "phone_number": driver.phone_number,
                "email": driver.email,
                "license_number": driver.license_number,
                "license_expiry_date": driver.license_expiry_date,
                "distance_driven": driver.total_distance_driven,
                "total_shipments_fulfilled": driver.total_shipments_completed,
            },
            "current_shipment_information": {
                "id": shipment.shipment_id if shipment else "N/A",
                "status": shipment.status if shipment else "N/A",
                "trip_status": shipment.trip_status if shipment else "N/A",
                "type": shipment.type if shipment else "N/A",
                "origin": shipment.origin_city_province if shipment else "N/A",
                "destination": shipment.destination_city_province if shipment else "N/A",
                "pickup_date": shipment.pickup_date if shipment else "N/A",
                "distance": shipment.distance if shipment else "N/A",
                "estimated_transit_time": shipment.estimated_transit_time if shipment else "N/A",
                "rate_per_km": shipment.rate_per_km if shipment else "N/A",
                "rate_per_ton": shipment.rate_per_ton if shipment else "N/A",
            }
        }

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

@router.get("/all-fleet-trailers")  # UnTested
def get_all_fleet_trailers(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
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

        return {
            "trailers": [{
                "id": trailer.id,
                "verification_status": trailer.is_verified,
                "status": trailer.status,
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.year,
                "license_plate": trailer.license_plate,
                "license_expiry_date": trailer.license_expiry_date,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "payload_capacity": trailer.payload_capacity,
                "current_vehicle": (
                    {
                        "make": truck.make,
                        "model": truck.model,
                        "year": truck.year,
                        "color": truck.color,
                        "axle_configuration": truck.axle_configuration,
                        "license_plate": truck.license_plate
                    }
                    if (truck := db.query(Vehicle).filter(Vehicle.id == trailer.truck_id).first())
                    else None
                )
            } for trailer in trailers]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/fleet-trailer/{id}") #Tested
def get_single_trailer(
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
        trailer = db.query(Trailer).filter(
            Trailer.id == id,
            Trailer.owner_id == company_id
        ).first()
        truck = db.query(Vehicle).filter(Vehicle.id == trailer.truck_id).first()

        if not trailer:
            raise HTTPException(
                status_code=404,
                detail=f"Trailer with ID {vehicle_data.id} not found or not authorized"
            )

        return {
            "trailer_information": {
                "id": trailer.id,
                "verification_status": trailer.is_verified,
                "status": trailer.status,
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.year,
                "color": trailer.color,
                "vin": trailer.vin,
                "license_plate": trailer.license_plate,
                "license_expiry_date": trailer.license_expiry_date,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "tare_weight": trailer.tare_weight,
                "gvm_weight": trailer.gvm_weight,
                "payload_capacity": trailer.payload_capacity,
                "current_truck_id": trailer.truck_id
            },
            "trailer_documents": {
                "registration_certificate_or_leasing_certificate": trailer.vrc_leasing,
                "license_disc": trailer.license_disk,
                "roadworthy_certificate": trailer.road_worthy_certificate,
            },
            "trailer_images": {
                "front_angle": trailer.front_angle_image,
                "rear_angle": trailer.rear_angle_image,
                "left_angle": trailer.left_angle_image,
                "right_angle": trailer.right_angle_image,
            },
            "assigned_vehicle_information": {
                "id": truck.id,
                "verification_status": truck.is_verified,
                "status": truck.status,
                "type": truck.type,
                "axle_configuration": truck.axle_configuration,
                "make": truck.make,
                "model": truck.model,
                "year": truck.year,
                "color": truck.color,
                "vin": truck.vin,
                "license_plate": truck.license_plate,
                "license_expiry_date": truck.license_expiry_date,
                "tare_weight": truck.tare_weight,
                "gvm_weight": truck.gvm_weight,
                "payload_capacity": truck.payload_capacity
            },
        }

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
