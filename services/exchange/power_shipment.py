from fastapi import APIRouter, Depends, HTTPException, status
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.shipper import Corporation
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.brokerage.finance import BrokerageLedger, FinancialAccounts
from models.spot_bookings.shipment_facility import ShipmentFacility, ContactPerson
from models.vehicle import ShipperTrailer
from schemas.brokerage.loadboard import LoadBoardEntryCreate
from schemas.exchange_bookings.power_shipment import Exchange_Power_Shipment_Booking #
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking
from schemas.shipment_facility import ShipmentFacilityCreate, FacilityContactCreate
from services.brokerage.brokerage_service import calculate_brokerage_details, create_brokerage_ledger_entry
from models.brokerage.loadboard import Ftl_Load_Board
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from services.brokerage.carrier_loadboard_service import calculate_rates, determine_payout_method
from services.finance.finance import handle_30_day_pay, handle_credit_card, handle_instant_eft
from services.shipment_service import calculate_qoute_for_power_shipment, calculate_quote_for_shipment
from utils.billing import BillingEngine
from utils.google_maps import AddressInput, calculate_distance

def create_power_shipment_exchange(
        db: Session,
        shipment_data: Exchange_Power_Shipment_Booking,
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
        raise HTTPException(status_code=403, detail="Shipper account is not verified. Please await verification to create a shipment exchange.")
    if shipper.status != "Active":
        raise HTTPException(status_code=403, detail="Shipper account is not active. Please await account activation to create a shipment exchange.")

    # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
    financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == company_id
    ).first()
    
    if not financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found.")
    if not financial_account.is_verified:
        raise HTTPException(status_code=403, detail="Financial account is not verified. Please await verification to create and finance a shipment exchange.")
    if financial_account.status != "Active":
        raise HTTPException(status_code=403, detail="Financial account is not active. Please await activation to create and finance a shipment exchange.")


    trailer = db.query(ShipperTrailer).filter(ShipperTrailer.id == shipment_data.trailer_id).first()
    if not trailer:
        raise ValueError("Trailer not found or does not belong to this shipper company")
    if not trailer.is_verified:
        raise ValueError("Trailer is not verified, please choose a different Trailer or await trailer verification")

    payment_terms = financial_account.payment_terms

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
    
    def safe_str(val):
        return val.value if hasattr(val, "value") else str(val)
    
    try:
        quote_per_shipment = calculate_qoute_for_power_shipment(
            db=db,
            required_truck_type=safe_str(shipment_data.required_truck_type),
            axle_configuration=safe_str(shipment_data.axle_configuration),
            distance=distance,
            minimum_weight_bracket=shipment_data.minimum_weight_bracket
        )
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Quote calculation failed: {e.detail}")
    
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

    # Step 1: Create the FTL shipment
    shipment = POWER_SHIPMENT_EXCHANGE(
        type="POWER",
        trip_type="1 Pickup, 1 Delivery",
        load_type=shipment_data.load_type,
        shipper_company_id=company_id,
        shipper_user_id=user_id,
        required_truck_type=shipment_data.required_truck_type,
        axle_configuration=shipment_data.axle_configuration,
        trailer_id=shipment_data.trailer_id,
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
        pickup_date=shipment_data.pickup_date,
        priority_level=shipment_data.priority_level,
        pickup_facility_id=pickup_facility.id,
        delivery_facility_id=dropoff_facility.id,
        customer_reference_number=shipment_data.customer_reference_number,
        shipment_weight=shipment_data.shipment_weight,
        commodity=shipment_data.commodity,
        temperature_control=shipment_data.temperature_control,
        hazardous_materials=shipment_data.hazardous_materials,
        packaging_quantity=shipment_data.packaging_quantity,
        packaging_type=shipment_data.packaging_type,
        pickup_number=shipment_data.pickup_number,
        pickup_notes=shipment_data.pickup_notes,
        delivery_number=shipment_data.delivery_number,
        delivery_notes=shipment_data.delivery_notes,
        estimated_transit_time=estimated_transit_time,
        distance=distance,
        automatically_accept_lower_bid=shipment_data.automatically_accept_lower_bid,
        allow_carrier_to_book_at_current_or_lower_offer_rate=shipment_data.allow_carrier_to_book_at_current_or_lower_offer_rate,
        offer_rate=shipment_data.offer_rate,
        backed_offer_rate=shipment_data.offer_rate * 0.90,
        suggested_rate=quote_per_shipment,
        payment_terms=financial_account.payment_terms,
        route_preview_embed=route_preview_embed,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    # Step 6: Calculate rates for LoadBoardEntry
    rate_per_km, rate_per_ton = calculate_rates(
        carrier_payable=shipment.backed_offer_rate,
        distance=distance,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,  # Example weight, can be adjusted dynamically
    )

    loadboard_entry = Exchange_Power_Load_Board(
        exchange_id=shipment.id,
        type=shipment.type,
        trip_type=shipment.trip_type,
        load_type=shipment_data.load_type,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,
        minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
        distance=distance,
        offer_rate=shipment.backed_offer_rate,
        rate_per_km=rate_per_km,
        rate_per_ton=rate_per_ton,
        payment_terms=financial_account.payment_terms,
        payment_date=BillingEngine.get_next_due_date(shipment.pickup_date, financial_account.payment_terms),
        required_truck_type=shipment_data.required_truck_type,
        axle_configuration=shipment_data.axle_configuration,
        trailer_id=shipment_data.trailer_id,
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
        route_preview_embed=route_preview_embed,
        pickup_date=shipment_data.pickup_date,
        priority_level=shipment_data.priority_level,
        customer_reference_number=shipment_data.customer_reference_number,
        shipment_weight=shipment_data.shipment_weight,
        commodity=shipment_data.commodity,
        temperature_control=shipment_data.temperature_control,
        hazardous_materials=shipment_data.hazardous_materials,
        packaging_quantity=shipment_data.packaging_quantity,
        packaging_type=shipment_data.packaging_type,
        pickup_number=shipment_data.pickup_number,
        pickup_notes=shipment_data.pickup_notes,
        delivery_number=shipment_data.delivery_number,
        delivery_notes=shipment_data.delivery_notes,
        estimated_transit_time=estimated_transit_time,
        pickup_appointment=f"{shipment.pickup_date}, {pickup_facility.start_time}-{pickup_facility.end_time}",
        pickup_facility_name=pickup_facility_data.name,
        pickup_scheduling_type=pickup_facility_data.scheduling_type,
        pickup_start_time=pickup_facility_data.start_time, 
        pickup_end_time=pickup_facility_data.end_time,
        pickup_facility_notes=pickup_facility_data.facility_notes,
        pickup_first_name=pickup_contact_data.first_name,
        pickup_last_name=pickup_contact_data.last_name,
        pickup_phone_number=pickup_contact_data.phone_number,
        pickup_email=pickup_contact_data.email,
        delivery_appointment=f"{dropoff_facility.start_time}-{dropoff_facility.end_time}",
        delivery_facility_name=dropoff_facility_data.name,
        delivery_scheduling_type=dropoff_facility_data.scheduling_type,
        delivery_start_time=dropoff_facility_data.start_time,
        delivery_end_time=dropoff_facility_data.end_time,
        delivery_facility_notes=dropoff_facility_data.facility_notes,
        delivery_first_name=dropoff_contact_data.first_name,
        delivery_last_name=dropoff_contact_data.last_name,
        delivery_phone_number=dropoff_contact_data.phone_number,
        delivery_email=dropoff_contact_data.email,
    )
    db.add(loadboard_entry)
    db.commit()
    db.refresh(loadboard_entry)

    # Step 6: Return all details
    return {
        "loadboard_entry": {
            "id": loadboard_entry.id,
            "shipment_id": shipment.id,
            "shipment_rate": loadboard_entry.offer_rate,
            "rate_per_km": loadboard_entry.rate_per_km,
            "rate_per_ton": loadboard_entry.rate_per_ton,
            "payment_terms": loadboard_entry.payment_terms,
            "created_at": loadboard_entry.created_at,
        },
    }