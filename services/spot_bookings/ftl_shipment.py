from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from datetime import timedelta
from models.shipper import Corporation, Consignor
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs, shipment_status_Update
from models.brokerage.finance import BrokerageLedger, FinancialAccounts, Brokers_Brokerage_Transactions
from models.spot_bookings.shipment_facility import ShipmentFacility, ContactPerson
from schemas.brokerage.loadboard import LoadBoardEntryCreate
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking, Enterprise_FTL_Shipment_Booking, Admin_Client_FTL_Shipment_Booking, FTL_Shipment_docs_create
from schemas.shipment_facility import ShipmentFacilityCreate, FacilityContactCreate
from schemas.shipper import ConsignorCreate
from schemas.brokerage.finance import Broker_Brokerage_TransactionCreate
from services.brokerage.brokerage_service import calculate_brokerage_details, create_brokerage_ledger_entry
from services.finance.billing_engine import billing_engine
from models.brokerage.loadboard import Ftl_Load_Board
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from services.brokerage.carrier_loadboard_service import calculate_rates, determine_payout_method
from services.finance.finance import handle_30_day_pay, handle_credit_card, handle_instant_eft
from services.shipment_service import calculate_quote_for_shipment
#from utils.billing import BillingEngine ###revert to it if need be
from utils.google_maps import AddressInput, RouteETAInput, calculate_distance, get_eta_and_polyline
from utils.consignor_service import get_or_create_consignor

