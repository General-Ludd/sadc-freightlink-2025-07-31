from sqlalchemy.sql import func
from sqlalchemy import DateTime, Date
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from models.base import Base
from enums import ShipperType
from enums import FacilityType
from utils.sast_datetime import get_sast_time

class Shipper_Support_Ticket(Base):
    __tablename__ = "shipper_support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    company_name = Column(String)
    email = Column(String)
    subject = Column(String)
    description = Column(String)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class Brokerage_Firm_Support_Ticket(Base):
    __tablename__ = "brokerage_firm_support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    company_name = Column(String)
    email = Column(String)
    subject = Column(String)
    description = Column(String)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class Carrier_Support_Ticket(Base):
    __tablename__ = "carrier_support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    company_name = Column(String)
    phone_number = Column(String)
    email = Column(String)
    subject = Column(String)
    description = Column(String)
    is_read = Column(Boolean, default=False)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class Brokerage_Firm_Support_Ticket(Base):
    __tablename__ = "brokerage_firms_support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    company_name = Column(String)
    phone_number = Column(String)
    email = Column(String)
    subject = Column(String)
    description = Column(String)
    is_read = Column(Boolean, default=False)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class Shipper_Support_Ticket(Base):
    __tablename__ = "shipper_support_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    company_name = Column(String)
    phone_number = Column(String)
    email = Column(String)
    subject = Column(String)
    description = Column(String)
    is_read = Column(Boolean, default=False)
    status = Column(String)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)