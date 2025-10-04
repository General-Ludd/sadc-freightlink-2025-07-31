from datetime import datetime, timedelta
import pytz
from fastapi import HTTPException
from sqlalchemy.orm import Session
# Import all models (adjust paths to your actual project structure)
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.brokerage.finance import BrokerageLedger, CarrierFinancialAccounts, Dedicated_Lane_BrokerageLedger, Interim_Invoice, Lane_Interim_Invoice, Lane_Invoice, Load_Invoice
from models.brokerage.loadboard import Dedicated_lanes_LoadBoard, Ftl_Load_Board, Power_Load_Board
from models.spot_bookings.shipment_facility import ShipmentFacility
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.administration import Platform_Super_Admins, Platform_Super_and_Support_Admins_Permissions
from models.carrier import Carrier
from models.vehicle import Vehicle
from models.user import Driver
from services.platform_administration_services.audit_records import AdminShipmentAssignmentLog  # create this if not already in models
# Import any helpers you use
from utils.datetime_utils import format_datetime_sast  # adjust import path as needed
from schemas.brokerage.loadboard import AdminAssignShipmentRequest  # request schema


@router.post("/assign-spot-shipment", status_code=200)
def admin_assign_spot_ftl_shipment_to_carrier(
    shipment_data: AdminAssignShipmentRequest,
    db: Session = Depends(get_db),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Allows an authenticated admin to manually assign a Spot FTL shipment
    to a specific carrier, on behalf of that carrier.
    """
    print(f"Authenticated Admin: {current_admin}")

    # --- Ensure admin privileges ---
    try:
        admin = db.query(Platform_Super_Admins).filter(Platform_Super_Admins.email == current_admin.get("email")).first()
        if not admin:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if not admin.is_verified:
            raise HTTPException(status_code=403, detail="Administrator Account not verified")
    except AssertionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        permissions = db.query(Platform_Super_and_Support_Admins_Permissions).filter(Platform_Super_and_Support_Admins_Permissions.id == admin.id).first()
    if not permissions.update_shipments:
        raise HTTPException(status_code=403, detail="Insufficient permissions to assign shipment to carrier")
    except AssertionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    carrier_id = shipment_data.carrier_id
    if not carrier_id:
        raise HTTPException(status_code=400, detail="Carrier ID must be provided.")

    try:
        # --- Step 1: Loadboard entry ---
        loadboard_entry = db.query(Ftl_Load_Board).filter(
            Ftl_Load_Board.shipment_id == shipment_data.shipment_id
        ).first()
        if not loadboard_entry:
            raise HTTPException(status_code=404, detail="Loadboard entry not found.")
        if loadboard_entry.status != "Available":
            raise HTTPException(status_code=400, detail="Shipment is no longer available for assignment.")

        # --- Step 2: Shipment record ---
        shipment = db.query(FTL_SHIPMENT).filter(
            FTL_SHIPMENT.id == shipment_data.shipment_id
        ).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found.")

        pickup_facility = db.query(ShipmentFacility).filter(
            ShipmentFacility.id == shipment.pickup_facility_id
        ).first()

        # --- Step 3: Brokerage Ledger ---
        brokerage_ledger = db.query(BrokerageLedger).filter(
            BrokerageLedger.shipment_id == shipment.id,
            BrokerageLedger.shipment_type == shipment.type,
        ).first()
        if not brokerage_ledger:
            raise HTTPException(status_code=404, detail="Shipment not found in Brokerage Ledger for specified lane type.")

        # --- Step 4: Carrier ---
        carrier = db.query(Carrier).filter(Carrier.id == shipment_data.carrier_id).first()
        if not carrier:
            raise HTTPException(status_code=404, detail="Carrier not found.")
        if not carrier.is_verified:
            raise HTTPException(status_code=400, detail="Carrier account not verified.")
        if carrier.status != "Active":
            raise HTTPException(status_code=400, detail="Carrier account not active.")

        # --- Step 5: Financial Account ---
        financial_account = db.query(CarrierFinancialAccounts).filter(
            CarrierFinancialAccounts.id == shipment_data.carrier_id
        ).first()
        if not financial_account:
            raise HTTPException(status_code=404, detail="Financial account not found.")
        if not financial_account.is_verified:
            raise HTTPException(status_code=403, detail="Financial account not verified.")
        if financial_account.status != "Active":
            raise HTTPException(status_code=403, detail="Financial account not active.")

        # --- Step 6: Vehicle ---
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == shipment_data.vehicle_id,
            Vehicle.owner_id == carrier.id,
        ).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found.")
        if not vehicle.is_verified:
            raise HTTPException(status_code=400, detail="Vehicle not verified.")
        if vehicle.status != "Active":
            raise HTTPException(status_code=400, detail="Vehicle not active.")

        # --- Step 7: Validate Truck Specs ---
        try:
            assert vehicle.type == shipment.required_truck_type, "Truck type mismatch"
            assert vehicle.equipment_type == shipment.equipment_type, "Equipment type mismatch"
            assert vehicle.trailer_type == shipment.trailer_type, "Trailer type mismatch"
            assert vehicle.trailer_length == shipment.trailer_length, "Trailer length mismatch"
            assert vehicle.payload_capacity >= shipment.minimum_weight_bracket, "Payload capacity too low"
        except AssertionError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # --- Step 8: Driver ---
        driver = db.query(Driver).filter(
            Driver.id == vehicle.primary_driver_id,
            Driver.current_vehicle_id == shipment_data.vehicle_id,
        ).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found.")
        if not driver.is_verified:
            raise HTTPException(status_code=400, detail="Driver not verified.")
        if driver.status != "Active":
            raise HTTPException(status_code=400, detail="Driver not active.")

        # Step 7: Update shipment
        shipment.shipment_status = "Assigned"
        shipment.trip_status = "Scheduled"
        shipment.carrier_id = carrier_id
        shipment.carrier_name = f"SADC FREIGHTLINK Carrier {carrier.id}"
        shipment.carrier_git_cover_amount = carrier.git_cover_amount
        shipment.carrier_liability_cover_amount = carrier.liability_insurance_cover_amount
        shipment.vehicle_id = vehicle.id
        shipment.vehicle_type = vehicle.type
        shipment.vehicle_make = vehicle.make
        shipment.vehicle_model = vehicle.model
        shipment.vehicle_color = vehicle.color
        shipment.vehicle_license_plate = vehicle.license_plate
        shipment.vehicle_vin = vehicle.vin
        shipment.vehicle_equipment_type = vehicle.equipment_type
        shipment.vehicle_trailer_type = vehicle.trailer_type
        shipment.vehicle_trailer_length = vehicle.trailer_length
        shipment.vehicle_tare_weight = vehicle.tare_weight
        shipment.vehicle_gvm_weight = vehicle.gvm_weight
        shipment.vehicle_payload_capacity = vehicle.payload_capacity
        shipment.driver_id = driver.id
        shipment.driver_first_name = driver.first_name 
        shipment.driver_last_name = driver.last_name
        shipment.driver_license_number = driver.license_number
        shipment.driver_phone_number = driver.phone_number
        shipment.driver_email = driver.email

        # Step 9: Update loadboard status
        loadboard_entry.status="Assigned"

        brokerage_ledger.carrier_id=carrier.id
        brokerage_ledger.carrier_company_type=carrier.type
        brokerage_ledger.carrier_company_name=carrier.legal_business_name
        brokerage_ledger.vehicle_id=vehicle.id
        brokerage_ledger.vehicle_make=vehicle.make
        brokerage_ledger.vehicle_model=vehicle.model
        brokerage_ledger.vehicle_year=vehicle.year
        brokerage_ledger.vehicle_color=vehicle.color
        brokerage_ledger.vehicle_vin=vehicle.vin
        brokerage_ledger.vehicle_license_plate=vehicle.license_plate
        brokerage_ledger.driver_id=driver.id
        brokerage_ledger.driver_first_name=driver.first_name
        brokerage_ledger.driver_last_name=driver.last_name
        brokerage_ledger.driver_id_number=driver.id_number
        brokerage_ledger.driver_license_number=driver.license_number

        # --- Step 11: Create shipment invoice ---
        shipment_invoice = Load_Invoice(
            shipment_id=shipment.id,
            shipment_type=shipment.type,
            invoice_type="Service Invoice",
            billing_date=shipment.pickup_date,
            due_date=shipment.invoice_due_date + timedelta(days=2),
            description=f"{shipment.type} Shipment {shipment.id}",
            status="Pending",
            carrier_company_id=carrier.id,
            carrier_financial_account_id=carrier.id,
            payment_terms=shipment.payment_terms,
            carrier_bank=financial_account.bank_name,
            carrier_bank_account=financial_account.account_number,
            payment_reference=f"{shipment.type} Shipment {shipment.id}",
            carrier_company_name=financial_account.legal_business_name,
            contact_person_name=f"{financial_account.directors_first_name} {financial_account.directors_last_name}",
            carrier_email=carrier.business_email,
            carrier_address=carrier.business_address,
            origin_address=shipment.complete_origin_address,
            destination_address=shipment.complete_destination_address,
            pickup_date=shipment.pickup_date,
            distance=shipment.distance,
            transit_time=shipment.estimated_transit_time,
            base_amount=brokerage_ledger.carrier_payable,
            due_amount=brokerage_ledger.carrier_payable,
        )

        db.add(shipment_invoice)
        db.flush()

        # --- Step 12: Log assignment ---
        assigned_shipment = Assigned_Spot_Ftl_Shipments(
            shipment_id=shipment.id,
            invoice_id=shipment_invoice.id,
            invoice_due_date = shipment.invoice_due_date + timedelta(days=2),
            invoice_status = shipment_invoice.status,
            trip_type=shipment.trip_type,
            load_type=shipment.load_type,
            carrier_id=carrier.id,
            carrier_name=carrier.legal_business_name,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            accepted_for=f"{driver.first_name} {driver.last_name}",
            accepted_at=format_datetime_sast(datetime.utcnow().replace(tzinfo=pytz.utc)),
            minimum_weight_bracket=shipment.minimum_weight_bracket,
            minimum_git_cover_amount=shipment.minimum_git_cover_amount,
            minimum_liability_cover_amount=shipment.minimum_liability_cover_amount,
            shipment_rate=brokerage_ledger.carrier_payable,
            distance=shipment.distance,
            rate_per_km=loadboard_entry.rate_per_km,
            rate_per_ton=loadboard_entry.rate_per_ton,
            payment_terms=loadboard_entry.payment_terms,
            status="Assigned",
            trip_status="Scheduled",
            required_truck_type=shipment.required_truck_type,
            equipment_type=shipment.equipment_type,
            trailer_type=shipment.trailer_type,
            trailer_length=shipment.trailer_length,
            origin_address=shipment.origin_address,
            origin_address_completed=shipment.complete_origin_address,
            origin_city_province=shipment.origin_city_province,
            origin_country=shipment.origin_country,
            origin_region=shipment.origin_region,
            destination_address=shipment.destination_address,
            destination_address_completed=shipment.complete_destination_address,
            destination_city_province=shipment.destination_city_province,
            destination_country=shipment.destination_country,
            destination_region=shipment.destination_region,
            route_preview_embed=shipment.route_preview_embed,
            pickup_date=shipment.pickup_date,
            priority_level=shipment.priority_level,
            customer_reference_number=shipment.customer_reference_number,
            shipment_weight=shipment.shipment_weight,
            commodity=shipment.commodity,
            temperature_control=shipment.temperature_control,
            hazardous_materials=shipment.hazardous_materials,
            packaging_quantity=shipment.packaging_quantity,
            packaging_type=shipment.packaging_type,
            pickup_number=shipment.pickup_number,
            pickup_notes=shipment.pickup_notes,
            delivery_number=shipment.delivery_number,
            delivery_notes=shipment.delivery_notes,
            pickup_facility_id=shipment.pickup_facility_id,
            delivery_facility_id=shipment.delivery_facility_id,
            estimated_transit_time=shipment.estimated_transit_time,
            eta_window=shipment.eta_window,
            eta_date=shipment.eta_date,
            pickup_start_time=pickup_facility.start_time,
            pickup_appointment=shipment.pickup_appointment
        )
        brokerage_ledger.load_invoice_id = shipment_invoice.id
        brokerage_ledger.load_invoice_due_date = shipment_invoice.due_date
        brokerage_ledger.load_invoice_status = shipment_invoice.status
        brokerage_ledger.shipment_status = "Assigned"
        db.add(assigned_shipment)

        # --- Step 13: Admin log ---
        admin_log = AdminShipmentAssignmentLog(
            shipment_id=shipment.id,
            carrier_id=carrier_id,
            assigned_by=current_admin.get("email"),
            assigned_at=datetime.utcnow(),
        )
        db.add(admin_log)

        db.commit()

        return {
            "message": f"Shipment {shipment.id} successfully assigned to carrier {carrier_id}",
            "assigned_by": current_admin.get("email"),
            "carrier": {"id": carrier_id, "name": carrier.legal_business_name},
            "vehicle": {"id": vehicle.id, "make": vehicle.make, "model": vehicle.model},
            "driver": {"id": driver.id, "first_name": driver.first_name, "last_name": driver.last_name},
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))