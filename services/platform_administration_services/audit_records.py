from sqlalchemy.sql import func
from sqlalchemy import DateTime, Float
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from models.base import Base

class AdminShipmentAssignmentLog(Base):
    __tablename__ = "admin_shipment_assignment_logs"
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, nullable=False)
    carrier_id = Column(Integer, nullable=False)
    assigned_by = Column(String, nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
