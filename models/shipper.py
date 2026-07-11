from sqlalchemy.sql import func
from sqlalchemy import DateTime, Date
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from models.base import Base
from enums import ShipperType
from enums import FacilityType
from utils.sast_datetime import get_sast_time

class Corporation(Base):
    __tablename__ = "corporations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    parent_company_id = Column(Integer, nullable=True)
    type = Column(Enum(ShipperType), nullable=False)
    facility_type = Column(Enum(FacilityType), nullable=True)  # subsidiary, outpost
    legal_business_name = Column(String, nullable=False)
    country_of_incorporation = Column(String, nullable=False)
    business_registration_number = Column(String, nullable=False)
    business_address = Column(String, nullable=False)
    business_email = Column(String, nullable=False)
    business_phone_number = Column(String, nullable=False)
    business_registration_certificate = Column(String, nullable=False)
    business_proof_of_address = Column(String, nullable=False)
    tax_clearance_certificate = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False)
    status = Column(Enum("Un-verified", "Active", "Under Investigation", "Suspended"), default="Un-verified") #Update in Database
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class Corporation_Profile(Base):
    __tablename__ = "corporate_client_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    commodities = Column(String)
    commodity_description = Column(String)
    maximum_git_insurance_required = Column(Integer)
    number_of_transport_providers_currently_used = Column(Integer)
    primary_routes = Column(String)
    tautliners = Column(Boolean, default=False)
    flatbeds = Column(Boolean, default=False)
    flatbeds_with_twistlocks = Column(Boolean, default=False)
    dropsides = Column(Boolean, default=False)
    skeletals = Column(Boolean, default=False)
    pantechs = Column(Boolean, default=False)
    bottom_dumpers = Column(Boolean, default=False)
    side_tippers = Column(Boolean, default=False)
    low_beds = Column(Boolean, default=False)
    timber_trailers = Column(Boolean, default=False)
    sugar_cane_trailers = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)


    

class Consignor(Base):
    __tablename__ = "consignors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    brokerage_firm_id = Column(Integer)
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
    shipments = Column(Integer)
    contract_lanes = Column(Integer)
    revenue_generated = Column(Integer)
    profit_generated = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class Client_Notification(Base):
    __tablename__ = "client_notifications"

    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False)   # The user ID in their respective table
    type = Column(String, nullable=False)  # e.g. "shipment_update", "payment", "dispute"
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)