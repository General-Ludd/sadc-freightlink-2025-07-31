from sqlalchemy import ARRAY, Boolean, Integer, String, Column, Float, Date, DateTime, Enum, func, ForeignKey, Text, Numeric
from models.base import Base
from utils.sast_datetime import get_sast_time

class Lane_Tender_Bid(Base):
    __tablename__ = "lane_tender_bids"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("ftl_lane_tenders.id"), nullable=False, index=True)
    carrier_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    submission_id = Column(String(36), nullable=False, index=True)

    carrier_name = Column(String, nullable=True)
    fleet_size = Column(Integer, nullable=True)
    primary_lanes = Column(Text, nullable=True)

    rate_basis = Column(String(50), nullable=True)

    main_bid_amount = Column(Numeric(14, 2), nullable=True)
    secondary_bid_amount = Column(Numeric(14, 2), nullable=True)

    main_rate_per_shipment = Column(Numeric(14, 2), nullable=True)
    secondary_rate_per_shipment = Column(Numeric(14, 2), nullable=True)

    slots_per_interval = Column(Integer, nullable=True)
    number_of_intervals = Column(Integer, nullable=True)
    per_slot_size = Column(Integer, nullable=True)

    main_per_slot_contract_bid = Column(Numeric(14, 2), nullable=True)
    main_total_contract_bid = Column(Numeric(14, 2), nullable=True)
    secondary_per_slot_contract_bid = Column(Numeric(14, 2), nullable=True)
    secondary_total_contract_bid = Column(Numeric(14, 2), nullable=True)
    bid_notes = Column(String, nullable=True)
    status = Column(Enum("Submitted", "Leading", "Outbidded", "Under-Review","Accepted", "Rejected", default="Submitted"))

    submitted_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)