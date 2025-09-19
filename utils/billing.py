import datetime
from datetime import date
from typing import List, Optional
from dateutil.relativedelta import relativedelta
from enum import Enum

from requests import Session
from enums import PaymentTerms
from models.brokerage.finance import FinancialAccounts, Interim_Invoice, Invoices, Lane_Interim_Invoice, Lane_Invoice, Load_Invoice, Shipment_Invoice

class BillingEngine:

    @staticmethod
    def get_next_billing_date(payment_terms: str, pickup_date: date) -> date:
        # Combine get_billing_anchor + get_shipment_billing_date
        import calendar
        day = pickup_date.day
        month = pickup_date.month
        year = pickup_date.year
        last_day = calendar.monthrange(year, month)[1]

        anchors = {
            "NET_7": [7, 14, 21, 28],
            "NET_10": [10, 20, last_day],
            "NET_15": [15, last_day],
            "EOM": [last_day],
            "PAB": [pickup_date.day],
        }

        if payment_terms == "PAB":
            return pickup_date

        for anchor in anchors[payment_terms]:
            if day <= anchor:
                return date(year, month, anchor)

        # Pick first anchor next month
        next_month = month + 1 if month < 12 else 1
        next_year = year + 1 if month == 12 else year
        next_last_day = calendar.monthrange(next_year, next_month)[1]
        next_anchor = anchors[payment_terms][0]
        if next_anchor > next_last_day:
            next_anchor = next_last_day
        return date(next_year, next_month, next_anchor)

    @staticmethod
    def check_spending_limit(financial_account, amount: float) -> bool:
        return (financial_account.total_outstanding + financial_account.projected_balance + amount) <= financial_account.spending_limit

    @staticmethod
    def create_shipment_invoice(
        db: Session,
        company_id: int,
        financial_account: FinancialAccounts,
        shipment_id: int,
        shipment_type: str,
        pickup_date: date,
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
            total=total_cost,
            base_amount=base_amount,
            other_surcharges=other_surcharges,
            vat=vat,
            due_amount=0 if is_pab else total_cost,
            description=description
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
            next_due = BillingEngine.get_next_due_date(current_date, payment_terms)
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
        shipper_company_id: int,
        total_shipments_quote: float,
        payment_terms: str,
        due_date: date,
    ):
        """
        Generates a single master contract invoice.
        """
        is_pab = payment_terms == "PAB"
        billing_date = date.today() if is_pab else due_date

        invoice = Contract_Invoice(
            contract_id=contract_id,
            contract_type=contract_type,
            company_id=shipper_company_id,
            financial_account_id=financial_account_id,
            business_name=business_name,
            contact_person_name=contact_person_name,
            billing_address=billing_address,
            payment_terms=payment_terms,
            billing_date=billing_date,
            due_date=due_date,
            total=total_shipments_quote,
            status="Paid" if is_pab else "Pending",
            is_paid=is_pab,
            due_amount=0 if is_pab else total_shipments_quote,
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
        """
        interim_invoices = []
        is_pab = payment_terms == "PAB"

        for due_date in payment_dates:
            invoice = Interim_Invoice(
                parent_invoice_id=parent_invoice_id,
                contract_id=contract_id,
                contract_type=contract_type,
                company_id=company_id,
                business_name=business_name,
                contact_person_name=contact_person_name,
                business_email=business_email,
                billing_address=billing_address,
                payment_terms=payment_terms,
                billing_date=date.today(),
                due_date=due_date,
                total=amount_per_invoice,
                status="Paid" if is_pab else "Pending",
                is_paid=is_pab,
                due_amount=0 if is_pab else amount_per_invoice,
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
        pickup_date: date,
        due_date: date,
        amount: float,
        company_id: int,
        payment_terms: str,
        description: str,
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
            business_name=business_name,
            contact_person_name=contact_person_name,
            business_email=business_email,
            billing_address=billing_address,
            payment_terms=payment_terms,
            billing_date=pickup_date,
            due_date=due_date,
            total=amount,
            description=description,
            status="Paid" if is_pab else "Pending",
            is_paid=is_pab,
            due_amount=0 if is_pab else amount,
        )

        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice