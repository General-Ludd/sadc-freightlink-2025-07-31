from datetime import date
from fastapi import Depends
from requests import Session
from db.database import SessionLocal
from models.brokerage.finance import Shipment_Invoice, Interim_Invoice, FinancialAccounts
from utils.billing import BillingEngine

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def apply_invoice_to_account(invoice: Shipment_Invoice,
                             today: date,
                             db: Session = Depends(get_db),
) -> None:
    """
    Apply a shipment or its parent interim invoice to the financial account if in active billing cycle.
    """

    # Fetch financial account
    financial_account = db.query(FinancialAccounts).filter_by(company_id=invoice.company_id).first()
    if not financial_account:
        return  # No account found

    # Check if invoice is due in the current billing cycle
    if BillingEngine.is_billing_cycle_active(invoice.due_date, financial_account.payment_terms, today):

        if invoice.is_subinvoice and invoice.parent_invoice_id:
            # Fetch parent interim invoice
            parent_invoice = db.query(Interim_Invoice).filter_by(id=invoice.parent_invoice_id).first()
            if parent_invoice and not parent_invoice.is_applied:
                financial_account.total_outstanding += parent_invoice.due_amount
                parent_invoice.is_applied = True
                db.add(parent_invoice)
        else:
            # Direct shipment invoice (non-sub-invoice)
            financial_account.total_outstanding += invoice.due_amount

        invoice.is_applied = True
        db.add(invoice)
        db.add(financial_account)


def billing_trigger(db: Session) -> None:
    """
    Go through unapplied shipment invoices and apply them to financial accounts based on payment terms.
    """
    today = date.today()

    unapplied_invoices = db.query(Shipment_Invoice).filter_by(is_applied=False).all()

    for invoice in unapplied_invoices:
        apply_invoice_to_account(db, invoice, today)

    db.commit()