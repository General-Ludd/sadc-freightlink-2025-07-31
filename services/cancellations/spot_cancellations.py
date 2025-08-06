from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from sqlalchemy.orm import Session
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.brokerage.loadboard import Ftl_Load_Board, Power_Load_Board
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from models.brokerage.finance import BrokerageLedger, FinancialAccounts, Shipment_Invoice, Load_Invoice
from utils.auth import get_current_user

def cancel_spot_ftl_shipment(db: Session, shipment_id: int, cancelled_by_user_id: int):
    # Step 1: Fetch shipment
    shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found.")

    if shipment.shipment_status in ["Completed", "In-Progress"]:
        raise HTTPException(status_code=400, detail="Shipment cannot be cancelled once it's in progress or completed.")

    # Step 2: Reverse SHIPPER financial account
    financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == shipment.shipper_company_id
    ).first()

    if not financial_account:
        raise HTTPException(status_code=404, detail="Shipper financial account not found.")

    quote = shipment.quote or 0

    if shipment.payment_terms == "PAB":
        financial_account.credit_balance += quote
    else:
        financial_account.total_outstanding -= quote
        if financial_account.total_outstanding < 0:
            financial_account.total_outstanding = 0

    db.add(financial_account)

    # Step 3: Reverse SHIPPER invoice
    shipper_invoice = db.query(Shipment_Invoices).filter(Shipment_Invoices.shipment_id == shipment.id,
                                                        Shipment_Invoice.type == shipment.type).first()
    if shipper_invoice:
        shipper_invoice.status = "Cancelled"
        shipper_invoice.due_date = None
        shipper_invoice.due_amount = 0
        db.add(shipper_invoice)

    # Step 4: Loadboard
    loadboard = db.query(Ftl_Load_Board).filter(Ftl_Load_Board.shipment_id == shipment.id).first()
    if loadboard:
        loadboard.status = "Cancelled"
        db.add(loadboard)

    # Step 5: Assigned Shipment
    assigned_shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
        Assigned_Spot_Ftl_Shipments.shipment_id == shipment.id
    ).first()

    if assigned_shipment:
        # Step 6: Reverse CARRIER financial account
        carrier_financial = db.query(CarrierFinancialAccounts).filter(
            CarrierFinancialAccounts.id == shipment.carrier_id
        ).first()

        if carrier_financial:
            carrier_financial.holding_balance -= assigned_shipment.shipment_rate
            if carrier_financial.holding_balance < 0:
                carrier_financial.holding_balance = 0
            db.add(carrier_financial)

        # Step 7: Reverse CARRIER invoice
        carrier_invoice = db.query(Load_Invoice).filter(
            Load_Invoice.shipment_id == shipment.id
        ).first()
        if carrier_invoice:
            carrier_invoice.status = "Cancelled"
            carrier_invoice.due_date = None
            carrier_invoice.due_amount = 0
            db.add(carrier_invoice)

        # Step 8: Clean shipment-assignment link
        shipment.carrier_id = None
        shipment.carrier_name = None
        shipment.carrier_git_cover_amount = None
        shipment.carrier_liability_cover_amount = None
        shipment.vehicle_id = None
        shipment.vehicle_type = None
        shipment.vehicle_make = None
        shipment.vehicle_model = None
        shipment.vehicle_color = None
        shipment.vehicle_license_plate = None
        shipment.vehicle_vin = None
        shipment.vehicle_equipment_type = None
        shipment.vehicle_trailer_type = None
        shipment.vehicle_trailer_length = None
        shipment.vehicle_tare_weight = None
        shipment.vehicle_gvm_weight = None
        shipment.vehicle_payload_capacity = None
        shipment.driver_id = None
        shipment.driver_first_name = None 
        shipment.driver_last_name = None
        shipment.driver_license_number = None
        shipment.driver_phone_number = None
        shipment.driver_email = None

        assigned_shipment.status = "Cancelled"
        assigned_shipment.trip_status = "Cancelled"
        db.add(assigned_shipment)

    # Step 9: Brokerage Ledger
    brokerage_ledger = db.query(BrokerageLedger).filter(
        BrokerageLedger.shipment_id == shipment.id
    ).first()

    if brokerage_ledger:
        brokerage_ledger.carrier_id = None
        brokerage_ledger.vehicle_id = None
        brokerage_ledger.driver_id = None
        brokerage_ledger.load_invoice_id = None
        brokerage_ledger.load_invoice_due_date = None
        brokerage_ledger.load_invoice_status = "Cancelled"
        brokerage_ledger.shipment_status = "Cancelled"
        db.add(brokerage_ledger)

    # Step 10: Final shipment update
    shipment.shipment_status = "Cancelled"
    shipment.trip_status = "Cancelled"

    db.add(shipment)
    db.commit()

    return {
        "success": True,
        "message": f"Shipment {shipment.id} cancelled. All financial and document records reversed."
    }


