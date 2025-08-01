from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange
from models.brokerage.finance import FinancialAccounts
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Lane_LoadBoard
from models.shipper import Corporation
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from schemas.exchange_bookings.dedicated_ftl_lane import Exchange_FTL_Lane_Booking
from schemas.shipment_facility import FacilityContactCreate, ShipmentFacilityCreate
from services.brokerage.carrier_loadboard_service import calculate_rates
from services.brokerage.recurrence_calculator import RecurrenceCalculator
from services.shipment_service import calculate_quote_for_shipment, calculate_total_shipment_quote
from utils.billing import BillingEngine
from utils.google_maps import AddressInput, calculate_distance


def create_dedicated_ftl_lane_exchange(
    db: Session,
    shipment_data: Exchange_FTL_Lane_Booking,
    pickup_facility_data: ShipmentFacilityCreate,
    dropoff_facility_data: ShipmentFacilityCreate,
    pickup_contact_data: FacilityContactCreate,
    dropoff_contact_data: FacilityContactCreate,
    current_user: dict,
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    shipper = db.query(Corporation).filter(Corporation.id == company_id).first()
    if not shipper:
        raise HTTPException(status_code=400, detail="Shipper account not found or not active.")
    if not shipper.is_verified:
        raise HTTPException(status_code=403, detail="Shipper account is not verified. Please await verification to create an exchange.")
    if shipper.status != "Active":
        raise HTTPException(status_code=403, detail="Shipper account is not active. Please await account activation to create an exchange.")

# Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
    financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == company_id
    ).first()
    
    if not financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found.")
    if not financial_account.is_verified:
        raise HTTPException(status_code=403, detail="Financial account is not verified. Please await verification to create and finance an exchange.")
    if financial_account.status != "Active":
        raise HTTPException(status_code=403, detail="Financial account is not active. Please await activation to create and finance an exchange.")


    # Step 1: Calculate Distance and Transit Time
    try:
        distance_data = calculate_distance(AddressInput(
            origin_address=shipment_data.origin_address,
            destination_address=shipment_data.destination_address
        ))
        distance = distance_data["distance"]  # Distance in kilometers
        estimated_transit_time = distance_data["duration"]  # Transit time as text
        complete_origin_address = distance_data["complete_origin_address"]
        origin_city_province = distance_data["origin_city_province"]
        origin_country = distance_data["origin_country"]
        origin_region = distance_data["origin_region"]
        complete_destination_address = distance_data["complete_destination_address"]
        destination_city_province = distance_data["destination_city_province"]
        destination_country = distance_data["destination_country"]
        destination_region = distance_data["destination_region"]
        route_preview_embed = distance_data["google_maps_embed_url"]
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Distance calculation failed: {e.detail}")
    
    
    # Step 1: Create Pickup and Dropoff Contact
    pickup_contact = ContactPerson(
        first_name=pickup_contact_data.first_name,
        last_name=pickup_contact_data.last_name,
        phone_number=pickup_contact_data.phone_number,
        email=pickup_contact_data.email,
    )
    db.add(pickup_contact)
    db.flush()

    dropoff_contact = ContactPerson(
        first_name=dropoff_contact_data.first_name,
        last_name=dropoff_contact_data.last_name,
        phone_number=dropoff_contact_data.phone_number,
        email=dropoff_contact_data.email,
    )
    db.add(dropoff_contact)
    db.flush()

    # Step 2: Create Pickup and Dropoff Facilities
    pickup_facility = ShipmentFacility(
        shipper_company_id=company_id,
        type="Pickup",
        address=shipment_data.origin_address,
        name=pickup_facility_data.name,
        scheduling_type=pickup_facility_data.scheduling_type,
        start_time=pickup_facility_data.start_time,
        end_time=pickup_facility_data.end_time,
        contact_person_relationship=pickup_contact,
        facility_notes=pickup_facility_data.facility_notes,
    )
    db.add(pickup_facility)
    db.flush()

    dropoff_facility = ShipmentFacility(
        shipper_company_id=company_id,
        type="Dropoff",
        address=shipment_data.destination_address,
        name=dropoff_facility_data.name,
        scheduling_type=dropoff_facility_data.scheduling_type,
        start_time=dropoff_facility_data.start_time,
        end_time=dropoff_facility_data.end_time,
        contact_person_relationship=dropoff_contact,
        facility_notes=dropoff_facility_data.facility_notes,
    )
    db.add(dropoff_facility)
    db.flush()

    # Ensure values are strings (support Enums or raw strings)
    def safe_str(val):
        return val.value if hasattr(val, "value") else str(val)

    try:
        quote_per_shipment = calculate_quote_for_shipment(
            db=db,
            required_truck_type=safe_str(shipment_data.required_truck_type),
            equipment_type=safe_str(shipment_data.equipment_type),
            trailer_type=safe_str(shipment_data.trailer_type),
            trailer_length=safe_str(shipment_data.trailer_length),
            distance=distance,
            minimum_weight_bracket=shipment_data.minimum_weight_bracket
        )
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Quote calculation failed: {e.detail}")

    try:
        all_payment_dates = BillingEngine.get_billing_dates(
             start_date=shipment_data.start_date,
             end_date=shipment_data.end_date,
             term=financial_account.payment_terms
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment schedule generation failed: {str(e)}")
    
    # Step 4: Calculate Recurrence Dates for Shipments
    recurrence_calculator = RecurrenceCalculator(
        recurrence_frequency=shipment_data.recurrence_frequency,
        recurrence_days=shipment_data.recurrence_days,
        start_date=shipment_data.start_date,
        end_date=shipment_data.end_date,
        shipments_per_interval=shipment_data.shipments_per_interval,
        skip_weekends=shipment_data.skip_weekends
    )
    shipment_dates = recurrence_calculator.get_recurrence_dates(total_shipments=quote_per_shipment)

    # Step 5: Calculate Total Shipments
    total_shipments = recurrence_calculator.calculate_total_shipments(total_shipments=len(shipment_dates))

    try:
        total_shipments_quote = calculate_total_shipment_quote(
            qoute_per_shipment=quote_per_shipment,
            total_shipments=total_shipments
        )
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Quote calculation failed: {e.detail}")
    
    recurrence_days_str = ", ".join(shipment_data.recurrence_days)

    # Step 6: Create the FTL Shipment
    shipment = FTL_Lane_Exchange(
        type="FTL Lane",
        load_type=shipment_data.load_type,
        trip_type="1 Pickup, 1 Delivery",
        shipper_company_id=company_id,
        shipper_user_id=user_id,
        payment_terms=financial_account.payment_terms,
        required_truck_type=shipment_data.required_truck_type,
        equipment_type=shipment_data.equipment_type,
        trailer_type=shipment_data.trailer_type,
        trailer_length=shipment_data.trailer_length,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,
        minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
        origin_address=shipment_data.origin_address,
        complete_origin_address=complete_origin_address,
        origin_city_province=origin_city_province,
        origin_country=origin_country,
        origin_region=origin_region,
        destination_address=shipment_data.destination_address,
        complete_destination_address=complete_destination_address,
        destination_city_province=destination_city_province,
        destination_country=destination_country,
        destination_region=destination_region,
        priority_level=shipment_data.priority_level,
        pickup_facility_id=pickup_facility.id,
        delivery_facility_id=dropoff_facility.id,
        customer_reference_number=shipment_data.customer_reference_number,
        average_shipment_weight=shipment_data.average_shipment_weight,
        commodity=shipment_data.commodity,
        temperature_control=shipment_data.temperature_control,
        hazardous_materials=shipment_data.hazardous_materials,
        packaging_quantity=shipment_data.packaging_quantity,
        packaging_type=shipment_data.packaging_type,
        pickup_number=shipment_data.pickup_number,
        pickup_notes=shipment_data.pickup_notes,
        delivery_number=shipment_data.delivery_number,
        delivery_notes=shipment_data.delivery_notes,
        estimated_transit_time=estimated_transit_time,  # Assign directly
        distance=distance,
        route_preview_embed=route_preview_embed,
        per_shipment_offer_rate=shipment_data.per_shipment_offer_rate,
        contract_offer_rate=shipment_data.per_shipment_offer_rate * total_shipments,
        backed_per_shipment_offer_rate=shipment_data.per_shipment_offer_rate * 0.90,
        backed_contract_offer_rate=shipment_data.per_shipment_offer_rate * total_shipments * 0.90,
        suggested_per_shipment_rate=quote_per_shipment,
        suggested_contract_rate=total_shipments_quote,
        recurrence_frequency=shipment_data.recurrence_frequency,
        recurrence_days=recurrence_days_str,
        skip_weekends=shipment_data.skip_weekends,
        shipments_per_interval=shipment_data.shipments_per_interval,
        start_date=shipment_data.start_date,
        end_date=shipment_data.end_date,
        total_shipments=total_shipments,  # Add total shipments to the shipment record
        payment_dates=all_payment_dates,  # Add payment dates to the shipment record
        shipment_dates=shipment_dates,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    # Step 6: Calculate rates for LoadBoardEntry
    rate_per_km, rate_per_ton = calculate_rates(
        carrier_payable=shipment.backed_per_shipment_offer_rate,
        distance=distance,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,  # Example weight, can be adjusted dynamically
    )

    loadboard_entry = Exchange_Ftl_Lane_LoadBoard(
        exchange_id=shipment.id,
        type=shipment.type,
        trip_type=shipment.trip_type,
        load_type=shipment.load_type,
        minimum_weight_bracket=shipment.minimum_weight_bracket,
        minimum_git_cover_amount=shipment.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment.minimum_liability_cover_amount,
        per_shipment_offer_rate=shipment.per_shipment_offer_rate,
        contract_offer_rate=shipment.contract_offer_rate,
        distance=shipment.distance,
        rate_per_km=rate_per_km,
        rate_per_ton=rate_per_ton,
        payment_terms=shipment.payment_terms,
        payment_dates=shipment.payment_dates,
        required_truck_type=shipment.required_truck_type,
        equipment_type=shipment.equipment_type,
        trailer_type=shipment.trailer_type,
        trailer_length=shipment.trailer_length,
        origin_address=shipment.origin_address,
        complete_origin_address=shipment.complete_origin_address,
        origin_city_province=shipment.origin_city_province,
        origin_country=origin_country,
        origin_region=origin_region,
        destination_address=shipment.destination_address,
        complete_destination_address=shipment.complete_destination_address,
        destination_city_province=shipment.destination_city_province,
        destination_country=shipment.destination_country,
        destination_region=shipment.destination_region,
        route_preview_embed=shipment.route_preview_embed,
        start_date=shipment.start_date,
        end_date=shipment.end_date,
        recurrence_frequency=shipment.recurrence_frequency,
        recurrence_days=recurrence_days_str,
        shipments_per_interval=shipment.shipments_per_interval,
        total_shipments=shipment.total_shipments,
        shipment_dates=shipment.shipment_dates,
        priority_level=shipment.priority_level,
        customer_reference_number=shipment.customer_reference_number,
        average_shipment_weight=shipment.average_shipment_weight,
        commodity=shipment.commodity,
        temperature_control=shipment.temperature_control,
        hazardous_materials=shipment.hazardous_materials,
        packaging_quantity=shipment.packaging_quantity,
        packaging_type=shipment.packaging_quantity,
        pickup_number=shipment.pickup_number,
        pickup_notes=shipment.pickup_notes,
        delivery_number=shipment.delivery_number,
        delivery_notes=shipment.delivery_notes,
        estimated_transit_time=shipment.estimated_transit_time,
        pickup_appointment=f"{pickup_facility.start_time} - {pickup_facility.end_time}",
        pickup_facility_name=pickup_facility.name,
        pickup_scheduling_type=pickup_facility.scheduling_type, # e.g., "First come, First served"
        pickup_start_time=pickup_facility.start_time,
        pickup_end_time=pickup_facility.end_time,
        pickup_facility_notes=pickup_facility.facility_notes,
        pickup_first_name=pickup_contact.first_name,
        pickup_last_name=pickup_contact.last_name,
        pickup_phone_number=pickup_contact.phone_number,
        pickup_email=pickup_contact.email,
        delivery_appointment=f"{dropoff_facility.start_time} - {dropoff_facility.end_time}",
        delivery_facility_name=dropoff_facility.name,
        delivery_scheduling_type=dropoff_facility.scheduling_type,  # e.g., "First come, First served"
        delivery_start_time=dropoff_facility.start_time,
        delivery_end_time=dropoff_facility.end_time,
        delivery_facility_notes=dropoff_facility.facility_notes,
        delivery_first_name=dropoff_contact.first_name,
        delivery_last_name=dropoff_contact.last_name,
        delivery_phone_number=dropoff_contact.phone_number,
        delivery_email=dropoff_contact.email,
    )
    db.add(loadboard_entry)
    db.commit()
    db.refresh(loadboard_entry)

    # Step 6: Return all details
    return {
        "loadboard_entry": {
            "id": loadboard_entry.id,
            "exchange_id": shipment.id,
            "payment_terms": loadboard_entry.payment_terms,
            "created_at": loadboard_entry.created_at,
        },
    }