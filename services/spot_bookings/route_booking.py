from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from datetime import timedelta
from models.shipper import Corporation, Consignor
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs, shipment_status_Update
from models.brokerage.finance import BrokerageLedger, FinancialAccounts, Brokers_Brokerage_Transactions
from models.spot_bookings.shipment_facility import ShipmentFacility, ContactPerson
from schemas.brokerage.loadboard import LoadBoardEntryCreate
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Booking, Enterprise_FTL_Shipment_Booking, Admin_Client_FTL_Shipment_Booking, FTL_Shipment_docs_create
from schemas.spot_bookings.route_booking import Admin_Bulk_Create_Route
from schemas.shipment_facility import ShipmentFacilityCreate, FacilityContactCreate
from schemas.shipper import ConsignorCreate
from schemas.brokerage.finance import Broker_Brokerage_TransactionCreate
from services.brokerage.brokerage_service import calculate_brokerage_details, create_brokerage_ledger_entry
from models.brokerage.loadboard import Ftl_Load_Board
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from services.brokerage.carrier_loadboard_service import calculate_rates, determine_payout_method
from services.finance.finance import handle_30_day_pay, handle_credit_card, handle_instant_eft
from services.shipment_service import calculate_quote_for_shipment
from services.finance.billing_engine import billing_engine
from utils.google_maps import AddressInput, RouteETAInput, calculate_distance, get_eta_and_polyline
from utils.consignor_service import get_or_create_consignor

