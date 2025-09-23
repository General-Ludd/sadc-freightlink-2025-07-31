import datetime
from datetime import date, timedelta
from typing import List, Optional
from dateutil.relativedelta import relativedelta
from enum import Enum
from requests import Session
from datetime import date, timedelta
from sqlalchemy.orm import Session
import time
import logging
from datetime import date, timedelta
from typing import Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
#from enums import PaymentTerms
from models.brokerage.finance import FinancialAccounts, Interim_Invoice, Invoices, Lane_Interim_Invoice, Lane_Invoice, Load_Invoice, Shipment_Invoice

class BillingEngine:

    def get_next_billing_date(payment_terms: str, pickup_date: date) -> date:
        import calendar

        if payment_terms is None:
            raise ValueError("payment_terms cannot be None")

        if hasattr(payment_terms, "value"):  # Enum case
            payment_terms = payment_terms.value
        else:  # String case
            payment_terms = str(payment_terms)

        payment_terms = payment_terms.upper().strip()

        day = pickup_date.day
        month = pickup_date.month
        year = pickup_date.year
        last_day = calendar.monthrange(year, month)[1]

        anchors = {
            "NET-7": [7, 14, 21, 28],
            "NET-10": [10, 20, last_day],
            "NET-15": [15, last_day],
            "EOM": [last_day],
            "PAB": [pickup_date.day],
        }

        if payment_terms == "PAB":
            return pickup_date  # Immediate billing

        if payment_terms not in anchors:
            raise ValueError(f"Unknown payment term: {payment_terms}")

        for anchor in anchors[payment_terms]:
            if day <= anchor:
                return date(year, month, anchor)

        # if no anchor left → pick first anchor next month
        next_month = month + 1 if month < 12 else 1
        next_year = year + 1 if month == 12 else year
        next_last_day = calendar.monthrange(next_year, next_month)[1]
        next_anchor = anchors[payment_terms][0]
        if next_anchor > next_last_day:
            next_anchor = next_last_day

        return date(next_year, next_month, next_anchor)


    @staticmethod
    def check_spending_limit(financial_account, amount: float) -> bool:
        return (financial_account.projected_balance + amount) <= financial_account.spending_limit

    @staticmethod
    def create_shipment_invoice(
        db: Session,
        company_id: int,
        financial_account: FinancialAccounts,
        shipment_id: int,
        shipment_type: str,
        origin_address: str,
        destination_address: str,
        pickup_date: date,
        distance: int,
        transit_time: str,
        total_cost: float,
        base_amount: float = None,
        other_surcharges: float = 0,
        vat: float = 0,
        contract_id: Optional[int] = None,
        contract_type: Optional[str] = None,
        description: Optional[str] = None
    ):
        base_amount = base_amount or total_cost
        billing_date = BillingEngine.get_next_billing_date(financial_account.payment_terms, pickup_date)
        is_pab = financial_account.payment_terms == "PAB"

        # Check spending limit
        if not is_pab and not BillingEngine.check_spending_limit(financial_account, total_cost):
            raise HTTPException(
                status_code=402,
                detail="Booking this shipment would exceed your company's spending limit for this billing cycle."
            )

        invoice = Shipment_Invoice(
            shipment_id=shipment_id,
            shipment_type=shipment_type,
            contract_id=contract_id,
            billing_date=billing_date,
            due_date=billing_date if not is_pab else date.today(),
            status="Paid" if is_pab else "Pending",
            is_paid=is_pab,
            company_id=company_id,
            financial_account_id=financial_account.id,
            payment_terms=financial_account.payment_terms,
            description=f"{shipment_type} shipment {shipment_id}",
            payment_reference=f"{shipment_type} shipment {shipment_id}",
            origin_address=origin_address,
            destination_address=destination_address,
            pickup_date=pickup_date,
            distance=distance,
            transit_time=transit_time,
            other_surcharges=other_surcharges,
            vat=vat,
            base_amount=total_cost,
            total=total_cost,
            due_amount=total_cost
        )

        db.add(invoice)

        # Update financial account
        if is_pab:
            financial_account.credit_balance -= total_cost
        else:
            financial_account.projected_balance += total_cost

        db.add(financial_account)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def get_contract_billing_dates(start_date: date, end_date: date, payment_terms: str) -> List[date]:
        """
        Generate all billing dates for a contract lane between start_date and end_date
        according to payment terms (NET_7, NET_10, NET_15, EOM, PAB)
        """
        billing_dates = []
        current_date = start_date

        while current_date <= end_date:
            next_due = BillingEngine.get_next_billing_date(payment_terms, current_date)
            billing_dates.append(next_due)
            current_date = next_due + timedelta(days=1)  # move past last due date

        return billing_dates

    @staticmethod
    def generate_contract_invoice(
        db: Session,
        contract_id: int,
        contract_type: str,
        financial_account_id: int,
        business_name: str,
        contact_person_name: str,
        billing_address: str,
        business_email: str,
        shipper_company_id: int,
        total_shipments_quote: float,
        payment_terms: str,
        contract_start_date: date,
        contract_end_date: date,
    ):
        """
        Generates a single master contract invoice.
        """
        is_pab = payment_terms == "PAB"
        billing_date = contract_start_date
        due_date = contract_end_date

        invoice = Invoices(
            contract_id=contract_id,
            contract_type=contract_type,
            company_id=shipper_company_id,
            financial_account_id=financial_account_id,
            business_name=business_name,
            contact_person_name=contact_person_name,
            billing_address=billing_address,
            business_email=business_email,
            payment_terms=payment_terms,
            billing_date=billing_date,
            due_date=due_date,
            total=total_shipments_quote,
            status="Paid" if is_pab else "Pending",
            is_paid=is_pab,
            due_amount=total_shipments_quote,
        )

        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def generate_interim_invoices(
        db: Session,
        parent_invoice_id: int,
        contract_id: int,
        contract_type: str,
        company_id: int,
        business_name: str,
        contact_person_name: str,
        business_email: str,
        billing_address: str,
        payment_dates: list[date],
        amount_per_invoice: float,
        payment_terms: str,
    ):
        """
        Splits contract invoice into interim invoices based on billing schedule.
        Billing date = start of billing cycle, Due date = end of billing cycle.
        """
        interim_invoices = []
        is_pab = payment_terms == "PAB"

        # define cycle length
        cycle_length_map = {
            "NET-7": 7,
            "NET-10": 10,
            "NET-15": 15,
            "EOM": None,  # special handling
            "PAB": None   # pay at booking — due immediately
        }
        cycle_length = cycle_length_map.get(payment_terms)

        for due_date in payment_dates:
            if payment_terms == "EOM":
                # billing date is 1st of the same month
                billing_date = due_date.replace(day=1)
            elif payment_terms == "PAB":
                billing_date = due_date  # billed & due same day
            else:
                billing_date = due_date - timedelta(days=cycle_length - 1)

            invoice = Interim_Invoice(
                parent_invoice_id=parent_invoice_id,
                contract_id=contract_id,
                contract_type=contract_type,
                company_id=company_id,
                business_name=business_name,
                contact_person_name=contact_person_name,
                business_email=business_email,
                billing_address=billing_address,
                financial_account_id=company_id,
                payment_reference=f"FTL Lane {billing_date}-{due_date}",
                description=f"FTL Lane-{contract_id}, billing period {billing_date} - {due_date}",
                payment_terms=payment_terms,
                billing_date=billing_date,
                due_date=due_date,
                base_amount=amount_per_invoice,
                total=amount_per_invoice,
                status="Paid" if is_pab else "Pending",
                is_paid=True if is_pab else False,
                due_amount=amount_per_invoice,
                invoice_type="Interim"
            )
            db.add(invoice)
            interim_invoices.append(invoice)

        db.commit()
        for inv in interim_invoices:
            db.refresh(inv)

        return interim_invoices

    @staticmethod
    def generate_shipment_invoice(
        db: Session,
        parent_invoice_id: int,
        contract_id: int,
        contract_type: str,
        shipment_id: int,
        shipment_type: str,
        due_date: date,
        amount: float,
        company_id: int,
        payment_terms: str,
        description: str,
        payment_reference: str,
        origin_address: str,
        destination_address: str,
        pickup_date: date,
        distance: int,
        transit_time: str,
        business_name: str,
        contact_person_name: str,
        business_email: str,
        billing_address: str,
    ):
        """
        Generates a shipment-level invoice tied to an interim invoice.
        """
        is_pab = payment_terms == "PAB"

        invoice = Shipment_Invoice(
            parent_invoice_id=parent_invoice_id,
            contract_id=contract_id,
            contract_type=contract_type,
            shipment_id=shipment_id,
            shipment_type=shipment_type,
            company_id=company_id,
            financial_account_id=company_id,
            business_name=business_name,
            contact_person_name=contact_person_name,
            business_email=business_email,
            billing_address=billing_address,
            payment_terms=payment_terms,
            billing_date=pickup_date,
            due_date=due_date,
            description=description,
            payment_reference=payment_reference,
            origin_address=origin_address,
            destination_address=destination_address,
            pickup_date=pickup_date,
            distance=distance,
            transit_time=transit_time,
            status="Paid" if is_pab else "Pending",
            is_paid=True if is_pab else False,
            base_amount=amount,
            total=amount,
            due_amount=amount,
        )

        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice


