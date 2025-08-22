from sqlalchemy.orm import Session
from models.carrier import Carrier, Carrier_Notification
from models.shipper import Corporation
from models.vehicle import Vehicle, Trailer, ShipperTrailer
from models.user import CarrierDirector
from schemas.vehicle import VehicleCreate, TrailerCreate, ShipperTrailerCreate, TrailerUpdate
from utils.auth import get_current_user
from fastapi import Depends, HTTPException
from utils.payload_capacity import calculate_payload_capacity  # Import the payload calculation function

def get_vehicle_by_id(vehicle_id: int, db: Session) -> Vehicle:
    return db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

def create_vehicle(db: Session, vehicle_data: VehicleCreate, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    # Create a temporary Vehicle object for payload calculation
    temp_truck = Vehicle(
        type=vehicle_data.type,
        tare_weight=vehicle_data.tare_weight,
        gvm_weight=vehicle_data.gvm_weight
    )

    # Calculate the payload capacity for the truck
    payload_capacity = calculate_payload_capacity(temp_truck)

    # Create the vehicle in the database
    truck = Vehicle(
        type=vehicle_data.type,
        make=vehicle_data.make,
        model=vehicle_data.model,
        year=vehicle_data.year,
        color=vehicle_data.color,
        axle_configuration=vehicle_data.axle_configuration,
        vin=vehicle_data.vin,
        license_plate=vehicle_data.license_plate,
        license_expiry_date=vehicle_data.license_expiry_date,
        tare_weight=vehicle_data.tare_weight,
        gvm_weight=vehicle_data.gvm_weight,
        tracker_providers_name=vehicle_data.tracker_providers_name,
        tracker_providers_country=vehicle_data.tracker_providers_country,
        tracker_id=vehicle_data.tracker_id,
        tracker_login_username=vehicle_data.tracker_login_username,
        tracker_login_password=vehicle_data.tracker_login_password,
        equipment_type=vehicle_data.equipment_type,
        owner_id=company_id,  # Use the company_id as the owner_id
        vrc_or_leasing=vehicle_data.vrc_or_leasing,
        vehicle_license_disk=vehicle_data.vehicle_license_disk,
        vehicle_road_worthy_certificate=vehicle_data.vehicle_road_worthy_certificate,
        vehicle_tracking_certificate=vehicle_data.vehicle_tracking_certificate,
        front_angle_image=vehicle_data.front_angle_image,
        rear_angle_image=vehicle_data.rear_angle_image,
        left_angle_image=vehicle_data.left_angle_image,
        right_angle_image=vehicle_data.right_angle_image,
        payload_capacity=payload_capacity,  # Assign calculated payload capacity
    )
    
    db.add(truck)
    db.commit()
    db.refresh(truck)

    # ✅ Create a notification for the vehicle creation
    notification = Carrier_Notification(
        company_id=company_id,
        type="vehicle_creation",
        message=f"New vehicle {truck.make} {truck.model} ({truck.license_plate}) has been added to your fleet and undergoing verification.",
        is_read=False
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    return truck

def create_trailer(db: Session, trailer_data: TrailerCreate, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    # Create a temporary Vehicle object for payload calculation
    temp_truck = Trailer(
        trailer_type=trailer_data.trailer_type,
        tare_weight=trailer_data.tare_weight,
        gvm_weight=trailer_data.gvm_weight
    )

    # Calculate the payload capacity for the truck
    payload_capacity = calculate_payload_capacity(temp_truck)

    # Create the Trailer
    trailer = Trailer(
        make=trailer_data.make,
        model=trailer_data.model,
        year=trailer_data.year,
        color=trailer_data.color,
        equipment_type=trailer_data.equipment_type,
        trailer_type=trailer_data.trailer_type,
        trailer_length=trailer_data.trailer_length,
        vin=trailer_data.vin,
        license_plate=trailer_data.license_plate,
        license_expiry_date=trailer_data.license_expiry_date,
        tare_weight=trailer_data.tare_weight,
        gvm_weight=trailer_data.gvm_weight,
        owner_id=company_id,
        company_name=carrier.legal_business_name,
        company_type=carrier.type,
        vrc_leasing=trailer_data.vrc_leasing,
        license_disk=trailer_data.license_disk,
        road_worthy_certificate=trailer_data.road_worthy_certificate,
        front_angle_image=trailer_data.front_angle_image,
        rear_angle_image=trailer_data.rear_angle_image,
        left_angle_image=trailer_data.left_angle_image,
        right_angle_image=trailer_data.right_angle_image,
        payload_capacity=payload_capacity,  # Assign calculated payload capacity
    )
    db.add(trailer)
    db.commit()
    db.refresh(trailer)
    return trailer

def create_shipper_trailer(db: Session, trailer_data: ShipperTrailerCreate, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    company = db.query(Corporation).filter(Corporation.id == company_id).first()
    if not company or not company.is_verified or company.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    # Create a temporary Vehicle object for payload calculation
    temp_truck = ShipperTrailer(
        trailer_type=trailer_data.trailer_type,
        tare_weight=trailer_data.tare_weight,
        gvm_weight=trailer_data.gvm_weight
    )

    # Calculate the payload capacity for the truck
    payload_capacity = calculate_payload_capacity(temp_truck)

    # Create the Trailer
    trailer = ShipperTrailer(
        make=trailer_data.make,
        model=trailer_data.model,
        year=trailer_data.year,
        color=trailer_data.color,
        equipment_type=trailer_data.equipment_type,
        trailer_type=trailer_data.trailer_type,
        trailer_length=trailer_data.trailer_length,
        vin=trailer_data.vin,
        license_plate=trailer_data.license_plate,
        license_expiry_date=trailer_data.license_expiry_date,
        tare_weight=trailer_data.tare_weight,
        gvm_weight=trailer_data.gvm_weight,
        owner_id=company_id,
        company_name=company.legal_business_name,
        company_type=company.type,
        vrc_leasing=trailer_data.vrc_leasing,
        license_disk=trailer_data.license_disk,
        road_worthy_certificate=trailer_data.road_worthy_certificate,
        front_angle_image=trailer_data.front_angle_image,
        rear_angle_image=trailer_data.rear_angle_image,
        left_angle_image=trailer_data.left_angle_image,
        right_angle_image=trailer_data.right_angle_image,
        payload_capacity=payload_capacity,  # Assign calculated payload capacity
    )
    db.add(trailer)
    db.commit()
    db.refresh(trailer)
    return trailer

def update_shipper_trailer(db: Session, trailer_id: int, trailer_data: TrailerUpdate, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")

    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    # Check if carrier exists and is valid
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    # Get the existing trailer (your filter was missing a comma between conditions)
    trailer = db.query(ShipperTrailer).filter(
        ShipperTrailer.id == trailer_id,
        ShipperTrailer.company_id == company_id
    ).first()

    if not trailer:
        raise HTTPException(status_code=404, detail="Trailer not found")

    # ✅ Update fields dynamically if provided
    update_fields = [
        "vin", "license_plate", "license_expiry_date", "vrc_leasing",
        "vehicle_license_disk", "road_worthy_certificate",
        "front_angle_image", "rear_angle_image", "left_angle_image", "right_angle_image"
    ]

    for field in update_fields:
        value = getattr(trailer_data, field)
        if value is not None:
            setattr(trailer, field, value)

    # When updating, always reset verification status
    trailer.is_verified = False
    trailer.status = "Suspended"

    db.commit()
    db.refresh(trailer)

    return {
        "message": f"Trailer-{trailer.id} updated successfully, please wait while it undergoes partial verification"
    }


