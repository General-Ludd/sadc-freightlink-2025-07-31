"""
payment_engine.py

SADC FREIGHTLINK Payment Engine

Responsible for:
- Initializing shipment payment schedules
- Calculating submission dates
- Calculating due dates
- Calculating expected payment dates
- Updating payment lifecycle
- Overdue detection

NOTE:
This engine DOES NOT:
- Generate invoices
- Generate PDFs
- Email customers
- Reconcile bank payments
"""

from datetime import date
from enum import Enum

from services.finance.finance_utils import (
    calculate_due_date,
    next_statement_date,
)


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    DUE = "DUE"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class FinanceStatus(str, Enum):
    AWAITING_DOCUMENTS = "AWAITING_DOCUMENTS"
    AWAITING_INVOICE = "AWAITING_INVOICE"
    AWAITING_SUBMISSION = "AWAITING_SUBMISSION"
    SUBMITTED = "SUBMITTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


class PaymentEngine:

    def initialize_payment(self, financial_account, trigger_date: date):

        schedule = {
            "payment_type": financial_account.payment_type,
            "payment_terms": financial_account.payment_terms,
            "payment_days": financial_account.payment_days,
            "payment_trigger": financial_account.payment_trigger,
            "statement_required": financial_account.statement_required,
            "submission_date": None,
            "due_date": None,
            "expected_payment_date": None,
            "payment_status": PaymentStatus.PENDING.value,
            "finance_status": FinanceStatus.AWAITING_INVOICE.value,
        }

        submission_date = self.calculate_submission_date(
            financial_account,
            trigger_date,
        )

        schedule["submission_date"] = submission_date

        if financial_account.payment_trigger == "Statement Date":
            due_trigger = submission_date
        else:
            due_trigger = trigger_date

        due_date = calculate_due_date(
            due_trigger,
            financial_account.payment_days or 0,
        )

        schedule["due_date"] = due_date
        schedule["expected_payment_date"] = due_date

        return schedule

    def calculate_submission_date(self, financial_account, trigger_date):

        if not financial_account.statement_required:
            return trigger_date

        return next_statement_date(
            trigger_date,
            financial_account.statement_cycle,
            financial_account.statement_days,
        )

    def mark_invoice_submitted(self, finance_record):

        finance_record["payment_status"] = PaymentStatus.SUBMITTED.value
        finance_record["finance_status"] = FinanceStatus.SUBMITTED.value

        return finance_record

    def mark_due(self, finance_record):

        finance_record["payment_status"] = PaymentStatus.DUE.value
        finance_record["finance_status"] = FinanceStatus.PAYMENT_PENDING.value

        return finance_record

    def mark_paid(self, finance_record, payment_date):

        finance_record["payment_status"] = PaymentStatus.PAID.value
        finance_record["finance_status"] = FinanceStatus.PAID.value
        finance_record["payment_received_date"] = payment_date

        return finance_record

    def check_overdue(self, finance_record):

        if finance_record["payment_status"] == PaymentStatus.PAID.value:
            return finance_record

        if date.today() > finance_record["expected_payment_date"]:

            finance_record["payment_status"] = PaymentStatus.OVERDUE.value
            finance_record["finance_status"] = FinanceStatus.OVERDUE.value

        return finance_record


payment_engine = PaymentEngine()