from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.spot_bookings.shipment_facility import ShipmentFacility
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE, Client_Shipment_Auction
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid, Shipment_Auction_Bid
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, CarrierFinancialAccounts, Dedicated_Lane_BrokerageLedger, Lane_Slot_Ledger, Exchange_Lane_Slot_Assignment, FinancialAccounts, Interim_Invoice, Lane_Interim_Invoice, Lane_Invoice, Load_Invoice, PlatformCommission
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Lane_LoadBoard, Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.brokerage.loadboard import Shipment_Auction_Loadboard
from models.carrier import Carrier, Carrier_Notification
from models.shipper import Corporation, Client_Notification
from models.spot_bookings.dedicated_lane_ftl_shipment import Client_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.vehicle import Vehicle
from schemas.exchange_bookings.auction import Accept_Bid, Exchange_FTL_Lane_Bid_Create, Exchange_FTL_Shipment_Bid_Create, Exchange_POWER_Shipment_Bid_Create, Create_Tender_Bid, Create_Shipment_Bid
from services.brokerage.carrier_loadboard_service import calculate_rates
from utils.billing import BillingEngine
from fastapi import HTTPException, Depends, Request
from sqlalchemy.orm import Session
import pytz
from datetime import datetime
from utils.sast_datetime import format_datetime_sast
from utils.google_maps import AddressInput, RouteETAInput, calculate_distance, get_eta_and_polyline