#######################################Power Shipment Cancellation######################################
def cancel_spot_power_shipment(shipment_id: int, db: Session, current_user: dict):
    user_id = current_user.get("id")
    company_id = current_user.get("company_id")

    # 1. Retrieve Shipment
    shipment = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if not shipment.shipper_company_id == company_id:
        raise HTTPException(status_code=403, detail="You are not authorized to cancel this shipment")
    if shipment.shipment_status == "Cancelled":
        raise HTTPException(status_code=400, detail="Shipment is already cancelled")
    if shipment.shipment_status in ["Completed", "In-Progress"]:
        raise HTTPException(status_code=400, detail="Shipment cannot be cancelled once it's in progress or completed.")

    # 2. Retrieve Financial Account
    financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == shipment.shipper_company_id).first()
    if not financial_account:
        raise HTTPException(status_code=404, detail="Financial account not found")

        # Update Load Invoice
        shipment_invoice = db.query(Shipment_Invoice).filter(
            Shipment_Invoice.shipment_id == shipment.invoice_id
        ).first()
        if shipment_invoice:
            shipment_invoice.status = "Cancelled"
            shipment_invoice.due_amount = 0
            db.add(shipment_invoice)

    # 3. Retrieve Brokerage Ledger
    brokerage_ledger = db.query(BrokerageLedger).filter(
        BrokerageLedger.shipment_id == shipment.id,
        BrokerageLedger.shipment_type == shipment.type
    ).first()

    # 4. Refund logic (Only if not assigned to carrier)
    if shipment.shipment_status == "Booked":
        if shipment.payment_terms == "PAB":
            financial_account.credit_balance += shipment.quote
        else:
            financial_account.total_outstanding -= shipment.quote
        db.add(financial_account)

    # 5. If Assigned, reverse carrier payout and financials
    if shipment.shipment_status == "Assigned":
        # Load Assigned Shipment Record
        assigned_shipment = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.shipment_id == shipment.id
        ).first()
        if assigned_shipment:
            assigned_shipment.status = "Cancelled"
            assigned_shipment.trip_status = "Cancelled"
            db.add(assigned_shipment)

        # Reverse carrier financials
        carrier_financial = db.query(CarrierFinancialAccounts).filter(
            CarrierFinancialAccounts.id == shipment.carrier_id
        ).first()

        if carrier_financial:
            carrier_financial.holding_balance -= brokerage_ledger.carrier_payable
            db.add(carrier_financial)

        # Update Load Invoice
        load_invoice = db.query(Load_Invoice).filter(
            Load_Invoice.shipment_id == shipment.id
        ).first()
        if load_invoice:
            load_invoice.status = "Cancelled"
            load_invoice.due_amount = 0
            db.add(load_invoice)

        # Update loadboard status to available (if you want to repost)
        loadboard_entry = db.query(Power_Load_Board).filter(
            Power_Load_Board.shipment_id == shipment.id
        ).first()
        if loadboard_entry:
            loadboard_entry.status = "Cancelled"
            db.add(loadboard_entry)

        # Revert Brokerage Ledger details
        brokerage_ledger.shipment_status = "Cancelled"
        brokerage_ledger.shipment_invoice_status = "Cancelled"
        brokerage_ledger.load_invoice_status = "Cancelled"
        db.add(brokerage_ledger)

    # 6. Update the Shipment Status
    shipment.shipment_status = "Cancelled"
    shipment.trip_status = "Cancelled"
    db.add(shipment)

    # 7. Finalize
    db.commit()

    return {"message": f"Shipment {shipment.id} cancelled successfully"}