from decimal import Decimal
from sqlalchemy.orm import Session

from models.brokerage.commission import CommissionRule


class CommissionCalculationError(Exception):
    pass


def calculate_commission(
    db: Session,
    shipment_rate: Decimal,
) -> dict:
    """
    Calculate SADC FREIGHTLINK commission based on
    commission rules stored in the database.
    """

    if shipment_rate is 0:
        raise CommissionCalculationError(
            f"Shipment rate is required to be greater then {shipment_rate}."
        )

    shipment_rate = Decimal(str(shipment_rate))

    if shipment_rate < 0:
        raise CommissionCalculationError(
            "Shipment rate cannot be negative."
        )

    # Find the applicable commission rule
    rule = (
        db.query(CommissionRule)
        .filter(
            CommissionRule.active == True,
            CommissionRule.min_rate <= shipment_rate,
            (
                (CommissionRule.max_rate.is_(None))
                | (CommissionRule.max_rate > shipment_rate)
            ),
        )
        .order_by(
            CommissionRule.min_rate.desc()
        )
        .first()
    )

    if not rule:
        raise CommissionCalculationError(
            f"No commission rule found for shipment rate "
            f"R{shipment_rate:,.2f}"
        )

    # -------------------------
    # FIXED COMMISSION
    # -------------------------

    if rule.commission_type == "FIXED":

        commission = Decimal(rule.commission_value)

    # -------------------------
    # PERCENTAGE COMMISSION
    # -------------------------

    elif rule.commission_type == "PERCENTAGE":

        percentage = Decimal(rule.commission_value)

        commission = (
            shipment_rate * percentage / Decimal("100")
        )

    else:

        raise CommissionCalculationError(
            f"Invalid commission type: "
            f"{rule.commission_type}"
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
        "commission_value": Decimal(
            rule.commission_value
        ),
        "rule_id": rule.id,
    }