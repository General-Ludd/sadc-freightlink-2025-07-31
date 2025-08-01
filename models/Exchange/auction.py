from sqlalchemy import Integer, String, Column, Float, Date, DateTime, func, Enum, Boolean, ForeignKey
from models.base import Base

class Exchange_FTL_Shipment_Bid(Base):
    __tablename__ = 'exchange_ftl_shipments_bids'

    id = Column(Integer, primary_key=True, index=True)
    exchange_id = Column(Integer, index=True)
    type = Column(String, default="FTL", nullable=False)
    carrier_id = Column(Integer, nullable=False)
    carrier_type = Column(String, nullable=False)
    carrier_name = Column(String, nullable=False)
    user_id = Column(Integer, index=True)
    bid_amount = Column(Integer,index=True, nullable=False)
    baked_bid_amount = Column(Integer, nullable=False)
    bid_notes = Column(String, nullable=True)
    status = Column(String, default="Placed", nullable=True, index=True)
    submitted_at = Column(DateTime, server_default=func.now())

class Exchange_POWER_Shipment_Bid(Base):
    __tablename__ = 'exchange_power_shipments_bids'

    id = Column(Integer, primary_key=True, index=True)
    exchange_id = Column(Integer, index=True)
    type = Column(String, default="POWER", nullable=False)
    carrier_id = Column(Integer, nullable=False)
    carrier_type = Column(String, nullable=False)
    carrier_name = Column(String, nullable=False)
    user_id = Column(Integer, index=True)
    bid_amount = Column(Integer,index=True, nullable=False)
    baked_bid_amount = Column(Integer, nullable=False)
    bid_notes = Column(String, nullable=True)
    status = Column(String, default="Placed", nullable=True, index=True)
    submitted_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Exchange_FTL_Lane_Bid(Base):
    __tablename__ = 'exchange_ftl_lane_bids'

    id = Column(Integer, primary_key=True, index=True)
    exchange_id = Column(Integer, index=True)
    type = Column(String, default="POWER", nullable=False)
    carrier_id = Column(Integer, nullable=False)
    carrier_type = Column(String, nullable=False)
    carrier_name = Column(String, nullable=False)
    user_id = Column(Integer, index=True)
    per_shipment_bid_amount = Column(Integer,index=True, nullable=False)
    contract_bid_amount = Column(Integer, index=True)
    baked_per_shipment_bid_amount = Column(Integer, nullable=False)
    baked_contract_bid_amount = Column(Integer, nullable=False)
    bid_notes = Column(String, nullable=True)
    status = Column(String, default="Placed", nullable=True, index=True)
    submitted_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())