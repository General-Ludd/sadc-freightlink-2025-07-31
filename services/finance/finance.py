from calendar import calendar
from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from enums import EquipmentType, Recurrence_Days, TrailerLength, TrailerType, TruckType
from models.brokerage.finance import Contract, LateFeeRates, Invoice, FinancialAccounts
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from services.brokerage.recurrence_calculator import RecurrenceCalculator
from services.shipment_service import calculate_qoute_for_power_shipment, calculate_quote_for_shipment, calculate_total_shipment_quote
from utils.google_maps import AddressInput, calculate_distance

def get_next_billing_date(current_date, payment_term):
    year = current_date.year
    month = current_date.month
    day = current_date.day

    def end_of_month(dt):
        last_day = calendar.monthrange(dt.year, dt.month)[1]
        return datetime(dt.year, dt.month, last_day)

    billing_days = {
        "NET_7": [7, 14, 21, 28],
        "NET_10": [10, 20, "EOM"],
        "NET_15": [15, "EOM"],
        "EOM": ["EOM"]
    }

    term_schedule = billing_days.get(payment_term.upper())
    possible_dates = []

    for item in term_schedule:
        if item == "EOM":
            billing_date = end_of_month(current_date)
        else:
            try:
                billing_date = datetime(year, month, item)
            except ValueError:
                continue  # skip invalid dates
        if billing_date >= current_date:
            possible_dates.append(billing_date)

    # If all options are in the past for this month, roll over to next month
    if not possible_dates:
        next_month = current_date.replace(day=28) + timedelta(days=4)
        return get_next_billing_date(next_month.replace(day=1), payment_term)

    return min(possible_dates)

def calculate_late_fees(db: Session):
    # Fetch the fixed late fee for invoices from the LateFeeRates table
    late_fee_rate_entry = db.query(LateFeeRates).filter(LateFeeRates.name == "invoices").first()
    
    if not late_fee_rate_entry:
        raise ValueError("Late fee rate for 'invoices' not found in LateFeeRates table.")
    
    late_fee_rate = late_fee_rate_entry.rate  # Fixed rate for overdue invoices
    
    # Get all overdue invoices
    overdue_invoices = db.query(Invoice).filter(
        Invoice.due_date < datetime.utcnow(),
        Invoice.status != "SETTLED"
    ).all()
    
    for invoice in overdue_invoices:
        days_overdue = (datetime.utcnow() - invoice.due_date).days
        late_fees = late_fee_rate * days_overdue  # Apply fixed rate for each day overdue
        invoice.late_fees += late_fees
        invoice.due_amount += late_fees  # Update total amount
        invoice.status = "OVERDUE"
        db.commit()


def handle_30_day_pay(db: Session, shipment: FTL_SHIPMENT, financial_account: FinancialAccounts):
    # Create invoice
    invoice = Invoice(
        shipment_id=shipment.id,
        company_id=shipment.shipper_company_id,
        financial_account_id=shipment.shipper_company_id,
        date_of_booking=shipment.created_at,
        due_date=shipment.created_at,
        due_amount=shipment.quote,
        status="Pending"
    )
    db.add(invoice)
    db.commit()
    db.refresh
    
    # Update financial account
    current_total_outstanding = int(financial_account.total_outstanding)
    current_num_outstanding_invoices = int(financial_account.num_outstanding_invoices)
    # Ensure the shipment quote is numeric
    quote_value = int(shipment.quote)
    additional_invoice = int(1)
    # Perform the addition
    financial_account.total_outstanding = current_total_outstanding + quote_value
    financial_account.num_outstanding_invoices = current_num_outstanding_invoices + additional_invoice
    # Commit the changes to the database
    db.commit()
    
    return {"message": "Invoice created for 30-Day Pay", "invoice_id": invoice.id}

def handle_instant_eft(db: Session, shipment: FTL_SHIPMENT, financial_account: FinancialAccounts):
    # Simulate EFT gateway call (to be replaced with real integration)
    payment_status = simulate_instant_eft_gateway(shipment.quote)
    
    if payment_status != "successful":
        return {"error": f"Payment failed: {payment_status}"}
    
    # Create and mark invoice as SETTLED
    invoice = Invoice(
        shipment_id=shipment.id,
        company_id=financial_account.id,
        amount=shipment.quote,
        due_date=shipment.pickup_date,
        status="SETTLED",
        paid_amount=shipment.quote
    )
    db.add(invoice)
    
    # Update financial account
    financial_account.total_spent += shipment.quote
    financial_account.total_paid += shipment.quote
    financial_account.num_paid_invoices += 1
    db.commit()
    
    return {"message": "Payment successful and shipment booked", "invoice_id": invoice.id}

