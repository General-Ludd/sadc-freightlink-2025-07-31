from datetime import datetime, date, timedelta
from fastapi import HTTPException, requests
from requests.exceptions import RequestException 
import requests
from sqlalchemy.orm import Session
from models.brokerage.finance import BrokerageLedger, Contract, Dedicated_Lane_BrokerageLedger, FinancialAccounts, Interim_Invoice, Shipment_Invoice
from models.brokerage.loadboard import Dedicated_lanes_LoadBoard
from models.shipper import Corporation
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from pydantic import BaseModel
from typing import List
from calendar import monthrange
from sqlalchemy.exc import SQLAlchemyError
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from schemas.brokerage.loadboard import FTL_lane_LoadBoard_Entry
from schemas.shipment_facility import FacilityContactCreate, ShipmentFacilityCreate
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import FTL_Lane_Create
from services.brokerage.brokerage_service import calculate_brokerage_details, calculate_contract_brokerage_details
from services.brokerage.carrier_loadboard_service import calculate_rates
from services.brokerage.recurrence_calculator import DedicatedLanesFtlShipmentPaymentSchedule, RecurrenceCalculator
from services.finance.finance import handle_30_day_pay, handle_contract_pay
from services.shipment_service import calculate_quote_for_shipment, calculate_total_shipment_quote
from utils.billing import BillingEngine
from utils.google_maps import AddressInput, calculate_distance
from datetime import datetime

