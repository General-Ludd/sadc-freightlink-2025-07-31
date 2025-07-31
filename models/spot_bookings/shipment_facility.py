from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy import DateTime, Time
from models.base import Base
from sqlalchemy.orm import relationship

class SchedulingType(str, Enum):
    FIRST_COME_FIRST_SERVED = "First come, First served"
    APPOINTMENT_ALREADY_SCHEDULED = "Appointment already scheduled"
    SCHEDULE_FOR_ME = "Schedule an appointment for me"

class ShippingFacilityType(str, Enum):
    PICKUP = "Pickup"
    DROPOFF = "Dropoff"

class ContactPerson(Base):
    __tablename__ = "facility_contact_people"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    email = Column(String, nullable=False)


class ShipmentFacility(Base):
    __tablename__ = "shipment_facilities"

    id = Column(Integer, primary_key=True, index=True)
    shipper_company_id = Column(Integer, nullable=True)
    type = Column(String, nullable=True)  # e.g., "Pickup" or "Dropoff"
    address = Column(String, nullable=False)
    name = Column(String, nullable=True)
    scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    contact_person = Column(Integer, ForeignKey("facility_contact_people.id"))
    contact_person_relationship = relationship("ContactPerson")
    facility_notes = Column(String, nullable=True)
