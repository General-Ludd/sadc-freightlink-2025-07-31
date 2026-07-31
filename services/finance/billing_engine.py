"""
billing_engine.py

SADC FREIGHTLINK
Production Billing Engine

This engine is responsible for initializing the complete billing
workflow whenever a shipment or lane booking is created.

Responsibilities
----------------
• Validate Financial Account
• Determine Billing Policy
• Calculate Statement Dates
• Calculate Due Dates
• Create Shipment Invoice
• Create Lane Invoice
• Return Billing Result

This engine DOES NOT

• Generate PDFs
• Send Emails
• Submit Statements
• Reconcile Payments

Those responsibilities belong to the
Submission Engine and Reconciliation Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy.orm import Session

from models.brokerage.finance import FinancialAccounts, Interim_Invoice, Invoices, Lane_Interim_Invoice, Lane_Invoice, Load_Invoice, Shipment_Invoice


from services.finance.invoice_builder import InvoiceBuilder


# ==============================================================================
# BILLING STATUS
# ==============================================================================

class BillingStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    INVOICE_CREATED = "INVOICE_CREATED"
    READY_FOR_SUBMISSION = "READY_FOR_SUBMISSION"
    SUBMITTED = "SUBMITTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


# ==============================================================================
# INVOICE TYPES
# ==============================================================================

class InvoiceType(str, Enum):
    SHIPMENT = "SHIPMENT"
    LANE = "LANE"
    INTERIM = "INTERIM"
    ADJUSTMENT = "ADJUSTMENT"
    CREDIT_NOTE = "CREDIT_NOTE"


# ==============================================================================
# BILLING CONTEXT
# ==============================================================================

@dataclass
class BillingContext:

    db: Session

    shipment: object

    financial_account: FinancialAccounts

    booking_amount: Decimal

    company_id: int

    shipment_type: str

    shipment_id: int

    invoice: Optional[Shipment_Invoice] = None

    billing_date: Optional[date] = None

    submission_date: Optional[date] = None

    statement_date: Optional[date] = None

    statement_cycle: Optional[str] = None

    statement_batch: Optional[str] = None

    due_date: Optional[date] = None

    expected_payment_date: Optional[date] = None

    payment_status: str = "Pending"

    billing_status: BillingStatus = BillingStatus.INITIALIZED


# ==============================================================================
# BILLING RESULT
# ==============================================================================

@dataclass
class BillingResult:

    success: bool

    invoice: Shipment_Invoice

    billing_date: date

    submission_date: date

    statement_date: Optional[date]

    statement_cycle: Optional[str]

    statement_batch: Optional[str]

    due_date: date

    expected_payment_date: date

    payment_terms: str

    payment_type: str

    invoice_status: str

    billing_status: BillingStatus

    message: str


# ==============================================================================
# BILLING ENGINE
# ==============================================================================

class BillingEngine:

    """
    Core Billing Engine.

    Every shipment, lane and contract booking
    enters the finance system through this class.
    """

    def __init__(self):

        self.builder = InvoiceBuilder()

    # ------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ------------------------------------------------------------------

    def initialize_shipment_billing(
        self,
        db: Session,
        shipment,
        financial_account: FinancialAccounts,
        booking_amount: Decimal,
    ) -> BillingResult:

        context = BillingContext(

            db=db,

            shipment=shipment,

            financial_account=financial_account,

            booking_amount=booking_amount,

            company_id=shipment.shipper_company_id,

            shipment_type=shipment.type,

            shipment_id=shipment.id,
        )

        self._validate_context(context)

        # ----------------------------------------------------------
        # Stage 1
        # Load the client's finance policy
        # ----------------------------------------------------------

        context = self._calculate_billing_policy(context)

        # ----------------------------------------------------------
        # Stage 2
        # Billing Date
        #
        # Every booking is billed immediately.
        # The statement/payment dates may differ.
        # ----------------------------------------------------------

        context.billing_date = date.today()

        # ----------------------------------------------------------
        # Stage 3
        # Determine Statement Cycle
        # ----------------------------------------------------------

        context = self._calculate_statement_cycle(context)

        # ----------------------------------------------------------
        # Stage 4
        # Determine Submission Date
        # ----------------------------------------------------------

        context = self._calculate_submission_date(context)

        # ----------------------------------------------------------
        # Stage 5
        # Calculate Due Date
        # ----------------------------------------------------------

        context = self._calculate_due_date(context)

        # ----------------------------------------------------------
        # Stage 6
        # Create Invoice
        #
        # Spot bookings only create Shipment Invoices.
        #
        # Lane booking workflows will call
        # _create_lane_invoice()
        # and _create_interim_invoice()
        # separately.
        # ----------------------------------------------------------

        context = self._create_shipment_invoice(context)

        # ----------------------------------------------------------
        # Stage 7
        # Update Financial Account
        # ----------------------------------------------------------
        context = self._update_financial_account(context)
        # ----------------------------------------------------------
        # Stage 8
        # Billing Ready
        # ----------------------------------------------------------

        context.billing_status = BillingStatus.READY_FOR_SUBMISSION

        # ----------------------------------------------------------
        # Persist Invoice
        # ----------------------------------------------------------

        db.add(context.invoice)
        db.commit()
        db.refresh(context.invoice)

        # ----------------------------------------------------------
        # Return Billing Result
        # ----------------------------------------------------------

        return self._build_result(context)

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_context(
        context: BillingContext
    ) -> None:

        if context.financial_account is None:
            raise ValueError("Financial Account not found.")

        if context.booking_amount <= 0:
            raise ValueError("Booking amount must be greater than zero.")

        if context.shipment is None:
            raise ValueError("Shipment cannot be None.")

        if context.shipment.id is None:
            raise ValueError("Shipment must be saved before billing.")

        if context.shipment.company_id is None:
            raise ValueError("Shipment company is missing.")

        if context.financial_account.payment_type is None:
            raise ValueError("Payment Type has not been configured.")

        if context.financial_account.payment_terms is None:
            raise ValueError("Payment Terms have not been configured.")

    # ------------------------------------------------------------------
    # PLACEHOLDERS
    # ------------------------------------------------------------------

    def _calculate_billing_policy(
        self,
        context: BillingContext,
    ) -> BillingContext:
        """
        Determines the client's billing policy.

        This function does NOT calculate dates.
        It simply validates and loads the billing
        configuration into the BillingContext for
        later processing.
        """

        account = context.financial_account

        # -------------------------------------------------------------
        # PAYMENT TYPE
        # -------------------------------------------------------------

        payment_type = account.payment_type

        if payment_type not in (
            "PAB",
            "COD",
            "Credit Account",
            "Contract Account",
            "Instant EFT",
            "Credit Card",
        ):
            raise ValueError(
                f"Unsupported payment type: {payment_type}"
            )

        # -------------------------------------------------------------
        # PAYMENT TERMS
        # -------------------------------------------------------------

        payment_terms = account.payment_terms

        if payment_type in (
            "Credit Account",
            "Contract Account",
        ) and payment_terms is None:
            raise ValueError(
                "Credit accounts require payment terms."
            )

        # -------------------------------------------------------------
        # PAYMENT DAYS
        # -------------------------------------------------------------

        payment_days = account.payment_days or 0

        if payment_days < 0:
            raise ValueError(
                "Payment days cannot be negative."
            )

        # -------------------------------------------------------------
        # PAYMENT TRIGGER
        # -------------------------------------------------------------

        payment_trigger = account.payment_trigger

        if payment_type in (
            "Credit Account",
            "Contract Account",
        ):
            if payment_trigger is None:
                raise ValueError(
                    "Credit accounts require a payment trigger."
                )

        # -------------------------------------------------------------
        # STATEMENT POLICY
        # -------------------------------------------------------------

        statement_required = bool(account.statement_required)

        statement_cycle = account.statement_cycle

        statement_days = account.statement_days or []

        if statement_required:

            if statement_cycle is None:
                raise ValueError(
                    "Statement cycle has not been configured."
                )

            if len(statement_days) == 0:
                raise ValueError(
                    "Statement submission days are required."
                )

        # -------------------------------------------------------------
        # POD POLICY
        # -------------------------------------------------------------

        pod_required = bool(account.pod_required)

        pod_cutoff_days = account.pod_cutoff_days or []

        # -------------------------------------------------------------
        # PAYMENT RUN
        # -------------------------------------------------------------

        payment_run_type = account.payment_run_type

        payment_run_days = account.payment_run_days or []

        # -------------------------------------------------------------
        # STORE POLICY
        # -------------------------------------------------------------

        #
        # These attributes are dynamically attached to the
        # BillingContext so that later stages don't need
        # to read the FinancialAccount again.
        #

        context.payment_type = payment_type
        context.payment_terms = payment_terms
        context.payment_days = payment_days
        context.payment_trigger = payment_trigger

        context.statement_required = statement_required
        context.statement_cycle_policy = statement_cycle
        context.statement_days = statement_days

        context.pod_required = pod_required
        context.pod_cutoff_days = pod_cutoff_days

        context.payment_run_type = payment_run_type
        context.payment_run_days = payment_run_days

        return context

    # ------------------------------------------------------------------
    # STATEMENT CYCLE CALCULATOR
    # ------------------------------------------------------------------

    def _calculate_statement_cycle(
        self,
        context: BillingContext,
    ) -> BillingContext:
        """
        Calculates the statement cycle this shipment belongs to.

        This function determines:

            • Statement Date
            • Statement Cycle
            • Statement Batch

        It does NOT calculate payment due dates.
        """

        from datetime import timedelta
        import calendar

        shipment_date = context.shipment.pickup_date

        if shipment_date is None:
            shipment_date = date.today()

        #
        # ---------------------------------------------------------
        # CLIENT DOES NOT REQUIRE STATEMENTS
        # ---------------------------------------------------------
        #

        if not context.statement_required:

            context.statement_date = shipment_date + timedelta(days=1)

            context.statement_cycle = "Immediate"

            context.statement_batch = (
                f"IMM-{context.company_id}-"
                f"{context.statement_date.strftime('%Y%m%d')}"
            )

            return context

        #
        # ---------------------------------------------------------
        # WEEKLY
        # ---------------------------------------------------------
        #

        if context.statement_cycle_policy == "Weekly":

            days_until_friday = (4 - shipment_date.weekday()) % 7

            statement_date = shipment_date + timedelta(days=days_until_friday)

            context.statement_date = statement_date

            context.statement_cycle = (
                f"Week Ending "
                f"{statement_date.strftime('%d %b %Y')}"
            )

            context.statement_batch = (
                f"WEEKLY-{context.company_id}-"
                f"{statement_date.strftime('%Y%m%d')}"
            )

            return context

        #
        # ---------------------------------------------------------
        # FORTNIGHTLY
        # ---------------------------------------------------------
        #

        if context.statement_cycle_policy == "Fortnightly":

            if shipment_date.day <= 15:

                statement_date = shipment_date.replace(day=15)

                cycle = (
                    f"1 - 15 "
                    f"{shipment_date.strftime('%B %Y')}"
                )

            else:

                last_day = calendar.monthrange(
                    shipment_date.year,
                    shipment_date.month
                )[1]

                statement_date = shipment_date.replace(day=last_day)

                cycle = (
                    f"16 - {last_day} "
                    f"{shipment_date.strftime('%B %Y')}"
                )

            context.statement_date = statement_date
            context.statement_cycle = cycle
            context.statement_batch = (
                f"FORTNIGHT-{context.company_id}-"
                f"{statement_date.strftime('%Y%m%d')}"
            )

            return context

        #
        # ---------------------------------------------------------
        # TWICE MONTHLY
        # ---------------------------------------------------------
        #

        if context.statement_cycle_policy == "Twice Monthly":

            statement_days = sorted(context.statement_days)

            if len(statement_days) != 2:
                raise ValueError(
                    "Twice Monthly requires exactly two statement days."
                )

            first_day = statement_days[0]
            second_day = statement_days[1]

            #
            # BEFORE FIRST CUT-OFF
            #

            if shipment_date.day < first_day:

                statement_date = shipment_date.replace(day=first_day)

                cycle = (
                    f"1 - {first_day-1} "
                    f"{shipment_date.strftime('%B %Y')}"
                )

            #
            # BEFORE SECOND CUT-OFF
            #

            elif shipment_date.day < second_day:

                statement_date = shipment_date.replace(day=second_day)

                cycle = (
                    f"{first_day} - {second_day-1} "
                    f"{shipment_date.strftime('%B %Y')}"
                )

            #
            # NEXT MONTH FIRST CUT-OFF
            #

            else:

                if shipment_date.month == 12:

                    next_month = 1
                    next_year = shipment_date.year + 1

                else:

                    next_month = shipment_date.month + 1
                    next_year = shipment_date.year

                statement_date = date(
                    next_year,
                    next_month,
                    first_day
                )

                last_day = calendar.monthrange(
                    shipment_date.year,
                    shipment_date.month
                )[1]

                cycle = (
                    f"{second_day} {shipment_date.strftime('%b')} - "
                    f"{first_day-1} "
                    f"{statement_date.strftime('%b %Y')}"
                )

            context.statement_date = statement_date
            context.statement_cycle = cycle
            context.statement_batch = (
                f"TWICE-{context.company_id}-"
                f"{statement_date.strftime('%Y%m%d')}"
            )

            return context

        #
        # ---------------------------------------------------------
        # MONTHLY
        # ---------------------------------------------------------
        #

        if context.statement_cycle_policy == "Monthly":

            statement_day = context.statement_days[0]

            if shipment_date.day <= statement_day:

                statement_date = shipment_date.replace(day=statement_day)

            else:

                if shipment_date.month == 12:

                    statement_date = date(
                        shipment_date.year + 1,
                        1,
                        statement_day,
                    )

                else:

                    statement_date = date(
                        shipment_date.year,
                        shipment_date.month + 1,
                        statement_day,
                    )

            context.statement_date = statement_date

            context.statement_cycle = shipment_date.strftime("%B %Y")

            context.statement_batch = (
                f"MONTHLY-{context.company_id}-"
                f"{statement_date.strftime('%Y%m%d')}"
            )

            return context

        #
        # ---------------------------------------------------------
        # CUSTOM
        # ---------------------------------------------------------
        #

        raise ValueError(
            f"Unsupported statement cycle: "
            f"{context.statement_cycle_policy}"
        )

    # ------------------------------------------------------------------
    # SUBMISSION DATE CALCULATOR
    # ------------------------------------------------------------------

    def _calculate_submission_date(
        self,
        context: BillingContext,
    ) -> BillingContext:
        """
        Determines when the invoice or statement
        should be submitted to the client's finance
        department.

        This does NOT calculate payment due dates.

        It only determines the submission date based
        on the customer's billing policy.
        """

        from datetime import timedelta

        shipment_date = context.shipment.pickup_date

        if shipment_date is None:
            shipment_date = date.today()

        payment_type = context.payment_type

        #
        # ---------------------------------------------------------
        # PAYMENT AT BOOKING
        # ---------------------------------------------------------
        #

        if payment_type == "PAB":

            context.submission_date = context.billing_date

            return context

        #
        # ---------------------------------------------------------
        # CASH ON DELIVERY
        # ---------------------------------------------------------
        #

        if payment_type == "COD":

            context.submission_date = shipment_date + timedelta(days=1)

            return context

        #
        # ---------------------------------------------------------
        # CREDIT CARD
        # ---------------------------------------------------------
        #

        if payment_type == "Credit Card":

            context.submission_date = context.billing_date

            return context

        #
        # ---------------------------------------------------------
        # INSTANT EFT
        # ---------------------------------------------------------
        #

        if payment_type == "Instant EFT":

            context.submission_date = context.billing_date

            return context

        #
        # ---------------------------------------------------------
        # CREDIT / CONTRACT ACCOUNT
        # ---------------------------------------------------------
        #

        if payment_type in ("Credit Account", "Contract Account"):

            #
            # Client requires statements.
            # Invoice is held until the statement date.
            #

            if context.statement_required:

                context.submission_date = context.statement_date

            #
            # Immediate invoice submission
            #

            else:

                context.submission_date = shipment_date + timedelta(days=1)

            return context

        #
        # ---------------------------------------------------------
        # FALLBACK
        # ---------------------------------------------------------
        #

        context.submission_date = context.billing_date

        return context

    # ------------------------------------------------------------------
    # DUE DATE CALCULATOR
    # ------------------------------------------------------------------

    def _calculate_due_date(
        self,
        context: BillingContext,
    ) -> BillingContext:
        """
        Calculates the contractual payment due date.

        The due date is calculated using the client's
        configured payment trigger and payment days.

        Examples
        --------
        PAB
            Due immediately.

        COD
            Pickup + 1 day.

        NET30 from Statement
            Statement Date + 30 days.

        NET15 from Invoice
            Invoice Date + 15 days.
        """

        from datetime import timedelta

        shipment = context.shipment

        booking_date = context.billing_date

        pickup_date = shipment.pickup_date

        delivery_date = getattr(
            shipment,
            "delivery_date",
            None
        )

        payment_type = context.payment_type

        payment_trigger = context.payment_trigger

        payment_days = context.payment_days or 0

        #
        # ----------------------------------------------------------
        # PAYMENT AT BOOKING
        # ----------------------------------------------------------
        #

        if payment_type == "PAB":

            context.due_date = booking_date
            context.expected_payment_date = booking_date

            return context

        #
        # ----------------------------------------------------------
        # CASH ON DELIVERY
        # ----------------------------------------------------------
        #

        if payment_type == "COD":

            due = pickup_date + timedelta(days=1)

            context.due_date = due
            context.expected_payment_date = due

            return context

        #
        # ----------------------------------------------------------
        # INSTANT EFT
        # ----------------------------------------------------------
        #

        if payment_type == "Instant EFT":

            context.due_date = booking_date
            context.expected_payment_date = booking_date

            return context

        #
        # ----------------------------------------------------------
        # CREDIT CARD
        # ----------------------------------------------------------
        #

        if payment_type == "Credit Card":

            context.due_date = booking_date
            context.expected_payment_date = booking_date

            return context

        #
        # ----------------------------------------------------------
        # CREDIT / CONTRACT ACCOUNTS
        # ----------------------------------------------------------
        #

        trigger_date = None

        match payment_trigger:

            case "Booking Date":
                trigger_date = booking_date

            case "Pickup Date":
                trigger_date = pickup_date

            case "Delivery Date":

                if delivery_date is None:
                    delivery_date = pickup_date

                trigger_date = delivery_date

            case "Invoice Date":
                trigger_date = context.submission_date

            case "POD Approved":

                #
                # During booking the POD does not exist.
                # Estimate approval as the submission date.
                #

                trigger_date = context.submission_date

            case "Statement Date":
                trigger_date = context.statement_date

            case "Manual":

                #
                # Finance team will manually update later.
                #

                context.due_date = None
                context.expected_payment_date = None

                return context

            case _:

                raise ValueError(
                    f"Unsupported payment trigger: "
                    f"{payment_trigger}"
                )

        #
        # ----------------------------------------------------------
        # CALCULATE DUE DATE
        # ----------------------------------------------------------
        #

        due_date = trigger_date + timedelta(days=payment_days)

        context.due_date = due_date

        context.expected_payment_date = due_date

        return context

    # ------------------------------------------------------------------
    # SHIPMENT INVOICE CREATION
    # ------------------------------------------------------------------

    def _create_shipment_invoice(
        self,
        context: BillingContext,
    ) -> BillingContext:
        """
        Creates and persists a Shipment Invoice.

        This method is responsible for:

        • Building the invoice
        • Populating finance information
        • Saving it to the database
        • Updating the BillingContext
        """

        shipment = context.shipment
        account = context.financial_account

        # ----------------------------------------------------------
        # BUILD BASE INVOICE
        # ----------------------------------------------------------

        invoice = Shipment_Invoice(

            #
            # Invoice Information
            #

            invoice_type="Service",

            shipment_id=shipment.id,

            shipment_type=shipment.type,

            contract_id=getattr(shipment, "contract_id", None),

            contract_type=getattr(shipment, "contract_type", None),

            description=f"{shipment.type} Shipment",

            status="Outstanding",

            is_paid=False,

            is_applied=False,

            #
            # Billing
            #

            billing_date=context.billing_date,

            due_date=context.due_date,

            #
            # Customer
            #

            company_id=shipment.company_id,

            financial_account_id=account.id,

            payment_terms=str(account.payment_terms),

            business_name=shipment.business_name,

            contact_person_name=getattr(
                shipment,
                "contact_person_name",
                "",
            ),

            business_email=shipment.business_email,

            billing_address=shipment.billing_address,

            #
            # Shipment
            #

            origin_address=shipment.origin_address,

            destination_address=shipment.destination_address,

            pickup_date=shipment.pickup_date,

            distance=shipment.distance,

            transit_time=shipment.estimated_transit_time,

            #
            # Charges
            #

            base_amount=context.booking_amount,

            other_surcharges=0,

            vat=0,

            total=context.booking_amount,

            due_amount=context.booking_amount,

            paid_amount=0,

            late_fees=0,
        )

        #
        # ----------------------------------------------------------
        # SAVE
        # ----------------------------------------------------------
        #

        context.db.add(invoice)

        context.db.flush()

        #
        # ----------------------------------------------------------
        # UPDATE CONTEXT
        # ----------------------------------------------------------
        #

        context.invoice = invoice

        context.billing_status = BillingStatus.INVOICE_CREATED

        return context

    # ------------------------------------------------------------------
    # CREATE LANE MASTER INVOICE
    # ------------------------------------------------------------------

    def _create_lane_invoice(
        self,
        context: BillingContext,
    ) -> BillingContext:
        """
        Creates the master Lane Invoice.

        The Lane Invoice represents the commercial
        agreement for a dedicated transport lane.

        It is the parent of:

            • Interim Invoices
            • Shipment Invoices
        """

        shipment = context.shipment
        account = context.financial_account

        lane_invoice = Invoices(

            #
            # Invoice Information
            #

            invoice_type="Contract Lane",

            contract_id=getattr(
                shipment,
                "contract_id",
                None,
            ),

            contract_type=getattr(
                shipment,
                "contract_type",
                None,
            ),

            parent_invoice_id=None,

            description=f"Dedicated Lane - {shipment.reference_number}",

            status="Active",

            is_paid=False,

            #
            # Billing
            #

            billing_date=context.billing_date,

            due_date=context.due_date,

            #
            # Customer
            #

            company_id=shipment.company_id,

            financial_account_id=account.id,

            payment_terms=str(account.payment_terms),

            business_name=shipment.business_name,

            contact_person_name=getattr(
                shipment,
                "contact_person_name",
                "",
            ),

            business_email=shipment.business_email,

            billing_address=shipment.billing_address,

            #
            # Charges
            #
            # Master invoices do not hold shipment
            # values. Totals are accumulated through
            # Interim Invoices.
            #

            base_amount=0,

            toll_fees=0,

            other_surcharges=0,

            vat=0,

            total=0,

            due_amount=0,

            paid_amount=0,

            late_fees=0,

            payment_reference=getattr(
                shipment,
                "reference_number",
                None,
            ),
        )

        #
        # Persist
        #

        context.db.add(lane_invoice)

        context.db.flush()

        context.invoice = lane_invoice

        context.billing_status = BillingStatus.INVOICE_CREATED

        return context

    # ------------------------------------------------------------------
    # CREATE INTERIM INVOICE
    # ------------------------------------------------------------------

    def _create_interim_invoice(
        self,
        context: BillingContext,
    ) -> BillingContext:
        """
        Creates (or retrieves) the Interim Invoice for the
        current billing cycle.

        One Interim Invoice exists per:

            Financial Account
            +
            Statement Batch

        Shipment invoices belonging to the same billing
        cycle will reference this invoice.
        """

        shipment = context.shipment
        account = context.financial_account

        #
        # ----------------------------------------------------------
        # Look for an existing Interim Invoice
        # ----------------------------------------------------------
        #

        interim_invoice = (
            context.db.query(Interim_Invoice)
            .filter(
                Interim_Invoice.financial_account_id == account.id,
                Interim_Invoice.contract_id == getattr(
                    shipment,
                    "contract_id",
                    None,
                ),
                Interim_Invoice.billing_date == context.statement_date,
                Interim_Invoice.status != "Cancelled",
            )
            .first()
        )

        #
        # ----------------------------------------------------------
        # Already exists
        # ----------------------------------------------------------
        #

        if interim_invoice:

            context.interim_invoice = interim_invoice

            return context

        #
        # ----------------------------------------------------------
        # Create new Interim Invoice
        # ----------------------------------------------------------
        #

        interim_invoice = Interim_Invoice(

            invoice_type="Interim",

            contract_id=getattr(
                shipment,
                "contract_id",
                None,
            ),

            contract_type=getattr(
                shipment,
                "contract_type",
                None,
            ),

            #
            # Parent is the Lane Invoice
            #

            parent_invoice_id=getattr(
                shipment,
                "invoice_id",
                None,
            ),

            is_subinvoice=True,

            billing_date=context.statement_date,

            due_date=context.due_date,

            description=(
                f"Interim Invoice "
                f"{context.statement_cycle}"
            ),

            status="Open",

            is_paid=False,

            is_applied=False,

            #
            # Customer
            #

            company_id=shipment.company_id,

            financial_account_id=account.id,

            payment_terms=str(account.payment_terms),

            business_name=shipment.business_name,

            contact_person_name=getattr(
                shipment,
                "contact_person_name",
                "",
            ),

            business_email=shipment.business_email,

            billing_address=shipment.billing_address,

            #
            # Totals
            # These will be updated as Shipment
            # Invoices are attached.
            #

            base_amount=0,

            other_surcharges=0,

            vat=0,

            total=0,

            due_amount=0,

            paid_amount=0,

            late_fees=0,

            payment_reference=(
                f"INT-{account.id}-"
                f"{context.statement_date.strftime('%Y%m%d')}"
            ),
        )

        #
        # ----------------------------------------------------------
        # Persist
        # ----------------------------------------------------------
        #

        context.db.add(interim_invoice)

        context.db.flush()

        context.interim_invoice = interim_invoice

        return context

# ------------------------------------------------------------------
# UPDATE FINANCIAL ACCOUNT
# ------------------------------------------------------------------

def _update_financial_account(
    self,
    context: BillingContext,
) -> BillingContext:
    """
    Updates the customer's Financial Account after an invoice
    has been created.

    This reserves credit immediately for credit customers and
    processes immediate payments for prepaid customers.

    Nothing outside the Billing Engine should manipulate the
    customer's finance balances.
    """

    account = context.financial_account

    amount = Decimal(context.booking_amount)

    payment_type = context.payment_type

    #
    # ----------------------------------------------------------
    # PAYMENT AT BOOKING
    # ----------------------------------------------------------
    #

    if payment_type == "PAB":

        account.credit_balance = (
            Decimal(account.credit_balance or 0)
            - amount
        )

        account.available_credit = (
            Decimal(account.available_credit or 0)
            - amount
        )

        context.invoice.status = "Paid"

        context.invoice.is_paid = True

        context.invoice.paid_amount = amount

        context.invoice.due_amount = Decimal(0)

    #
    # ----------------------------------------------------------
    # CREDIT / CONTRACT ACCOUNT
    # ----------------------------------------------------------
    #

    else:

        account.projected_balance = (
            Decimal(account.projected_balance or 0)
            + amount
        )

        context.invoice.status = "Outstanding"

        context.invoice.is_paid = False

        context.invoice.paid_amount = Decimal(0)

        context.invoice.due_amount = amount

    #
    # ----------------------------------------------------------
    # Persist
    # ----------------------------------------------------------
    #

    context.db.add(account)

    context.db.add(context.invoice)

    context.db.flush()

    return context

    # ------------------------------------------------------------------
    # BUILD BILLING RESULT
    # ------------------------------------------------------------------

    def _build_result(
        self,
        context: BillingContext,
    ) -> BillingResult:
        """
        Builds the BillingResult returned to the booking
        workflow.

        The booking function should never need to inspect
        the BillingContext directly. Instead, it receives
        this immutable BillingResult containing all
        information required to continue processing.
        """

        if context.invoice is None:
            raise ValueError(
                "Billing Engine failed to create an invoice."
            )

        return BillingResult(

            success=True,

            invoice=context.invoice,

            billing_date=context.billing_date,

            submission_date=context.submission_date,

            statement_date=context.statement_date,

            statement_cycle=context.statement_cycle,

            statement_batch=context.statement_batch,

            due_date=context.due_date,

            expected_payment_date=context.expected_payment_date,

            payment_terms=str(context.payment_terms),

            payment_type=str(context.payment_type),

            invoice_status=context.invoice.status,

            billing_status=context.billing_status,

            message="Billing successfully initialized.",
        )


# ==============================================================================
# SINGLETON
# ==============================================================================

billing_engine = BillingEngine()