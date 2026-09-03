from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    Boolean,
    DateTime,
    func,
)

from models.base import Base


class CommissionRule(Base):
    __tablename__ = "commission_rules"

    id = Column(Integer, primary_key=True, index=True)

    # Minimum shipment rate this rule applies to
    min_rate = Column(Numeric(14, 2), nullable=False)

    # Maximum shipment rate.
    # NULL means unlimited.
    max_rate = Column(Numeric(14, 2), nullable=True)

    # FIXED or PERCENTAGE
    commission_type = Column(String(20), nullable=False)

    # For FIXED:
    #     400 means R400
    #
    # For PERCENTAGE:
    #     3 means 3%
    commission_value = Column(Numeric(14, 4), nullable=False)

    active = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )