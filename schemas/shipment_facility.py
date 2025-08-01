from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, time, date

from sqlalchemy import Date

from enums import SchedulingType

class ShipmentFacilityCreate(BaseModel):
    name: str
    scheduling_type: SchedulingType
    start_time: time
    end_time: time
    facility_notes: Optional[str]


class PickupFacilityInfoResponse(BaseModel):
    city_province: str
    address: str
    date: date
    operating_hours: str
    contact_person_name: str
    contact_phone_number: str
    notes: Optional[str] = None

class DeliveryFacilityInfoResponse(BaseModel):
    city_province: str
    address: str
    date: date
    operating_hours: str
    contact_person_name: str
    contact_phone_number: str
    notes: Optional[str] = None

class FacilityContactCreate(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    email: EmailStr

class FacilityContactPersonResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    phone_number: str
    email: EmailStr