def handle_credit_card(db: Session, shipment: FTL_SHIPMENT, financial_account: FinancialAccounts):
    if not financial_account.credit_card_token:
        return {"error": "Credit card token not found"}
    
    # Simulate payment gateway call (to be replaced with real integration)
    payment_status = simulate_credit_card_payment(
        token=financial_account.credit_card_token,
        amount=shipment.quote
    )
    
    if payment_status != "successful":
        return {"error": f"Payment failed: {payment_status}"}
    
    # Create and mark invoice as SETTLED
    invoice = Invoice(
        shipment_id=shipment.id,
        company_id=financial_account.id,
        amount=shipment.quote,
        due_date=shipment.pickup_date,
        status="SETTLED",
        paid_amount=shipment.quote
    )
    db.add(invoice)
    
    # Update financial account
    financial_account.total_spent += shipment.quote
    financial_account.total_paid += shipment.quote
    financial_account.num_paid_invoices += 1
    db.commit()
    
    return {"message": "Payment successful and shipment booked", "invoice_id": invoice.id}

def handle_contract_pay(db: Session, shipment: FTL_Lane, financial_account: FinancialAccounts):
    # Create Contract
    contract = Contract(
        lane_id=shipment.id,
        lane_type=shipment.type,
        shipper_company_id=shipment.shipper_company_id,
        shipper_country_of_incorporation=financial_account.business_country_of_incorporation,
        shipper_legal_business_name=financial_account.company_name,
        director_name="{financial_account.directors_first_name} {financial_account.directors_last_name}",
        directors_id_numebr=financial_account.directors_id_number,
        shipper_user_id=shipment.shipper_user_id,
        start_date=shipment.start_date,
        end_date=shipment.end_date,
        recurrence_frequency=shipment.recurrence_frequency,
        recurrence_days=shipment.recurrence_days,
        total_num_of_shipments=shipment.total_shipments,
        shipments_per_interval=shipment.shipments_per_interval,
        average_weight_per_shipment=shipment.average_shipment_weight,
        shipment_dates=shipment.shipment_dates,  # Use the calculated shipment dates from the shipment
        minimum_git_cover_amount=shipment.minimum_git_cover_amount,
        minimum_liability_cover_amount=shipment.minimum_liability_cover_amount,
        payment_terms=financial_account.payment_terms,
        payment_dates=shipment.payment_dates,  # Use the calculated payment dates from the shipment
        is_active=False,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    
    # Update financial account
    current_total_outstanding = int(financial_account.total_outstanding)
    # Ensure the shipment quote is numeric
    quote_value = int(shipment.contract_quote)
    # Perform the addition
    financial_account.total_outstanding = current_total_outstanding + quote_value
    # Commit the changes to the database
    db.commit()

    # Optionally update the financial account or other details here if needed

    return {"message": "Contract created successfully", "contract_id": contract.id}

def calculate_spot_ftl_quote(
    db: Session,
    origin_address: str,
    destination_address: str,
    required_truck_type,
    equipment_type,
    trailer_type,
    trailer_length,
    minimum_weight_bracket: int
):
    # Step 1: Calculate Distance and Transit Time
    try:
        distance_data = calculate_distance(AddressInput(
            origin_address=origin_address,
            destination_address=destination_address
        ))
        distance = distance_data["distance"]
        estimated_transit_time = distance_data["duration"]
        route_preview_embed = distance_data["google_maps_embed_url"]
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Distance calculation failed: {e.detail}")

    # Ensure values are strings (support Enums or raw strings)
    def safe_str(val):
        return val.value if hasattr(val, "value") else str(val)

    try:
        quote = calculate_quote_for_shipment(
            db=db,
            required_truck_type=safe_str(required_truck_type),
            equipment_type=safe_str(equipment_type),
            trailer_type=safe_str(trailer_type),
            trailer_length=safe_str(trailer_length),
            distance=distance,
            minimum_weight_bracket=minimum_weight_bracket
        )
        return {
            "quote_amount": f"R{quote}",
            "distance_km": distance,
            "estimated_transit_time": estimated_transit_time,
            "route_preview_embed": route_preview_embed
            }

    except HTTPException as e:
            raise HTTPException(status_code=500, detail=f"Quote calculation failed: {e.detail}")
    
def calculate_spot_ftl_lane_quote(
    db: Session,
    origin_address: str,
    destination_address: str,
    required_truck_type,
    equipment_type,
    trailer_type,
    trailer_length,
    minimum_weight_bracket: int,
    recurrence_frequency,
    recurrence_days: list[Recurrence_Days],
    start_date: date,
    end_date: date,
    shipments_per_interval:int,
    skip_weekends: bool
):
    # Step 1: Calculate Distance and Transit Time
    try:
        distance_data = calculate_distance(AddressInput(
            origin_address=origin_address,
            destination_address=destination_address
        ))
        distance = distance_data["distance"]
        estimated_transit_time = distance_data["duration"]
        route_preview_embed = distance_data["google_maps_embed_url"]
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Distance calculation failed: {e.detail}")

    # Ensure values are strings (support Enums or raw strings)
    def safe_str(val):
        return val.value if hasattr(val, "value") else str(val)

    try:
        quote_per_shipment = calculate_quote_for_shipment(
            db=db,
            required_truck_type=safe_str(required_truck_type),
            equipment_type=safe_str(equipment_type),
            trailer_type=safe_str(trailer_type),
            trailer_length=safe_str(trailer_length),
            distance=distance,
            minimum_weight_bracket=minimum_weight_bracket
        )
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Distance calculation failed: {e.detail}")
    
    # Step 4: Calculate Recurrence Dates for Shipments
    recurrence_calculator = RecurrenceCalculator(
        recurrence_frequency=recurrence_frequency,
        recurrence_days=recurrence_days,
        start_date=start_date,
        end_date=end_date,
        shipments_per_interval=shipments_per_interval,
        skip_weekends=skip_weekends
    )
    shipment_dates = recurrence_calculator.get_recurrence_dates(total_shipments=quote_per_shipment)

    # Step 5: Calculate Total Shipments
    total_shipments = recurrence_calculator.calculate_total_shipments(total_shipments=len(shipment_dates))

    try:
        total_shipments_quote = calculate_total_shipment_quote(
            qoute_per_shipment=quote_per_shipment,
            total_shipments=total_shipments
        )
        return {
            "quote_amount_per_shipment": f"R{quote_per_shipment}",
            "total_contract_qoute": f"R{total_shipments_quote}",
            "distance_km": distance,
            "estimated_transit_time": estimated_transit_time,
            "route_preview_embed": route_preview_embed
            }
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Quote calculation failed: {e.detail}")
    


def calculate_spot_power_quote(
    db: Session,
    origin_address: str,
    destination_address: str,
    required_truck_type,
    axle_configuration,
    minimum_weight_bracket: int
):
    # Step 1: Calculate Distance and Transit Time
    try:
        distance_data = calculate_distance(AddressInput(
            origin_address=origin_address,
            destination_address=destination_address
        ))
        distance = distance_data["distance"]
        estimated_transit_time = distance_data["duration"]
        route_preview_embed = distance_data["google_maps_embed_url"]
    except HTTPException as e:
        raise HTTPException(status_code=500, detail=f"Distance calculation failed: {e.detail}")

    # Ensure values are strings (support Enums or raw strings)
    def safe_str(val):
        return val.value if hasattr(val, "value") else str(val)

    try:
        quote = calculate_qoute_for_power_shipment(
            db=db,
            required_truck_type=safe_str(required_truck_type),
            axle_configuration=safe_str(axle_configuration),
            distance=distance,
            minimum_weight_bracket=minimum_weight_bracket
        )
        return {
            "quote_amount": f"R{quote}",
            "distance_km": distance,
            "estimated_transit_time": estimated_transit_time,
            "route_preview_embed": route_preview_embed
            }

    except HTTPException as e:
            raise HTTPException(status_code=500, detail=f"Quote calculation failed: {e.detail}")