from sqlalchemy import ARRAY, Boolean, Integer, String, Column, Float, Date, DateTime, Enum, func
from models.base import Base
from utils.sast_datetime import get_sast_time

class Diesel_Index(Base):
    __tablename__ = "diesel_index"

    id = Column(Integer, primary_key=True, index=True)
    country = Column(String) #E.g. South Africa
    iso_code = Column(String)  # E.g. ZA
    currency = Column(String) #E.g ZAR
    region = Column(String, nullable=True) #E.g. Coastal / In-Land / National
    commence_date = Column(Date, nullable=False) #E.g. 2026/09/18
    price = Column(Float, nullable=False) #E.g. 29.46
    is_active = Column(Boolean, default=True)  # Whether the index is active
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())