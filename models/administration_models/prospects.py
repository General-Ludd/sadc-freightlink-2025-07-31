from models.base import Base
from sqlalchemy import DateTime, Date
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Enum, UniqueConstraint
from utils.sast_datetime import get_sast_time

class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String)
    industry = Column(String)
    website = Column(String, nullable=True)
    country = Column(String, nullable=True)
    status = Column(String)
    current_stage = Column(String)
    notes = Column(String)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class Branches(Base):
    __tablename__ = "prospect_branches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer)
    branch_name = Column(String)
    city = Column(String)
    province = Column(String)
    country = Column(String)
    division = Column(String)
    description = Column(String)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)


class Prospect_Contact(Base):
    __tablename__ = "prospect_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer)
    branch_id = Column(Integer, nullable=True)
    location = Column(String)
    first_name = Column(String)
    last_name = Column(String)
    job_title = Column(String)
    department = Column(String)
    phone = Column(String)
    mobile = Column(String, nullable=True)
    email = Column(String, nullable=True)
    linkedin_url = Column(String, nullable=True)
    contact_status = Column(String)
    notes = Column(String)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class Contact_Interaction(Base):
    __tablename__ = "prospect_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer)
    contact_id = Column(Integer)
    interaction_type = Column(String)
    interaction_direction = Column(String)
    subject = Column(String)
    notes = Column(String)
    outcome = Column(String)
    interaction_date = Column(DateTime)
    next_action = Column(String)
    next_follow_up_at = Column(DateTime)
    created_by = Column(String)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class Freight_Profile(Base):
    __tablename__ = "prospect_freight_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer)
    commodity = Column(String)
    estimated_volumes = Column(Integer)
    interval = Column(String)
    core_routes = Column(String)
    current_carrier_model = Column(String)
    equipment = Column(String)
    pain_point = Column(String)
    frequency = Column(String)
    procurement_model = Column(String)
