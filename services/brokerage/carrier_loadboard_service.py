from datetime import date, datetime, timedelta
from typing import Optional
import pytz
from sqlalchemy import String, cast
from sqlalchemy.orm import Session
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, CarrierFinancialAccounts, Dedicated_Lane_BrokerageLedger, Interim_Invoice, Lane_Interim_Invoice, Lane_Invoice, Load_Invoice
from models.brokerage.loadboard import Dedicated_lanes_LoadBoard, Ftl_Load_Board, Power_Load_Board
from models.carrier import Carrier
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.user import Driver
from models.vehicle import Vehicle
from schemas.brokerage.loadboard import AssignShipmentRequest, Individual_lane_id, LoadBoardEntryCreate
from fastapi import HTTPException, status

from utils.sast_datetime import format_datetime_sast

def calculate_rates(carrier_payable: int, distance: int, minimum_weight_bracket: int):
    """
    Calculate rates per km and per ton using integers where possible.
    Avoid PG numeric errors by rounding values to the nearest cent.
    Convert weight from kg to tons for proper rate per ton calculation.
    """
    # Ensure valid inputs
    if distance <= 0:
        raise ValueError("Distance must be greater than 0")
    if minimum_weight_bracket <= 0:
        raise ValueError("Minimum weight bracket must be greater than 0")

    # Convert minimum weight bracket from kg to tons
    weight_in_tons = minimum_weight_bracket / 1000

    # Calculate Rate Per Km (posting_price / distance)
    rate_per_km = carrier_payable / distance

    # Calculate Rate Per Ton (posting_price / weight_in_tons)
    rate_per_ton = carrier_payable / weight_in_tons

    # Return rates as integers for storage
    return round(rate_per_km), round(rate_per_ton)


def determine_payout_method(payment_type: str):
    """
    Determine payout method based on payment type.
    """
    if payment_type in ["Credit_Card", "Instant_EFT"]:
        return "48 Hrs EFT"
    elif payment_type == "30_DAY_STANDARD":
        return "30 Days POD"
    elif payment_type == "NET 7":
        return "7 Days after POD"
    elif payment_type == "NET 10":
        return "10 Days after POD"
    elif payment_type == "NET 15":
        return "15 Days after POD"
    elif payment_type == "EOM":
        return "End of the month"
    else:
        raise HTTPException(status_code=400, detail="Invalid payment method")


def create_loadboard_entry(db: Session, loadboard_data: LoadBoardEntryCreate):
    """
    Create a loadboard entry, ensuring correct rates and payout method.
    """
    # Fetch the shipment to validate existence
    shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == loadboard_data.shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Calculate rates
    rate_per_km, rate_per_ton = calculate_rates(
        shipment_rate=loadboard_data.shipment_rate,
        distance=loadboard_data.distance,
        minimum_weight_bracket=loadboard_data.minimum_weight_bracket,
    )

    # Determine payout method
    payout_method = determine_payout_method(shipment.payment_terms)

    # Create LoadBoard Entry
    loadboard_entry = Ftl_Load_Board(
        shipment_id=loadboard_data.shipment_id,
        minimum_weight_bracket=loadboard_data.minimum_weight_bracket,
        shipment_rate=loadboard_data.shipment_rate,
        distance=loadboard_data.distance,
        rate_per_km=rate_per_km,  # Rate per km stored as integer
        rate_per_ton=rate_per_ton,  # Rate per ton stored as integer
        payout_method=payout_method,
    )
    db.add(loadboard_entry)
    db.commit()
    db.refresh(loadboard_entry)

    # Return the created entry
    return loadboard_entry

