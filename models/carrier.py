from sqlalchemy.sql import func
from sqlalchemy import DateTime, Float
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from models.base import Base
from enums import CarrierType
from .user import Driver

class Carrier(Base):
    __tablename__ = 'carriers'

    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    type = Column(Enum(CarrierType, default='fleet'), nullable=False)
    legal_business_name = Column(String, unique=True, nullable=False)
    country_of_incorporation = Column(String, nullable=False)
    business_registration_number = Column(Integer, unique=True, nullable=False)
    git_insurance_policy_number = Column(String, unique=True, nullable=False)
    git_cover_amount = Column(Integer, nullable=False)
    name_of_git_cover_insurance_company = Column(String, nullable=False)
    liability_insurance_policy_number = Column(String, unique=True, nullable=False)
    liability_insurance_cover_amount = Column(Integer, nullable=False)
    name_of_liability_cover_insurance_company = Column(String, nullable=False)
    business_address = Column(String, nullable=False)
    business_email = Column(String, unique=True, nullable=False)
    business_phone_number = Column(String, unique=True, nullable=False)
    business_registration_certificate = Column(String, nullable=False)
    proof_of_address = Column(String, nullable=False)
    brnc_certificate = Column(String, nullable=False)
    git_insurance_certificate = Column(String, nullable=False)
    liability_insurance_certificate = Column(String, nullable=False)
    number_of_vehicles = Column(Integer, default=0, nullable=False)
    number_of_trailers = Column(Integer, default=0, nullable=False)
    number_of_drivers = Column(Integer, default=0, nullable=False)
    number_of_completed_shipments = Column(Integer, default=0, nullable=False)
    number_of_completed_dedicated_lanes = Column(Integer, default=0, nullable=False)
    number_of_ongoing_dedicated_lanes = Column(Integer, default=0, nullable=False)
    rating = Column(Float, default=0.0, nullable=True)
    is_verified = Column(Boolean, default=False)
    status = Column(Enum("Un-verified", "Active", "Under Investigation", "Suspended"), default="Un-verified") #Update in Database
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Carrier_Profile(Base):
    __tablename__ = "carrier_profile"

    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    carrier_id = Column(Integer, nullable=False)
    primary_routes = Column(String)
    rigid_tautliners = Column(Integer)
    triaxle_tautliners = Column(Integer)
    superlink_tautliners = Column(Integer)
    rigid_flatbeds = Column(Integer)
    triaxle_flatbeds = Column(Integer)
    superlink_flatbeds = Column(Integer)
    rigid_flatbeds_with_twistlocks = Column(Integer)
    triaxle_flatbeds_with_twistlocks = Column(Integer)
    superlink_flatbeds_with_twistlocks = Column(Integer)
    rigid_dropsides = Column(Integer)
    triaxle_dropside = Column(Integer)
    superlink_dropside = Column(Integer)
    triaxle_skeletals = Column(Integer)
    superlink_skeletals = Column(Integer)
    rigid_pantechs = Column(Integer)
    triaxle_pantechs = Column(Integer)
    triaxle_side_tippers = Column(Integer)
    superlink_side_tippers = Column(Integer)
    low_beds = Column(Integer)
    rigid_end_tipper = Column(Integer)
    triaxle_end_tipper = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    recipient_type = Column(String, nullable=False)  # "shipper", "carrier", "agent", "admin"
    recipient_id = Column(Integer, nullable=False)   # The user ID in their respective table
    type = Column(String, nullable=False)  # e.g. "shipment_update", "payment", "dispute"
    message = Column(String, nullable=False)
    related_id = Column(Integer, nullable=True)      # e.g. shipment_id or dispute_id
    related_type = Column(String, nullable=True)     # "shipment", "dispute", "payment"
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Carrier_Notification(Base):
    __tablename__ = "carrier_notifications"

    id = Column(Integer, autoincrement=True, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False)   # The user ID in their respective table
    type = Column(String, nullable=False)  # e.g. "shipment_update", "payment", "dispute"
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

