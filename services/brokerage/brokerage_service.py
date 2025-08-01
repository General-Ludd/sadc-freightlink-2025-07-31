from sqlalchemy.orm import Session
from models.brokerage.finance import BrokerageLedger, Dedicated_Lane_BrokerageLedger
from models.brokerage.finance import BrokerageLedger, PlatformCommission, PaymentMethods
from schemas.brokerage.finance import BrokerageTransactionCreate
from fastapi import HTTPException

def calculate_brokerage_details(db: Session, booking_amount: int, shipment_type: str, payment_method: str):
    # Fetch platform commission rate
    platform_commission_entry = db.query(PlatformCommission).filter(PlatformCommission.name == shipment_type).first()
    if not platform_commission_entry:
        raise HTTPException(status_code=404, detail=f"Platform commission for type '{shipment_type}' not found")

    # Convert to integer or float
    commission_percentage = int(platform_commission_entry.commission)  # Ensure it's an integer

    # Fetch transaction fee for the payment method
    payment_method_entry = db.query(PaymentMethods).filter(PaymentMethods.name == payment_method).first()
    if not payment_method_entry:
        raise HTTPException(status_code=404, detail=f"Transaction fee for payment method '{payment_method}' not found")

    # Convert to integer or float
    transaction_fee_rate = int(payment_method_entry.transaction_fee)  # Ensure it's an integer

    # Calculate platform commission
    platform_commission = booking_amount * (commission_percentage / 10000)

    # Calculate transaction fees
    transaction_fee = booking_amount * (transaction_fee_rate / 10000)

    # Calculate true platform earnings
    true_platform_earnings = platform_commission - transaction_fee

    # Calculate carrier payout
    carrier_payout = booking_amount - platform_commission

    return platform_commission, transaction_fee, true_platform_earnings, int(carrier_payout)

def create_brokerage_ledger_entry(db: Session, transaction_data: BrokerageTransactionCreate):
    ledger_entry = BrokerageLedger(
        shipment_id=transaction_data.shipment_id,
        booking_amount=transaction_data.booking_amount,
        platform_commission=transaction_data.platform_commission,
        transaction_fee=transaction_data.transaction_fee,
        true_platform_earnings=transaction_data.true_platform_earnings,
        carrier_payout=transaction_data.carrier_payout,
        payment_method=transaction_data.payment_method,
    )
    db.add(ledger_entry)
    db.commit()
    db.refresh(ledger_entry)
    return ledger_entry

def calculate_contract_brokerage_details(db: Session, booking_amount: int, shipment_type: str, payment_method: str, total_shipments: int):
    # Fetch platform commission rate
    platform_commission_entry = db.query(PlatformCommission).filter(PlatformCommission.name == shipment_type).first()
    if not platform_commission_entry:
        raise HTTPException(status_code=404, detail=f"Platform commission for type '{shipment_type}' not found")
    commission_percentage = int(platform_commission_entry.commission)

    # Fetch transaction fee for the payment method
    payment_method_entry = db.query(PaymentMethods).filter(PaymentMethods.name == payment_method).first()
    if not payment_method_entry:
        raise HTTPException(status_code=404, detail=f"Transaction fee for payment method '{payment_method}' not found")
    transaction_fee_rate = int(payment_method_entry.transaction_fee)

    # Contract-Level Calculations
    platform_commission = int(booking_amount * (commission_percentage / 10000))
    transaction_fee = int(booking_amount * (transaction_fee_rate / 10000))
    true_platform_earnings = int(platform_commission - transaction_fee)
    carrier_payout = int(booking_amount - platform_commission)

    # Shipment-Level Breakdown
    shipment_booking_amount = int(booking_amount / total_shipments)
    shipment_platform_commission = int(platform_commission / total_shipments)
    shipment_transaction_fee = int(transaction_fee / total_shipments)
    shipment_true_earnings = int(true_platform_earnings / total_shipments)
    shipment_carrier_payout = int(carrier_payout / total_shipments)

    return {
        "contract_booking_amount": booking_amount,
        "contract_platform_commission": platform_commission,
        "contract_transaction_fee": transaction_fee,
        "contract_true_earnings": true_platform_earnings,
        "contract_carrier_payout": carrier_payout,
        "shipment_booking_amount": shipment_booking_amount,
        "shipment_platform_commission": shipment_platform_commission,
        "shipment_transaction_fee": shipment_transaction_fee,
        "shipment_true_earnings": shipment_true_earnings,
        "shipment_carrier_payout": shipment_carrier_payout,
    }

def create_brokerage_ledger_entry(db: Session, transaction_data: dict, total_shipments: int):
    ledger_entry = Dedicated_Lane_BrokerageLedger(
        contract_booking_amount=transaction_data["contract_booking_amount"],
        contract_platform_commission=transaction_data["contract_platform_commission"],
        contract_transaction_fee=transaction_data["contract_transaction_fee"],
        contract_true_earnings=transaction_data["contract_true_earnings"],
        contract_carrier_payout=transaction_data["contract_carrier_payout"],
        payment_method=transaction_data["payment_method"],
        total_shipments=total_shipments,
        shipment_booking_amount=transaction_data["shipment_booking_amount"],
        shipment_platform_commission=transaction_data["shipment_platform_commission"],
        shipment_transaction_fee=transaction_data["shipment_transaction_fee"],
        shipment_true_earnings=transaction_data["shipment_true_earnings"],
        shipment_carrier_payout=transaction_data["shipment_carrier_payout"],
    )
    db.add(ledger_entry)
    db.commit()
    db.refresh(ledger_entry)
    return ledger_entry