def create_dedicated_lane_ftl_shipment(
    db: Session,
    shipment_data: FTL_Lane_Create,
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
        raise HTTPException(status_code=403, detail="Shipper account is not verified. Please await verification to create a contract lane.")
    if shipper.status != "Active":
        raise HTTPException(status_code=403, detail="Shipper account is not active. Please await account activation to create a contract lane.")

    # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
    financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == company_id
    ).first()
    
    if not financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found.")
    if not financial_account.is_verified:
        raise HTTPException(status_code=403, detail="Financial account is not verified. Please await verification to create and finance a contract lane.")
    if financial_account.status != "Active":
        raise HTTPException(status_code=403, detail="Financial account is not active. Please await activation to create and finance a contract lane.")

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

    payment_term = financial_account.payment_terms.strip().upper()

    try:
        all_payment_dates = BillingEngine.get_billing_dates(
             start_date=shipment_data.start_date,
             end_date=shipment_data.end_date,
             term=payment_term
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

    # Step 6: Calculate Brokerage Details
    brokerage_details = calculate_contract_brokerage_details(
        db=db,
        booking_amount=total_shipments_quote,
        shipment_type="FTL Lane",
        payment_method=financial_account.payment_terms,
        total_shipments=total_shipments
    )

    recurrence_days_str = ", ".join(shipment_data.recurrence_days)

    # Step 6: Create the FTL Shipment
    shipment = FTL_Lane(
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
        qoute_per_shipment=quote_per_shipment,
        contract_quote=total_shipments_quote,
        recurrence_frequency=shipment_data.recurrence_frequency,
        recurrence_days=recurrence_days_str,
        skip_weekends=shipment_data.skip_weekends,
        shipments_per_interval=shipment_data.shipments_per_interval,
        start_date=shipment_data.start_date,
        end_date=shipment_data.end_date,
        total_shipments=total_shipments,  # Add total shipments to the shipment record
        payment_dates=all_payment_dates,  # Add payment dates to the shipment record
        shipment_dates=shipment_dates,
        status="Booked",
        progress=0
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

################Create Contract Invoice###################
    try:
        last_billing_date = all_payment_dates[-1]  # Final due date

        contract_invoice = BillingEngine.generate_contract_invoice(
            db=db,
            contract_id=shipment.id,
            contract_type=shipment.type,
            financial_account_id=financial_account.id,
            business_name=shipper.legal_business_name,
            contact_person_name=f"{financial_account.directors_first_name} {financial_account.directors_last_name}",
            billing_address=shipper.business_address,
            shipper_company_id=company_id,
            total_shipments_quote=total_shipments_quote,
            payment_terms=payment_term,
            due_date=last_billing_date,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contract invoice generation failed: {str(e)}")

#################Create Interim Invoices#####################
    try:
        amount_per_invoice = round(total_shipments_quote / len(all_payment_dates), 2)

        generated_interim_invoices = BillingEngine.generate_interim_invoices(
            parent_invoice_id=contract_invoice.id,
            contract_id=shipment.id,
            contract_type="FTL Lane",
            company_id=company_id,
            business_name=financial_account.company_name,
            contact_person_name=f"{financial_account.directors_first_name} {financial_account.directors_last_name}",
            business_email=financial_account.directors_email_address,
            billing_address=financial_account.business_address,
            payment_dates=all_payment_dates,
            amount_per_invoice=amount_per_invoice,
            payment_terms=financial_account.payment_terms,
            db=db
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Interim invoice generation failed: {str(e)}")

    # ✅ Preload all interim invoices, sorted by due date
    interim_invoices = db.query(Interim_Invoice).filter(
        Interim_Invoice.contract_id == str(shipment.id),
        Interim_Invoice.invoice_type == "Interim"
    ).order_by(Interim_Invoice.due_date).all()

    if not interim_invoices:
        raise HTTPException(status_code=500, detail="No interim invoices available to attach shipment invoices to.")

    from datetime import datetime, date

    # ✅ Create sub-shipments and assign them to the correct interim invoice
    for pickup_date in shipment_dates:
        for _ in range(shipment_data.shipments_per_interval):
            # Find matching interim invoice (first due_date >= pickup_date)
            parent_invoice = next(
                (
                    inv for inv in interim_invoices
                    if (
                        isinstance(inv.due_date, str) and datetime.fromisoformat(inv.due_date).date() >= pickup_date
                    ) or (
                        isinstance(inv.due_date, datetime) and inv.due_date.date() >= pickup_date
                    ) or (
                        isinstance(inv.due_date, date) and inv.due_date >= pickup_date
                    )
                ),
                None
            )

            if not parent_invoice:
                raise HTTPException(
                    status_code=500,
                    detail=f"No interim invoice found for pickup date: {pickup_date}"
                )

            sub_shipment = FTL_SHIPMENT(
                is_subshipment=True,
                dedicated_lane_id=shipment.id,
                type="FTL",
                trip_type="1 Pickup - 1 Drop Off",
                load_type=shipment_data.load_type,
                shipper_company_id=company_id,
                shipper_user_id=user_id,
                payment_terms=financial_account.payment_terms,
                invoice_id=None,  # Set after invoice is created
                invoice_status="Pending",
                minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
                minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
                required_truck_type=shipment_data.required_truck_type,
                equipment_type=shipment_data.equipment_type,
                trailer_type=shipment_data.trailer_type,
                trailer_length=shipment_data.trailer_length,
                minimum_weight_bracket=shipment_data.minimum_weight_bracket,
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
                pickup_date=pickup_date,
                priority_level=shipment_data.priority_level,
                pickup_facility_id=pickup_facility.id,
                delivery_facility_id=dropoff_facility.id,
                customer_reference_number=shipment_data.customer_reference_number,
                shipment_weight=shipment_data.average_shipment_weight,
                commodity=shipment_data.commodity,
                temperature_control=shipment_data.temperature_control,
                hazardous_materials=shipment_data.hazardous_materials,
                packaging_quantity=shipment_data.packaging_quantity,
                packaging_type=shipment_data.packaging_type,
                pickup_number=shipment_data.pickup_number,
                pickup_notes=shipment_data.pickup_notes,
                delivery_number=shipment_data.delivery_number,
                delivery_notes=shipment_data.delivery_notes,
                distance=distance,
                estimated_transit_time=estimated_transit_time,
                quote=quote_per_shipment,
                route_preview_embed=route_preview_embed,
                shipment_status="Booked",
                trip_status="Scheduled"
            )
            db.add(sub_shipment)
            db.flush()

            try:
                shipment_invoice = BillingEngine.generate_shipment_invoice(
                    contract_id=shipment.id,
                    contract_type=shipment.type,
                    parent_invoice_id=parent_invoice.id,
                    shipment_id=sub_shipment.id,
                    shipment_type=sub_shipment.type,
                    pickup_date=pickup_date,
                    due_date=parent_invoice.due_date,
                    amount=quote_per_shipment,
                    company_id=company_id,
                    payment_terms=financial_account.payment_terms,
                    #New
                    description=f"FTL Shipment {sub_shipment.id}",
                    business_name=shipper.legal_business_name,
                    contact_person_name=f"{financial_account.directors_first_name}-{financial_account.directors_last_name}",
                    business_email=shipper.business_email,
                    billing_address=shipper.business_address,
                    db=db
                )

                sub_shipment.invoice_id = shipment_invoice.id
                sub_shipment.invoice_due_date = shipment_invoice.due_date
                sub_shipment.invoice_status = shipment_invoice.status
                shipment.invoice_id = contract_invoice.id
                shipment.invoice_status = contract_invoice.status
                shipment.invoice_due_date = contract_invoice.due_date
                db.add(sub_shipment)

            except Exception as e:
                print(f"🚨 Error generating shipment invoice for sub-shipment {sub_shipment.id}: {e}")
                raise HTTPException(status_code=500, detail=f"Shipment invoice generation failed: {e}")

    db.commit()

    # Step 8: Create Brokerage Ledger Entry
    brokerage_ledger_entry = Dedicated_Lane_BrokerageLedger(
        contract_id=shipment.id,
        contract_invoice_id=contract_invoice.id,
        contract_invoice_due_date=contract_invoice.due_date,
        contract_invoice_status=contract_invoice.status,
        shipper_company_id=company_id,
        shipper_company_name=financial_account.company_name,
        shipper_type=shipper.type,
        lane_type=shipment.type,
        shipper_company_registration_number=financial_account.business_registration_number,
        shipper_company_country_of_incorporation=financial_account.business_country_of_incorporation,
        contract_booking_amount=brokerage_details["contract_booking_amount"],
        contract_platform_commission=brokerage_details["contract_platform_commission"],
        contract_transaction_fee=brokerage_details["contract_transaction_fee"],
        contract_true_platform_earnings=brokerage_details["contract_true_earnings"],
        contract_carrier_payable=brokerage_details["contract_carrier_payout"],
        payment_terms=financial_account.payment_terms,
        payment_dates=all_payment_dates,
        lane_status="Booked",
        lane_minimum_git_cover_amount=shipment.minimum_git_cover_amount,
        lane_minimum_liability_cover_amount=shipment.minimum_liability_cover_amount,
        contract_start_date=shipment.start_date,
        contract_end_date=shipment.end_date,
        total_shipments=total_shipments,
        booking_amount_per_shipment=brokerage_details["shipment_booking_amount"],
        platform_commission_per_shipment=brokerage_details["shipment_platform_commission"],
        transaction_fee_per_shipment=brokerage_details["shipment_transaction_fee"],
        true_platform_earnings_per_shipment=brokerage_details["shipment_true_earnings"],
        carrier_payable_per_shipment=brokerage_details["shipment_carrier_payout"],
    )
    db.add(brokerage_ledger_entry)
    db.commit()
    db.refresh(brokerage_ledger_entry)

    # Step 6: Calculate rates for LoadBoardEntry
    rate_per_km, rate_per_ton = calculate_rates(
        carrier_payable=brokerage_details["shipment_carrier_payout"],
        distance=distance,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,  # Example weight, can be adjusted dynamically
    )

    loadboard_data = FTL_lane_LoadBoard_Entry(
        shipment_id=shipment.id,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,
        minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
        distance=distance,
        contract_rate=brokerage_details["contract_carrier_payout"],
        rate_per_km=int(rate_per_km),
        rate_per_ton=int(rate_per_ton),
        payment_terms=financial_account.payment_terms,
        recurrence_frequency=shipment_data.recurrence_frequency,
        recurrence_days=shipment_data.recurrence_days,
        skip_weekends=shipment_data.skip_weekends,
        shipments_per_interval=shipment_data.shipments_per_interval,
        total_shipments=total_shipments,
        rate_per_shipment=brokerage_details["shipment_carrier_payout"],
        start_date=shipment_data.start_date,
        end_date=shipment_data.end_date,
        shipment_dates=shipment_dates,
        status="Available",
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

    loadboard_entry = Dedicated_lanes_LoadBoard(
        shipment_id=loadboard_data.shipment_id,
        type="FTL",
        trip_type=shipment.trip_type,
        load_type=shipment_data.load_type,
        minimum_weight_bracket=shipment_data.minimum_weight_bracket,
        minimum_git_cover_amount=shipment_data.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment_data.minimum_liability_cover_amount,
        distance=distance,
        contract_rate=brokerage_details["contract_carrier_payout"],
        rate_per_km=rate_per_km,
        rate_per_ton=rate_per_ton,
        payment_terms=financial_account.payment_terms,
        payment_dates=all_payment_dates,
        recurrence_frequency=shipment_data.recurrence_frequency,
        recurrence_days=shipment_data.recurrence_days,
        skip_weekends=shipment_data.skip_weekends,
        shipments_per_interval=shipment_data.shipments_per_interval,
        total_shipments=total_shipments,
        rate_per_shipment=brokerage_details["shipment_carrier_payout"],
        start_date=shipment_data.start_date,
        end_date=shipment_data.end_date,
        shipment_dates=shipment_dates,
        status="Available",
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
    db.add(loadboard_entry)
    db.commit()
    db.refresh(loadboard_entry)

    # Print Billing Dates
    print("Billing Dates for Contract:")
    for date in all_payment_dates:
        print(f"- {date.strftime('%Y-%m-%d')}")

    return {
        "message": "Contract and sub-shipments created successfully",
        "contract_id": shipment.id,
        "contract_invoice_due_date": last_billing_date,
        "billing_dates": all_payment_dates,
        "shipment_dates": shipment_dates
    }