def assign_spot_ftl_shipment_to_carrier(
    db: Session,
    shipment_data: AssignShipmentRequest,
    current_user: dict,
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    carrier_id = current_user.get("company_id")
    if not carrier_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        # Step 1: LoadBoardEntry
        loadboard_entry = db.query(Ftl_Load_Board).filter(Ftl_Load_Board.shipment_id == shipment_data.shipment_id
        ).first()
        if not loadboard_entry:
            raise HTTPException(status_code=404, detail="Loadboard entry not found")
        if loadboard_entry.status != "Available":
            raise HTTPException(status_code=400, detail="Shipment is no longer available for assignment")

        # Step 2: Shipment record
        shipment = db.query(FTL_SHIPMENT).filter(
            FTL_SHIPMENT.id == shipment_data.shipment_id
        ).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        # Step 3: Brokerage Ledger
        brokerage_ledger = db.query(BrokerageLedger).filter(
                BrokerageLedger.shipment_id == shipment_data.shipment_id,
            BrokerageLedger.shipment_type == shipment.type
        ).first()
        if not brokerage_ledger:
            raise HTTPException(status_code=404, detail="Shipment not found in Brokerage Ledger for specified lane type")

        # Step 4: Carrier
        carrier = db.query(Carrier).filter(Carrier.id == carrier_id).first()
        if not carrier:
            raise HTTPException(status_code=400, detail="Carrier not found.")
        if not carrier.is_verified:
            raise HTTPException(status_code=400, detail="Carrier account not verified, please await verification in order to be able to accept shipments")
        if carrier.status != "Active":
            raise HTTPException(status_code=400, detail="Carrier account not active, please await account activation in order to be able to accept shipments")

        # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
        financial_account = db.query(CarrierFinancialAccounts).filter(
            CarrierFinancialAccounts.id == carrier_id
        ).first()
        if not financial_account:
            raise HTTPException(status_code=404, detail="Financial account not found.")
        if not financial_account.is_verified:
            raise HTTPException(status_code=403, detail="Financial account is not verified, Please await verification to accept shipments.")
        if financial_account.status != "Active":
            raise HTTPException(status_code=403, detail="Financial account is not active, Please await activation to accept shipments.")

        # Step 5: Vehicle
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == shipment_data.vehicle_id,
            Vehicle.owner_id == carrier_id
        ).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found.")
        if not vehicle.is_verified:
            raise HTTPException(status_code=404, detail="Vehicle account not verified, please await vehicle verification in order to accept shipments or select a different vehicle")
        if vehicle.status != "Active":
            raise HTTPException(status_code=404, detail="Vehicle account not active, please await vehicle activation in order to accept shipments or select a different vehicle")

        try:
            assert vehicle.type == shipment.required_truck_type, "Truck type mismatch"
            assert vehicle.equipment_type == shipment.equipment_type, "Equipment type mismatch"
            assert vehicle.trailer_type == shipment.trailer_type, "Trailer type mismatch"
            assert vehicle.trailer_length == shipment.trailer_length, "Trailer length mismatch"
            assert vehicle.payload_capacity >= shipment.minimum_weight_bracket, "Payload capacity too low"
        except AssertionError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Step 6: Driver
        driver = db.query(Driver).filter(
            Driver.id == vehicle.primary_driver_id,
            Driver.current_vehicle_id == shipment_data.vehicle_id
        ).first()
        if not driver:
            raise HTTPException(status_code=400, detail="Driver not found.")
        if not driver.is_verified:
            raise HTTPException(status_code=400, detail="Driver not verified, please await driver verification or assign a different driver to vehicle")
        if driver.status != "Active":
            raise HTTPException(status_code=400, detail="Driver account or not active, please await driver activation or assign a different driver to vehicle")

        # Step 7: Update shipment
        shipment.shipment_status = "Assigned"
        shipment.trip_status = "Scheduled"
        shipment.carrier_id = carrier_id
        shipment.carrier_name = f"SADC FREIGHTLINK Contractor {carrier.id}"
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

        financial_account.holding_balance= (financial_account.holding_balance + brokerage_ledger.carrier_payable)

        try:
            shipment_invoice = Load_Invoice(
                shipment_id = shipment.id,
                shipment_type = shipment.type,
                invoice_type = "Service Invoice",
                billing_date = shipment.pickup_date,
                due_date = shipment.invoice_due_date,
                description = f"{shipment.type} Shipment {shipment.id}",
                status = "Pending",

                carrier_company_id = carrier_id,
                carrier_financial_account_id = carrier_id,
                payment_terms = shipment.payment_terms,
                carrier_bank = financial_account.bank_name,
                carrier_bank_account = financial_account.account_number,
                payment_reference = f"{shipment.type} Shipment {shipment.id}",
                carrier_company_name = financial_account.legal_business_name,
                contact_person_name = f"{financial_account.directors_first_name} {financial_account.directors_last_name}",
                carrier_email = carrier.business_email,
                carrier_address = carrier.business_address,

                origin_address = shipment.complete_origin_address,
                destination_address = shipment.complete_destination_address,
                pickup_date = shipment.pickup_date,
                distance = shipment.distance,
                transit_time = shipment.estimated_transit_time,

                base_amount = brokerage_ledger.carrier_payable,
                due_amount = brokerage_ledger.carrier_payable,
            )
            db.add(shipment_invoice)
            db.flush()

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Shipment invoice generation failed: {e}")

        # Step 9: Log assignment
        assigned_shipment = Assigned_Spot_Ftl_Shipments(
            shipment_id=shipment.id,
            invoice_id=shipment_invoice.id,
            invoice_due_date = shipment.invoice_due_date,
            invoice_status = shipment_invoice.status,
            trip_type=shipment.trip_type,
            load_type=shipment.load_type,
            carrier_id=carrier_id,
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
            hazardous_materials=loadboard_entry.hazardous_metarials,
            packaging_quantity=shipment.packaging_quantity,
            packaging_type=shipment.packaging_type,
            pickup_number=shipment.pickup_number,
            pickup_notes=shipment.pickup_notes,
            delivery_number=shipment.delivery_number,
            delivery_notes=shipment.delivery_notes,
            pickup_facility_id=shipment.pickup_facility_id,
            delivery_facility_id=shipment.delivery_facility_id,
            estimated_transit_time=shipment.estimated_transit_time
        )
        brokerage_ledger.load_invoice_id = shipment_invoice.id
        brokerage_ledger.load_invoice_due_date = shipment_invoice.due_date
        brokerage_ledger.load_invoice_status = shipment_invoice.status
        brokerage_ledger.shipment_status = "Assigned"
        db.add(assigned_shipment)
        db.commit()

        return {
            "message": f"Shipment {shipment.id} successfully assigned to carrier {carrier_id}",
            "carrier": {
                "id": carrier_id,
                "name": carrier.legal_business_name
            },
            "vehicle": {
                "id": vehicle.id,
                "make": vehicle.make,
                "model": vehicle.model,
                "color": vehicle.color,
                "license_plate": vehicle.license_plate
            },
            "driver": {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

def assign_spot_power_shipment_to_carrier(
    db: Session,
    shipment_data: AssignShipmentRequest,
    current_user: dict,
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    carrier_id = current_user.get("company_id")
    if not carrier_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        # Step 1: LoadBoardEntry
        loadboard_entry = db.query(Power_Load_Board).filter(Power_Load_Board.shipment_id == shipment_data.shipment_id
        ).first()
        if not loadboard_entry:
            raise HTTPException(status_code=404, detail="Loadboard entry not found")
        if loadboard_entry.status != "Available":
            raise HTTPException(status_code=400, detail="Shipment is no longer available for assignment")

        # Step 2: Shipment record
        shipment = db.query(POWER_SHIPMENT).filter(
            POWER_SHIPMENT.id == shipment_data.shipment_id
        ).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        # Step 3: Brokerage Ledger
        brokerage_ledger = db.query(BrokerageLedger).filter(
                BrokerageLedger.shipment_id == shipment_data.shipment_id,
            BrokerageLedger.shipment_type == shipment.type
        ).first()
        if not brokerage_ledger:
            raise HTTPException(status_code=404, detail="Shipment not found in Brokerage Ledger for specified lane type")

        # Step 4: Carrier
        carrier = db.query(Carrier).filter(Carrier.id == carrier_id).first()
        if not carrier:
            raise HTTPException(status_code=400, detail="Carrier not found.")
        if not carrier.is_verified:
            raise HTTPException(status_code=400, detail="Carrier account not verified, please await verification in order to be able to accept shipments")
        if carrier.status != "Active":
            raise HTTPException(status_code=400, detail="Carrier account not active, please await account activation in order to be able to accept shipments")

        try:
            assert carrier.git_cover_amount >= shipment.minimum_git_cover_amount, "Carrier GIT Cover Amount does not meet shipment GIT cover amount requirement"
            assert carrier.liability_insurance_cover_amount >= shipment.minimum_liability_cover_amount, "Carrier Liability Cover Amount does not meet shipment Liability cover amount requirement"
        except AssertionError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
        financial_account = db.query(CarrierFinancialAccounts).filter(
            CarrierFinancialAccounts.id == carrier_id
        ).first()
        if not financial_account:
            raise HTTPException(status_code=404, detail="Financial account not found.")
        if not financial_account.is_verified:
            raise HTTPException(status_code=403, detail="Financial account is not verified, Please await verification to accept shipments.")
        if financial_account.status != "Active":
            raise HTTPException(status_code=403, detail="Financial account is not active, Please await activation to accept shipments.")

        # Step 5: Vehicle
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == shipment_data.vehicle_id,
            Vehicle.owner_id == carrier_id
        ).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if not vehicle.is_verified:
            raise HTTPException(status_code=404, detail="Vehicle verified, please await or request vehicle verification to assign shipments to vehicle {shipment_data.vehicle_id}, or select a different vehicle.")
        if vehicle.status != "Active":
            raise HTTPException(status_code=404, detail="Vehicle account not active, please await vehicle activation or select a different vehicle to assign shipment {shipment_data.shipment_id} to.")

        try:
            assert vehicle.type == shipment.required_truck_type, "Truck type mismatch"
            assert vehicle.axle_configuration == shipment.axle_configuration, "Axle Configuration type mismatch"
            assert vehicle.payload_capacity >= shipment.minimum_weight_bracket, "Payload capacity too low"
        except AssertionError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Step 6: Driver
        driver = db.query(Driver).filter(
            Driver.id == vehicle.primary_driver_id,
            Driver.current_vehicle_id == shipment_data.vehicle_id
        ).first()
        if not driver:
            raise HTTPException(status_code=400, detail="Driver not found.")
        if not driver.is_verified:
            raise HTTPException(status_code=400, detail="Driver account not verified")
        if driver.status != "Active":
            raise HTTPException(status_code=400, detail="Driver account not active, please await driver activation or select a different driver to assign vehicle {shipment_data.vehicle_id} to.")

        # Step 7: Update shipment
        shipment.shipment_status = "Assigned"
        shipment.trip_status = "Scheduled"
        shipment.carrier_id = carrier_id
        shipment.carrier_name = f"SADC FREIGHTLINK Contractor {carrier.id}"
        shipment.carrier_git_cover_amount = carrier.git_cover_amount
        shipment.carrier_liability_cover_amount = carrier.liability_insurance_cover_amount
        shipment.vehicle_id = vehicle.id
        shipment.vehicle_type = vehicle.type
        shipment.vehicle_make = vehicle.make
        shipment.vehicle_model = vehicle.model
        shipment.vehicle_color = vehicle.color
        shipment.vehicle_license_plate = vehicle.license_plate
        shipment.vehicle_vin = vehicle.vin
        shipment.axle_configuration = vehicle.axle_configuration
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

        financial_account.holding_balance= (financial_account.holding_balance + brokerage_ledger.carrier_payable)

        try:
            shipment_invoice = Load_Invoice(
                shipment_id = shipment.id,
                shipment_type = shipment.type,
                invoice_type = "Service Invoice",
                billing_date = shipment.pickup_date,
                due_date = shipment.invoice_due_date,
                description = f"{shipment.type} Shipment {shipment.id}",
                status = "Pending",

                carrier_company_id = carrier_id,
                carrier_financial_account_id = carrier_id,
                payment_terms = shipment.payment_terms,
                carrier_bank = financial_account.bank_name,
                carrier_bank_account = financial_account.account_number,
                payment_reference = f"{shipment.type} Shipment {shipment.id}",
                carrier_company_name = financial_account.legal_business_name,
                contact_person_name = f"{financial_account.directors_first_name} {financial_account.directors_last_name}",
                carrier_email = carrier.business_email,
                carrier_address = carrier.business_address,

                origin_address = shipment.complete_origin_address,
                destination_address = shipment.complete_destination_address,
                pickup_date = shipment.pickup_date,
                distance = shipment.distance,
                transit_time = shipment.estimated_transit_time,

                base_amount = brokerage_ledger.carrier_payable,
                due_amount = brokerage_ledger.carrier_payable,
            )
            db.add(shipment_invoice)
            db.flush()

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Shipment invoice generation failed: {e}")

        # Step 9: Log assignment
        assigned_shipment = Assigned_Power_Shipments(
            shipment_id=shipment.id,
            invoice_id=shipment_invoice.id,
            invoice_due_date = shipment.invoice_due_date,
            invoice_status = shipment_invoice.status,
            trip_type=shipment.trip_type,
            load_type=shipment.load_type,
            carrier_id=carrier_id,
            carrier_name=carrier.legal_business_name,
            vehicle_id=vehicle.id,
            trailer_id=shipment.trailer_id,
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
            required_truck_type=shipment.required_truck_type,
            axle_configuration=shipment.axle_configuration,
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
            hazardous_materials=loadboard_entry.hazardous_materials,
            packaging_quantity=shipment.packaging_quantity,
            packaging_type=shipment.packaging_type,
            pickup_number=shipment.pickup_number,
            pickup_notes=shipment.pickup_notes,
            delivery_number=shipment.delivery_number,
            delivery_notes=shipment.delivery_notes,
            pickup_facility_id=shipment.pickup_facility_id,
            delivery_facility_id=shipment.delivery_facility_id,
            estimated_transit_time=shipment.estimated_transit_time
        )
        brokerage_ledger.load_invoice_id = shipment_invoice.id
        brokerage_ledger.load_invoice_due_date = shipment_invoice.due_date
        brokerage_ledger.load_invoice_status = shipment_invoice.status
        brokerage_ledger.shipment_status = "Assigned"
        db.add(assigned_shipment)
        db.commit()

        return {
            "message": f"Shipment {shipment.id} successfully assigned to carrier {carrier_id}",
            "carrier": {
                "id": carrier_id,
                "name": carrier.legal_business_name
            },
            "vehicle": {
                "id": vehicle.id,
                "make": vehicle.make,
                "model": vehicle.model,
                "color": vehicle.color,
                "license_plate": vehicle.license_plate
            },
            "driver": {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def ensure_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date format: {value}")
    return None  # fallback if it's None or unexpected type


#################
def assign_spot_ftl_lane_to_carrier(db: Session, shipment_data: Individual_lane_id, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    carrier_id = current_user.get("company_id")

    if not carrier_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    loadboard_entry = db.query(Dedicated_lanes_LoadBoard).filter(
        Dedicated_lanes_LoadBoard.shipment_id == shipment_data.shipment_id
    ).first()
    if not loadboard_entry or loadboard_entry.status != "Available":
        raise HTTPException(status_code=400, detail="Loadboard entry is not available for assignment")

    lane = db.query(FTL_Lane).filter(FTL_Lane.id == shipment_data.shipment_id).first()
    if not lane:
        raise HTTPException(status_code=404, detail="Contract Lane not found")

    brokerage_ledger = db.query(Dedicated_Lane_BrokerageLedger).filter(
        Dedicated_Lane_BrokerageLedger.contract_id == shipment_data.shipment_id,
        Dedicated_Lane_BrokerageLedger.lane_type == lane.type
    ).first()
    if not brokerage_ledger:
        raise HTTPException(status_code=404, detail="Shipment not found in Brokerage Ledger")

    # Step 4: Carrier
    carrier = db.query(Carrier).filter(Carrier.id == carrier_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found.")
    if not carrier.is_verified:
        raise HTTPException(status_code=400, detail="Carrier account not verified, please await verification in order to be able to accept shipments")
    if carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier account not active, please await account activation in order to be able to accept shipments")
    
    try:
        assert carrier.git_cover_amount >= lane.minimum_git_cover_amount, "Carrier GIT Cover Amount does not meet shipment GIT cover amount requirement"
        assert carrier.liability_insurance_cover_amount >= lane.minimum_liability_cover_amount, "Carrier Liability Cover Amount does not meet shipment Liability cover amount requirement"
        assert carrier.number_of_vehicles >= lane.shipments_per_interval, "Carrier fleet size does not satisfy the contract lane's required number of vehicle per interval."
    except AssertionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
    financial_account = db.query(CarrierFinancialAccounts).filter(
        CarrierFinancialAccounts.id == carrier_id
    ).first()
    if not financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found.")
    if not financial_account.is_verified:
        raise HTTPException(status_code=403, detail="Financial account is not verified, Please await verification to accept shipments.")
    if financial_account.status != "Active":
        raise HTTPException(status_code=403, detail="Financial account is not active, Please await activation to accept shipments.")

    # Assign lane + ledger
    lane.status = "Assigned"
    lane.progress = 0
    lane.carrier_id = carrier_id
    lane.carrier_fleet_size = carrier.number_of_vehicles
    lane.carrier_git_cover_amount = carrier.git_cover_amount
    lane.carrier_liability_cover_amount = carrier.liability_insurance_cover_amount
    loadboard_entry.status = "Assigned"

    brokerage_ledger.carrier_id = carrier.id
    brokerage_ledger.carrier_company_name = carrier.legal_business_name
    brokerage_ledger.carrier_company_registration_number = carrier.business_registration_number
    brokerage_ledger.carrier_country_of_incorporation = carrier.country_of_incorporation
    brokerage_ledger.carrier_fleet_size = carrier.number_of_vehicles

    financial_account.holding_balance += brokerage_ledger.contract_carrier_payable

    lane_invoice = Lane_Invoice(
        contract_id=lane.id,
        lane_type=lane.type,
        invoice_type="Lane Invoice",
        billing_date=ensure_date(lane.start_date),
        due_date=ensure_date(lane.end_date),
        description=f"{lane.type} Lane {lane.id}",
        status="Pending",
        company_id=carrier_id,
        carrier_company_name=carrier.legal_business_name,
        contact_person_name=f"{financial_account.directors_first_name} {financial_account.directors_last_name}",
        business_email=carrier.business_email,
        business_address=carrier.business_address,
        carrier_financial_account_id=carrier_id,
        payment_terms=lane.payment_terms,
        carrier_bank=financial_account.bank_name,
        carrier_bank_account=financial_account.account_number,
        payment_reference=f"{lane.type} Lane {lane.id}",
        base_amount=brokerage_ledger.contract_carrier_payable,
        due_amount=brokerage_ledger.contract_carrier_payable
    )
    db.add(lane_invoice)
    db.flush()

    # Step 1: Generate Lane Interim Invoices
    booking_interim_invoices = db.query(Interim_Invoice).filter(
        Interim_Invoice.contract_id == shipment_data.shipment_id,
        Interim_Invoice.contract_type == lane.type
    ).all()

    lane_interim_invoices = []
    for booking_invoice in booking_interim_invoices:
        original_due = ensure_date(booking_invoice.due_date)
        new_due = ensure_date(booking_invoice.billing_date)

        interim = Lane_Interim_Invoice(
            contract_id=lane.id,
            contract_type=lane.type,
            is_subinvoice=True,
            description=f"Lane Interim Invoice for Contract Invoice {lane.id}",
            status="Pending",
            billing_date=ensure_date(booking_invoice.billing_date),
            original_due_date=original_due,
            due_date=new_due,
            carrier_company_id=carrier_id,
            carrier_name=carrier.legal_business_name,
            carrier_email=carrier.business_email,
            carrier_address=carrier.business_address,
            carrier_financial_account_id=financial_account.id,
            invoice_payment_terms=lane.payment_terms,
            carrier_bank=financial_account.bank_name,
            carrier_bank_account=financial_account.account_number,
            payment_reference=f"Lane Interim Invoice for Contract Invoice {lane.id}",
            base_amount=booking_invoice.base_amount,
            due_amount=booking_invoice.due_amount,
        )
        db.add(interim)
        lane_interim_invoices.append(interim)

    db.flush()

    assigned_lane = Assigned_Ftl_Lanes(
        lane_id=lane.id,
        type=lane.type,
        trip_type=lane.trip_type,
        load_type=lane.load_type,
        carrier_id=carrier_id,
        carrier_name=carrier.legal_business_name,
        contract_rate=brokerage_ledger.contract_carrier_payable,
        rate_per_shipment=brokerage_ledger.carrier_payable_per_shipment,
        payment_terms=brokerage_ledger.payment_terms,
        payment_dates=brokerage_ledger.payment_dates,
        complete_origin_address=lane.complete_origin_address,
        complete_destination_address=lane.complete_destination_address,
        distance=lane.distance,
        rate_per_km=loadboard_entry.rate_per_km,
        rate_per_ton=loadboard_entry.rate_per_ton,
        minimum_git_cover_amount=lane.minimum_git_cover_amount,
        minimum_liability_cover_amount=lane.minimum_liability_cover_amount,
        status="Assigned",
        recurrence_frequency=lane.recurrence_frequency,
        recurrence_days=lane.recurrence_days,
        skip_weekends=lane.skip_weekends,
        shipments_per_interval=lane.shipments_per_interval,
        total_shipments=lane.total_shipments,
        start_date=lane.start_date,
        end_date=lane.end_date,
        shipment_dates=lane.shipment_dates,
        required_truck_type=lane.required_truck_type,
        equipment_type=lane.equipment_type,
        trailer_type=lane.trailer_type,
        trailer_length=lane.trailer_length,
        minimum_weight_bracket=lane.minimum_weight_bracket,
        pickup_appointment=f"{loadboard_entry.pickup_start_time} - {loadboard_entry.pickup_end_time}",
        origin_address=lane.origin_address,
        origin_city_province=lane.origin_city_province,
        origin_country=lane.origin_country,
        origin_region=lane.origin_region,
        delivery_appointment=f"{loadboard_entry.delivery_start_time} - {loadboard_entry.delivery_end_time}",
        destination_address=lane.destination_address,
        destination_city_province=lane.destination_city_province,
        destination_country=lane.destination_country,
        destinationn_region=lane.destination_country,
        route_preview_embed=loadboard_entry.route_preview_embed,
        priority_level=lane.priority_level,
        customer_reference_number=lane.customer_reference_number,
        average_shipment_weight=lane.average_shipment_weight,
        commodity=lane.commodity,
        temperature_control=lane.temperature_control,
        hazardous_materials=lane.hazardous_materials,
        packaging_quantity=lane.packaging_quantity,
        packaging_type=lane.packaging_type,
        pickup_number=lane.pickup_number,
        pickup_notes=lane.pickup_notes,
        delivery_number=lane.delivery_number,
        delivery_notes=lane.delivery_notes,
        estimated_transit_time=lane.estimated_transit_time,
        pickup_facility_id=lane.pickup_facility_id,
        delivery_facility_id=lane.delivery_facility_id,
    )

    brokerage_ledger.carrier_lane_invoice_id = lane_invoice.id
    brokerage_ledger.carrier_lane_invoice_due_date = lane_invoice.due_date
    brokerage_ledger.carrier_lane_invoice_status = lane_invoice.status
    db.add(assigned_lane)
    db.flush()

    # Step 2: Assign sub-shipments + Generate Load Invoices
    sub_shipments = db.query(FTL_SHIPMENT).filter(
        FTL_SHIPMENT.dedicated_lane_id == shipment_data.shipment_id,
        FTL_SHIPMENT.is_subshipment == True
    ).all()

    if not sub_shipments:
        raise HTTPException(status_code=404, detail="No sub-shipments found.")

    for sub_shipment in sub_shipments:
        amount = brokerage_ledger.carrier_payable_per_shipment
        due = ensure_date(sub_shipment.invoice_due_date)
        pickup_date = ensure_date(sub_shipment.pickup_date)

        parent_invoice = next((
            i for i in lane_interim_invoices
            if pickup_date <= ensure_date(i.original_due_date)
        ), None)

        if not parent_invoice:
            raise HTTPException(status_code=400, detail=f"No Lane Interim Invoice found for Sub-Shipment {sub_shipment.id}")

        load_invoice = Load_Invoice(
            contract_id=lane.id,
            contract_type=lane.type,
            shipment_id=sub_shipment.id,
            is_subinvoice=True,
            parent_invoice_id=parent_invoice.id,
            description=f"Load Invoice for Sub-Shipment {sub_shipment.id}",
            billing_date=sub_shipment.pickup_date,
            due_date=due,
            carrier_company_id=carrier_id,
            carrier_financial_account_id=financial_account.id,
            carrier_company_name=carrier.legal_business_name,
            payment_terms=lane.payment_terms,
            carrier_bank=financial_account.bank_name,
            carrier_bank_account=financial_account.account_number,
            payment_reference=f"Load {sub_shipment.id} of Lane {lane.id}",
            contact_person_name=f"{financial_account.directors_first_name} {financial_account.directors_last_name}",
            carrier_email=carrier.business_email,
            carrier_address=carrier.business_address,
            status="Pending",
            base_amount=amount,
            due_amount=amount,
        )
        db.add(load_invoice)

        assigned = Assigned_Spot_Ftl_Shipments(
            is_subshipment=True,
            lane_id=assigned_lane.id,
            shipment_id=sub_shipment.id,
            type="FTL",
            trip_type=sub_shipment.trip_type,
            load_type=sub_shipment.load_type,
            carrier_id=carrier_id,
            carrier_name=carrier.legal_business_name,
            vehicle_id=None,
            driver_id=None,
            accepted_for=None,
            accepted_at=None,
            minimum_weight_bracket=sub_shipment.minimum_weight_bracket,
            minimum_git_cover_amount=sub_shipment.minimum_git_cover_amount,
            minimum_liability_cover_amount=sub_shipment.minimum_liability_cover_amount,
            shipment_rate=amount,
            distance=sub_shipment.distance,
            rate_per_km=loadboard_entry.rate_per_km,
            rate_per_ton=loadboard_entry.rate_per_ton,
            payment_terms=lane.payment_terms,
            status="Assigned",
            trip_status="Scheduled",
            required_truck_type=sub_shipment.required_truck_type,
            equipment_type=sub_shipment.equipment_type,
            trailer_type=sub_shipment.trailer_type,
            trailer_length=sub_shipment.trailer_length,
            origin_address=sub_shipment.origin_address,
            origin_address_completed=sub_shipment.complete_origin_address,
            origin_city_province=sub_shipment.origin_city_province,
            origin_country=sub_shipment.origin_country,
            origin_region=sub_shipment.origin_region,
            destination_address=sub_shipment.destination_address,
            destination_address_completed=sub_shipment.complete_destination_address,
            destination_city_province=sub_shipment.destination_city_province,
            destination_country=sub_shipment.destination_country,
            destination_region=sub_shipment.destination_region,
            route_preview_embed=sub_shipment.route_preview_embed,
            pickup_date=sub_shipment.pickup_date,
            priority_level=sub_shipment.priority_level,
            customer_reference_number=sub_shipment.customer_reference_number,
            shipment_weight=sub_shipment.shipment_weight,
            commodity=sub_shipment.commodity,
            temperature_control=sub_shipment.temperature_control,
            hazardous_materials=sub_shipment.hazardous_materials,
            packaging_quantity=sub_shipment.packaging_quantity,
            packaging_type=sub_shipment.packaging_type,
            pickup_number=sub_shipment.pickup_number,
            pickup_notes=sub_shipment.pickup_notes,
            delivery_number=sub_shipment.delivery_number,
            delivery_notes=sub_shipment.delivery_notes,
            estimated_transit_time=sub_shipment.estimated_transit_time
        )
        db.add(assigned)

    db.commit()

def assign_ftl_shipment_from_loadboard_to_carrier(
    db: Session,
    shipment_id: int,
    carrier_id: int,
    vehicle_id: int,
):
    try:
        # Step 1: LoadBoardEntry
        loadboard_entry = db.query(Ftl_Load_Board).filter(Ftl_Load_Board.shipment_id == shipment_id
        ).first()
        if not loadboard_entry:
            raise HTTPException(status_code=404, detail="Loadboard entry not found")
        if loadboard_entry.status != "Available":
            raise HTTPException(status_code=400, detail="Shipment is not available for assignment")

        # Step 2: Shipment record
        shipment = db.query(FTL_SHIPMENT).filter(
            FTL_SHIPMENT.id == shipment_id
        ).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        # Step 3: Brokerage Ledger
        brokerage_ledger = db.query(BrokerageLedger).filter(
            cast(BrokerageLedger.shipment_id, String) == str(shipment_id),
            BrokerageLedger.shipment_type == shipment.type
        ).first()
        if not brokerage_ledger:
            raise HTTPException(status_code=404, detail="Shipment not found in Brokerage Ledger for specified lane type")

        # Step 4: Carrier
        carrier = db.query(Carrier).filter(Carrier.id == carrier_id).first()
        if not carrier or not carrier.is_verified or carrier.status != "Active":
            raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

        financial_account = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.id == carrier_id).first()
        if not financial_account or not financial_account.is_verified or financial_account.status != "Active":
            raise HTTPException(status_code=400, detail="Carrier Financial Account not found, not verified, or not active")

        # Step 5: Vehicle
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == vehicle_id,
            cast(Vehicle.owner_id, String) == str(carrier_id)
        ).first()
        if not vehicle or not vehicle.is_verified or vehicle.status != "Active":
            raise HTTPException(status_code=404, detail="Vehicle not found, not verified, or not active")

        if not all([
            vehicle.type == shipment.required_truck_type,
            vehicle.equipment_type == shipment.equipment_type,
            vehicle.trailer_type == shipment.trailer_type,
            vehicle.trailer_length == shipment.trailer_length,
            vehicle.payload_capacity >= shipment.minimum_weight_bracket
        ]):
            raise HTTPException(status_code=400, detail="Vehicle does not meet shipment requirements")

        # Step 6: Driver
        driver = db.query(Driver).filter(
            Driver.id == vehicle.primary_driver_id,
            cast(Driver.current_vehicle_id, String) == str(vehicle_id)
        ).first()
        if not driver or not driver.is_verified or driver.status != "Active":
            raise HTTPException(status_code=400, detail="Driver not found, not verified, or not active")

        # Step 7: Update shipment
        shipment.shipment_status = "Assigned"
        shipment.carrier_id = carrier_id
        shipment.carrier_name = f"SADC FREIGHTLINK Contractor {carrier.id}"
        shipment.carrier_git_cover_amount = carrier.git_cover_amount
        shipment.carrier_liability_cover_amount = carrier.liability_insurance_cover_amount
        shipment.vehicle_id = vehicle_id
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

        # Step 9: Log assignment
        assigned_shipment = Assigned_Spot_Ftl_Shipments(
            shipment_id=shipment_id,
            carrier_id=carrier_id,
            carrier_name=carrier.legal_business_name,
            vehicle_id=vehicle_id,
            vehicle_make=vehicle.make,
            vehicle_model=vehicle.model,
            vehicle_color=vehicle.color,
            vehicle_license_plate=vehicle.license_plate,
            driver_id=driver.id,
            driver_first_name=driver.first_name,
            driver_last_name=driver.last_name,
            accepted_for=f"{driver.first_name} {driver.last_name}",
            accepted_at=format_datetime_sast(datetime.utcnow().replace(tzinfo=pytz.utc)),
            minimum_weight_bracket=shipment.minimum_weight_bracket,
            shipment_rate=brokerage_ledger.carrier_payable,
            distance=shipment.distance,
            rate_per_km=loadboard_entry.rate_per_km,
            rate_per_ton=loadboard_entry.rate_per_ton,
            payment_terms=loadboard_entry.payment_terms,
            status="Assigned",
            required_truck_type=shipment.required_truck_type,
            equipment_type=shipment.equipment_type,
            trailer_type=shipment.trailer_type,
            trailer_length=shipment.trailer_length,
            origin_address=shipment.origin_address,
            origin_address_completed=shipment.complete_origin_address,
            origin_address_city_provice=shipment.origin_city_province,
            pickup_appointment=loadboard_entry.pickup_start_time,
            destination_address=shipment.destination_address,
            destination_address_completed=shipment.complete_destination_address,
            destination_address_city_provice=shipment.destination_city_province,
            delivery_appointment=loadboard_entry.delivery_start_time,
            pickup_date=shipment.pickup_date,
            priority_level=shipment.priority_level,
            customer_reference_number=shipment.customer_reference_number,
            shipment_weight=shipment.shipment_weight,
            commodity=shipment.commodity,
            packaging_quantity=shipment.packaging_quantity,
            packaging_type=shipment.packaging_type,
            pickup_number=shipment.pickup_number,
            pickup_notes=shipment.pickup_notes,
            delivery_number=shipment.delivery_number,
            delivery_notes=shipment.delivery_notes,
            estimated_transit_time=shipment.estimated_transit_time,
            pickup_facility_id=shipment.pickup_facility_id,
            delivery_facility_id=shipment.delivery_facility_id,
        )

        db.add(assigned_shipment)
        db.commit()

        try:
            shipment_invoice = Load_Invoice(
                shipment_id = shipment.id,
                shipment_type = shipment.type,
                invoice_type = "Service Invoice",
                billing_date = shipment.pickup_date,
                due_date = shipment.invoice_due_date,
                description = f"{shipment.type} Shipment {shipment.id}",
                status = "Pending",

                carrier_company_id = carrier_id,
                carrier_financial_account_id = carrier_id,
                payment_terms = shipment.payment_terms,
                carrier_bank = financial_account.bank_name,
                carrier_bank_account = financial_account.account_number,
                payment_reference = f"{shipment.type} Shipment {shipment.id}",
                business_name = financial_account.legal_business_name,
                contact_person_name = f"{financial_account.directors_first_name} {financial_account.directors_last_name}",
                business_email = carrier.business_email,
                billing_address = carrier.business_address,

                origin_address = shipment.complete_origin_address,
                destination_address = shipment.complete_destination_address,
                pickup_date = shipment.pickup_date,
                distance = shipment.distance,
                transit_time = shipment.estimated_transit_time,

                base_amount = brokerage_ledger.carrier_payable,
                due_amount = brokerage_ledger.carrier_payable,
            )
            assigned_shipment.invoice_id = shipment_invoice.id
            financial_account.total_earned  + brokerage_ledger.carrier_payable
            db.add(shipment_invoice)

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Shipment invoice generation failed: {e}")

        # Step 9: Update loadboard status
        loadboard_entry.status = "Assigned"

        brokerage_ledger.carrier_id = carrier.id
        brokerage_ledger.carrier_company_type = carrier.type
        brokerage_ledger.carrier_company_name = carrier.legal_business_name
        brokerage_ledger.vehicle_id = vehicle.id
        brokerage_ledger.vehicle_make = vehicle.make
        brokerage_ledger.vehicle_model = vehicle.model
        brokerage_ledger.vehicle_year = vehicle.year
        brokerage_ledger.vehicle_color = vehicle.color
        brokerage_ledger.vehicle_vin = vehicle.vin
        brokerage_ledger.vehicle_license_plate = vehicle.license_plate
        brokerage_ledger.driver_id = driver.id
        brokerage_ledger.driver_first_name = driver.first_name
        brokerage_ledger.driver_last_name = driver.last_name
        brokerage_ledger.driver_id_number = driver.id_number
        brokerage_ledger.driver_license_number = driver.license_number

        return {
            "message": f"Shipment {shipment_id} successfully assigned to carrier {carrier_id}",
            "carrier": {
                "id": carrier_id,
                "name": carrier.legal_business_name
            },
            "vehicle": {
                "id": vehicle_id,
                "make": vehicle.make,
                "model": vehicle.model,
                "color": vehicle.color,
                "license_plate": vehicle.license_plate
            },
            "driver": {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    

def assign_dedicated_ftl_lane_to_carrier(
    db: Session,
    shipment_id: int,
    lane_type: str,
    carrier_id: int,
):
    """
    Assign a shipment to a carrier, filtering by shipment_id and lane_type.
    """
    try:
        # Step 1: Query the LoadBoardEntry by shipment_id AND lane_type
        loadboard_entry = db.query(Dedicated_lanes_LoadBoard).filter(
            cast(Dedicated_lanes_LoadBoard.shipment_id, String) == str(shipment_id)
        ).first()
        if not loadboard_entry:
            raise HTTPException(status_code=404, detail="Loadboard entry not found for specified lane type")

        # Step 2: Ensure the shipment is still available
        if loadboard_entry.status != "Available":
            raise HTTPException(status_code=400, detail="Shipment is not available for assignment")

        # Step 3: Query the FTL_Lane by shipment_id AND lane_type
        shipment = db.query(FTL_Lane).filter(
            FTL_Lane.id == shipment_id
        ).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found with specified lane type")
        
        # Step 3: Get all sub-shipments
        sub_shipments = db.query(FTL_SHIPMENT).filter(
            FTL_SHIPMENT.dedicated_lane_id == shipment_id
        ).all()
        if not sub_shipments:
            raise HTTPException(status_code=404, detail="No sub-shipments found")

        # Step 4: Query the brokerage ledger by contract_id AND lane_type
        brokerage_ledger = db.query(Dedicated_Lane_BrokerageLedger).filter(
            cast(Dedicated_Lane_BrokerageLedger.contract_id, String) == str(shipment_id),
            Dedicated_Lane_BrokerageLedger.lane_type == lane_type
        ).first()
        if not brokerage_ledger:
            raise HTTPException(status_code=404, detail="Shipment not found in Brokerage Ledger for specified lane type")

        # Step 4: Validate the carrier exists and is active
        carrier = db.query(Carrier).filter(Carrier.id == carrier_id).first()
        if not carrier or carrier.is_verified == "True":
            raise HTTPException(status_code=400, detail="Carrier not found or not verified")
        
        carrier_requirements = db.query(Carrier).filter(Carrier.id == carrier_id).first()
        if not all ([
            carrier_requirements.git_cover_amount >= shipment.minimum_git_cover_amount,
            carrier_requirements.liability_insurance_cover_amount >= shipment.minimum_liability_cover_amount,
        ]):
            raise HTTPException(status_code=400, detail="Carrier does not meet contract GIT/Liability insurance requirements")

        # Step 5: Validate the Fleet
        required_vehicle_count = shipment.shipments_per_interval

        # Query all verified vehicles for the carrier that meet shipment requirements
        matching_vehicles = db.query(Vehicle).filter(
        Vehicle.owner_id == carrier_id,
        Vehicle.is_verified == "True",
        Vehicle.type == shipment.required_truck_type,
        Vehicle.equipment_type == shipment.equipment_type,
        Vehicle.trailer_type == shipment.trailer_type,
        Vehicle.trailer_length >= shipment.trailer_length,
        Vehicle.payload_capacity >= shipment.minimum_weight_bracket
        ).all()

        # Check if enough matching vehicles are available
        if len(matching_vehicles) < required_vehicle_count:
            raise HTTPException(
                status_code=400,
                detail=f"Carrier does not have enough suitable vehicles. Required: {required_vehicle_count}, Available: {len(matching_vehicles)}"
            )

        # Step 6: Validate the Fleet's Drivers
        required_driver_count = shipment.shipments_per_interval

        # Query all verified Drivers for the carrier that meet shipment requirements
        matching_drivers = db.query(Driver).filter(
        Driver.company_id == carrier_id,
        Vehicle.is_verified == "True",
        ).all()

        # Check if enough matching vehicles are available
        if len(matching_drivers) < required_driver_count:
            raise HTTPException(
                status_code=400,
                detail=f"Carrier does not have enough suitable vehicles. Required: {required_driver_count}, Available: {len(matching_drivers)}"
            )

        # Step 7: Insert into Assigned_Spot_Ftl_Shipments
        assigned_shipment = Assigned_Ftl_Lanes(
            lane_id=shipment_id,
            type="FTL",
            trip_type=shipment.trip_type,
            load_type=shipment.load_type,
            carrier_id=carrier_id,
            accepted_at=format_datetime_sast(datetime.utcnow().replace(tzinfo=pytz.utc)),
            minimum_weight_bracket=shipment.minimum_weight_bracket,
            minimum_git_cover_amount=shipment.minimum_git_cover_amount,
            contract_rate=brokerage_ledger.contract_carrier_payable,
            rate_per_shipment=loadboard_entry.rate_per_shipment,
            distance=shipment.distance,
            rate_per_km=loadboard_entry.rate_per_km,
            rate_per_ton=loadboard_entry.rate_per_ton,
            payment_terms=loadboard_entry.payment_terms,
            status="Assigned",
            recurrence_frequency=loadboard_entry.recurrence_frequency,
            recurrence_days=loadboard_entry.recurrence_days,
            shipments_per_interval=loadboard_entry.shipments_per_interval,
            total_shipments=loadboard_entry.total_shipments,
            start_date=shipment.start_date,
            end_date=shipment.end_date,
            shipment_dates=loadboard_entry.shipment_dates,
            required_truck_type=shipment.required_truck_type,
            equipment_type=shipment.equipment_type,
            trailer_type=shipment.trailer_type,
            trailer_length=shipment.trailer_length,
            origin_address=shipment.origin_address,
            origin_address_completed=shipment.complete_origin_address,
            origin_city_province=shipment.origin_city_province,
            origin_country=shipment.origin_country,
            origin_region=shipment.origin_region,
            route_preview_embed=shipment.route_preview_embed,
            estimated_transit_time=shipment.estimated_transit_time,
            pickup_appointment=loadboard_entry.pickup_start_time,
            destination_address=shipment.destination_address,
            destination_address_completed=shipment.complete_destination_address,
            destination_address_city_provice=shipment.destination_city_province,
            destination_country=shipment.origin_country,
            destination_region=shipment.origin_region,
            delivery_appointment=loadboard_entry.delivery_start_time,
            priority_level=shipment.priority_level,
            customer_reference_number=shipment.customer_reference_number,
            average_shipment_weight=shipment.average_shipment_weight,
            commodity=shipment.commodity,
            temperature_control=shipment.temperature_control,
            hazardous_materials=shipment.hazardous_materials,
            packaging_quantity=shipment.packaging_quantity,
            packaging_type=shipment.packaging_type,
            pickup_number=shipment.pickup_number,
            pickup_notes=shipment.pickup_notes,
            delivery_number=shipment.delivery_number,
            delivery_notes=shipment.delivery_notes,
        )
        db.add(assigned_shipment)

        # Step 7: Insert into Assigned_Spot_Ftl_Shipments
        for pickup_date in loadboard_entry.shipment_dates:
            for _ in range(loadboard_entry.shipments_per_interval):
                assign_sub_shipment = Assigned_Spot_Ftl_Shipments(
                    shipment_id=shipment_id,
                    type="FTL",
                    trip_type=shipment.trip_type,
                    load_type=shipment.load_type,
                    carrier_id=carrier_id,
                    carrier_name=carrier.legal_business_name,
                    accepted_at=format_datetime_sast(datetime.utcnow().replace(tzinfo=pytz.utc)),
                    minimum_weight_bracket=shipment.minimum_weight_bracket,
                    minimum_git_cover_amount=shipment.minimum_git_cover_amount,
                    minimum_liability_cover_amount=shipment.minimum_liability_cover_amount,
                    shipment_rate=loadboard_entry.rate_per_shipment,
                    distance=shipment.distance,
                    rate_per_km=loadboard_entry.rate_per_km,
                    rate_per_ton=loadboard_entry.rate_per_ton,
                    payment_terms=loadboard_entry.payment_terms,
                    status="Assigned",
                    pickup_date=pickup_date,
                    required_truck_type=shipment.required_truck_type,
                    equipment_type=shipment.equipment_type,
                    trailer_type=shipment.trailer_type,
                    trailer_length=shipment.trailer_length,
                    origin_address=shipment.origin_address,
                    origin_address_completed=shipment.complete_origin_address,
                    origin_city_province=shipment.origin_city_province,
                    origin_country=shipment.origin_country,
                    origin_region=shipment.origin_region,
                    route_preview_embed=shipment.route_preview_embed,
                    estimated_transit_time=shipment.estimated_transit_time,
                    pickup_appointment=loadboard_entry.pickup_start_time,
                    destination_address=shipment.destination_address,
                    destination_address_completed=shipment.complete_destination_address,
                    destination_address_city_provice=shipment.destination_city_province,
                    destination_country=shipment.origin_country,
                    destination_region=shipment.origin_region,
                    delivery_appointment=loadboard_entry.delivery_start_time,
                    priority_level=shipment.priority_level,
                    customer_reference_number=shipment.customer_reference_number,
                    average_shipment_weight=shipment.average_shipment_weight,
                    commodity=shipment.commodity,
                    temperature_control=shipment.temperature_control,
                    hazardous_materials=shipment.hazardous_materials,
                    packaging_quantity=shipment.packaging_quantity,
                    packaging_type=shipment.packaging_type,
                    pickup_number=shipment.pickup_number,
                    pickup_notes=shipment.pickup_notes,
                    delivery_number=shipment.delivery_number,
                    delivery_notes=shipment.delivery_notes,
                )
                db.add(assign_sub_shipment)

        # Step 8: Update LoadBoardEntry status
        loadboard_entry.status = "Assigned"

        # Step 9: Assign shipment
        shipment.status = "Assigned",
        shipment.carrier_id = carrier_id,

        # Step 10: Assign sub-shipment
        for sub in sub_shipments:
            sub.carrier_id = carrier_id
            sub.carrier_name = carrier.legal_business_name
            sub.shipment_status = "Assigned"

        # Step 10: Update brokerage ledger
        brokerage_ledger.carrier_id = carrier_id,
        brokerage_ledger.carrier_company_name = carrier.legal_business_name,
        brokerage_ledger.carrier_company_registration_number = carrier.business_registration_number,
        brokerage_ledger.carrier_country_of_incorporation = carrier.country_of_incorporation

        # Step 10: Commit changes
        db.commit()

        return {
            "message": f"Dedicated lane {shipment_id} from {shipment.complete_origin_address} to {shipment.complete_destination_address} successfully assigned to carrier {carrier_id}",
            "carrier": {"id": carrier_id, "name": carrier.legal_business_name},
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def assign_power_shipment_to_carrier(
    db: Session,
    shipment_id: int,
    carrier_id: int,
    vehicle_id: int,
):
    """
    Assign a shipment to a carrier, along with vehicle and driver details.
    """
    try:
        # Step 1: Query the LoadBoardEntry by shipment_id
        loadboard_entry = db.query(Power_Load_Board).filter(
            cast(Power_Load_Board.shipment_id, String) == str(shipment_id)
        ).first()
        if not loadboard_entry:
            raise HTTPException(status_code=404, detail="Loadboard entry not found")

        # Step 2: Ensure the shipment is still available
        if loadboard_entry.status != "Posted":
            raise HTTPException(status_code=400, detail="Shipment is not available for assignment")

        # Step 3: Query the POWER_SHIPMENT by shipment_id
        shipment = db.query(POWER_SHIPMENT).filter(
            POWER_SHIPMENT.id == shipment_id
        ).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        # Step 4: Query the brokerage ledger
        brokerage_ledger = db.query(BrokerageLedger).filter(
            cast(BrokerageLedger.shipment_id, String) == str(shipment_id),
            BrokerageLedger.shipment_type == shipment.type
        ).first()
        if not brokerage_ledger:
            raise HTTPException(status_code=404, detail="Shipment not found in Brokerage Ledger")

        # Step 5: Validate carrier
        carrier = db.query(Carrier).filter(Carrier.id == carrier_id).first()
        if not carrier:
            raise HTTPException(status_code=404, detail="Carrier not found")
        if not (
            carrier.is_verified and
            carrier.git_cover_amount >= shipment.minimum_git_cover_amount and
            carrier.liability_insurance_cover_amount >= shipment.minimum_liability_cover_amount
        ):
            raise HTTPException(status_code=400, detail="Carrier not verified or does not meet GIT/Liability requirements")

        # Step 6: Validate vehicle
        vehicle = db.query(Vehicle).filter(
            Vehicle.id == vehicle_id,
            cast(Vehicle.owner_id, String) == str(carrier_id)
        ).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found or does not belong to carrier")
        if not vehicle.is_verified:
            raise HTTPException(status_code=400, detail="Vehicle is not verified")
        if not (
            vehicle.type == shipment.required_truck_type and
            vehicle.equipment_type == shipment.axle_configuration and
            vehicle.payload_capacity >= shipment.minimum_weight_bracket
        ):
            raise HTTPException(status_code=400, detail="Vehicle does not meet shipment requirements")

        # Step 7: Validate driver
        driver = db.query(Driver).filter(
            Driver.id == vehicle.primary_driver_id,
            cast(Driver.current_vehicle, String) == str(vehicle_id)
        ).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        if not driver.is_verified:
            raise HTTPException(status_code=400, detail="Driver is not verified")

        # Step 8: Assign shipment
        shipment.shipment_status = "Assigned"
        shipment.carrier_id = carrier_id
        shipment.carrier_name = carrier.legal_business_name
        shipment.carrier_git_cover_amount = carrier.git_cover_amount
        shipment.carrier_liability_cover_amount = carrier.liability_insurance_cover_amount
        shipment.vehicle_id = vehicle_id
        shipment.vehicle_type = vehicle.type
        shipment.vehicle_make = vehicle.make
        shipment.vehicle_model = vehicle.model
        shipment.vehicle_color = vehicle.color
        shipment.vehicle_license_plate = vehicle.license_plate
        shipment.vehicle_vin = vehicle.vin
        shipment.driver_id = driver.id
        shipment.driver_first_name = driver.first_name 
        shipment.driver_last_name = driver.last_name
        shipment.driver_license_number = driver.license_number
        shipment.driver_phone_number = driver.phone_number
        shipment.driver_email = driver.email
 
        # Step 9: Update LoadBoardEntry status
        loadboard_entry.status = "Assigned"

        # Step 10: Log into Assigned_Spot_Ftl_Shipments
        assigned_shipment = Assigned_Power_Shipments(
            shipment_id=shipment_id,
            carrier_id=carrier_id,
            carrier_name=carrier.legal_business_name,
            vehicle_id=vehicle_id,
            vehicle_type=vehicle.type,
            vehicle_axle_configuration=vehicle.axle_configuration,
            vehicle_make=vehicle.make,
            vehicle_model=vehicle.model,
            vehicle_color=vehicle.color,
            vehicle_license_plate=vehicle.license_plate,
            driver_id=driver.id,
            driver_first_name=driver.first_name,
            driver_last_name=driver.last_name,
            accepted_for=f"{driver.first_name} {driver.last_name}",
            accepted_at=format_datetime_sast(datetime.utcnow().replace(tzinfo=pytz.utc)),
            minimum_weight_bracket=shipment.minimum_weight_bracket,
            shipment_rate=brokerage_ledger.carrier_payable,
            distance=shipment.distance,
            rate_per_km=loadboard_entry.rate_per_km,
            rate_per_ton=loadboard_entry.rate_per_ton,
            payment_terms=loadboard_entry.payment_terms,
            status="Assigned",
            required_truck_type=shipment.required_truck_type,
            axle_configuration=shipment.axle_configuration,
            trailer_type=shipment.trailer_type,
            trailer_length=shipment.trailer_length,
            origin_address=shipment.origin_address,
            origin_address_completed=shipment.complete_origin_address,
            origin_address_city_provice=shipment.origin_city_province,
            pickup_appointment=loadboard_entry.pickup_start_time,
            destination_address=shipment.destination_address,
            destination_address_completed=shipment.complete_destination_address,
            destination_address_city_provice=shipment.destination_city_province,
            delivery_appointment=loadboard_entry.delivery_start_time,
            pickup_date=shipment.pickup_date,
            priority_level=shipment.priority_level,
            customer_reference_number=shipment.customer_reference_number,
            shipment_weight=shipment.shipment_weight,
            commodity=shipment.commodity,
            packaging_quantity=shipment.packaging_quantity,
            packaging_type=shipment.packaging_type,
            pickup_number=shipment.pickup_number,
            pickup_notes=shipment.pickup_notes,
            delivery_number=shipment.delivery_number,
            delivery_notes=shipment.delivery_notes,
            estimated_transit_time=shipment.estimated_transit_time
        )

        db.add(assigned_shipment)
        db.commit()

        brokerage_ledger.carrier_id = carrier.id
        brokerage_ledger.carrier_company_type = carrier.type
        brokerage_ledger.carrier_company_name = carrier.legal_business_name
        brokerage_ledger.vehicle_id = vehicle.id
        brokerage_ledger.vehicle_make = vehicle.make
        brokerage_ledger.vehicle_model = vehicle.model
        brokerage_ledger.vehicle_year = vehicle.year
        brokerage_ledger.vehicle_color = vehicle.color
        brokerage_ledger.vehicle_vin = vehicle.vin
        brokerage_ledger.vehicle_license_plate = vehicle.license_plate
        brokerage_ledger.driver_id = driver.id
        brokerage_ledger.driver_first_name = driver.first_name
        brokerage_ledger.driver_last_name = driver.last_name
        brokerage_ledger.driver_id_number = driver.id_number
        brokerage_ledger.driver_license_number = driver.license_number

        return {
            "message": f"Shipment {shipment_id} successfully assigned to carrier {carrier_id}",
            "carrier": {
                "id": carrier.id,
                "name": carrier.legal_business_name
            },
            "vehicle": {
                "id": vehicle.id,
                "make": vehicle.make,
                "model": vehicle.model,
                "color": vehicle.color,
                "license_plate": vehicle.license_plate
            },
            "driver": {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name
            },
            "live_location": getattr(driver, "live_location", "Not Available")
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))