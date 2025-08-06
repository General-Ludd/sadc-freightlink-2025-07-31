from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE
from models.Exchange.auction import Exchange_FTL_Lane_Bid, Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, CarrierFinancialAccounts, Dedicated_Lane_BrokerageLedger, FinancialAccounts, Interim_Invoice, Lane_Interim_Invoice, Lane_Invoice, Load_Invoice
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Lane_LoadBoard, Exchange_Ftl_Load_Board, Exchange_Power_Load_Board
from models.carrier import Carrier
from models.shipper import Corporation
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.vehicle import Vehicle
from schemas.exchange_bookings.auction import Accept_Bid, Exchange_FTL_Lane_Bid_Create, Exchange_FTL_Shipment_Bid_Create, Exchange_POWER_Shipment_Bid_Create
from services.brokerage.carrier_loadboard_service import calculate_rates
from utils.billing import BillingEngine

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
        raise HTTPException(status_code=500, detail=f"Exhange billing process failed: {str(e)}")

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
        shipment_invoice = BillingEngine.generate_shipment_invoice(
            shipment_id=shipment.id,
            shipment_type=shipment.type,
            pickup_date=shipment.pickup_date,
            due_date=BillingEngine.get_next_due_date(shipment.pickup_date, financial_account.payment_terms),
            amount=bid.baked_bid_amount,
            company_id=company_id,
            payment_terms=financial_account.payment_terms,
            #New
            description=f"FTL Shipment {shipment.id}",
            business_name=shipper.legal_business_name,
            contact_person_name=f"{financial_account.directors_first_name}-{financial_account.directors_last_name}",
            business_email=shipper.business_email,
            billing_address=shipper.business_address,
            db=db
        )

        shipment.invoice_id = shipment_invoice.id
        shipment.invoice_due_date = shipment_invoice.due_date
        shipment.invoice_status = shipment_invoice.status
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
    db.add(brokerage_transaction)
    db.commit()
    db.refresh(brokerage_transaction)

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

        # Step 9: Update loadboard status
    exchange.auction_status="Closed"
    exchange.trip_savings = (exchange.suggested_price - bid.baked_bid_amount)
    exchange.exchange_savings = (exchange.offer_price - bid.baked_bid_amount)
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
        estimated_transit_time=shipment.estimated_transit_time
    )
    brokerage_transaction.load_invoice_id = load_invoice.id
    brokerage_transaction.load_invoice_due_date = load_invoice.due_date
    brokerage_transaction.load_invoice_status = load_invoice.status
    db.add(assigned_shipment)
    db.commit()

