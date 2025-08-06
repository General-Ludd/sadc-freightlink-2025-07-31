from sqlalchemy.sql import func
from sqlalchemy import DateTime, Date
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from models.base import Base
from enums import ShipperType
from enums import FacilityType

class Corporation(Base):
    __tablename__ = "corporations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    type = Column(Enum(ShipperType), nullable=False)
    facility_type = Column(Enum(FacilityType), nullable=True)  # subsidiary, outpost
    legal_business_name = Column(String, nullable=False)
    country_of_incorporation = Column(String, nullable=False)
    business_registration_number = Column(Integer, nullable=False)
    business_address = Column(String, nullable=False)
    business_email = Column(String, nullable=False)
    business_phone_number = Column(String, nullable=False)
    business_registration_certificate = Column(String, nullable=False)
    business_proof_of_address = Column(String, nullable=False)
    tax_clearance_certificate = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    status = Column(Enum("Un-verified", "Active", "Under Investigation", "Suspended"), default="Un-verified") #Update in Database
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Consignor(Base):
    __tablename__ = "consignors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    status = Column(String)
    priority_level = Column(String)
    company_name = Column(String)
    client_type = Column(String)
    business_sector = Column(String)
    company_website = Column(String)
    business_address = Column(String)
    contact_person_name = Column(String)
    position = Column(String)
    phone_number = Column(String)
    email = Column(String)
    preferred_contact_method = Column(String)
    client_notes = Column(String)
    shipments = column(Integer)
    contract_lanes = Column(Integer)
    revenue_generated = Column(Integer)
    profit_generated = Column(Integer)