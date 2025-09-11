from sqlalchemy.orm import Session
from models.brokerage.finance import FinancialAccounts, BankTransaction
import math

def process_deposit(db: Session, transaction_id: str, unique_transaction_key: str,
                    amount: float, reference: str, timestamp: str):
    """
    Process Nedbank deposit into FinancialAccount.
    Ensures unique_transaction_key and converts floats to integers.
    """

    # Prevent duplicates
    existing = db.query(BankTransaction).filter_by(unique_transaction_key=unique_transaction_key).first()
    if existing:
        return {"status": "ignored", "message": "Duplicate transaction from Nedbank"}

    # Convert amount to integer
    deposit_amount = int(math.floor(amount))

    if not reference.startswith("FA-"):
        return {"status": "error", "message": "Invalid reference format"}

    account_id = int(reference.split("-")[1])
    account = db.query(FinancialAccounts).get(account_id)
    if not account:
        return {"status": "error", "message": f"Financial account {account_id} not found"}

    # Apply business rules
    if account.payment_terms == "PAB":
        account.credit_balance += deposit_amount
    else:
        if deposit_amount >= account.total_outstanding:
            excess = deposit_amount - account.total_outstanding
            account.total_paid += account.total_outstanding
            account.total_outstanding = 0
            account.credit_balance += excess
        else:
            account.total_outstanding -= deposit_amount
            account.total_paid += deposit_amount

    # Save processed transaction
    txn = BankTransaction(
        transaction_id=transaction_id,
        unique_transaction_key=unique_transaction_key,
        reference=reference,
        amount=deposit_amount,
    )
    db.add(txn)
    db.commit()

    return {
        "status": "success",
        "account_id": account_id,
        "new_credit_balance": account.credit_balance,
        "new_total_outstanding": account.total_outstanding,
        "new_total_paid": account.total_paid
    }