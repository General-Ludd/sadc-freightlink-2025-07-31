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
    def get_next_due_date(issue_date: datetime.date, term: PaymentTerms):
        day = issue_date.day
        month = issue_date.month
        year = issue_date.year

        if term == PaymentTerms.NET_7:
            if day <= 7:
                return datetime.date(year, month, 14)
            elif day <= 14:
                return datetime.date(year, month, 21)
            elif day <= 21:
                return datetime.date(year, month, 28)
            else:
                # Next month's 7th
                next_month = issue_date + relativedelta(months=1)
                return datetime.date(next_month.year, next_month.month, 7)

        elif term == PaymentTerms.NET_10:
            if day <= 10:
                return datetime.date(year, month, 20)
            elif day <= 20:
                return BillingEngine.get_end_of_month(issue_date)
            else:
                next_month = issue_date + relativedelta(months=1)
                return datetime.date(next_month.year, next_month.month, 10)

        elif term == PaymentTerms.NET_15:
            if day <= 15:
                return BillingEngine.get_end_of_month(issue_date)
            else:
                next_month = issue_date + relativedelta(months=1)
                return datetime.date(next_month.year, next_month.month, 15)

        elif term == PaymentTerms.EOM:
            return BillingEngine.get_end_of_month(issue_date)

        elif term == PaymentTerms.PAB:
            # Pay Before Booking – special case
            return issue_date

    @staticmethod
    def get_end_of_month(date_obj: datetime.date):
        first_of_next_month = (date_obj.replace(day=1) + relativedelta(months=1))
        return first_of_next_month - datetime.timedelta(days=1)

    @staticmethod
    def is_within_spending_limit(financial_account: FinancialAccounts, amount: int):
        return (financial_account.total_outstanding + amount) <= financial_account.spending_limit

    @staticmethod
    def should_allow_new_invoice(financial_account: FinancialAccounts, invoice_amount: int, pickup_date: datetime.date):
        """Determines if a new invoice is allowed based on spending limits and due date logic."""
        if BillingEngine.is_within_spending_limit(financial_account, invoice_amount):
            return True

        due_date = BillingEngine.get_next_due_date(datetime.date.today(), financial_account.payment_terms)
        return pickup_date > due_date

    @staticmethod
    def get_billing_dates(start_date: datetime.date, end_date: datetime.date, term: PaymentTerms):
        dates = []

        # Include standard billing dates within contract duration
        current = start_date
        while current <= end_date:
            if term == PaymentTerms.EOM:
                billing_date = BillingEngine.get_end_of_month(current)
                if billing_date >= start_date and billing_date <= end_date:
                    dates.append(billing_date)
                current = billing_date + datetime.timedelta(days=1)

            elif term == PaymentTerms.NET_15:
                mid = datetime.date(current.year, current.month, 15)
                eom = BillingEngine.get_end_of_month(current)
                if mid >= start_date and mid <= end_date:
                    dates.append(mid)
                if eom >= start_date and eom <= end_date:
                    dates.append(eom)
                current = eom + datetime.timedelta(days=1)

            elif term == PaymentTerms.NET_10:
                for d in [10, 20]:
                    try:
                        billing = datetime.date(current.year, current.month, d)
                        if billing >= start_date and billing <= end_date:
                            dates.append(billing)
                    except:
                        continue
                eom = BillingEngine.get_end_of_month(current)
                if eom >= start_date and eom <= end_date:
                    dates.append(eom)
                current = eom + datetime.timedelta(days=1)

            elif term == PaymentTerms.NET_7:
                for d in [7, 14, 21, 28]:
                    try:
                        billing = datetime.date(current.year, current.month, d)
                        if billing >= start_date and billing <= end_date:
                            dates.append(billing)
                    except:
                        continue
                current = BillingEngine.get_end_of_month(current) + datetime.timedelta(days=1)

            elif term == PaymentTerms.PAB:
                return [start_date]

        # ✅ Add one additional billing date AFTER end_date
        one_day_after_end = end_date + datetime.timedelta(days=1)
        next_due = BillingEngine.get_next_due_date(one_day_after_end, term)
        dates.append(next_due)

        return sorted(list(set(dates)))  # Remove duplicates
    
    @staticmethod
    def generate_dedicated_lane_schedule_invoices(
        contract_id: int,
        contract_start: datetime.date,
        contract_end: datetime.date,
        total_amount: float,
        payment_term: PaymentTerms,
        db: Session,
    ):
        """
        Generate interim invoices for a dedicated FTL contract based on duration and payment terms.
        """
        # 1. Get billing dates
        billing_dates = BillingEngine.get_billing_dates(contract_start, contract_end, payment_term)

        if not billing_dates:
            raise ValueError("No billing dates found within the contract duration.")

        # 2. Calculate how much each invoice should be
        amount_per_invoice = total_amount / len(billing_dates)

        # 3. Create invoices
        invoices = BillingEngine.generate_interim_invoices(
            contract_id=contract_id,
            payment_dates=billing_dates,
            amount_per_invoice=amount_per_invoice,
            db=db
        )

        return invoices

    @staticmethod
    def generate_contract_invoice(
        contract_id: int,
        contract_type: str,
        financial_account_id: int,
        business_name: str,
        contact_person_name: str,
        billing_address: str,
        shipper_company_id:int,
        total_shipments_quote: int,
        due_date: date,
        payment_terms: str,
        db: Session,
    ):
        invoice = Invoices(
            contract_id=contract_id,
            contract_type=contract_type,
            company_id=shipper_company_id,
            financial_account_id=financial_account_id,
            business_name=business_name,
            contact_person_name=contact_person_name,
            billing_address=billing_address,
            due_amount=total_shipments_quote,
            billing_date=datetime.date.today(),
            due_date=due_date,
            payment_terms=payment_terms,
            status="Pending",
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def generate_interim_invoices(
        contract_id: int,
        contract_type: str,
        parent_invoice_id: int,
        payment_dates: List[date],
        company_id: int,
        business_name: str,
        contact_person_name: str,
        business_email: str,
        billing_address: str,
        payment_terms: str,
        amount_per_invoice: int,
        db: Session
    ):
        interim_invoices = []

        for due_date in payment_dates:
            invoice = Interim_Invoice(
                contract_id=contract_id,
                contract_type=contract_type,
                parent_invoice_id=parent_invoice_id,
                billing_date=date.today(),
                due_date=due_date,
                payment_terms=payment_terms,
                due_amount=amount_per_invoice,
                payment_reference=f"{contract_type}-{contract_id}-{due_date}",
                company_id=company_id,
                financial_account_id=company_id,
                business_name=business_name,
                contact_person_name=contact_person_name,
                business_email=business_email,
                billing_address=billing_address,
                status="Pending"
            )
            db.add(invoice)
            interim_invoices.append(invoice)

        db.commit()
        for invoice in interim_invoices:
            db.refresh(invoice)

        return interim_invoices

    @staticmethod
    def generate_shipment_invoice(
        db: Session,
        pickup_date: date,
        description: str,
        business_name: str,
        contact_person_name: str,
        business_email: str,
        billing_address: str,
        due_date: date,
        amount: int,
        company_id: int,
        payment_terms: str,
        shipment_id: int,
        shipment_type: str,
        contract_id: Optional [int] = None,
        contract_type: Optional [str] = None,
        parent_invoice_id: Optional [int] = None,
    ):
        invoice = Shipment_Invoice(
            invoice_type="Shipment",
            shipment_id=shipment_id,
            shipment_type=shipment_type,
            parent_invoice_id=parent_invoice_id,
            contract_id=contract_id,
            billing_date=pickup_date,
            due_date=due_date,
            is_subinvoice=True,
            status="Pending",
            is_paid=False,
            description=description,
            business_name=business_name,
            business_email=business_email,
            billing_address=billing_address,
            contact_person_name=contact_person_name,
            contract_type=contract_type,
            company_id=company_id,
            financial_account_id=company_id,
            payment_terms=payment_terms,
            total=amount,
            base_amount=amount,
            due_amount=amount,
            vat=0,
            other_surcharges=0,
            paid_amount=0,
            late_fees=0,
            platform_name="SADC FREIGHTLINK",
            platform_email="billing@sadcfreightlink.com",
            platform_address="5 Feza Street, Cape Town, Harare, Khayelitsha",
            platform_bank="First National Bank RSA (FNB)",
            platform_bank_account="938299489018"
        )
        db.add(invoice)
        db.flush()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def is_billing_cycle_active(due_date: date, payment_terms: PaymentTerms, today: date = date.today()) -> bool:
        """
        Determines if an invoice should now be applied to the financial account,
        based on current date and the payment terms.
        """

        if payment_terms == PaymentTerms.EOM:
            # Entire month of due date is active
            return today.month == due_date.month and today.year == due_date.year

        elif payment_terms == PaymentTerms.NET_15:
            # If due on 15th → activate from 1st to 15th
            # If due at EOM → activate from 16th onward
            if due_date.day == 15:
                return today <= due_date and today.day <= 15 and today.month == due_date.month and today.year == due_date.year
            else:
                return today >= date(due_date.year, due_date.month, 16) and today.month == due_date.month

        elif payment_terms == PaymentTerms.NET_10:
            # Activate in the 10-day cycle where the due_date falls
            if due_date.day == 10:
                return today.day <= 10 and today.month == due_date.month
            elif due_date.day == 20:
                return 11 <= today.day <= 20 and today.month == due_date.month
            else:  # EOM
                return today.day >= 21 and today.month == due_date.month

        elif payment_terms == PaymentTerms.NET_7:
            # 4 cycles per month
            if due_date.day in [7]:
                return today.day <= 7 and today.month == due_date.month
            elif due_date.day in [14]:
                return 8 <= today.day <= 14 and today.month == due_date.month
            elif due_date.day in [21]:
                return 15 <= today.day <= 21 and today.month == due_date.month
            elif due_date.day in [28]:
                return 22 <= today.day <= 28 and today.month == due_date.month

        elif payment_terms == PaymentTerms.PAB:
            return True  # Immediate activation

        return False  # Default fallback


    @staticmethod
    def get_invoice_for_date(
        db: Session,
        contract_id: int,
        target_date: datetime.date,
    ):
        return db.query(Invoices).filter(
            Invoices.contract_id == contract_id,
            Invoices.due_date == target_date
        ).first()


##############################################Carrier Side Billing##########################################
    @staticmethod
    def generate_assigned_lane_invoice(
        db: Session,
        contract_id: int,
        lane_type: str,
        carrier_company_id: int,
        carrier_company_name: str,
        contact_person_name: str,
        business_email: str,
        business_address: str,
        carrier_financial_account_id: int,
        carrier_bank: str,
        carrier_bank_account: str,
        payment_terms: str,
        total_due_amount: int,
        toll_fees: int = 0,
        other_surcharges: int = 0,
        description: str = "",
        due_date: Optional[date] = None,
    ):
        invoice = Lane_Invoice(
            contract_id=contract_id,
            lane_type=lane_type,
            invoice_type="Lane",
            billing_date=date.today(),
            contract_invoice_id=None,
            due_date=due_date,
            description=description,
            status="Pending",
            is_paid=False,
            company_id=carrier_company_id,
            carrier_company_name=carrier_company_name,
            contact_person_name=contact_person_name,
            business_email=business_email,
            business_address=business_address,
            carrier_financial_account_id=carrier_financial_account_id,
            carrier_bank=carrier_bank,
            carrier_bank_account=carrier_bank_account,
            payment_terms=payment_terms,
            base_amount=total_due_amount,
            toll_fees=toll_fees,
            other_surcharges=other_surcharges,
            due_amount=total_due_amount + toll_fees + other_surcharges,
            paid_amount=0,
            late_fees=0,
            payment_reference=f"{lane_type.upper()}-{contract_id}-{date.today()}",
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice
    
    @staticmethod
    def generate_assigned_interim_invoices(
        db: Session,
        contract_id: int,
        contract_type: str,
        carrier_company_id: int,
        carrier_name: str,
        contact_person_name: str,
        carrier_email: str,
        carrier_address: str,
        carrier_financial_account_id: int,
        carrier_bank: str,
        carrier_bank_account: str,
        invoice_payment_terms: str,
        payment_dates: List[date],
        amount_per_invoice: int,
        parent_invoice_id: Optional[int] = None,
        other_surcharges: int = 0,
    ):
        interim_invoices = []

        for due_date in payment_dates:
            invoice = Lane_Interim_Invoice(
                contract_id=contract_id,
                contract_type=contract_type,
                invoice_type="Interim",
                billing_date=date.today(),
                due_date=due_date,
                description=f"{contract_type} interim payment due {due_date}",
                status="Pending",
                is_paid=False,
                is_subinvoice=True,
                is_applied=False,
                parent_invoice_id=parent_invoice_id,
                carrier_company_id=carrier_company_id,
                carrier_name=carrier_name,
                carrier_email=carrier_email,
                carrier_address=carrier_address,
                carrier_financial_account_id=carrier_financial_account_id,
                invoice_payment_terms=invoice_payment_terms,
                carrier_bank=carrier_bank,
                carrier_bank_account=carrier_bank_account,
                payment_reference=f"{contract_type.upper()}-INT-{contract_id}-{due_date}",
                base_amount=amount_per_invoice,
                other_surcharges=other_surcharges,
                due_amount=amount_per_invoice + other_surcharges,
                paid_out_amount=0,
                detention_fees=0
            )
            db.add(invoice)
            interim_invoices.append(invoice)

        db.commit()
        for invoice in interim_invoices:
            db.refresh(invoice)

        return interim_invoices
    

    @staticmethod
    def generate_assigned_shipment_invoice(
        db: Session,
        contract_id: int,
        contract_type: str,
        shipment_id: int,
        shipment_type: str,
        carrier_company_id: int,
        carrier_financial_account_id: int,
        payment_terms: str,
        carrier_bank: str,
        carrier_bank_account: str,
        business_name: str,
        contact_person_name: str,
        business_email: str,
        business_address: str,
        origin_address: str,
        destination_address: str,
        pickup_date: date,
        distance: int,
        transit_time: str,
        amount: int,
        parent_invoice_id: Optional[int] = None,
        other_surcharges: int = 0,
        detention_fees: int = 0,
        due_date: Optional[date] = None,
    ):
        invoice = Load_Invoice(
            contract_id=contract_id,
            contract_type=contract_type,
            shipment_id=shipment_id,
            shipment_type=shipment_type,
            invoice_type="Load Invoice",
            billing_date=date.today(),
            due_date=due_date,
            description=f"Load invoice for shipment {shipment_id}",
            status="Pending",
            is_paid=False,
            is_applied=False,
            is_subinvoice=True,
            parent_invoice_id=parent_invoice_id,
            carrier_company_id=carrier_company_id,
            carrier_financial_account_id=carrier_financial_account_id,
            payment_terms=payment_terms,
            carrier_bank=carrier_bank,
            carrier_bank_account=carrier_bank_account,
            payment_reference=f"LOAD-{contract_id}-{shipment_id}",
            business_name=business_name,
            contact_person_name=contact_person_name,
            business_email=business_email,
            business_address=business_address,
            origin_address=origin_address,
            destination_address=destination_address,
            pickup_date=pickup_date,
            distance=distance,
            transit_time=transit_time,
            base_amount=amount,
            other_surcharges=other_surcharges,
            detention_fees=detention_fees,
            due_amount=amount + other_surcharges + detention_fees,
            paid_out_amount=0
        )
        db.add(invoice)
        db.flush()
        db.refresh(invoice)
        return invoice