def admin_bulk_create_client_ftl_shipment(
        db: Session,
        route_data: Admin_Bulk_Create_Route,
        current_user: dict,
):
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = route_data.client_id
    user_id = route_data.user_id
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

    billing_account = enterprise_financial_account

    previous_shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == route_data.previous_shipment_id).first()
    previous_pickup_facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == previous_shipment.pickup_facility_id).first()
    previous_delivery_facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == previous_shipment.delivery_facility_id).first()
    previous_pickup_contact = db.query(ContactPerson).filter(ContactPerson.id == previous_pickup_facility.contact_person).first()
    previous_delivery_contact = db.query(ContactPerson).filter(ContactPerson.id == previous_delivery_facility.contact_person).first()
    previous_docs = db.query(FTL_Shipment_Docs).filter(FTL_Shipment_Docs.shipment_id == previous_shipment.id).first()

    # Step 1: Calculate Distance and Transit Time
    try:
        distance_data = calculate_distance(AddressInput(
            origin_address=previous_shipment.origin_address,
            destination_address=previous_shipment.destination_address
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
            origin_address=previous_shipment.origin_address,
            destination_address=previous_shipment.destination_address,
            start_date=route_data.pickup_date,
            start_time=previous_pickup_facility.end_time,
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
        route_data,
        Admin_Bulk_Create_Route
    )

    if is_admin_booking:

        # If admin entered a shipment rate use it
        if route_data.rate is not None:

            quote_per_shipment = route_data.rate

        else:
            # Use market rate
            quote_per_shipment = calculate_quote_for_shipment(
                db=db,
                required_truck_type=safe_str(previous_shipment.required_truck_type),
                equipment_type=safe_str(previous_shipment.equipment_type),
                trailer_type=safe_str(previous_shipment.trailer_type),
                trailer_length=safe_str(previous_shipment.trailer_length),
                distance=distance,
                minimum_weight_bracket=previous_shipment.minimum_weight_bracket
            )

    else:

        # Normal client booking
        quote_per_shipment = calculate_quote_for_shipment(
            db=db,
            required_truck_type=safe_str(previous_shipment.required_truck_type),
            equipment_type=safe_str(previous_shipment.equipment_type),
            trailer_type=safe_str(previous_shipment.trailer_type),
            trailer_length=safe_str(previous_shipment.trailer_length),
            distance=distance,
            minimum_weight_bracket=previous_shipment.minimum_weight_bracket
        )

    number_of_trucks = route_data.number_of_trucks_required or 1

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
        first_name=previous_pickup_contact.first_name,
        last_name=previous_pickup_contact.last_name,
        phone_number=previous_pickup_contact.phone_number,
        email=previous_pickup_contact.email,
    )
    db.add(pickup_contact)
    db.flush()

    dropoff_contact = ContactPerson(
        first_name=previous_delivery_contact.first_name,
        last_name=previous_delivery_contact.last_name,
        phone_number=previous_delivery_contact.phone_number,
        email=previous_delivery_contact.email,
    )
    db.add(dropoff_contact)
    db.flush()

    pickup_facility = ShipmentFacility(
        shipper_company_id=route_data.client_id,
        type="Pickup",
        address=previous_shipment.origin_address,
        name=previous_pickup_facility.name,
        scheduling_type=previous_pickup_facility.scheduling_type,
        start_time=previous_pickup_facility.start_time,
        end_time=previous_pickup_facility.end_time,
        contact_person_relationship=pickup_contact,
        facility_notes=previous_pickup_facility.facility_notes,
    )
    db.add(pickup_facility)
    db.flush()

    dropoff_facility = ShipmentFacility(
        shipper_company_id=route_data.client_id,
        type="Dropoff",
        address=previous_shipment.destination_address,
        name=previous_delivery_facility.name,
        scheduling_type=previous_delivery_facility.scheduling_type,
        start_time=previous_delivery_facility.start_time,
        end_time=previous_delivery_facility.end_time,
        contact_person_relationship=dropoff_contact,
        facility_notes=previous_delivery_facility.facility_notes,
    )
    db.add(dropoff_facility)
    db.flush()

    for truck_number in range(number_of_trucks):

        truck_reference = (
            f"{previous_shipment.customer_reference_number}-T{truck_number+1}"
            if previous_shipment.customer_reference_number
            else f"TRUCK-{truck_number+1}"
        )
        # Step 1: Create the FTL shipment
        shipment = FTL_SHIPMENT(
            type="FTL",
            trip_type="1 Pickup, 1 Delivery",
            load_type="Live Loading",
            shipper_company_id=route_data.client_id,
            shipper_user_id=route_data.user_id,
            required_truck_type=previous_shipment.required_truck_type,
            equipment_type=previous_shipment.equipment_type,
            trailer_type=previous_shipment.trailer_type,
            trailer_length=previous_shipment.trailer_length,
            minimum_weight_bracket=previous_shipment.minimum_weight_bracket,
            minimum_git_cover_amount=previous_shipment.minimum_git_cover_amount,
            minimum_liability_cover_amount=previous_shipment.minimum_liability_cover_amount,
            origin_address=previous_shipment.origin_address,
            complete_origin_address=complete_origin_address,
            origin_city_province=origin_city_province,
            origin_country=origin_country,
            origin_region=origin_region,
            destination_address=previous_shipment.destination_address,
            complete_destination_address=complete_destination_address,
            destination_city_province=destination_city_province,
            destination_country=destination_country,
            destination_region=destination_region,
            pickup_date=route_data.pickup_date,
            pickup_appointment=(f"{previous_pickup_facility.start_time} - {previous_pickup_facility.start_time}"),
            priority_level=previous_shipment.priority_level,
            pickup_facility_id=pickup_facility.id,
            delivery_facility_id=dropoff_facility.id,
            customer_reference_number=truck_reference,
            shipment_weight=previous_shipment.shipment_weight,
            commodity=previous_shipment.commodity,
            temperature_control=previous_shipment.temperature_control,
            hazardous_materials=previous_shipment.hazardous_materials,
            packaging_quantity=previous_shipment.packaging_quantity,
            packaging_type=previous_shipment.packaging_type,
            pickup_number=previous_shipment.pickup_number,
            pickup_notes=previous_shipment.pickup_notes,
            delivery_number=previous_shipment.delivery_number,
            delivery_notes=previous_shipment.delivery_notes,
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
            commercial_invoice=previous_docs.commercial_invoice,
            packaging_list=previous_docs.packaging_list,
            customs_declaration_form=previous_docs.customs_declaration_form,
            import_or_export_permits=previous_docs.import_or_export_permits,
            certificate_of_origin=previous_docs.certificate_of_origin,
            da5501orsad500=previous_docs.da5501orsad500,
        )
        db.add(shipment_document)
        db.commit()
        db.refresh(shipment_document)

        payment_terms = billing_account.payment_terms

        # --- Generate Invoice ---
        billing_result = billing_engine.initialize_shipment_billing(
            db=db,
            shipper=enterprise,
            shipment=shipment,
            financial_account=billing_account,
            booking_amount=quote_per_shipment
        )

        invoice = billing_result.invoice

        shipment.invoice_id = invoice.id
        shipment.invoice_due_date = invoice.expected_payment_date
        shipment.invoice_status = invoice.status

        db.add(shipment)
        db.commit()
        db.refresh(shipment)

        # Step 4: Calculate brokerage details
        # ---------------------------------------
        # Brokerage calculation
        # ---------------------------------------

        if is_admin_booking and route_data.commission is not None:

            platform_commission = route_data.commission

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
            shipper_company_id=billing_account.id,
            shipper_type=enterprise.type,
            shipper_company_name=enterprise.legal_business_name,
            booking_amount=quote_per_shipment,
            shipment_invoice_id=invoice.id,
            shipment_invoice_due_date=invoice.expected_payment_date,
            shipment_invoice_status=invoice.status,
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
            minimum_weight_bracket=previous_shipment.minimum_weight_bracket,  # Example weight, can be adjusted dynamically
        )

        # Step 7: Create a loadboard entry
        loadboard_data = LoadBoardEntryCreate(
            shipment_id=shipment.id,
            type=shipment.type,
            trip_type=shipment.trip_type,
            load_type=shipment.load_type,
            minimum_weight_bracket=shipment.minimum_weight_bracket,
            minimum_git_cover_amount=shipment.minimum_git_cover_amount,
            minimum_liability_cover_amount=shipment.minimum_liability_cover_amount,
            distance=distance,
            shipment_rate=carrier_payable,
            rate_per_km=int(rate_per_km),  # Convert to integer (e.g., cents)
            rate_per_ton=int(rate_per_ton),  # Convert to integer
            payment_terms=billing_account.payment_terms,  # Dynamic payout method
            payment_date=(invoice.expected_payment_date + timedelta(days=1)),
            required_truck_type=shipment.required_truck_type,
            equipment_type=shipment.equipment_type,
            trailer_type=shipment.trailer_type,
            trailer_length=shipment.trailer_length,
            origin_address=shipment.origin_address,
            complete_origin_address=complete_origin_address,
            origin__city_province=origin_city_province,
            origin_country=origin_country,
            origin_region=origin_region,
            destination_address=shipment.destination_address,
            complete_destination_address=complete_destination_address,
            destination_city_province=destination_city_province,
            destination_country=destination_country,
            destination_region=destination_region,
            route_preview_embed=route_preview_embed,
            pickup_date=shipment.pickup_date,
            priority_level=shipment.priority_level,
            customer_reference_number=truck_reference,
            shipment_weight=shipment.shipment_weight,
            commodity=shipment.commodity,
            temperature_control=shipment.temperature_control,
            hazardous_metarials=shipment.hazardous_materials,
            packaging_quantity=shipment.packaging_quantity,
            packaging_type=shipment.packaging_type,
            pickup_number=shipment.pickup_number,
            pickup_notes=shipment.pickup_notes,
            delivery_number=shipment.delivery_number,
            delivery_notes=shipment.delivery_notes,
            estimated_transit_time=estimated_transit_time,
            pickup_facility_name=previous_pickup_facility.name,
            pickup_scheduling_type=previous_pickup_facility.scheduling_type,
            pickup_start_time=previous_pickup_facility.start_time,
            pickup_end_time=previous_pickup_facility.end_time,
            pickup_facility_notes=previous_pickup_facility.facility_notes,
            pickup_first_name=previous_pickup_contact.first_name,
            pickup_last_name=previous_pickup_contact.last_name,
            pickup_phone_number=previous_pickup_contact.phone_number,
            pickup_email=previous_pickup_contact.email,
            delivery_facility_name=previous_delivery_facility.name,
            delivery_scheduling_type=previous_delivery_facility.scheduling_type,
            delivery_start_time=previous_delivery_facility.start_time,
            delivery_end_time=previous_delivery_facility.end_time,
            delivery_facility_notes=previous_delivery_facility.facility_notes,
            delivery_first_name=previous_delivery_contact.first_name,
            delivery_last_name=previous_delivery_contact.last_name,
            delivery_phone_number=previous_delivery_contact.phone_number,
            delivery_email=previous_delivery_contact.email,
        )

        loadboard_entry = Ftl_Load_Board(
            shipment_id=loadboard_data.shipment_id,
            type=loadboard_data.type,
            trip_type=loadboard_data.trip_type,
            load_type=loadboard_data.load_type,
            minimum_weight_bracket=shipment.minimum_weight_bracket,
            minimum_git_cover_amount=shipment.minimum_git_cover_amount,
            minimum_liability_cover_amount=shipment.minimum_liability_cover_amount,
            distance=distance,
            shipment_rate=loadboard_data.shipment_rate,
            rate_per_km=loadboard_data.rate_per_km,
            rate_per_ton=loadboard_data.rate_per_ton,
            payment_terms=loadboard_data.payment_terms,
            payment_date=loadboard_data.payment_date,
            required_truck_type=shipment.required_truck_type,
            equipment_type=shipment.equipment_type,
            trailer_type=shipment.trailer_type,
            trailer_length=shipment.trailer_length,
            origin_address=shipment.origin_address,
            complete_origin_address=complete_origin_address,
            origin_city_province=origin_city_province,
            origin_country=origin_country,
            origin_region=origin_region,
            destination_address=shipment.destination_address,
            complete_destination_address=complete_destination_address,
            destination_city_province=destination_city_province,
            destination_country=destination_country,
            destination_region=destination_region,
            route_preview_embed=route_preview_embed,
            pickup_date=shipment.pickup_date,
            priority_level=shipment.priority_level,
            customer_reference_number=truck_reference,
            shipment_weight=shipment.shipment_weight,
            commodity=shipment.commodity,
            temperature_control=shipment.temperature_control,
            hazardous_metarials=shipment.hazardous_materials,
            packaging_quantity=shipment.packaging_quantity,
            packaging_type=shipment.packaging_type,
            pickup_number=shipment.pickup_number,
            pickup_notes=shipment.pickup_notes,
            delivery_number=shipment.delivery_number,
            delivery_notes=shipment.delivery_notes,
            estimated_transit_time=estimated_transit_time,
            eta_date=shipment.eta_date,
            eta_window=shipment.eta_window,
            pickup_appointment=f"{shipment.pickup_date}, {pickup_facility.start_time}-{pickup_facility.end_time}",
            pickup_facility_name=previous_pickup_facility.name,
            pickup_scheduling_type=previous_pickup_facility.scheduling_type,
            pickup_start_time=previous_pickup_facility.start_time, 
            pickup_end_time=previous_pickup_facility.end_time,
            pickup_facility_notes=previous_pickup_facility.facility_notes,
            pickup_first_name=previous_pickup_contact.first_name,
            pickup_last_name=previous_pickup_contact.last_name,
            pickup_phone_number=previous_pickup_contact.phone_number,
            pickup_email=previous_pickup_contact.email,
            delivery_appointment=f"{previous_delivery_facility.start_time}-{previous_delivery_facility.end_time}",
            delivery_facility_name=previous_delivery_facility.name,
            delivery_scheduling_type=previous_delivery_facility.scheduling_type,
            delivery_start_time=previous_delivery_facility.start_time,
            delivery_end_time=previous_delivery_facility.end_time,
            delivery_facility_notes=previous_delivery_facility.facility_notes,
            delivery_first_name=previous_delivery_contact.first_name,
            delivery_last_name=previous_delivery_contact.last_name,
            delivery_phone_number=previous_delivery_contact.phone_number,
            delivery_email=previous_delivery_contact.email,
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