def place_power_shipment_bid(db: Session, bid_data: Exchange_POWER_Shipment_Bid_Create, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    exchange = db.query(POWER_SHIPMENT_EXCHANGE).filter(
        POWER_SHIPMENT_EXCHANGE.id == bid_data.exchange_id,
        POWER_SHIPMENT_EXCHANGE.auction_status == "Open"
    ).first()
    if not exchange:
        raise ValueError("Exchange not found, or Exchange bidding closed")
    if exchange.auction_status !="Open":
        raise ValueError("Exchange bidding closed")

    exchange_loadboard = db.query(Exchange_Power_Load_Board).filter(
        Exchange_Power_Load_Board.exchange_id == bid_data.exchange_id,
        Exchange_Power_Load_Board.status == "Open"
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
    existing_bids = db.query(Exchange_POWER_Shipment_Bid).filter(
        Exchange_POWER_Shipment_Bid.exchange_id == bid_data.exchange_id
    ).all()

    baked_bid = bid_data.bid_amount * 1.10

    # Determine if this bid is the lowest
    is_lowest_bid = all(bid_data.bid_amount < existing_bid.bid_amount for existing_bid in existing_bids)

    # Set status based on comparison
    new_bid_status = "Placed" if is_lowest_bid else "Outbidded"

    # Create the new bid
    bid = Exchange_POWER_Shipment_Bid(
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
        db.query(Exchange_POWER_Shipment_Bid).filter(
            Exchange_POWER_Shipment_Bid.exchange_id == bid_data.exchange_id,
            Exchange_POWER_Shipment_Bid.id != bid.id  # exclude the new bid itself
        ).update(
            {"status": "Outbidded"},
            synchronize_session=False
        )
        exchange.leading_bid_id = bid.id
        exchange.leading_bid_amount = baked_bid
        db.commit()

    return bid


def accept_power_shipment_exchange_bid(db: Session, bid_data: Accept_Bid, current_user:dict):
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
    bid = db.query(Exchange_POWER_Shipment_Bid).filter(
        Exchange_POWER_Shipment_Bid.id == bid_data.bid_id
    ).first()

    # Fetch existing bids for comparison
    bid_verification = db.query(Exchange_POWER_Shipment_Bid).filter(
        Exchange_POWER_Shipment_Bid.exchange_id == bid.exchange_id
    ).all()

    carrier = db.query(Carrier).filter(Carrier.id == bid.carrier_id).first()
    if not carrier:
        raise ValueError("Carrier account not found")

    exchange = db.query(POWER_SHIPMENT_EXCHANGE).filter(
        POWER_SHIPMENT_EXCHANGE.id == bid.exchange_id,
    ).first()
    if not exchange:
        raise ValueError("Exchange not found.")
    if exchange.auction_status !="Open":
        raise ValueError("Exchange bidding closed.")
    
    exchange_loadboard = db.query(Exchange_Power_Load_Board).filter(
        Exchange_Power_Load_Board.exchange_id == bid.exchange_id
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
        raise HTTPException(status_code=500, detail=f"Exhange billing process failed: {str(e)}")

    # Step 1: Create the FTL shipment
    shipment = POWER_SHIPMENT(
        type="POWER",
        trip_type="1 Pickup, 1 Delivery",
        load_type=exchange.load_type,
        shipper_company_id=company_id,
        shipper_user_id=user_id,
        required_truck_type=exchange.required_truck_type,
        axle_configuration=exchange.axle_configuration,
        trailer_id=exchange.trailer_id,
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
        shipment_invoice = BillingEngine.generate_shipment_invoice(
            shipment_id=shipment.id,
            shipment_type=shipment.type,
            pickup_date=shipment.pickup_date,
            due_date=BillingEngine.get_next_due_date(shipment.pickup_date, financial_account.payment_terms),
            amount=bid.baked_bid_amount,
            company_id=company_id,
            payment_terms=financial_account.payment_terms,
            #New
            description=f"POWER Shipment {shipment.id}",
            business_name=shipper.legal_business_name,
            contact_person_name=f"{financial_account.directors_first_name}-{financial_account.directors_last_name}",
            business_email=shipper.business_email,
            billing_address=shipper.business_address,
            db=db
        )
        shipment.invoice_id = shipment_invoice.id
        shipment.invoice_due_date = shipment_invoice.due_date
        shipment.invoice_status = shipment_invoice.status
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
    db.add(brokerage_transaction)
    db.commit()
    db.refresh(brokerage_transaction)

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

        # Step 9: Update loadboard status
    exchange.auction_status="Closed"
    exchange.trip_savings = (exchange.suggested_rate - bid.baked_bid_amount)
    exchange.exchange_savings = (exchange.offer_rate - bid.baked_bid_amount)
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
    assigned_shipment = Assigned_Power_Shipments(
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
        axle_configuration=shipment.axle_configuration,
        trailer_id=shipment.trailer_id,
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
        estimated_transit_time=shipment.estimated_transit_time
    )
    brokerage_transaction.load_invoice_id = load_invoice.id
    brokerage_transaction.load_invoice_due_date = load_invoice.due_date
    brokerage_transaction.load_invoice_status = load_invoice.status
    db.add(assigned_shipment)
    db.commit()

def place_ftl_lane_bid(db: Session, bid_data: Exchange_FTL_Lane_Bid_Create, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    exchange = db.query(FTL_Lane_Exchange).filter(
        FTL_Lane_Exchange.id == bid_data.exchange_id,
        FTL_Lane_Exchange.auction_status == "Open"
    ).first()
    if not exchange:
        raise ValueError("Exchange not found, or Exchange bidding closed")
    if exchange.auction_status !="Open":
        raise ValueError("Exchange bidding closed")

    exchange_loadboard = db.query(Exchange_Ftl_Lane_LoadBoard).filter(
        Exchange_Ftl_Lane_LoadBoard.exchange_id == bid_data.exchange_id,
        Exchange_Ftl_Lane_LoadBoard.status == "Open"
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

    fleet_size_verification = db.query(Vehicle).filter(Vehicle.owner_id == company_id,
                                                  Vehicle.type == exchange.required_truck_type,
                                                  Vehicle.equipment_type == exchange.equipment_type,
                                                  Vehicle.trailer_type == exchange.trailer_type,
                                                  Vehicle.trailer_length == exchange.trailer_length,
                                                  Vehicle.payload_capacity >= exchange.minimum_weight_bracket,
                                                  Vehicle.is_verified.is_(True)).count()
    try:
        assert fleet_size_verification >= exchange.shipments_per_interval, f"Carrier fleet size of (fleet_size_verification) does not meet the exchange lane's fleet size requirement of {exchange.shipments_per_interval} ({exchange.required_truck_type}-{exchange.trailer_length}-{exchange.trailer_type}-{exchange.equipment_type}'s) to be provided on a per interval basis"
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
    existing_bids = db.query(Exchange_FTL_Lane_Bid).filter(
        Exchange_FTL_Lane_Bid.exchange_id == bid_data.exchange_id
    ).all()

    baked_bid = bid_data.per_shipment_bid_amount * 1.10

    # Determine if this bid is the lowest
    is_lowest_bid = all(bid_data.per_shipment_bid_amount < existing_bid.per_shipment_bid_amount for existing_bid in existing_bids)

    # Set status based on comparison
    new_bid_status = "Placed" if is_lowest_bid else "Outbidded"

    # Create the new bid
    bid = Exchange_FTL_Lane_Bid(
        exchange_id=bid_data.exchange_id,
        carrier_id=company_id,
        carrier_type=carrier.type,
        carrier_name=carrier.legal_business_name,
        user_id=user_id,
        per_shipment_bid_amount=bid_data.per_shipment_bid_amount,
        contract_bid_amount=(bid_data.per_shipment_bid_amount * exchange.total_shipments),
        baked_per_shipment_bid_amount=baked_bid,
        baked_contract_bid_amount=(baked_bid * exchange.total_shipments),
        bid_notes=bid_data.bid_notes,
        status=new_bid_status
    )
    exchange.number_of_bids_submitted = (exchange.number_of_bids_submitted or 0) + 1
    db.add(bid)
    db.commit()
    db.refresh(bid)

    # If this is the new lowest bid, update all other bids to Outbidded
    if is_lowest_bid:
        db.query(Exchange_FTL_Lane_Bid).filter(
            Exchange_FTL_Lane_Bid.exchange_id == bid_data.exchange_id,
            Exchange_FTL_Lane_Bid.id != bid.id  # exclude the new bid itself
        ).update(
            {"status": "Outbidded"},
            synchronize_session=False
        )
        exchange.leading_bid_id = bid.id
        exchange.leading_per_shipment_bid_amount = baked_bid
        exchange.leading_contract_bid_amount = (baked_bid * exchange.total_shipments)
        db.commit()

    return bid


def accept_a_ftl_lane_exchange_bid(db: Session, bid_data: Accept_Bid, current_user:dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")
    if not company_id:
        raise ValueError("User does not belong to a company")
    
    shipper = db.query(Corporation).filter(Corporation.id == company_id).first()
    if not shipper:
        raise ValueError("Shipper Account not verified, or not Active")
    if shipper.status != "Active":
        raise ValueError("Shipper Account is not activated")
    if not shipper.is_verified:
        raise ValueError("Shipper Account is not verified")

    # Fetch existing bids for comparison
    bid = db.query(Exchange_FTL_Lane_Bid).filter(
        Exchange_FTL_Lane_Bid.id == bid_data.bid_id
    ).first()

    # Fetch existing bids for comparison
    bid_verification = db.query(Exchange_FTL_Lane_Bid).filter(
        Exchange_FTL_Lane_Bid.exchange_id == bid.exchange_id
    ).all()

    carrier = db.query(Carrier).filter(Carrier.id == bid.carrier_id).first()
    if not carrier:
        raise ValueError("Carrier account not found")

    exchange = db.query(FTL_Lane_Exchange).filter(
        FTL_Lane_Exchange.id == bid.exchange_id,
    ).first()
    if not exchange:
        raise ValueError("Exchange not found.")
    if exchange.auction_status !="Open":
        raise ValueError("Exchange bidding closed.")
    
    exchange_loadboard = db.query(Exchange_Ftl_Lane_LoadBoard).filter(
        Exchange_Ftl_Lane_LoadBoard.exchange_id == bid.exchange_id
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
        all_payment_dates = BillingEngine.get_billing_dates(
             start_date=exchange.start_date,
             end_date=exchange.end_date,
             term=financial_account.payment_terms
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment schedule generation failed: {str(e)}")

    # Step 6: Create the FTL Shipment
    shipment = FTL_Lane(
        type="FTL Lane",
        load_type=exchange.load_type,
        trip_type="1 Pickup, 1 Delivery",
        shipper_company_id=company_id,
        shipper_user_id=user_id,
        payment_terms=exchange.payment_terms,
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
        priority_level=exchange.priority_level,
        pickup_facility_id=exchange.id,
        delivery_facility_id=exchange.id,
        customer_reference_number=exchange.customer_reference_number,
        average_shipment_weight=exchange.average_shipment_weight,
        commodity=exchange.commodity,
        temperature_control=exchange.temperature_control,
        hazardous_materials=exchange.hazardous_materials,
        packaging_quantity=exchange.packaging_quantity,
        packaging_type=exchange.packaging_type,
        pickup_number=exchange.pickup_number,
        pickup_notes=exchange.pickup_notes,
        delivery_number=exchange.delivery_number,
        delivery_notes=exchange.delivery_notes,
        estimated_transit_time=exchange.estimated_transit_time,  # Assign directly
        distance=exchange.distance,
        route_preview_embed=exchange.route_preview_embed,
        qoute_per_shipment=bid.baked_per_shipment_bid_amount,
        contract_quote=bid.baked_contract_bid_amount,
        recurrence_frequency=exchange.recurrence_frequency,
        recurrence_days=exchange.recurrence_days,
        skip_weekends=exchange.skip_weekends,
        shipments_per_interval=exchange.shipments_per_interval,
        start_date=exchange.start_date,
        end_date=exchange.end_date,
        total_shipments=exchange.total_shipments,  # Add total shipments to the shipment record
        payment_dates=exchange.payment_dates,  # Add payment dates to the shipment record
        shipment_dates=exchange.shipment_dates,
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
            total_shipments_quote=bid.baked_contract_bid_amount,
            payment_terms=exchange.payment_terms,
            due_date=last_billing_date,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contract invoice generation failed: {str(e)}")

#################Create Interim Invoices#####################
    try:
        amount_per_invoice = round(bid.baked_contract_bid_amount / len(all_payment_dates), 2)

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
    for pickup_date in exchange.shipment_dates:
        for _ in range(exchange.shipments_per_interval):
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
            
            shipper_sub_shipment = FTL_SHIPMENT(
                is_subshipment=True,
                dedicated_lane_id=shipment.id,
                type="FTL",
                trip_type="1 Pickup - 1 Drop Off",
                load_type=exchange.load_type,
                shipper_company_id=company_id,
                shipper_user_id=user_id,
                payment_terms=financial_account.payment_terms,
                invoice_id=None,  # Set after invoice is created
                invoice_status="Pending",
                minimum_git_cover_amount=exchange.minimum_git_cover_amount,
                minimum_liability_cover_amount=exchange.minimum_liability_cover_amount,
                required_truck_type=exchange.required_truck_type,
                equipment_type=exchange.equipment_type,
                trailer_type=exchange.trailer_type,
                trailer_length=exchange.trailer_length,
                minimum_weight_bracket=exchange.minimum_weight_bracket,
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
                pickup_date=pickup_date,
                priority_level=exchange.priority_level,
                pickup_facility_id=exchange.id,
                delivery_facility_id=exchange.id,
                customer_reference_number=exchange.customer_reference_number,
                shipment_weight=exchange.average_shipment_weight,
                commodity=exchange.commodity,
                temperature_control=exchange.temperature_control,
                hazardous_materials=exchange.hazardous_materials,
                packaging_quantity=exchange.packaging_quantity,
                packaging_type=exchange.packaging_type,
                pickup_number=exchange.pickup_number,
                pickup_notes=exchange.pickup_notes,
                delivery_number=exchange.delivery_number,
                delivery_notes=exchange.delivery_notes,
                distance=exchange.distance,
                estimated_transit_time=exchange.estimated_transit_time,
                quote=bid.baked_per_shipment_bid_amount,
                route_preview_embed=exchange.route_preview_embed,
                shipment_status="Assigned",
                trip_status="Scheduled"
            )
            db.add(shipper_sub_shipment)
            db.flush()

            try:
                shipment_invoice = BillingEngine.generate_shipment_invoice(
                    contract_id=shipment.id,
                    contract_type=shipment.type,
                    parent_invoice_id=parent_invoice.id,
                    shipment_id=shipper_sub_shipment.id,
                    shipment_type=shipper_sub_shipment.type,
                    pickup_date=pickup_date,
                    due_date=parent_invoice.due_date,
                    amount=bid.baked_per_shipment_bid_amount,
                    company_id=company_id,
                    payment_terms=financial_account.payment_terms,
                    #New
                    description=f"FTL Shipment {shipper_sub_shipment.id}",
                    business_name=shipper.legal_business_name,
                    contact_person_name=f"{financial_account.directors_first_name}-{financial_account.directors_last_name}",
                    business_email=shipper.business_email,
                    billing_address=shipper.business_address,
                    db=db
                )

                shipper_sub_shipment.invoice_id = shipment_invoice.id
                shipper_sub_shipment.invoice_due_date = shipment_invoice.due_date
                shipper_sub_shipment.invoice_status = shipment_invoice.status
                shipment.invoice_id = contract_invoice.id
                shipment.invoice_status = contract_invoice.status
                shipment.invoice_due_date = contract_invoice.due_date
                db.add(shipment_invoice)

            except Exception as e:
                print(f"🚨 Error generating shipment invoice for sub-shipment {shipper_sub_shipment.id}: {e}")
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
        contract_booking_amount=bid.baked_contract_bid_amount,
        contract_platform_commission=(bid.baked_contract_bid_amount - bid.contract_bid_amount),
        contract_transaction_fee=0,
        contract_true_platform_earnings=(bid.baked_contract_bid_amount - bid.contract_bid_amount),
        contract_carrier_payable=bid.contract_bid_amount,
        payment_terms=financial_account.payment_terms,
        payment_dates=all_payment_dates,
        lane_status="Assigned",
        lane_minimum_git_cover_amount=shipment.minimum_git_cover_amount,
        lane_minimum_liability_cover_amount=shipment.minimum_liability_cover_amount,
        contract_start_date=shipment.start_date,
        contract_end_date=shipment.end_date,
        total_shipments=exchange.total_shipments,
        booking_amount_per_shipment=bid.baked_per_shipment_bid_amount,
        platform_commission_per_shipment=(bid.baked_per_shipment_bid_amount - bid.per_shipment_bid_amount),
        transaction_fee_per_shipment=0,
        true_platform_earnings_per_shipment=(bid.baked_per_shipment_bid_amount - bid.per_shipment_bid_amount),
        carrier_payable_per_shipment=bid.per_shipment_bid_amount,
    )
    exchange.auction_status="Closed"
    exchange_loadboard.status="Closed"
    db.add(brokerage_ledger_entry)
    db.commit()
    db.refresh(brokerage_ledger_entry)

    # Step 4: Carrier
    carrier = db.query(Carrier).filter(Carrier.id == bid.carrier_id).first()
    if not carrier:
        raise HTTPException(status_code=400, detail="Carrier not found.")
    if not carrier.is_verified:
        raise HTTPException(status_code=400, detail="Carrier account not verified, please await verification in order to be able to accept shipments")
    if carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier account not active, please await account activation in order to be able to accept shipments")
    
    try:
        assert carrier.git_cover_amount >= exchange.minimum_git_cover_amount, "Carrier GIT Cover Amount does not meet shipment GIT cover amount requirement"
        assert carrier.liability_insurance_cover_amount >= exchange.minimum_liability_cover_amount, "Carrier Liability Cover Amount does not meet shipment Liability cover amount requirement"
        assert carrier.number_of_vehicles >= exchange.shipments_per_interval, "Carrier fleet size does not satisfy the contract lane's required number of vehicle per interval."
    except AssertionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Step 3: Retrieve Financial Account & Generate Payment Dates Based on Terms
    carrier_financial_account = db.query(CarrierFinancialAccounts).filter(
        CarrierFinancialAccounts.id == bid.carrier_id
    ).first()
    if not carrier_financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found.")
    if not carrier_financial_account.is_verified:
        raise HTTPException(status_code=403, detail="Financial account is not verified, Please await verification to accept shipments.")
    if carrier_financial_account.status != "Active":
        raise HTTPException(status_code=403, detail="Financial account is not active, Please await activation to accept shipments.")

    # Assign lane + ledger
    shipment.carrier_id = carrier.id
    shipment.carrier_fleet_size = carrier.number_of_vehicles
    shipment.carrier_git_cover_amount = carrier.git_cover_amount
    shipment.carrier_liability_cover_amount = carrier.liability_insurance_cover_amount

    brokerage_ledger_entry.carrier_id = carrier.id
    brokerage_ledger_entry.carrier_company_name = carrier.legal_business_name
    brokerage_ledger_entry.carrier_company_registration_number = carrier.business_registration_number
    brokerage_ledger_entry.carrier_country_of_incorporation = carrier.country_of_incorporation
    brokerage_ledger_entry.carrier_fleet_size = carrier.number_of_vehicles

    # Step 6: Calculate rates for LoadBoardEntry
    rate_per_km, rate_per_ton = calculate_rates(
        carrier_payable=bid.per_shipment_bid_amount,
        distance=exchange.distance,
        minimum_weight_bracket=exchange.minimum_weight_bracket,  # Example weight, can be adjusted dynamically
    )

    assigned_lane = Assigned_Ftl_Lanes(
        lane_id=shipment.id,
        type=shipment.type,
        trip_type=exchange.trip_type,
        load_type=shipment.load_type,
        carrier_id=carrier.id,
        carrier_name=carrier.legal_business_name,
        contract_rate=bid.contract_bid_amount,
        rate_per_shipment=bid.per_shipment_bid_amount,
        payment_terms=exchange.payment_terms,
        payment_dates=exchange.payment_dates,
        complete_origin_address=exchange.complete_origin_address,
        complete_destination_address=exchange.complete_destination_address,
        distance=exchange.distance,
        rate_per_km=rate_per_km,
        rate_per_ton=rate_per_ton,
        minimum_git_cover_amount=exchange.minimum_git_cover_amount,
        minimum_liability_cover_amount=exchange.minimum_liability_cover_amount,
        status="Assigned",
        recurrence_frequency=exchange.recurrence_frequency,
        recurrence_days=exchange.recurrence_days,
        skip_weekends=exchange.skip_weekends,
        shipments_per_interval=exchange.shipments_per_interval,
        total_shipments=exchange.total_shipments,
        start_date=exchange.start_date,
        end_date=exchange.end_date,
        shipment_dates=exchange.shipment_dates,
        required_truck_type=exchange.required_truck_type,
        equipment_type=exchange.equipment_type,
        trailer_type=exchange.trailer_type,
        trailer_length=exchange.trailer_length,
        minimum_weight_bracket=exchange.minimum_weight_bracket,
        pickup_appointment=f"{exchange_loadboard.pickup_start_time} - {exchange_loadboard.pickup_end_time}",
        origin_address=exchange.origin_address,
        origin_city_province=exchange.origin_city_province,
        origin_country=exchange.origin_country,
        origin_region=exchange.origin_region,
        delivery_appointment=f"{exchange_loadboard.delivery_start_time} - {exchange_loadboard.delivery_end_time}",
        destination_address=exchange.destination_address,
        destination_city_province=exchange.destination_city_province,
        destination_country=exchange.destination_country,
        destinationn_region=exchange.destination_country,
        route_preview_embed=exchange.route_preview_embed,
        priority_level=exchange.priority_level,
        customer_reference_number=exchange.customer_reference_number,
        average_shipment_weight=exchange.average_shipment_weight,
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
        pickup_facility_id=exchange.pickup_facility_id,
        delivery_facility_id=exchange.delivery_facility_id,
    )
    db.add(assigned_lane)
    db.flush()

    brokerage_ledger = db.query(Dedicated_Lane_BrokerageLedger).filter(
        Dedicated_Lane_BrokerageLedger.contract_id == shipment.id,
        Dedicated_Lane_BrokerageLedger.lane_type == shipment.type
    ).first()
    if not brokerage_ledger:
        raise HTTPException(status_code=404, detail="Shipment not found in Brokerage Ledger")

    lane_invoice = Lane_Invoice(
        contract_id=shipment.id,
        lane_type=assigned_lane.type,
        invoice_type="Lane Invoice",
        billing_date=assigned_lane.start_date,
        due_date=assigned_lane.end_date,
        description=f"{assigned_lane.type} Lane {assigned_lane.id}",
        status="Pending",
        company_id=carrier.id,
        carrier_company_name=carrier.legal_business_name,
        contact_person_name=f"{carrier_financial_account.directors_first_name} {carrier_financial_account.directors_last_name}",
        business_email=carrier.business_email,
        business_address=carrier.business_address,
        carrier_financial_account_id=carrier.id,
        payment_terms=assigned_lane.payment_terms,
        carrier_bank=carrier_financial_account.bank_name,
        carrier_bank_account=carrier_financial_account.account_number,
        payment_reference=f"{assigned_lane.type} Lane {assigned_lane.id}",
        base_amount=bid.contract_bid_amount,
        due_amount=bid.contract_bid_amount
    )
    db.add(lane_invoice)
    db.flush()

    # Step 1: Generate Lane Interim Invoices
    booking_interim_invoices: List[Interim_Invoice] =  db.query(Interim_Invoice).filter(
        Interim_Invoice.contract_id == shipment.id,
        Interim_Invoice.contract_type == shipment.type
    ).all()

    lane_interim_invoices: List[Lane_Interim_Invoice] = []
    for booking_invoice in booking_interim_invoices:
        original_due = booking_invoice.due_date
        new_due = booking_invoice.billing_date

        interim = Lane_Interim_Invoice(
            contract_id=shipment.id,
            contract_type=shipment.type,
            is_subinvoice=True,
            description=f"Lane Interim Invoice for Contract Invoice {shipment.id}",
            status="Pending",
            billing_date=booking_invoice.billing_date,
            original_due_date=original_due,
            due_date=new_due,
            carrier_company_id=carrier.id,
            carrier_name=carrier.legal_business_name,
            carrier_email=carrier.business_email,
            carrier_address=carrier.business_address,
            carrier_financial_account_id=carrier_financial_account.id,
            invoice_payment_terms=shipment.payment_terms,
            carrier_bank=carrier_financial_account.bank_name,
            carrier_bank_account=carrier_financial_account.account_number,
            payment_reference=f"Lane Interim Invoice for Contract Invoice {shipment.id}",
            base_amount=(bid.contract_bid_amount / len(all_payment_dates)),
            due_amount=(bid.contract_bid_amount / len(all_payment_dates)),
        )
        brokerage_ledger_entry.carrier_lane_invoice_id = lane_invoice.id
        brokerage_ledger_entry.carrier_lane_invoice_due_date = lane_invoice.due_date
        brokerage_ledger_entry.carrier_lane_invoice_status = lane_invoice.status
        carrier_financial_account.holding_balance += bid.contract_bid_amount
        db.add(interim)
        lane_interim_invoices.append(interim)

    db.flush()

    # Step 2: Assign sub-shipments + Generate Load Invoices
    sub_shipments = db.query(FTL_SHIPMENT).filter(
        FTL_SHIPMENT.dedicated_lane_id == shipment.id,
        FTL_SHIPMENT.is_subshipment == True
    ).all()

    if not sub_shipments:
        raise HTTPException(status_code=404, detail="No sub-shipments found.")

    for sub in sub_shipments:
        pickup_date = sub.pickup_date
        due_date = sub.invoice_due_date
        amount = brokerage_ledger.carrier_payable_per_shipment

        # Find matching interim invoice
        carrier_parent_invoice = None
        for i in lane_interim_invoices:
            try:
                due_date = datetime.strptime(i.original_due_date, "%Y-%m-%d").date()
                if pickup_date <= due_date:
                    carrier_parent_invoice = i
                    break
            except Exception as e:
                print(f"Error parsing date: {e}")

        # Create Load Invoice
        load_invoice = Load_Invoice(
            contract_id=shipment.id,
            contract_type=sub.type,
            shipment_id=sub.id,
            is_subinvoice=True,
            parent_invoice_id=carrier_parent_invoice.id,
            description=f"Load Invoice for Sub-Shipment {sub.id}",
            billing_date=pickup_date,
            due_date=due_date,
            carrier_company_id=carrier.id,
            carrier_financial_account_id=financial_account.id,
            carrier_company_name=carrier.legal_business_name,
            payment_terms=exchange.payment_terms,
            carrier_bank=carrier_financial_account.bank_name,
            carrier_bank_account=carrier_financial_account.account_number,
            payment_reference=f"Load {sub.id} of Lane {shipment.id}",
            contact_person_name=f"{carrier_financial_account.directors_first_name} {carrier_financial_account.directors_last_name}",
            carrier_email=carrier.business_email,
            carrier_address=carrier.business_address,
            status="Pending",
            base_amount=amount,
            due_amount=amount
        )
        db.add(load_invoice)


        # Create Sub-Shipment Assignment
        assigned_sub = Assigned_Spot_Ftl_Shipments(
            is_subshipment=True,
            lane_id=assigned_lane.id,
            shipment_id=sub.id,
            invoice_Id=load_invoice.id,
            invoice_due_date=load_invoice.due_date,
            invoice_status=load_invoice.status,
            type="FTL",
            trip_type=sub.trip_type,
            load_type=sub.load_type,
            carrier_id=carrier.id,
            carrier_name=carrier.legal_business_name,
            vehicle_id=None,
            driver_id=None,
            accepted_for=None,
            accepted_at=None,
            minimum_weight_bracket=sub.minimum_weight_bracket,
            minimum_git_cover_amount=sub.minimum_git_cover_amount,
            minimum_liability_cover_amount=sub.minimum_liability_cover_amount,
            shipment_rate=amount,
            distance=sub.distance,
            rate_per_km=rate_per_km,
            rate_per_ton=rate_per_ton,
            payment_terms=exchange.payment_terms,
            status="Assigned",
            trip_status="Scheduled",
            required_truck_type=sub.required_truck_type,
            equipment_type=sub.equipment_type,
            trailer_type=sub.trailer_type,
            trailer_length=sub.trailer_length,
            origin_address=sub.origin_address,
            origin_address_completed=sub.complete_origin_address,
            origin_city_province=sub.origin_city_province,
            origin_country=sub.origin_country,
            origin_region=sub.origin_region,
            destination_address=sub.destination_address,
            destination_address_completed=sub.complete_destination_address,
            destination_city_province=sub.destination_city_province,
            destination_country=sub.destination_country,
            destination_region=sub.destination_region,
            route_preview_embed=sub.route_preview_embed,
            pickup_date=pickup_date,
            priority_level=sub.priority_level,
            pickup_facility_id=sub.pickup_facility_id,
            delivery_facility_id=sub.delivery_facility_id,
            customer_reference_number=sub.customer_reference_number,
            shipment_weight=sub.shipment_weight,
            commodity=sub.commodity,
            temperature_control=sub.temperature_control,
            hazardous_materials=sub.hazardous_materials,
            packaging_quantity=sub.packaging_quantity,
            packaging_type=sub.packaging_type,
            pickup_number=sub.pickup_number,
            pickup_notes=sub.pickup_notes,
            delivery_number=sub.delivery_number,
            delivery_notes=sub.delivery_notes,
            estimated_transit_time=sub.estimated_transit_time
        )
        db.add(assigned_sub)

    db.commit()

    # Step 6: Return all details
    return {
        "bid accepted successfuly": {
            "id": shipment.id,
            "exchange_id": exchange.id,
            "payment_terms": exchange.payment_terms,
        },
    }