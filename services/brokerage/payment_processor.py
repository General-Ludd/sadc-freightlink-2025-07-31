from sqlalchemy.orm import Session
from models.brokerage.finance import FinancialAccounts
import math

def process_deposit(db: Session, amount: float, reference: str, timestamp: str):
    """
    Process Nedbank deposit and update FinancialAccount accordingly.
    Convert floats from bank to integers before applying.
    """

    # Ensure reference is Financial Account ID
    if not reference.startswith("FA-"):
        return {"status": "error", "message": "Invalid reference"}

    account_id = int(reference.split("-")[1])
    account = db.query(FinancialAccounts).get(account_id)
    if not account:
        return {"status": "error", "message": f"Financial account {account_id} not found"}

    # Convert deposit amount → integer (floor by default)
    deposit_amount = int(math.floor(amount))

    if account.payment_terms == "PAB":
        # Prepaid account: all deposits become credit
        account.credit_balance += deposit_amount

    else:
        # Postpaid: deduct deposits from outstanding
        if deposit_amount >= account.total_outstanding:
            # More than enough → clear outstanding, put excess in credit
            excess = deposit_amount - account.total_outstanding
            account.total_paid += account.total_outstanding
            account.total_outstanding = 0
            account.credit_balance += excess
        else:
            # Partial payment
            account.total_outstanding -= deposit_amount
            account.total_paid += deposit_amount

    db.commit()

    return {
        "status": "success",
        "account_id": account_id,
        "amount": deposit_amount,
    }