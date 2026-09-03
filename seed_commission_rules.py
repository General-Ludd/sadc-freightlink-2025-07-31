from decimal import Decimal

from db.database import SessionLocal

from models.brokerage.commission import CommissionRule


COMMISSION_RULES = [
    {
        "min_rate": Decimal("0"),
        "max_rate": Decimal("7500"),
        "commission_type": "FIXED",
        "commission_value": Decimal("100"),
    },
    {
        "min_rate": Decimal("7500"),
        "max_rate": Decimal("12500"),
        "commission_type": "FIXED",
        "commission_value": Decimal("200"),
    },
    {
        "min_rate": Decimal("12500"),
        "max_rate": Decimal("18000"),
        "commission_type": "FIXED",
        "commission_value": Decimal("400"),
    },
    {
        "min_rate": Decimal("18000"),
        "max_rate": Decimal("24500"),
        "commission_type": "FIXED",
        "commission_value": Decimal("650"),
    },
    {
        "min_rate": Decimal("24500"),
        "max_rate": Decimal("50000"),
        "commission_type": "FIXED",
        "commission_value": Decimal("850"),
    },
    {
        "min_rate": Decimal("50000"),
        "max_rate": Decimal("75000"),
        "commission_type": "PERCENTAGE",
        "commission_value": Decimal("3"),
    },
    {
        "min_rate": Decimal("75000"),
        "max_rate": Decimal("100000"),
        "commission_type": "PERCENTAGE",
        "commission_value": Decimal("4"),
    },
    {
        "min_rate": Decimal("100000"),
        "max_rate": Decimal("150000"),
        "commission_type": "PERCENTAGE",
        "commission_value": Decimal("5"),
    },
    {
        "min_rate": Decimal("150000"),
        "max_rate": Decimal("250000"),
        "commission_type": "PERCENTAGE",
        "commission_value": Decimal("6"),
    },
    {
        "min_rate": Decimal("250000"),
        "max_rate": None,
        "commission_type": "PERCENTAGE",
        "commission_value": Decimal("7"),
    },
]


def seed_commission_rules():

    db = SessionLocal()

    try:

        # Prevent duplicate seeding
        existing = db.query(CommissionRule).count()

        if existing > 0:
            print(
                "Commission rules already exist. "
                "Skipping seed."
            )
            return

        for rule_data in COMMISSION_RULES:

            rule = CommissionRule(
                **rule_data,
                active=True,
            )

            db.add(rule)

        db.commit()

        print(
            f"Successfully inserted "
            f"{len(COMMISSION_RULES)} commission rules."
        )

    except Exception:

        db.rollback()
        raise

    finally:

        db.close()


if __name__ == "__main__":
    seed_commission_rules()