def place_ftl_shipment_bid(db: Session, bid_data: Exchange_FTL_Shipment_Bid_Create, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    exchange = db.query(FTL_SHIPMENT_EXCHANGE).filter(
        FTL_SHIPMENT_EXCHANGE.id == bid_data.exchange_id,
        FTL_SHIPMENT_EXCHANGE.auction_status == "Open"
    ).first()
    if not exchange:
        raise ValueError("Exchange not found, or Exchange bidding closed")
    if exchange.auction_status !="Open":
        raise ValueError("Exchange bidding closed")

    exchange_loadboard = db.query(Exchange_Ftl_Load_Board).filter(
        Exchange_Ftl_Load_Board.exchange_id == bid_data.exchange_id,
        Exchange_Ftl_Load_Board.status == "Open"
    ).first()
    if not exchange_loadboard:
        raise ValueError("Exchange board not found.")
    if exchange_loadboard.status !="Open":
        raise ValueError("Exchange bidding closed")

    carrier = db.query(Carrier).filter(
        Carrier.id == company_id).first()
    if not carrier:
        raise ValueError("Carrier Not found")
    if not carrier.is_verified:
        raise ValueError("Carrier company account not verified. Please request or await verification.")
    if carrier.status != "Active":
        raise ValueError("Carrier account is not active.")

    try:
        assert carrier.git_cover_amount >= exchange.minimum_git_cover_amount, "Carrier GIT Cover Amount does not meet exchange GIT cover amount requirement"
        assert carrier.liability_insurance_cover_amount >= exchange.minimum_liability_cover_amount, "Carrier Liability Cover Amount does not meet exchange Liability cover amount requirement"
    except AssertionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
    financial_account = db.query(CarrierFinancialAccounts).filter(
        CarrierFinancialAccounts.id == company_id
    ).first()
    if not financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found.")
    if not financial_account.is_verified:
        raise HTTPException(status_code=403, detail="Financial account is not verified, Please await verification to accept shipments.")
    if financial_account.status != "Active":
        raise HTTPException(status_code=403, detail="Financial account is not active, Please await activation to accept shipments.")


    # Fetch existing bids for comparison
    existing_bids = db.query(Exchange_FTL_Shipment_Bid).filter(
        Exchange_FTL_Shipment_Bid.exchange_id == bid_data.exchange_id
    ).all()

    baked_bid = bid_data.bid_amount * 1.10

    # Determine if this bid is the lowest
    is_lowest_bid = all(bid_data.bid_amount < existing_bid.bid_amount for existing_bid in existing_bids)

    # Set status based on comparison
    new_bid_status = "Placed" if is_lowest_bid else "Outbidded"

    # Create the new bid
    bid = Exchange_FTL_Shipment_Bid(
        exchange_id=bid_data.exchange_id,
        carrier_id=company_id,
        carrier_type=carrier.type,
        carrier_name=carrier.legal_business_name,
        user_id=user_id,
        bid_amount=bid_data.bid_amount,
        baked_bid_amount=baked_bid,
        bid_notes=bid_data.bid_notes,
        status=new_bid_status
    )
    exchange.number_of_bids_submitted = (exchange.number_of_bids_submitted or 0) + 1
    db.add(bid)
    db.commit()
    db.refresh(bid)

    # If this is the new lowest bid, update all other bids to Outbidded
    if is_lowest_bid:
        db.query(Exchange_FTL_Shipment_Bid).filter(
            Exchange_FTL_Shipment_Bid.exchange_id == bid_data.exchange_id,
            Exchange_FTL_Shipment_Bid.id != bid.id  # exclude the new bid itself
        ).update(
            {"status": "Outbidded"},
            synchronize_session=False
        )
        exchange.leading_bid_id = bid.id
        exchange.leading_bid_amount = baked_bid
        exchange_loadboard.leading_bid_id = bid.id,
        exchange_loadboard.leading_bid_amount = bid.bid_amount
        db.commit()

    return bid


def accept_ftl_shipment_exchange_bid(db: Session, bid_data: Accept_Bid, current_user:dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    shipper = db.query(Corporation).filter(Corporation.id == company_id).first()
    if not shipper:
        raise HTTPException(status_code=400, detail="Shipper Account not verified, or not Active")
    if shipper.status != "Active":
        raise ValueError("Shipper Account is not activated")
    if not shipper.is_verified:
        raise ValueError("Shipper Account is not verified")

    # Fetch existing bids for comparison
    bid = db.query(Exchange_FTL_Shipment_Bid).filter(
        Exchange_FTL_Shipment_Bid.id == bid_data.bid_id
    ).first()

    # Fetch existing bids for comparison
    bid_verification = db.query(Exchange_FTL_Shipment_Bid).filter(
        Exchange_FTL_Shipment_Bid.exchange_id == bid.exchange_id
    ).all()

    carrier = db.query(Carrier).filter(Carrier.id == bid.carrier_id).first()
    if not carrier:
        raise ValueError("Carrier account not found")

    exchange = db.query(FTL_SHIPMENT_EXCHANGE).filter(
        FTL_SHIPMENT_EXCHANGE.id == bid.exchange_id,
    ).first()
    if not exchange:
        raise ValueError("Exchange not found.")
    if exchange.auction_status !="Open":
        raise ValueError("Exchange has ended and bidding closed.")
    
    exchange_loadboard = db.query(Exchange_Ftl_Load_Board).filter(
        Exchange_Ftl_Load_Board.exchange_id == bid.exchange_id
    ).first()
    if not exchange_loadboard:
        raise ValueError("Exchange board not found.")
    if exchange_loadboard.status !="Open":
        raise ValueError("Exchange Loadboard bidding closed.")

   # Step 2: Retrieve financial account and payment type
    financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == company_id
    ).first()

    if not financial_account:
        raise Exception("Financial account not found") 

    try:
        if financial_account.payment_terms == "PAB":
            # If financial account's payment terms is (PAB), deduct from credit balance
            if financial_account.credit_balance >= bid.baked_bid_amount:
                financial_account.credit_balance -= bid.baked_bid_amount
            else:
                raise HTTPException(
                    status_code=402,
                    detail=f"Attempt to accept bid failed due to insufficient funds. Please deposit at least R{bid.baked_bid_amount:.2f} to proceed, failure to do so will result with the exchange closing with no bids accepted."
                )
        else:
            projected_balance = financial_account.total_outstanding + bid.baked_bid_amount
            if projected_balance <= financial_account.spending_limit:
                financial_account.total_outstanding = projected_balance
            else:
                raise HTTPException(
                    status_code=402,
                    detail="Shipment booking failed: excepting this bid would exceed your company's per financial billing cycle spending limits."
                )
        db.add(financial_account)
        db.flush()
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Exchange billing process failed: {str(e)}")

    try:
        pickup_facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == exchange.pickup_facility_id).first()
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pickup appointment query failed: {str(e)}")        

    carrier = db.query(Carrier).filter(
        Carrier.id == bid.carrier_id).first()
    if not carrier:
        raise ValueError("Carrier Not found")
    if not carrier.is_verified:
        raise ValueError("Carrier company account not verified. Please request or await verification.")
    if carrier.status != "Active":
        raise ValueError("Carrier account is not active.")
    
    carrier_financial_account = db.query(CarrierFinancialAccounts).filter(
        CarrierFinancialAccounts.id == bid.carrier_id).first()
    if not carrier_financial_account:
        raise ValueError("Carrier Financial Account Not found")
    if not carrier_financial_account.is_verified:
        raise ValueError("Carrier company Financial Account not verified. Please request or await verification.")
    if carrier_financial_account.status != "Active":
        raise ValueError("Carrier Financial Account is not active.")

    # Step 1: Calculate Distance and Transit Time
    try:
        distance_data = calculate_distance(AddressInput(
            origin_address=exchange.origin_address,
            destination_address=exchange.destination_address
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
            origin_address=exchange.origin_address,
            destination_address=exchange.destination_address,
            start_date=exchange.pickup_date,
            start_time=pickup_facility.end_time,
        ))
        eta_date = trip_data["eta_date"]  # Distance in kilometers
        eta_window = trip_data["eta_window"]  # Transit time as text
        polyline = trip_data["polyline"]
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Trip info calculation failed: {e.detail}")

    def safe_str(val):
        return val.value if hasattr(val, "value") else str(val)

    # Step 1: Create the FTL shipment
    shipment = FTL_SHIPMENT(
        type="FTL",
        trip_type="1 Pickup, 1 Delivery",
        load_type=exchange.load_type,
        shipper_company_id=company_id,
        shipper_user_id=user_id,
        required_truck_type=exchange.required_truck_type,
        equipment_type=exchange.equipment_type,
        trailer_type=exchange.trailer_type,
        trailer_length=exchange.trailer_length,
        minimum_weight_bracket=exchange.minimum_weight_bracket,
        minimum_git_cover_amount=exchange.minimum_git_cover_amount,
        minimum_liability_cover_amount=exchange.minimum_liability_cover_amount,
        origin_address=exchange.origin_address,
        complete_origin_address=exchange.complete_origin_address,
        origin_city_province=exchange.origin_city_province,
        origin_country=exchange.origin_country,
        origin_region=exchange.origin_region,
        destination_address=exchange.destination_address,
        complete_destination_address=exchange.complete_destination_address,
        destination_city_province=exchange.destination_city_province,
        destination_country=exchange.destination_country,
        destination_region=exchange.destination_region,
        pickup_date=exchange.pickup_date,
        priority_level=exchange.priority_level,
        pickup_facility_id=exchange.pickup_facility_id,
        delivery_facility_id=exchange.delivery_facility_id,
        customer_reference_number=exchange.customer_reference_number,
        shipment_weight=exchange.shipment_weight,
        commodity=exchange.commodity,
        temperature_control=exchange.temperature_control,
        hazardous_materials=exchange.hazardous_materials,
        packaging_quantity=exchange.packaging_quantity,
        packaging_type=exchange.packaging_type,
        pickup_number=exchange.pickup_number,
        pickup_notes=exchange.pickup_notes,
        delivery_number=exchange.delivery_number,
        delivery_notes=exchange.delivery_notes,
        estimated_transit_time=exchange.estimated_transit_time,
        distance=exchange.distance,
        quote=bid.baked_bid_amount,
        payment_terms=exchange_loadboard.payment_terms,
        route_preview_embed=exchange.route_preview_embed,
        eta_date=eta_date,
        eta_window=eta_window,
        polyline=polyline,
        pickup_appointment=f"{pickup_facility.start_time}-{pickup_facility.end_time}",
        shipment_status="Assigned",
        trip_status="Scheduled",
        carrier_id=carrier.id,
        carrier_name=f"SADC FREIGHTLINK Sub-contractor {carrier.id}",
        carrier_git_cover_amount=carrier.git_cover_amount,
        carrier_liability_cover_amount=carrier.liability_insurance_cover_amount,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    try:
        shipment_invoice = BillingEngine.create_shipment_invoice(
            company_id=company_id,
            financial_account=financial_account,
            shipment_id=shipment.id,
            shipment_type=shipment.type,
            origin_address=exchange.origin_address,
            destination_address=exchange.destination_address,
            pickup_date=shipment.pickup_date,
            distance=exchange.distance,
            transit_time=exchange.estimated_transit_time,
            total_cost=bid.baked_bid_amount,
            base_amount=bid.baked_bid_amount,
            db=db
        )
        db.add(shipment)

    except Exception as e:
        print(f"🚨 Error generating shipment invoice for shipment {shipment.id} from {exchange.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Shipment invoice generation failed: {e}")
    
     # Step 5: Create the brokerage transaction
    brokerage_transaction = BrokerageLedger(
        shipment_id=shipment.id,
        shipment_type=shipment.type,
        shipper_company_id=company_id,
        shipper_type=shipper.type,
        shipper_company_name=shipper.legal_business_name,
        booking_amount=bid.baked_bid_amount,
        shipment_invoice_id=shipment_invoice.id,
        shipment_invoice_due_date=shipment_invoice.due_date,
        shipment_invoice_status=shipment_invoice.status,
        platform_commission=(bid.baked_bid_amount - bid.bid_amount),
        transaction_fee=0,
        true_platform_earnings=(bid.baked_bid_amount - bid.bid_amount),
        payment_terms=financial_account.payment_terms,
        carrier_payable=bid.bid_amount,
    )
    shipment.invoice_id = shipment_invoice.id
    shipment.invoice_due_date = shipment_invoice.due_date
    shipment.invoice_status = shipment_invoice.status
    db.add(brokerage_transaction)
    db.commit()
    db.refresh(brokerage_transaction)

        # Step 9: Update loadboard status
    exchange.auction_status="Closed"
    exchange.trip_savings = (exchange.suggested_price - bid.baked_bid_amount)
    exchange.exchange_savings = (exchange.offer_price - bid.baked_bid_amount)
    exchange.winning_bid_price = bid.baked_bid_amount
    exchange_loadboard.status="Closed"

    brokerage_transaction.carrier_id=carrier.id
    brokerage_transaction.carrier_company_type=carrier.type
    brokerage_transaction.carrier_company_name=carrier.legal_business_name

    carrier_financial_account.holding_balance= (carrier_financial_account.holding_balance + brokerage_transaction.carrier_payable)

    try:
        load_invoice = Load_Invoice(
            shipment_id = shipment.id,
            shipment_type = shipment.type,
            invoice_type = "Service Invoice",
            billing_date = shipment.pickup_date,
            due_date = shipment.invoice_due_date,
            description = f"{shipment.type} Shipment {shipment.id}",
            status = "Pending",

            carrier_company_id = carrier.id,
            carrier_financial_account_id = carrier.id,
            payment_terms = shipment.payment_terms,
            carrier_bank = carrier_financial_account.bank_name,
            carrier_bank_account = carrier_financial_account.account_number,
            payment_reference = f"{shipment.type} Shipment {shipment.id}",
            carrier_company_name = carrier_financial_account.legal_business_name,
            contact_person_name = f"{carrier_financial_account.directors_first_name} {carrier_financial_account.directors_last_name}",
            carrier_email = carrier.business_email,
            carrier_address = carrier.business_address,
            origin_address = shipment.complete_origin_address,
            destination_address = shipment.complete_destination_address,
            pickup_date = shipment.pickup_date,
            distance = shipment.distance,
            transit_time = shipment.estimated_transit_time,

            base_amount = brokerage_transaction.carrier_payable,
            due_amount = brokerage_transaction.carrier_payable,
        )
        db.add(load_invoice)
        db.flush()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shipment invoice generation failed: {e}")

    # Step 9: Log assignment
    assigned_shipment = Assigned_Spot_Ftl_Shipments(
        shipment_id=shipment.id,
        invoice_id=load_invoice.id,
        invoice_due_date = load_invoice.due_date,
        invoice_status = load_invoice.status,
        trip_type=shipment.trip_type,
        load_type=shipment.load_type,
        carrier_id=carrier.id,
        carrier_name=carrier.legal_business_name,
        minimum_weight_bracket=shipment.minimum_weight_bracket,
        minimum_git_cover_amount=shipment.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment.minimum_liability_cover_amount,
        shipment_rate=brokerage_transaction.carrier_payable,
        distance=shipment.distance,
        rate_per_km=exchange_loadboard.rate_per_km,
        rate_per_ton=exchange_loadboard.rate_per_ton,
        payment_terms=exchange_loadboard.payment_terms,
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
        hazardous_materials=exchange_loadboard.hazardous_materials,
        packaging_quantity=shipment.packaging_quantity,
        packaging_type=shipment.packaging_type,
        pickup_number=shipment.pickup_number,
        pickup_notes=shipment.pickup_notes,
        delivery_number=shipment.delivery_number,
        delivery_notes=shipment.delivery_notes,
        pickup_facility_id=shipment.pickup_facility_id,
        delivery_facility_id=shipment.delivery_facility_id,
        estimated_transit_time=shipment.estimated_transit_time,
        eta_window=eta_window,
        eta_date=eta_date,
        pickup_start_time=pickup_facility.start_time,
        accepted_at=format_datetime_sast(datetime.utcnow().replace(tzinfo=pytz.utc)),
    )
    brokerage_transaction.load_invoice_id = load_invoice.id
    brokerage_transaction.load_invoice_due_date = load_invoice.due_date
    brokerage_transaction.load_invoice_status = load_invoice.status
    db.add(assigned_shipment)
    db.commit()
    try:
        carrier_notification = Carrier_Notification(
            company_id=bid.carrier_id,
            type=f"FTL exchange-{bid.exchange_id} bid accepted",
            message=f"Congratulations your bid of R{bid.baked_bid_amount:.2f} on Exchange ID {bid.exchange_id} has been accepted. FTL Shipment {assigned_shipment.shipment_id} has been assigned to your company.",  
        )
        db.add(carrier_notification)
        db.commit()
    except Exception as e:
        print(f"🚨 Failed to create notification for Carrier {bid.carrier_id}: {e}")
    try:
        client_notification = Client_Notification(
            company_id=bid.carrier_id,
            type=f"FTL exchange-{bid.exchange_id} awarded and closed",
            message=f"Exchange ID-{bid.exchange_id} has been assigned to Carrier {bid.carrier_id} at the bid amount of R{bid.baked_bid_amount:.2f}. FTL Shipment {assigned_shipment.shipment_id} has been created from the Exchange.",  
        )
        db.add(client_notification)
        db.commit()
    except Exception as e:
        print(f"🚨 Failed to create notification for Client {company_id}: {e}")

##############################################################################################################################################
##############################################################################################################################################
##############################################################################################################################################
##############################################################################################################################################

def place_auction_bid(
    id: int,
    bid_data: Create_Shipment_Bid,
    db: Session,
    current_user: dict,
):
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    if not user_id:
        raise HTTPException(status_code=400, detail="User ID missing from authentication token")

    try:
        auction = db.query(Client_Shipment_Auction).filter(
            Client_Shipment_Auction.id == id,
            Client_Shipment_Auction.status == "Active"
        ).first()

        if not auction:
            raise HTTPException(status_code=404, detail="Load not found or bidding is closed")

        if auction.status != "Active":
            raise HTTPException(status_code=400, detail=f"Load is not accepting bids. Current status: {auction.status}")

        auction_loadboard = db.query(Shipment_Auction_Loadboard).filter(
            Shipment_Auction_Loadboard.auction_id == auction.id,
            Shipment_Auction_Loadboard.is_visible_to_carrier == True
        ).first()

        if not auction_loadboard:
            raise HTTPException(status_code=404, detail="Load is not available on the carrier loadboard")

        carrier = db.query(Carrier).filter(
            Carrier.id == company_id
        ).first()

        if not carrier:
            raise HTTPException(status_code=404, detail="Carrier not found")

        if not carrier.is_verified:
            raise HTTPException(status_code=403, detail="Carrier company account not verified, please request account verification")

        if carrier.status != "Active":
            raise HTTPException(status_code=403, detail="Carrier account is not Active, please request account activation")

        if carrier.git_cover_amount is None or carrier.git_cover_amount < auction.minimum_git_cover_amount:
            raise HTTPException(status_code=400, detail=f"Carrier GIT cover amount of 'R{carrier.git_cover_amount or 0}' does not satisfy the tender's required minimum of 'R{auction.minimum_git_cover_amount}'")

        if carrier.liability_insurance_cover_amount is None or carrier.liability_insurance_cover_amount < auction.minimum_liability_cover_amount:
            raise HTTPException(status_code=400, detail=f"Carrier liability cover amount 'R{carrier.liability_insurance_cover_amount or 0}' does not satisfy the tender's required minimum of 'R{auction.minimum_liability_cover_amount}'")

        carrier_profile = db.query(Carrier_Profile).filter(
            Carrier_Profile.carrier_id == carrier.id
        ).first()

        if not carrier_profile:
            raise HTTPException(status_code=400, detail="Carrier profile not found. Please complete your fleet profile before bidding.")

        fleet_fields = [
            "rigid_tautliners",
            "triaxle_tautliners",
            "superlink_tautliners",
            "rigid_flatbeds",
            "triaxle_flatbeds",
            "superlink_flatbeds",
            "rigid_flatbeds_with_twistlocks",
            "triaxle_flatbeds_with_twistlocks",
            "superlink_flatbeds_with_twistlocks",
            "rigid_dropsides",
            "triaxle_dropside",
            "superlink_dropside",
            "triaxle_skeletals",
            "superlink_skeletals",
            "rigid_pantechs",
            "triaxle_pantechs",
            "triaxle_side_tippers",
            "superlink_side_tippers",
            "low_beds",
            "rigid_end_tipper",
            "triaxle_end_tipper"
        ]

        fleet_size = sum((getattr(carrier_profile, field) or 0) for field in fleet_fields)

        if fleet_size <= 0:
            raise HTTPException(status_code=400, detail="Carrier fleet profile contains no vehicles")

        if bid_data.rate is None:
            raise HTTPException(status_code=400, detail="Bid per shipment is required")

        if bid_data.rate <= 0:
            raise HTTPException(status_code=400, detail="Bid per shipment must be greater than zero")

        existing_bid = db.query(Shipment_Auction_Bid).filter(
            Shipment_Auction_Bid.auction_id == auction.id,
            Shipment_Auction_Bid.carrier_id == carrier.id
        ).first()

        if existing_bid:
            raise HTTPException(status_code=400, detail="You have already placed a bid on this load exchange")

        bid = Shipment_Auction_Bid(
            auction_id=auction.id,
            carrier_id=carrier.id,
            bidder_user_id=user_id,
            carrier_name=carrier.legal_business_name,
            fleet_size=fleet_size,
            primary_lanes=carrier_profile.primary_routes,
            rate=bid_data.rate,
            number_of_loads=bid_data.number_of_loads,
            lead_time=bid_data.lead_time,
            bid_notes=bid_data.bid_notes,
            status="Submitted"
        )

        db.add(bid)
        db.commit()
        db.refresh(bid)

        return {
            "message": "Load exchange bid submitted successfully",
            "bid_id": bid.id,
            "auction_id": auction.id,
            "carrier_id": carrier.id,
            "rate": float(bid.rate),
            "number_of_loads": bid.number_of_loads,
            "lead_time": bid.lead_time,
            "status": bid.status
        }

    except HTTPException:
        # Re-raise standard HTTP exceptions safely 
        raise
    except Exception as e:
        # FIXED: Roll back the DB session instead of bid_data
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

def place_tender_bid(
    db: Session,
    bid_data: Create_Tender_Bid,
    current_user: dict
):
    # ============================================================
    # 1. CURRENT USER
    # ============================================================

    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="User ID missing from authentication token"
        )

    # ============================================================
    # 2. GET ACTIVE TENDER
    # ============================================================

    tender = db.query(Lane_Tender_RFQ).filter(
        Lane_Tender_RFQ.id == bid_data.tender_id,
        Lane_Tender_RFQ.is_active == True
    ).first()

    if not tender:
        raise HTTPException(
            status_code=404,
            detail="Tender not found or bidding is closed"
        )

    if tender.status != "Active":
        raise HTTPException(
            status_code=400,
            detail=f"Tender is not accepting bids. Current status: {tender.status}"
        )

    # ============================================================
    # 3. VERIFY TENDER LOADBOARD
    # ============================================================

    tender_loadboard = db.query(Lane_Tender_Loadboard).filter(
        Lane_Tender_Loadboard.tender_id == tender.id,
        Lane_Tender_Loadboard.is_visible_to_carrier == True
    ).first()

    if not tender_loadboard:
        raise HTTPException(
            status_code=404,
            detail="Tender is not available on the carrier loadboard"
        )

    # ============================================================
    # 4. GET CARRIER
    # ============================================================

    carrier = db.query(Carrier).filter(
        Carrier.id == company_id
    ).first()

    if not carrier:
        raise HTTPException(
            status_code=404,
            detail="Carrier not found"
        )

    if not carrier.is_verified:
        raise HTTPException(
            status_code=403,
            detail=(
                "Carrier company account not verified, "
                "please request account verification"
            )
        )

    if carrier.status != "Active":
        raise HTTPException(
            status_code=403,
            detail=(
                "Carrier account is not Active, "
                "please request account activation."
            )
        )

    # ============================================================
    # 5. VALIDATE CARRIER INSURANCE
    # ============================================================

    if (
        carrier.git_cover_amount is None
        or carrier.git_cover_amount < tender.minimum_git_cover_amount
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Carrier GIT cover amount of "
                f"'R{carrier.git_cover_amount or 0}' does not satisfy "
                f"the tender's required minimum of "
                f"'R{tender.minimum_git_cover_amount}'"
            )
        )

    if (
        carrier.liability_insurance_cover_amount is None
        or carrier.liability_insurance_cover_amount
        < tender.minimum_liability_cover_amount
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Carrier liability cover amount "
                f"'R{carrier.liability_insurance_cover_amount or 0}' "
                f"does not satisfy the tender's required minimum of "
                f"'R{tender.minimum_liability_cover_amount}'"
            )
        )

    # ============================================================
    # 6. GET CARRIER PROFILE
    # ============================================================

    carrier_profile = db.query(Carrier_Profile).filter(
        Carrier_Profile.carrier_id == carrier.id
    ).first()

    if not carrier_profile:
        raise HTTPException(
            status_code=400,
            detail="Carrier profile not found. Please complete your fleet profile before bidding."
        )

    # ============================================================
    # 7. CALCULATE FLEET SIZE
    # ============================================================

    fleet_fields = [
        "rigid_tautliners",
        "triaxle_tautliners",
        "superlink_tautliners",
        "rigid_flatbeds",
        "triaxle_flatbeds",
        "superlink_flatbeds",
        "rigid_flatbeds_with_twistlocks",
        "triaxle_flatbeds_with_twistlocks",
        "superlink_flatbeds_with_twistlocks",
        "rigid_dropsides",
        "triaxle_dropside",
        "superlink_dropside",
        "triaxle_skeletals",
        "superlink_skeletals",
        "rigid_pantechs",
        "triaxle_pantechs",
        "triaxle_side_tippers",
        "superlink_side_tippers",
        "low_beds",
        "rigid_end_tipper",
        "triaxle_end_tipper"
    ]

    fleet_size = sum(
        (getattr(carrier_profile, field) or 0)
        for field in fleet_fields
    )

    if fleet_size <= 0:
        raise HTTPException(
            status_code=400,
            detail="Carrier fleet profile contains no vehicles"
        )

    # ============================================================
    # 8. VALIDATE BID RATE
    # ============================================================

    if bid_data.bid_per_shipment is None:
        raise HTTPException(
            status_code=400,
            detail="Bid per shipment is required"
        )

    if bid_data.bid_per_shipment <= 0:
        raise HTTPException(
            status_code=400,
            detail="Bid per shipment must be greater than zero"
        )

    # ============================================================
    # 9. VALIDATE SLOTS PER INTERVAL
    # ============================================================

    if bid_data.slots_per_interval is None:
        raise HTTPException(
            status_code=400,
            detail="Slots per interval is required"
        )

    if bid_data.slots_per_interval <= 0:
        raise HTTPException(
            status_code=400,
            detail="Slots per interval must be greater than zero"
        )

    # ============================================================
    # 10. GET VOLUME PROFILES
    # ============================================================

    volume_profiles = db.query(
        Lane_Tender_RFQ_Volume_Profile
    ).filter(
        Lane_Tender_RFQ_Volume_Profile.tender_id == tender.id
    ).order_by(
        Lane_Tender_RFQ_Volume_Profile.period_sequence
    ).all()

    if not volume_profiles:
        raise HTTPException(
            status_code=400,
            detail="Tender does not contain a volume profile"
        )

    # ============================================================
    # 11. DETERMINE NUMBER OF CONTRACT INTERVALS
    # ============================================================

    number_of_intervals = len(volume_profiles)

    # ============================================================
    # 12. CALCULATE PER-SLOT SIZE
    #
    # Example:
    #
    # 4 weekly volume profiles
    # 2 slots per interval
    #
    # 2 × 4 = 8
    #
    # Therefore this bid represents 8 total contract slots.
    # ============================================================

    per_slot_size = (
        bid_data.slots_per_interval
        * number_of_intervals
    )

    if per_slot_size <= 0:
        raise HTTPException(
            status_code=400,
            detail="Unable to calculate contract slot size"
        )

    # ============================================================
    # 13. CALCULATE TOTAL CONTRACT BID
    #
    # Example:
    #
    # R10,000 per shipment
    # × 8 contract slots
    # = R80,000
    # ============================================================

    total_contract_bid = (
        bid_data.bid_per_shipment
        * per_slot_size
    )

    # ============================================================
    # 14. CREATE BID
    # ============================================================

    bid = Lane_Tender_RFQ_Bids(
        tender_id=tender.id,
        carrier_id=carrier.id,
        bidder_user_id=user_id,
        carrier_name=carrier.legal_business_name,
        fleet_size=fleet_size,
        primary_lanes=carrier_profile.primary_routes,
        bid_per_shipment=bid_data.bid_per_shipment,
        slots_per_interval=bid_data.slots_per_interval,
        per_slot_size=per_slot_size,
        bid_notes=bid_data.bid_notes,
        status="Submitted"
    )

    # ============================================================
    # 15. SAVE
    # ============================================================

    db.add(bid)
    db.commit()
    db.refresh(bid)

    # ============================================================
    # 16. RESPONSE
    # ============================================================

    return {
        "message": "Tender bid submitted successfully",
        "bid_id": bid.id,
        "tender_id": tender.id,
        "carrier_id": carrier.id,
        "bid_per_shipment": float(bid.bid_per_shipment),
        "slots_per_interval": bid.slots_per_interval,
        "number_of_intervals": number_of_intervals,
        "per_slot_size": bid.per_slot_size,
        "total_contract_bid": float(total_contract_bid),
        "fleet_size": fleet_size,
        "status": bid.status
    }