def create_ftl_shipment(
        db: Session,
        shipment_data: FTL_Shipment_Booking,
        pickup_facility_data: ShipmentFacilityCreate,
        dropoff_facility_data: ShipmentFacilityCreate,
        pickup_contact_data: FacilityContactCreate,
        dropoff_contact_data: FacilityContactCreate,
        shipment_documents_data: FTL_Shipment_docs_create,
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
        raise HTTPException(status_code=403, detail="Shipper account is not verified. Please await verification to create a shipment.")
    if shipper.status != "Active":
        raise HTTPException(status_code=403, detail="Shipper account is not active. Please await account activation to create a shipment.")

    # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
    financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == company_id
    ).first()
    
    if not financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found.")
    if not financial_account.is_verified:
        raise HTTPException(status_code=403, detail="Financial account is not verified. Please await verification to create and finance a shipment.")
    if financial_account.status != "Active":
        raise HTTPException(status_code=403, detail="Financial account is not active. Please await activation to create and finance  a shipment.")

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

    # Step 2: get ETA Date, ETA Window, Polylines
    try:
        trip_data = get_eta_and_polyline(RouteETAInput(
            origin_address=shipment_data.origin_address,
            destination_address=shipment_data.destination_address,
            start_date=shipment_data.pickup_date,
            start_time=pickup_facility_data.end_time,
        ))
        eta_date = trip_data["eta_date"]  # Distance in kilometers
        eta_window = trip_data["eta_window"]  # Transit time as text
        polyline = trip_data["polyline"]
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Trip info calculation failed: {e.detail}")

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

    system_quote = quote_per_shipment

    if shipment_data.offered_shipment_rate is not None:
        booking_amount = shipment_data.offered_shipment_rate
    else:
        booking_amount = system_quote

    try:
        if financial_account.payment_terms == "PAB":
            if financial_account.credit_balance >= booking_amount:
                financial_account.credit_balance -= booking_amount
            else:
                raise HTTPException(
                    status_code=402,
                    detail=f"Shipment booking failed due to insufficient funds. Please deposit at least R{quote_per_shipment:.2f} to proceed."
                )
        else:
            projected_balance = financial_account.total_outstanding + booking_amount
            if projected_balance <= financial_account.spending_limit:
                financial_account.total_outstanding = projected_balance
            else:
                raise HTTPException(
                    status_code=402,
                    detail="Shipment booking failed: booking this shipment would exceed your company's spending limit."
                )

        db.add(financial_account)
        db.flush()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shipment billing process failed: {str(e)}")

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
    shipment = FTL_SHIPMENT(
        consignor_id=shipment_data.consignor_id,
        type="FTL",
        trip_type="1 Pickup, 1 Delivery",
        load_type="Live Loading",
        shipper_company_id=company_id,
        shipper_user_id=user_id,
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
        pickup_date=shipment_data.pickup_date,
        pickup_appointment=(f"{pickup_facility_data.start_time} - {pickup_facility_data.start_time}"),
        priority_level=shipment_data.priority_level,
        pickup_facility_id=pickup_facility.id,
        delivery_facility_id=dropoff_facility.id,
        customer_reference_number=shipment_data.customer_reference_number,
        shipment_weight=shipment_data.shipment_weight,
        commodity=shipment_data.commodity,
        temperature_control=shipment_data.temperature_control,
        hazardous_materials=shipment_data.hazardous_materials,
        under_bond=shipment_data.under_bond,
        rib_requirements=shipment_data.rib_requirements,
        packaging_quantity=shipment_data.packaging_quantity,
        packaging_type=shipment_data.packaging_type,
        pickup_number=shipment_data.pickup_number,
        pickup_notes=shipment_data.pickup_notes,
        delivery_number=shipment_data.delivery_number,
        delivery_notes=shipment_data.delivery_notes,
        estimated_transit_time=estimated_transit_time,
        distance=distance,
        eta_date=eta_date,
        eta_window=eta_window,
        polyline=polyline,
        quote=booking_amount,
        payment_terms=financial_account.payment_terms,
        route_preview_embed=route_preview_embed,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)


    shipment_documents_data = FTL_Shipment_Docs(
        shipment_id=shipment.id,
        commercial_invoice=shipment_documents_data.commercial_invoice,
        packaging_list=shipment_documents_data.packaging_list,
        customs_declaration_form=shipment_documents_data.customs_declaration_form,
        import_or_export_permits=shipment_documents_data.import_or_export_permits,
        certificate_of_origin=shipment_documents_data.certificate_of_origin,
        da5501orsad500=shipment_documents_data.da5501orsad500,
    )
    db.add(shipment_documents_data)
    db.commit()
    db.refresh(shipment_documents_data)

    payment_terms = financial_account.payment_terms

    # --- Generate Invoice ---
    shipment_invoice = billing_engine.initialize_shipment_billing(
        db=db,
        shipper=shipper,
        shipment=shipment,
        financial_account=financial_account,
        booking_amount=booking_amount
    )
    shipment.invoice_id = shipment_invoice.id
    shipment.invoice_due_date = shipment_invoice.due_date
    shipment.invoice_status = shipment_invoice.status

    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    # Step 4: Calculate brokerage details
    brokerage_details = calculate_brokerage_details(
        db=db,
        booking_amount=booking_amount,
        shipment_type="FTL",
        payment_method=financial_account.payment_terms,
    )

    # Step 5: Create the brokerage transaction
    brokerage_transaction = BrokerageLedger(
        shipment_id=shipment.id,
        shipment_type=shipment.type,
        shipper_company_id=company_id,
        shipper_type=shipper.type,
        shipper_company_name=shipper.legal_business_name,
        booking_amount=booking_amount,
        shipment_invoice_id=shipment_invoice.id,
        shipment_invoice_due_date=shipment_invoice.due_date,
        shipment_invoice_status=shipment_invoice.status,
        platform_commission=brokerage_details[0],
        transaction_fee=brokerage_details[1],
        true_platform_earnings=brokerage_details[2],
        payment_terms=financial_account.payment_terms,
        carrier_payable=brokerage_details[3],
    )
    db.add(brokerage_transaction)
    db.commit()
    db.refresh(brokerage_transaction)

    # Step 6: Calculate rates for LoadBoardEntry
    rate_per_km, rate_per_ton = calculate_rates(
        carrier_payable=brokerage_details[3],
        distance=distance,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,  # Example weight, can be adjusted dynamically
    )

    # Step 7: Create a loadboard entry
    loadboard_data = LoadBoardEntryCreate(
        shipment_id=shipment.id,
        type=shipment.type,
        trip_type=shipment.trip_type,
        load_type=shipment.load_type,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,
        minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
        distance=distance,
        shipment_rate=brokerage_details[3],
        rate_per_km=int(rate_per_km),  # Convert to integer (e.g., cents)
        rate_per_ton=int(rate_per_ton),  # Convert to integer
        payment_terms=financial_account.payment_terms,  # Dynamic payout method
        payment_date=BillingEngine.get_next_billing_date(payment_terms, shipment_data.pickup_date) + timedelta(days=2),
        required_truck_type=shipment_data.required_truck_type,
        equipment_type=shipment_data.equipment_type,
        trailer_type=shipment_data.trailer_type,
        trailer_length=shipment_data.trailer_length,
        origin_address=shipment_data.origin_address,
        complete_origin_address=complete_origin_address,
        origin__city_province=origin_city_province,
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
        hazardous_metarials=shipment_data.hazardous_materials,
        packaging_quantity=shipment_data.packaging_quantity,
        packaging_type=shipment_data.packaging_type,
        pickup_number=shipment_data.pickup_number,
        pickup_notes=shipment_data.pickup_notes,
        delivery_number=shipment_data.delivery_number,
        delivery_notes=shipment_data.delivery_notes,
        estimated_transit_time=estimated_transit_time,
        pickup_facility_name=pickup_facility_data.name,
        pickup_scheduling_type=pickup_facility_data.scheduling_type,
        pickup_start_time=pickup_facility_data.start_time,
        pickup_end_time=pickup_facility_data.end_time,
        pickup_facility_notes=pickup_facility_data.facility_notes,
        pickup_first_name=pickup_contact_data.first_name,
        pickup_last_name=pickup_contact_data.last_name,
        pickup_phone_number=pickup_contact_data.phone_number,
        pickup_email=pickup_contact_data.email,
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

    loadboard_entry = Ftl_Load_Board(
        shipment_id=loadboard_data.shipment_id,
        type=loadboard_data.type,
        trip_type=loadboard_data.trip_type,
        load_type=loadboard_data.load_type,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,
        minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
        distance=distance,
        shipment_rate=loadboard_data.shipment_rate,
        rate_per_km=loadboard_data.rate_per_km,
        rate_per_ton=loadboard_data.rate_per_ton,
        payment_terms=loadboard_data.payment_terms,
        payment_date=loadboard_data.payment_date,
        required_truck_type=shipment_data.required_truck_type,
        equipment_type=shipment_data.equipment_type,
        trailer_type=shipment_data.trailer_type,
        trailer_length=shipment_data.trailer_length,
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
        hazardous_metarials=shipment_data.hazardous_materials,
        under_bond=shipment_data.under_bond,
        rib_requirements=shipment_data.rib_requirements,
        packaging_quantity=shipment_data.packaging_quantity,
        packaging_type=shipment_data.packaging_type,
        pickup_number=shipment_data.pickup_number,
        pickup_notes=shipment_data.pickup_notes,
        delivery_number=shipment_data.delivery_number,
        delivery_notes=shipment_data.delivery_notes,
        estimated_transit_time=estimated_transit_time,
        eta_date=shipment.eta_date,
        eta_window=shipment.eta_window,
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
    shipment.shipment_status = "Booked"
    shipment.trip_status = "Scheduled"
    db.add(loadboard_entry)
    db.commit()
    db.refresh(loadboard_entry)

    initial_status = shipment_status_Update(
        shipment_id=shipment.id,
        type="FTL",
        status="Booked",
        trip_status="Scheduled",
        location_description="Shipment booking has been processed."
    )
    db.add(initial_status)
    db.commit()
    db.refresh(initial_status)

    # Step 6: Return all details
    return {"shipment_id": shipment.id}

################################################Broker Shipment Create###################################
def broker_create_ftl_shipment(
        db: Session,  # For new consignor
        shipment_data: FTL_Shipment_Booking,
        broker_transaction_data: Broker_Brokerage_TransactionCreate,
        pickup_facility_data: ShipmentFacilityCreate,
        dropoff_facility_data: ShipmentFacilityCreate,
        pickup_contact_data: FacilityContactCreate,
        dropoff_contact_data: FacilityContactCreate,
        shipment_documents_data: FTL_Shipment_docs_create,
        consignor_data: Optional[ConsignorCreate] = None, # For new consignor
        current_user: dict = None,
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
        raise HTTPException(status_code=400, detail="Brokerage firm account not found or not active.")
    if not shipper.is_verified:
        raise HTTPException(status_code=403, detail="Brokerage firm account is not verified. Please await verification to create a shipment.")
    if shipper.status != "Active":
        raise HTTPException(status_code=403, detail="Brokerage account is not active. Please await account activation to create a shipment.")

    # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
    financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == company_id
    ).first()
    
    if not financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found.")
    if not financial_account.is_verified:
        raise HTTPException(status_code=403, detail="Financial account is not verified. Please await verification to create and finance a shipment.")
    if financial_account.status != "Active":
        raise HTTPException(status_code=403, detail="Financial account is not active. Please await activation to create and finance  a shipment.")

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

    # Step 2: get ETA Date, ETA Window, Polylines
    try:
        trip_data = get_eta_and_polyline(RouteETAInput(
            origin_address=shipment_data.origin_address,
            destination_address=shipment_data.destination_address,
            start_date=shipment_data.pickup_date,
            start_time=pickup_facility_data.end_time,
        ))
        eta_date = trip_data["eta_date"]  # Distance in kilometers
        eta_window = trip_data["eta_window"]  # Transit time as text
        polyline = trip_data["polyline"]
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Trip info calculation failed: {e.detail}")

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
        if financial_account.payment_terms == "PAB":
            if financial_account.credit_balance >= quote_per_shipment:
                financial_account.credit_balance -= quote_per_shipment
            else:
                raise HTTPException(
                    status_code=402,
                    detail=f"Shipment booking failed due to insufficient funds. Please deposit at least R{quote_per_shipment:.2f} to proceed."
                )
        else:
            projected_balance = financial_account.total_outstanding + quote_per_shipment
            if projected_balance <= financial_account.spending_limit:
                financial_account.total_outstanding = projected_balance
            else:
                raise HTTPException(
                    status_code=402,
                    detail="Shipment booking failed: booking this shipment would exceed your company's spending limit."
                )

        db.add(financial_account)
        db.flush()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shipment billing process failed: {str(e)}")

    if not shipment_data.consignor_id and not consignor_data:
        raise HTTPException(
            status_code=400,
            detail="Please provide either consignor_id or data to create a new consignor."
        )

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
    
    consignor_id = get_or_create_consignor(db, shipment_data, consignor_data, current_user)

    # Step 1: Create the FTL shipment
    shipment = FTL_SHIPMENT(
        consignor_id=consignor_id,
        type="FTL",
        trip_type="1 Pickup, 1 Delivery",
        load_type="Live Loading",
        shipper_company_id=company_id,
        shipper_user_id=user_id,
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
        pickup_date=shipment_data.pickup_date,
        pickup_appointment=(f"{pickup_facility_data.start_time} - {pickup_facility_data.end_time}"),
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
        eta_date=eta_date,
        eta_window=eta_window,
        polyline=polyline,
        quote=quote_per_shipment,
        payment_terms=financial_account.payment_terms,
        route_preview_embed=route_preview_embed,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    try:
        client = db.query(Consignor).filter(Consignor.id == consignor_id).first()

        broker_transaction = Brokers_Brokerage_Transactions(
            brokerage_firm_id=company_id,
            shipment_id=shipment.id,
            type=shipment.type,
            consignor_id=client.id,
            per_shipment_consignor_billable=broker_transaction_data.consignor_billable,
            per_shipment_platform_booking_amount=quote_per_shipment,
            per_shipment_profit=int(broker_transaction_data.consignor_billable - quote_per_shipment)
        )
        client.revenue_generated += broker_transaction_data.consignor_billable
        client.profit_generated += int(broker_transaction_data.consignor_billable - quote_per_shipment)
        db.add(broker_transaction)
        db.commit()
        db.refresh(broker_transaction)
        print(f"✅ Broker transaction created with ID {broker_transaction.id}")
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to create broker transaction: {e}")

    shipment_documents_data = FTL_Shipment_Docs(
        shipment_id=shipment.id,
        commercial_invoice=shipment_documents_data.commercial_invoice,
        packaging_list=shipment_documents_data.packaging_list,
        customs_declaration_form=shipment_documents_data.customs_declaration_form,
        import_or_export_permits=shipment_documents_data.import_or_export_permits,
        certificate_of_origin=shipment_documents_data.certificate_of_origin,
        da5501orsad500=shipment_documents_data.da5501orsad500,
    )
    db.add(shipment_documents_data)
    db.commit()
    db.refresh(shipment_documents_data)

    payment_terms = financial_account.payment_terms

    # --- Generate Invoice ---
    shipment_invoice = BillingEngine.create_shipment_invoice(
        db=db,
        company_id=company_id,
        financial_account=financial_account,
        shipment_id=shipment.id,
        shipment_type=shipment.type,
        origin_address=shipment.origin_address,
        destination_address=shipment.destination_address,
        pickup_date=shipment.pickup_date,
        distance=shipment.distance,
        transit_time=shipment.estimated_transit_time,
        total_cost=quote_per_shipment
    )
    shipment.invoice_id = shipment_invoice.id
    shipment.invoice_due_date = shipment_invoice.due_date
    shipment.invoice_status = shipment_invoice.status

    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    try:

        initial_status = shipment_status_Update(
            shipment_id=shipment.id,
            type="FTL",
            status="Booked",
            trip_status="Scheduled",
            location_description="Shipment booking has been processed."
        )
        db.add(initial_status)
        db.commit()
        db.refresh(initial_status)

    except SQLAlchemyError as e:
        # Rollback on error to avoid leaving the session in an inconsistent state
        db.rollback()
        print("Database error:", e)
        return {"error": "Failed to create shipment or status update", "details": str(e)}

    # Step 4: Calculate brokerage details
    brokerage_details = calculate_brokerage_details(
        db=db,
        booking_amount=quote_per_shipment,
        shipment_type="FTL",
        payment_method=financial_account.payment_terms,
    )

    # Step 5: Create the brokerage transaction
    brokerage_transaction = BrokerageLedger(
        shipment_id=shipment.id,
        shipment_type=shipment.type,
        shipper_company_id=company_id,
        shipper_type=shipper.type,
        shipper_company_name=shipper.legal_business_name,
        booking_amount=quote_per_shipment,
        shipment_invoice_id=shipment_invoice.id,
        shipment_invoice_due_date=shipment_invoice.due_date,
        shipment_invoice_status=shipment_invoice.status,
        platform_commission=brokerage_details[0],
        transaction_fee=brokerage_details[1],
        true_platform_earnings=brokerage_details[2],
        payment_terms=financial_account.payment_terms,
        carrier_payable=brokerage_details[3],
    )
    db.add(brokerage_transaction)
    db.commit()
    db.refresh(brokerage_transaction)

    # Step 6: Calculate rates for LoadBoardEntry
    rate_per_km, rate_per_ton = calculate_rates(
        carrier_payable=brokerage_details[3],
        distance=distance,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,  # Example weight, can be adjusted dynamically
    )

    # Step 7: Create a loadboard entry
    loadboard_data = LoadBoardEntryCreate(
        shipment_id=shipment.id,
        type=shipment.type,
        trip_type=shipment.trip_type,
        load_type=shipment.load_type,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,
        minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
        distance=distance,
        shipment_rate=brokerage_details[3],
        rate_per_km=int(rate_per_km),  # Convert to integer (e.g., cents)
        rate_per_ton=int(rate_per_ton),  # Convert to integer
        payment_terms=financial_account.payment_terms,  # Dynamic payout method
        payment_date=BillingEngine.get_next_billing_date(payment_terms, shipment.pickup_date) + timedelta(days=2),
        required_truck_type=shipment_data.required_truck_type,
        equipment_type=shipment_data.equipment_type,
        trailer_type=shipment_data.trailer_type,
        trailer_length=shipment_data.trailer_length,
        origin_address=shipment_data.origin_address,
        complete_origin_address=complete_origin_address,
        origin__city_province=origin_city_province,
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
        hazardous_metarials=shipment_data.hazardous_materials,
        packaging_quantity=shipment_data.packaging_quantity,
        packaging_type=shipment_data.packaging_type,
        pickup_number=shipment_data.pickup_number,
        pickup_notes=shipment_data.pickup_notes,
        delivery_number=shipment_data.delivery_number,
        delivery_notes=shipment_data.delivery_notes,
        estimated_transit_time=estimated_transit_time,
        pickup_facility_name=pickup_facility_data.name,
        pickup_scheduling_type=pickup_facility_data.scheduling_type,
        pickup_start_time=pickup_facility_data.start_time,
        pickup_end_time=pickup_facility_data.end_time,
        pickup_facility_notes=pickup_facility_data.facility_notes,
        pickup_first_name=pickup_contact_data.first_name,
        pickup_last_name=pickup_contact_data.last_name,
        pickup_phone_number=pickup_contact_data.phone_number,
        pickup_email=pickup_contact_data.email,
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

    loadboard_entry = Ftl_Load_Board(
        shipment_id=loadboard_data.shipment_id,
        type=loadboard_data.type,
        trip_type=loadboard_data.trip_type,
        load_type=loadboard_data.load_type,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,
        minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
        distance=distance,
        shipment_rate=loadboard_data.shipment_rate,
        rate_per_km=loadboard_data.rate_per_km,
        rate_per_ton=loadboard_data.rate_per_ton,
        payment_terms=loadboard_data.payment_terms,
        payment_date=loadboard_data.payment_date,
        required_truck_type=shipment_data.required_truck_type,
        equipment_type=shipment_data.equipment_type,
        trailer_type=shipment_data.trailer_type,
        trailer_length=shipment_data.trailer_length,
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
        hazardous_metarials=shipment_data.hazardous_materials,
        packaging_quantity=shipment_data.packaging_quantity,
        packaging_type=shipment_data.packaging_type,
        pickup_number=shipment_data.pickup_number,
        pickup_notes=shipment_data.pickup_notes,
        delivery_number=shipment_data.delivery_number,
        delivery_notes=shipment_data.delivery_notes,
        estimated_transit_time=estimated_transit_time,
        eta_date=shipment.eta_date,
        eta_window=shipment.eta_window,
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
    shipment.shipment_status = "Booked"
    shipment.trip_status = "Scheduled"
    db.add(loadboard_entry)
    db.commit()
    db.refresh(loadboard_entry)

    # Step 6: Return all details
    return {"shipment_id": shipment.id}


############################################################################################################
###########################################Enterprise FTL Shipment Booking##################################
############################################################################################################
def admin_create_client_ftl_shipment(
        db: Session,
        shipment_data: Admin_Client_FTL_Shipment_Booking,
        pickup_facility_data: ShipmentFacilityCreate,
        dropoff_facility_data: ShipmentFacilityCreate,
        pickup_contact_data: FacilityContactCreate,
        dropoff_contact_data: FacilityContactCreate,
        shipment_documents_data: FTL_Shipment_docs_create,
        current_user: dict,
):
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = shipment_data.client_id
    user_id = shipment_data.user_id
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    enterprise = db.query(Corporation).filter(Corporation.id == company_id).first()
    if not enterprise:
        raise HTTPException(status_code=400, detail="Enterprise shipper account not found or not active, please contact support to request account activation.")
    if not enterprise.is_verified:
        raise HTTPException(status_code=403, detail="Enterprise shipper account is not verified. Please await verification to create a shipment.")
    if enterprise.status != "Active":
        raise HTTPException(status_code=403, detail="Enterprise shipper account is not active. Please await account activation to create a shipment.")

    # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
    enterprise_financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == company_id
    ).first()
    
    if not enterprise_financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found.")
    if not enterprise_financial_account.is_verified:
        raise HTTPException(status_code=403, detail="Financial account is not verified. Please await verification to create and finance a shipment.")
    if enterprise_financial_account.status != "Active":
        raise HTTPException(status_code=403, detail="Financial account is not active. Please await activation to create and finance  a shipment.")

    facility = None
    facility_financial_account = None

    if shipment_data.facility_id:
        facility = db.query(Corporation).filter(Corporation.id == shipment_data.facility_id).first()
        if not facility:
            raise HTTPException(status_code=400, detail="Facility shipping account not found or not active.")
        if not facility.is_verified:
            raise HTTPException(status_code=403, detail="Facility shipping account is not verified.")
        if facility.status != "Active":
            raise HTTPException(status_code=403, detail="Facility account is not active.")

        facility_financial_account = db.query(FinancialAccounts).filter(
            FinancialAccounts.id == facility.id
        ).first()

        if not facility_financial_account:
            raise HTTPException(status_code=404, detail="Facility financial account not found.")
        if not facility_financial_account.is_verified:
            raise HTTPException(status_code=403, detail="Facility financial account is not verified.")
        if facility_financial_account.status != "Active":
            raise HTTPException(status_code=403, detail="Facility financial account inactive.")

        # Facility booking path
        billing_account = facility_financial_account
        billing_company = facility

    else:
        # ENTERPRISE DIRECT BOOKING PATH
        billing_account = enterprise_financial_account
        billing_company = enterprise

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

    # Step 2: get ETA Date, ETA Window, Polylines
    try:
        trip_data = get_eta_and_polyline(RouteETAInput(
            origin_address=shipment_data.origin_address,
            destination_address=shipment_data.destination_address,
            start_date=shipment_data.pickup_date,
            start_time=pickup_facility_data.end_time,
        ))
        eta_date = trip_data["eta_date"]  # Distance in kilometers
        eta_window = trip_data["eta_window"]  # Transit time as text
        polyline = trip_data["polyline"]
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Trip info calculation failed: {e.detail}")

    def safe_str(val):
        return val.value if hasattr(val, "value") else str(val)

    # ---------------------------------------
    # Determine shipment rate
    # ---------------------------------------

    is_admin_booking = isinstance(
        shipment_data,
        Admin_Client_FTL_Shipment_Booking
    )

    if is_admin_booking:

        # If admin entered a shipment rate use it
        if shipment_data.shipment_rate is not None:

            quote_per_shipment = shipment_data.shipment_rate

        else:
            # Use market rate
            quote_per_shipment = calculate_quote_for_shipment(
                db=db,
                required_truck_type=safe_str(shipment_data.required_truck_type),
                equipment_type=safe_str(shipment_data.equipment_type),
                trailer_type=safe_str(shipment_data.trailer_type),
                trailer_length=safe_str(shipment_data.trailer_length),
                distance=distance,
                minimum_weight_bracket=shipment_data.minimum_weight_bracket
            )

    else:

        # Normal client booking
        quote_per_shipment = calculate_quote_for_shipment(
            db=db,
            required_truck_type=safe_str(shipment_data.required_truck_type),
            equipment_type=safe_str(shipment_data.equipment_type),
            trailer_type=safe_str(shipment_data.trailer_type),
            trailer_length=safe_str(shipment_data.trailer_length),
            distance=distance,
            minimum_weight_bracket=shipment_data.minimum_weight_bracket
        )

    number_of_trucks = shipment_data.number_of_required_trucks or 1

    created_shipments = []

    total_booking_amount = (quote_per_shipment * number_of_trucks)

    try:
        if billing_account.payment_terms == "PAB":
            if billing_account.credit_balance >= total_booking_amount:
                billing_account.credit_balance -= total_booking_amount
            else:
                raise HTTPException(
                    status_code=402,
                    detail=f"Shipment booking failed due to insufficient funds. Please deposit at least R{quote_per_shipment:.2f} to proceed."
                )
        else:
            projected_balance = billing_account.total_outstanding + total_booking_amount
            if projected_balance <= billing_account.spending_limit:
                billing_account.total_outstanding = projected_balance
            else:
                raise HTTPException(
                    status_code=402,
                    detail="Shipment booking failed: booking this shipment would exceed your company's spending limit."
                )

        db.add(billing_account)
        db.flush()

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shipment billing process failed: {str(e)}")

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
        shipper_company_id=billing_company.id,
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
        shipper_company_id=billing_company.id,
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

    for truck_number in range(number_of_trucks):

        truck_reference = (
            f"{shipment_data.customer_reference_number}-T{truck_number+1}"
            if shipment_data.customer_reference_number
            else f"TRUCK-{truck_number+1}"
        )
        # Step 1: Create the FTL shipment
        shipment = FTL_SHIPMENT(
            type="FTL",
            trip_type="1 Pickup, 1 Delivery",
            load_type="Live Loading",
            shipper_company_id=billing_company.id,
            shipper_user_id=user_id,
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
            pickup_date=shipment_data.pickup_date,
            pickup_appointment=(f"{pickup_facility_data.start_time} - {pickup_facility_data.start_time}"),
            priority_level=shipment_data.priority_level,
            pickup_facility_id=pickup_facility.id,
            delivery_facility_id=dropoff_facility.id,
            customer_reference_number=truck_reference,
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
            eta_date=eta_date,
            eta_window=eta_window,
            polyline=polyline,
            quote=quote_per_shipment,
            payment_terms=billing_account.payment_terms,
            route_preview_embed=route_preview_embed,
        )
        db.add(shipment)
        db.commit()
        db.refresh(shipment)


        shipment_document = FTL_Shipment_Docs(
            shipment_id=shipment.id,
            commercial_invoice=shipment_documents_data.commercial_invoice,
            packaging_list=shipment_documents_data.packaging_list,
            customs_declaration_form=shipment_documents_data.customs_declaration_form,
            import_or_export_permits=shipment_documents_data.import_or_export_permits,
            certificate_of_origin=shipment_documents_data.certificate_of_origin,
            da5501orsad500=shipment_documents_data.da5501orsad500,
        )
        db.add(shipment_document)
        db.commit()
        db.refresh(shipment_document)

        payment_terms = billing_account.payment_terms

        # --- Generate Invoice ---
        shipment_invoice = BillingEngine.create_shipment_invoice(
            db=db,
            company_id=billing_company.id,
            financial_account=billing_account,
            shipment_id=shipment.id,
            shipment_type=shipment.type,
            origin_address=shipment.origin_address,
            destination_address=shipment.destination_address,
            pickup_date=shipment.pickup_date,
            distance=shipment.distance,
            transit_time=shipment.estimated_transit_time,
            total_cost=quote_per_shipment
        )
        shipment.invoice_id = shipment_invoice.id
        shipment.invoice_due_date = shipment_invoice.due_date
        shipment.invoice_status = shipment_invoice.status

        db.add(shipment)
        db.commit()
        db.refresh(shipment)

        # Step 4: Calculate brokerage details
        # ---------------------------------------
        # Brokerage calculation
        # ---------------------------------------

        if is_admin_booking and shipment_data.commission_rate is not None:

            platform_commission = shipment_data.commission_rate

            # Keep your existing transaction fee logic
            brokerage_details = calculate_brokerage_details(
                db=db,
                booking_amount=quote_per_shipment,
                shipment_type="FTL",
                payment_method=billing_account.payment_terms,
            )

            transaction_fee = brokerage_details[1]

            carrier_payable = (
                quote_per_shipment
                - platform_commission
            )

            true_platform_earnings = (
                platform_commission
                + transaction_fee
            )

        else:

            (
                platform_commission,
                transaction_fee,
                true_platform_earnings,
                carrier_payable,
            ) = calculate_brokerage_details(
                db=db,
                booking_amount=quote_per_shipment,
                shipment_type="FTL",
                payment_method=billing_account.payment_terms,
            )

        # Step 5: Create the brokerage transaction
        brokerage_transaction = BrokerageLedger(
            shipment_id=shipment.id,
            shipment_type=shipment.type,
            shipper_company_id=billing_company.id,
            shipper_type=billing_company.type,
            shipper_company_name=billing_company.legal_business_name,
            booking_amount=quote_per_shipment,
            shipment_invoice_id=shipment_invoice.id,
            shipment_invoice_due_date=shipment_invoice.due_date,
            shipment_invoice_status=shipment_invoice.status,
            platform_commission=platform_commission,
            transaction_fee=transaction_fee,
            true_platform_earnings=true_platform_earnings,
            payment_terms=billing_account.payment_terms,
            carrier_payable=carrier_payable,
        )
        db.add(brokerage_transaction)
        db.commit()
        db.refresh(brokerage_transaction)

        # Step 6: Calculate rates for LoadBoardEntry
        rate_per_km, rate_per_ton = calculate_rates(
            carrier_payable=carrier_payable,
            distance=distance,
            minimum_weight_bracket=shipment_data.minimum_weight_bracket,  # Example weight, can be adjusted dynamically
        )

        # Step 7: Create a loadboard entry
        loadboard_data = LoadBoardEntryCreate(
            shipment_id=shipment.id,
            type=shipment.type,
            trip_type=shipment.trip_type,
            load_type=shipment.load_type,
            minimum_weight_bracket=shipment_data.minimum_weight_bracket,
            minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
            minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
            distance=distance,
            shipment_rate=carrier_payable,
            rate_per_km=int(rate_per_km),  # Convert to integer (e.g., cents)
            rate_per_ton=int(rate_per_ton),  # Convert to integer
            payment_terms=billing_account.payment_terms,  # Dynamic payout method
            payment_date=BillingEngine.get_next_billing_date(payment_terms, shipment_data.pickup_date) + timedelta(days=2),
            required_truck_type=shipment_data.required_truck_type,
            equipment_type=shipment_data.equipment_type,
            trailer_type=shipment_data.trailer_type,
            trailer_length=shipment_data.trailer_length,
            origin_address=shipment_data.origin_address,
            complete_origin_address=complete_origin_address,
            origin__city_province=origin_city_province,
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
            customer_reference_number=truck_reference,
            shipment_weight=shipment_data.shipment_weight,
            commodity=shipment_data.commodity,
            temperature_control=shipment_data.temperature_control,
            hazardous_metarials=shipment_data.hazardous_materials,
            packaging_quantity=shipment_data.packaging_quantity,
            packaging_type=shipment_data.packaging_type,
            pickup_number=shipment_data.pickup_number,
            pickup_notes=shipment_data.pickup_notes,
            delivery_number=shipment_data.delivery_number,
            delivery_notes=shipment_data.delivery_notes,
            estimated_transit_time=estimated_transit_time,
            pickup_facility_name=pickup_facility_data.name,
            pickup_scheduling_type=pickup_facility_data.scheduling_type,
            pickup_start_time=pickup_facility_data.start_time,
            pickup_end_time=pickup_facility_data.end_time,
            pickup_facility_notes=pickup_facility_data.facility_notes,
            pickup_first_name=pickup_contact_data.first_name,
            pickup_last_name=pickup_contact_data.last_name,
            pickup_phone_number=pickup_contact_data.phone_number,
            pickup_email=pickup_contact_data.email,
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

        loadboard_entry = Ftl_Load_Board(
            shipment_id=loadboard_data.shipment_id,
            type=loadboard_data.type,
            trip_type=loadboard_data.trip_type,
            load_type=loadboard_data.load_type,
            minimum_weight_bracket=shipment_data.minimum_weight_bracket,
            minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
            minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
            distance=distance,
            shipment_rate=loadboard_data.shipment_rate,
            rate_per_km=loadboard_data.rate_per_km,
            rate_per_ton=loadboard_data.rate_per_ton,
            payment_terms=loadboard_data.payment_terms,
            payment_date=loadboard_data.payment_date,
            required_truck_type=shipment_data.required_truck_type,
            equipment_type=shipment_data.equipment_type,
            trailer_type=shipment_data.trailer_type,
            trailer_length=shipment_data.trailer_length,
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
            customer_reference_number=truck_reference,
            shipment_weight=shipment_data.shipment_weight,
            commodity=shipment_data.commodity,
            temperature_control=shipment_data.temperature_control,
            hazardous_metarials=shipment_data.hazardous_materials,
            packaging_quantity=shipment_data.packaging_quantity,
            packaging_type=shipment_data.packaging_type,
            pickup_number=shipment_data.pickup_number,
            pickup_notes=shipment_data.pickup_notes,
            delivery_number=shipment_data.delivery_number,
            delivery_notes=shipment_data.delivery_notes,
            estimated_transit_time=estimated_transit_time,
            eta_date=shipment.eta_date,
            eta_window=shipment.eta_window,
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
        shipment.shipment_status = "Booked"
        shipment.trip_status = "Scheduled"
        db.add(loadboard_entry)
        db.commit()
        db.refresh(loadboard_entry)

        initial_status = shipment_status_Update(
            shipment_id=shipment.id,
            type="FTL",
            status="Booked",
            trip_status="Scheduled",
            location_description="Shipment booking has been processed."
        )
        db.add(initial_status)
        db.commit()
        db.refresh(initial_status)

        created_shipments.append(
            shipment.id
        )

    # Step 6: Return all details
    return {
        "number_of_trucks_requested": number_of_trucks,

        "number_of_shipments_created": len(
            created_shipments
        ),

        "shipment_ids": created_shipments
    }
