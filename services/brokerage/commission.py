from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy import nullslast # Add this import at the top
from models.brokerage.commission import CommissionRule


class CommissionCalculationError(Exception):
    pass


def calculate_commission(
    db: Session,
    shipment_rate: Decimal,
) -> dict:

    if shipment_rate is None:
        raise CommissionCalculationError(
            "Shipment rate is required."
        )

    try:
        shipment_rate = Decimal(str(shipment_rate))
    except (InvalidOperation, ValueError, TypeError):
        raise CommissionCalculationError(
            "Shipment rate must be a valid number."
        )

    if shipment_rate <= 0:
        raise CommissionCalculationError(
            "Shipment rate must be greater than R0.00."
        )

    rule = (
        db.query(CommissionRule)
        .filter(
            CommissionRule.active == True,
            CommissionRule.min_rate <= shipment_rate,
            or_(
                CommissionRule.max_rate > shipment_rate
            )
        )
        .order_by(
            nullslast(CommissionRule.min_rate.desc()) # Force NULLs to the bottom
        )
        .first()
    )

    if not rule:
        raise CommissionCalculationError(
            f"No commission rule found for shipment rate "
            f"R{shipment_rate:,.2f}"
        )

    if rule.commission_type == "FIXED":

        if rule.commission_value is None:
            raise CommissionCalculationError(
                f"Commission rule {rule.id} has no commission value."
            )

        commission = Decimal(str(rule.commission_value))

    elif rule.commission_type == "PERCENTAGE":

        if rule.commission_value is None:
            raise CommissionCalculationError(
                f"Commission rule {rule.id} has no commission value."
            )

        percentage = Decimal(str(rule.commission_value))

        commission = (
            shipment_rate * percentage / Decimal("100")
        )

    else:

        raise CommissionCalculationError(
            f"Invalid commission type: "
            f"{rule.commission_type}"
        )

    if commission < 0:
        raise CommissionCalculationError(
            f"Commission cannot be negative. "
            f"Rule {rule.id} returned R{commission:,.2f}."
        )

    commission = commission.quantize(
        Decimal("0.01")
    )

    net_amount = (
        shipment_rate - commission
    ).quantize(
        Decimal("0.01")
    )

    return {
        "shipment_rate": shipment_rate,
        "commission": commission,
        "net_amount": net_amount,
        "commission_type": rule.commission_type,
        "commission_value": Decimal(str(rule.commission_value)),
        "rule_id": rule.id,
    }
