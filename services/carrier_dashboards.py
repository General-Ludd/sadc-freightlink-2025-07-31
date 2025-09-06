from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.carrier import Carrier
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.user import Driver, DriverAssignmentHistory
from models.vehicle import Trailer, Vehicle, Vehicle_Schedule

def assign_driver_to_vehicle(
    db: Session,
    vehicle_id: int,
    driver_id: int,
    current_user: dict
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user["company_id"]

    # Validate carrier
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not verified, inactive")

    # Validate driver
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver or not driver.is_verified or driver.company_id != carrier.id:
        raise HTTPException(status_code=404, detail="Driver not found or not verified")

    # Validate vehicle
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle or not vehicle.is_verified or vehicle.owner_id != carrier.id:
        raise HTTPException(status_code=404, detail="Vehicle not found, not verified or does not belong to this carrier company")
    
    ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.vehicle_id == vehicle.id,
                                                       FTL_SHIPMENT.shipment_status == "Assigned").all()
    
    ftl_assignments = db.query(Assigned_Spot_Ftl_Shipments).filter(Assigned_Spot_Ftl_Shipments.vehicle_id == vehicle.id,
                                                       Assigned_Spot_Ftl_Shipments.status == "Assigned").all()

    power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipment_status == "Assigned",
                                                        POWER_SHIPMENT.vehicle_id == vehicle.id).all()
    
    power_assignments = db.query(Assigned_Power_Shipments).filter(Assigned_Power_Shipments.vehicle_id == vehicle.id,
                                                       Assigned_Power_Shipments.status == "Assigned").all()

    # 🚨 Check if vehicle already has a primary driver
    if vehicle.primary_driver_id:
        return {
            "message": f"Vehicle-{vehicle.id} already has a primary driver assigned. "
                       f"Please remove Driver-{vehicle.primary_driver_id} first."
        }

    # 🚨 Prevent assigning a driver already assigned to another vehicle
    if driver.current_vehicle_id and driver.current_vehicle_id != vehicle_id:
        raise HTTPException(status_code=400, detail="Driver is already assigned to another vehicle")

    # 🚨 Check if vehicle currently has shipments in transit
    in_progress_ftl = db.query(FTL_SHIPMENT).filter(
        FTL_SHIPMENT.vehicle_id == vehicle.id,
        FTL_SHIPMENT.shipment_status == "In-Progress"
    ).first()

    in_progress_power = db.query(POWER_SHIPMENT).filter(
        POWER_SHIPMENT.vehicle_id == vehicle.id,
        POWER_SHIPMENT.shipment_status == "In-Progress"
    ).first()

    if in_progress_ftl or in_progress_power:
        raise HTTPException(
            status_code=400,
            detail=f"Vehicle-{vehicle.id} has a shipment it is or should be currently In-Progress. "
                   f"Please complete that shipment before assigning a new driver."
        )

    # Assign driver to vehicle
    driver.current_vehicle_id = vehicle_id
    vehicle.primary_driver_id = driver_id
    for shipment in ftl_shipments:
        shipment.driver_id = driver.id
        shipment.driver_first_name = driver.first_name
        shipment.driver_last_name = driver.last_name
        shipment.driver_license_number = driver.license_number
        shipment.driver_email = driver.email
        shipment.driver_phone_number = driver.phone_number

    for shipment in power_shipments:
        shipment.driver_id = driver.id
        shipment.driver_first_name = driver.first_name
        shipment.driver_last_name = driver.last_name
        shipment.driver_license_number = driver.license_number
        shipment.driver_email = driver.email
        shipment.driver_phone_number = driver.phone_number

    for assignment in ftl_assignments:
        assignment.driver_id = driver.id

    for assignment in power_assignments:
        assignment.driver_id = driver.id

    # Track history
    assignment = DriverAssignmentHistory(
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        assigners_id=current_user.get("id"),
        assigners_first_name=current_user.get("first_name"),
        assigners_last_name=current_user.get("last_name"),
    )
    db.add(assignment)

    db.commit()
    db.refresh(driver)
    db.refresh(vehicle)

    return {"message": f"Driver successfully to Vehicle-{vehicle.id}"}


