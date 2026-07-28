from __future__ import annotations

from datetime import date
from typing import Optional

from models.brokerage.loadboard import Ftl_Load_Board
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, shipment_status_Update
from models.brokerage.finance import Load_Invoice, FinancialAccounts, BrokerageLedger, Shipment_Invoice
from fastapi import HTTPException
from sqlalchemy.orm import Session

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_

from db.database import SessionLocal


def run_ftl_load_expiry():

    print("=" * 80)
    print("RUNNING FTL LOAD EXPIRY SERVICE")
    print("=" * 80)

    db = SessionLocal()

    try:

        now = datetime.now(ZoneInfo("Africa/Johannesburg"))

        today = now.date()

        current_time = now.time()

        expired_loads = (
            db.query(Ftl_Load_Board)
            .filter(
                Ftl_Load_Board.status == "Available",
                or_(

                    Ftl_Load_Board.pickup_date < today,

                    and_(
                        Ftl_Load_Board.pickup_date == today,
                        Ftl_Load_Board.pickup_end_time <= current_time
                    )

                )
            )
            .all()
        )

        print(f"Expired Loads Found : {len(expired_loads)}")

        processed = 0

        failed = 0

        for load in expired_loads:

            print("")
            print("-" * 80)
            print(f"Shipment : {load.shipment_id}")

            try:

                shipment = (
                    db.query(FTL_SHIPMENT)
                    .filter(
                        FTL_SHIPMENT.id == load.shipment_id
                    )
                    .first()
                )

                if shipment is None:

                    print("Shipment missing.")

                    failed += 1

                    continue

                ledger = (
                    db.query(BrokerageLedger)
                    .filter(
                        BrokerageLedger.shipment_id == shipment.id
                    )
                    .first()
                )

                shipment_invoice = None

                if shipment.invoice_id:

                    shipment_invoice = (
                        db.query(Shipment_Invoice)
                        .filter(
                            Shipment_Invoice.id == shipment.invoice_id
                        )
                        .first()
                    )

                carrier_invoice = (
                    db.query(Load_Invoice)
                    .filter(
                        Load_Invoice.shipment_id == shipment.id
                    )
                    .first()
                )

                financial_account = (
                    db.query(FinancialAccounts)
                    .filter(
                        FinancialAccounts.id == shipment.shipper_company_id
                    )
                    .first()
                )
                # ---------------------------------------------------------
                # 1. Update Loadboard
                # ---------------------------------------------------------

                load.status = "Failed"

                print("✓ Loadboard updated")


                # ---------------------------------------------------------
                # 2. Update Shipment
                # ---------------------------------------------------------

                shipment.shipment_status = "Failed"
                shipment.trip_status = "Failed"
                shipment.invoice_status = "Cancelled"

                print("✓ Shipment updated")


                # ---------------------------------------------------------
                # 3. Shipment Invoice
                # ---------------------------------------------------------

                if shipment_invoice:

                    shipment_invoice.status = "Cancelled"

                    print("✓ Shipment invoice cancelled")

                else:

                    print("No shipment invoice found.")


                # ---------------------------------------------------------
                # 4. Carrier Load Invoice
                # ---------------------------------------------------------

                if carrier_invoice:

                    carrier_invoice.status = "Cancelled"

                    print("✓ Carrier invoice cancelled")

                else:

                    print("No carrier invoice found.")


                # ---------------------------------------------------------
                # 5. Brokerage Ledger
                # ---------------------------------------------------------

                if ledger:

                    ledger.shipment_status = "Failed"

                    ledger.shipment_invoice_status = "Cancelled"

                    ledger.load_invoice_status = "Cancelled"

                    print("✓ Brokerage ledger updated")

                else:

                    print("No brokerage ledger found.")


                # ---------------------------------------------------------
                # 6. Financial Account
                # ---------------------------------------------------------

                if financial_account:

                    booking_amount = shipment.quote or 0

                    if financial_account.payment_terms == "PAB":

                        financial_account.credit_balance += booking_amount

                        print(
                            f"✓ Credited PAB balance : R{booking_amount}"
                        )

                    else:

                        financial_account.total_outstanding -= booking_amount

                        if financial_account.total_outstanding < 0:

                            financial_account.total_outstanding = 0

                        print(
                            f"✓ Reduced outstanding balance : R{booking_amount}"
                        )

                else:

                    print("Financial account not found.")


                # ---------------------------------------------------------
                # 7. Shipment Status History
                # ---------------------------------------------------------

                status_update = shipment_status_Update(

                    shipment_id=shipment.id,

                    type="FTL",

                    status="Failed",

                    trip_status="Failed",

                    location_description=(
                        "Shipment expired on the loadboard before carrier acceptance."
                    )

                )

                db.add(status_update)

                print("✓ Shipment status history created")


                # ---------------------------------------------------------
                # 8. Commit
                # ---------------------------------------------------------

                db.commit()

                processed += 1

                print("✓ Shipment committed")

                print(f"✓ Shipment {shipment.id} marked as FAILED successfully.")

            except Exception as shipment_error:

                db.rollback()

                failed += 1

                print("")
                print("X" * 80)
                print(f"FAILED TO PROCESS SHIPMENT {load.shipment_id}")
                print(shipment_error)
                print("X" * 80)

                continue


        print("")
        print("=" * 80)
        print("FTL LOAD EXPIRY COMPLETE")
        print("=" * 80)

        print(f"Expired Loads Found : {len(expired_loads)}")
        print(f"Processed          : {processed}")
        print(f"Failed             : {failed}")

        return {
            "success": True,
            "expired_found": len(expired_loads),
            "processed": processed,
            "failed": failed
        }

    except Exception as e:

        db.rollback()

        print("")
        print("=" * 80)
        print("FATAL ERROR")
        print("=" * 80)
        print(str(e))

        return {
            "success": False,
            "error": str(e)
        }

    finally:

        db.close()

        print("")
        print("=" * 80)
        print("FTL EXPIRY SERVICE FINISHED")
        print("=" * 80)