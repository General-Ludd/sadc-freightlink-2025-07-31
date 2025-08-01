from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.carrier import Carrier
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.user import Driver, DriverAssignmentHistory
from models.vehicle import Trailer, Vehicle

def assign_primary_driver(
    db: Session,
    driver_id: int,
    vehicle_id: int,
    role: str,  # "primary" or "secondary"
    current_user: dict
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user["company_id"]

    if role not in ["primary", "secondary"]:
        raise HTTPException(status_code=400, detail="Role must be 'primary' or 'secondary'")

    # Validate carrier
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not verified or inactive")

    # Validate driver
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver or not driver.is_verified or driver.company_id != carrier.id:
        raise HTTPException(status_code=404, detail="Driver not found or not verified")

    # Validate vehicle
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle or not vehicle.is_verified or vehicle.owner_id != carrier.id:
        raise HTTPException(status_code=404, detail="Vehicle not found or not verified")
    
    ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.vehicle_id == vehicle.id,
                                                       FTL_SHIPMENT.shipment_status == "Assigned").all()
    
    ftl_assignments = db.query(Assigned_Spot_Ftl_Shipments).filter(Assigned_Spot_Ftl_Shipments.vehicle_id == vehicle.id,
                                                       Assigned_Spot_Ftl_Shipments.status == "Assigned").all()

    power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipment_status == "Assigned",
                                                        POWER_SHIPMENT.vehicle_id == vehicle.id).all()
    
    power_assignments = db.query(Assigned_Power_Shipments).filter(Assigned_Power_Shipments.vehicle_id == vehicle.id,
                                                       Assigned_Power_Shipments.status == "Assigned").all()

    # Prevent assigning a driver already assigned to another vehicle
    if driver.current_vehicle_id and driver.current_vehicle_id != vehicle_id:
        raise HTTPException(status_code=400, detail="Driver is already assigned to another vehicle")

    # Check for role conflicts
    if role == "primary" and vehicle.primary_driver_id and vehicle.primary_driver_id != driver_id:
        raise HTTPException(status_code=400, detail="Vehicle already has a different primary driver")
    if role == "secondary" and vehicle.secondary_driver_id and vehicle.secondary_driver_id != driver_id:
        raise HTTPException(status_code=400, detail="Vehicle already has a different secondary driver")

    # Assign driver to vehicle
    driver.current_vehicle_id = vehicle_id
    for shipment in ftl_shipments:
        shipment.driver_id = driver.id
        shipment.driver_name = f"{driver.first_name}-{driver.last_name}"

    for shipment in power_shipments:
        shipment.driver_id = driver.id
        shipment.driver_first_name = driver.first_name
        shipment.driver_last_name = driver.last_name

    for assignment in ftl_assignments:
        assignment.driver_id = driver.id

    for assignment in power_assignments:
        assignment.driver_id = driver.id


    if role == "primary":
        vehicle.primary_driver_id = driver_id
    else:
        vehicle.secondary_driver_id = driver_id

    # Track history
    assignment = DriverAssignmentHistory(
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        assigned_by=current_user.get("user_id"),
        role=role
    )
    db.add(assignment)

    db.commit()
    db.refresh(driver)
    db.refresh(vehicle)

    return {"message": f"Driver assigned as {role} driver successfully"}


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