def assign_trailer_to_vehicle(
    db: Session,
    trailer_id: int,
    vehicle_id: int,
    current_user: dict
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user["company_id"]

    # Step 1: Fetch and validate vehicle
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    if not vehicle.is_verified or vehicle.status != "Active":
        raise HTTPException(status_code=400, detail="Vehicle is not verified or not active")

    if vehicle.owner_id != company_id:
        raise HTTPException(status_code=403, detail="Vehicle does not belong to your Fleet")

    # Step 2: Fetch and validate trailer
    trailer = db.query(Trailer).filter(Trailer.id == trailer_id).first()
    if not trailer:
        raise HTTPException(status_code=404, detail="Trailer not found")

    if not trailer.is_verified:
        raise HTTPException(status_code=400, detail="Trailer is not verified")

    if trailer.owner_id != vehicle.owner_id:
        raise HTTPException(status_code=403, detail="Trailer does not belong to the same Fleet as the vehicle")

    if trailer.truck_id:
        raise HTTPException(
            status_code=400,
            detail=f"Trailer is currently attached to vehicle ID {trailer.truck_id}"
        )

    # Step 3: Assign trailer to vehicle
    trailer.truck_id = vehicle.id
    vehicle.trailer_id = trailer.id
    vehicle.equipment_type = trailer.equipment_type
    vehicle.trailer_type = trailer.trailer_type
    vehicle.trailer_length = trailer.trailer_length
    vehicle.payload_capacity = (vehicle.payload_capacity - trailer.tare_weight)

    db.commit()
    db.refresh(trailer)

    return {"message": f"Trailer (ID: {trailer.id}) successfully assigned to Vehicle (ID: {vehicle.id})"}


def assign_shipment_to_vehicle(
    db: Session,
    vehicle_id: int,
    shipment_id: int,
    shipment_type: str,
    current_user: dict
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user["company_id"]

    try:
        # -------------------
        # FETCH SHIPMENT
        # -------------------
        if shipment_type == "FTL":
            shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == shipment_id).first()
            if not shipment:
                raise HTTPException(status_code=404, detail="Client FTL shipment not found")
            carrier_shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
                Assigned_Spot_Ftl_Shipments.shipment_id == shipment_id
            ).first()
            if not carrier_shipment:
                raise HTTPException(status_code=404, detail="Carrier assigned FTL shipment not found")
        else:
            shipment = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.id == shipment_id).first()
            if not shipment:
                raise HTTPException(status_code=404, detail="Client Power shipment not found")
            carrier_shipment = db.query(Assigned_Power_Shipments).filter(
                Assigned_Power_Shipments.shipment_id == shipment_id
            ).first()
            if not carrier_shipment:
                raise HTTPException(status_code=404, detail="Carrier assigned Power shipment not found")

        # -------------------
        # VALIDATE VEHICLE
        # -------------------
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if not vehicle.is_verified or vehicle.status != "Active":
            raise HTTPException(status_code=400, detail="Vehicle is not verified or not active")
        if vehicle.owner_id != company_id:
            raise HTTPException(status_code=403, detail="Vehicle does not belong to your Fleet")

        # -------------------
        # VEHICLE REQUIREMENTS
        # -------------------
        if shipment_type == "FTL":
            if vehicle.type != shipment.required_truck_type:
                raise HTTPException(status_code=400, detail="Vehicle type does not match required truck type")
            if vehicle.equipment_type != shipment.equipment_type:
                raise HTTPException(status_code=400, detail="Vehicle equipment type does not match required equipment type")
            if vehicle.trailer_type != shipment.trailer_type:
                raise HTTPException(status_code=400, detail="Vehicle trailer type does not match required trailer type")
            if vehicle.trailer_length != shipment.trailer_length:
                raise HTTPException(status_code=400, detail="Vehicle trailer length does not match required trailer length")
            if vehicle.payload_capacity < shipment.minimum_weight_bracket:
                raise HTTPException(status_code=400, detail="Vehicle payload capacity is not sufficient")
        else:  # POWER
            if vehicle.type != shipment.required_truck_type:
                raise HTTPException(status_code=400, detail="Vehicle type does not match required truck type")
            if vehicle.axle_configuration != shipment.axle_configuration:
                raise HTTPException(status_code=400, detail="Vehicle axle configuration does not match required axle configuration")
            if vehicle.payload_capacity < shipment.minimum_weight_bracket:
                raise HTTPException(status_code=400, detail="Vehicle payload capacity is not sufficient")

        # -------------------
        # ASSIGN VEHICLE
        # -------------------
        vehicle_schedule = Vehicle_Schedule(
            vehicle_id=vehicle_id,
            status="Assigned",
            shipment_id=shipment_id,
            shipment_type=shipment_type,
            origin=shipment.origin_city_province,
            destination=shipment.destination_city_province,  # ✅ fixed
            pickup_date=shipment.pickup_date,
            pickup_appointment=carrier_shipment.pickup_appointment,
            eta_date=carrier_shipment.eta_date,
            eta_window=carrier_shipment.eta_window,
            distance=carrier_shipment.distance,
            rate=carrier_shipment.shipment_rate,
            commodity=carrier_shipment.commodity,
            weight=carrier_shipment.shipment_weight,
        )

        # ✅ fixed tuple bug
        shipment.vehicle_id = vehicle.id
        shipment.driver_id = vehicle.driver_id if vehicle.driver_id else None

        db.add(vehicle_schedule)
        db.commit()
        db.refresh(vehicle_schedule)

        return {
            "message": f"{shipment.type} Shipment ID-{shipment_id} successfully assigned to Vehicle {vehicle_id}",
            "vehicle_schedule_id": vehicle_schedule.id
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

