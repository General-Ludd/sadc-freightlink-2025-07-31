from datetime import datetime
from argon2 import PasswordHasher
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import Column, Date, Float, String, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from models.base import Base
from sqlalchemy.orm import relationship
from sqlalchemy import Enum

# Use Argon2 for password hashing
ph = PasswordHasher()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    id_number = Column(Integer, unique=True, nullable=False)
    address = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    company_id = Column(Integer, nullable=True)
    facility_id = Column(Integer, nullable=True)

    @staticmethod
    def hash_password(password: str) -> str:
        return ph.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return ph.verify(hashed_password, plain_password)
        except:
            return False


class CarrierDirector(Base):
    __tablename__ = "carrier_directors"

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    id_number = Column(String, nullable=False)
    address = Column(String, nullable=False)
    email = Column(String, index=True, nullable=False)
    phone_number = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    company_id = Column(Integer, nullable=False)
    company_name = Column(String, nullable=False)

    @staticmethod
    def hash_password(password: str) -> str:
        return ph.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return ph.verify(hashed_password, plain_password)
        except:
            return False

class CarrierUser(Base):
    __tablename__ = "carrier_users"

    id = Column(Integer, unique=True, primary_key=True)
    role = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    nationality = Column(String, nullable=False)
    id_number = Column(String, nullable=False)
    home_address = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    id_document = Column(String, nullable=False)
    proof_of_address = Column(String, nullable=False)
    password_hash = Column(String, nullable=True)
    company_id = Column(Integer, nullable=False)
    company_name = Column(String, nullable=False)
    company_type = Column(String, nullable=False)
    is_director = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    status = Column(Enum("Un-verified", "Active", "Under Investigation", "Suspended", "Deleted"), default="Un-verified") #Update in Database
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Driver(Base):
    __tablename__ = "fleet_drivers"

    id = Column(Integer, unique=True, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    nationality = Column(String, nullable=False)
    id_number = Column(String, unique=True, nullable=False)
    license_number = Column(String, unique=True, nullable=False)
    license_expiry_date = Column(Date, nullable=False)
    prdp_number = Column(String, unique=True, nullable=False)
    prdp_expiry_date = Column(Date, nullable=False)
    passport_number = Column(String)
    address = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_number = Column(String, unique=True, nullable=False)
    company_id = Column(Integer, nullable=False)
    company_name = Column(String, nullable=False)
    company_type = Column(String, nullable=False)
    current_vehicle_id = Column(Integer, nullable=True)
    latitude = Column(Float)
    longitude = Column(Float)
    speed = Column(Integer)
    heading = Column(Integer)
    location_description = Column(String, nullable=True)
    time_stamp = Column(DateTime(timezone=True), server_default=func.now())  # When this data was fetched
    password_hash = Column(String, nullable=False)
    id_document = Column(String, nullable=False)
    license_document = Column(String, nullable=False)
    prdp_document = Column(String, nullable=False)
    passport_document = Column(String, nullable=True)
    proof_of_address = Column(String, nullable=False)
    is_user = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    status = Column(Enum("Un-verified", "Active", "Under Investigation", "Suspended", "Deleted"), default="Un-verified") #Update in Database
    service_status = Column(String, default="Available") #################Update in database
    total_shipments_completed = Column(Integer, default=0) #################Update in database
    total_distance_driven = Column(Integer, default=0) #################Update in database
    rating = Column(Float, default=0.0) #################Update in database
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class DriverAssignmentHistory(Base):
    __tablename__ = "driver_assignment_history"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer)
    vehicle_id = Column(Integer)
    assigned_by = Column(Integer)  # optional: user/admin ID
    role = Column(String)  # "primary" or "secondary"
    assigned_at = Column(DateTime, default=datetime.utcnow)

    @staticmethod
    def hash_password(password: str) -> str:
        return ph.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return ph.verify(hashed_password, plain_password)
        except:
            return False


class Director(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    id_number = Column(String, nullable=False)
    nationality = Column(String, nullable=False)
    home_address = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    email = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    id_document = Column(String, nullable=False)
    proof_of_address = Column(String, nullable=False)
    is_director = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    status = Column(Enum("Un-verified", "Active", "Under Investigation", "Suspended", "Deleted"), default="Un-verified") #Update in Database                                     
    company_id = Column(Integer, nullable=True)
    facility_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())