# import your models & BillingEngine here:
# from app.models import FinancialAccounts, Shipment_Invoice, Interim_Invoice, Invoices, FTL_Lane (if used)
# from app.billing import BillingEngine

logger = logging.getLogger("billing_worker")
logger.setLevel(logging.INFO)

class BillingWorker:

    @staticmethod
    def _get_cycle_window(today: date, payment_terms: str) -> Tuple[date, date]:
        """
        Returns inclusive cycle_start, cycle_end for 'today' given payment_terms.
        Uses BillingEngine.get_next_billing_date(payment_terms, today) to determine current anchor.
        """
        if hasattr(payment_terms, "value"):  # normalize Enum
            payment_terms = str(payment_terms.value)
        payment_terms = str(payment_terms).upper().strip()

        current_anchor = BillingEngine.get_next_billing_date(payment_terms, today)

        import calendar
        last_day = calendar.monthrange(current_anchor.year, current_anchor.month)[1]

        def anchors_for_month(pt: str, y: int, m: int) -> List[int]:
            if pt == "NET-7":
                cand = [7, 14, 21, 28]
            elif pt == "NET-10":
                cand = [10, 20, calendar.monthrange(y, m)[1]]
            elif pt == "NET-15":
                cand = [15, calendar.monthrange(y, m)[1]]
            elif pt == "EOM":
                cand = [calendar.monthrange(y, m)[1]]
            elif pt == "PAB":
                return [today.day]
            else:
                raise ValueError(f"Unknown payment terms: {payment_terms}")

            return [d for d in cand if d <= calendar.monthrange(y, m)[1]]

        anchors = anchors_for_month(payment_terms, current_anchor.year, current_anchor.month)

        try:
            idx = anchors.index(current_anchor.day)
        except ValueError:
            return (date(current_anchor.year, current_anchor.month, 1), current_anchor)

        if idx > 0:
            prev_anchor_day = anchors[idx - 1]
            prev_anchor_date = date(current_anchor.year, current_anchor.month, prev_anchor_day)
        else:
            prev_month = current_anchor.month - 1
            prev_year = current_anchor.year
            if prev_month == 0:
                prev_month = 12
                prev_year -= 1
            prev_anchors = anchors_for_month(payment_terms, prev_year, prev_month)
            prev_anchor_day = prev_anchors[-1]
            prev_anchor_date = date(prev_year, prev_month, prev_anchor_day)

        cycle_start = prev_anchor_date + timedelta(days=1)
        cycle_end = current_anchor

        if payment_terms == "EOM":
            cycle_start = date(current_anchor.year, current_anchor.month, 1)

        if payment_terms == "PAB":
            cycle_start = today
            cycle_end = today

        return (cycle_start, cycle_end)

    @staticmethod
    def apply_due_invoices_for_company(db: Session, company_id: int):
        """
        Find Pending + not-applied invoices for company in current billing cycle and apply them.
        - Shipment invoices (standalone): apply and add to projected_balance.
        - Shipment sub-invoices: mark applied; then apply their parent Interim invoice (if not applied)
          and add interim.total to projected_balance (once).
        - Interim invoices: apply (add interim.total to projected_balance) and mark child shipments applied.
        """
        today = date.today()
        account = (
            db.query(FinancialAccounts)
            .filter(FinancialAccounts.company_id == company_id)
            .first()
        )
        if not account:
            return

        pt = account.payment_terms
        cycle_start, cycle_end = BillingWorker._get_cycle_window(today, pt)

        # --- INTERIM invoices ---
        interims = db.query(Interim_Invoice).filter(
            Interim_Invoice.company_id == company_id,
            or_(
                Interim_Invoice.billing_date.between(cycle_start, cycle_end),
                Interim_Invoice.due_date.between(cycle_start, cycle_end),
            ),
            Interim_Invoice.status == "Pending",
            Interim_Invoice.is_applied == False,
        ).all()

        for interim in interims:
            BillingWorker._apply_interim_invoice(db, interim, account, mark_children=True)

        # --- SHIPMENT invoices ---
        shipments = db.query(Shipment_Invoice).filter(
            Shipment_Invoice.company_id == company_id,
            or_(
                Shipment_Invoice.billing_date.between(cycle_start, cycle_end),
                Shipment_Invoice.due_date.between(cycle_start, cycle_end),
            ),
            Shipment_Invoice.status == "Pending",
            Shipment_Invoice.is_applied == False,
        ).all()

        for sh in shipments:
            if sh.parent_invoice_id:
                sh.is_applied = True
                sh.status = "Due"
                db.add(sh)

                parent = db.query(Interim_Invoice).get(sh.parent_invoice_id)
                if parent and not parent.is_applied and parent.status == "Pending":
                    BillingWorker._apply_interim_invoice(db, parent, account, mark_children=True)
            else:
                BillingWorker._apply_shipment_invoice(db, sh, account)

        db.commit()

    # ----------------- Helpers -----------------

    @staticmethod
    def _apply_interim_invoice(
        db: Session, interim: Interim_Invoice, account: FinancialAccounts, mark_children: bool = False
    ):
        """
        Apply interim invoice -> add interim.total to projected_balance, mark interim and its shipments as applied.
        """
        if interim.is_applied:
            return

        account.projected_balance = (account.projected_balance or 0) + (interim.due_amount or 0)
        interim.is_applied = True
        interim.status = "Due"
        db.add(account)
        db.add(interim)

        if mark_children:
            children = db.query(Shipment_Invoice).filter(Shipment_Invoice.parent_invoice_id == interim.id).all()
            for s in children:
                s.is_applied = True
                s.status = "Due"
                db.add(s)

    @staticmethod
    def _apply_shipment_invoice(db: Session, sh: Shipment_Invoice, account: FinancialAccounts):
        """
        Apply standalone shipment invoice: mark applied and add its total to projected_balance.
        """
        if sh.is_applied:
            return

        account.projected_balance = (account.projected_balance or 0) + (sh.due_amount or 0)
        sh.is_applied = True
        sh.status = "Due"
        db.add(account)
        db.add(sh)


# --------- NON-STOP LOOP ----------
def run_billing_worker_loop(SessionLocal, interval_seconds: int = 30):
    logger.info("Starting billing worker loop (interval %s seconds)", interval_seconds)
    while True:
        try:
            session: Session = SessionLocal()
            accounts = session.query(FinancialAccounts).filter(
                FinancialAccounts.status == "Active",
                FinancialAccounts.is_verified == True,
            ).all()

            for acc in accounts:
                try:
                    BillingWorker.apply_due_invoices_for_company(session, acc.company_id)
                    session.commit()
                except Exception:
                    session.rollback()
                    logger.exception("Failed to process invoices for company_id=%s", acc.company_id)
        except Exception:
            logger.exception("Billing worker main loop error")
        finally:
            session.close()
        time.sleep(interval_seconds)
