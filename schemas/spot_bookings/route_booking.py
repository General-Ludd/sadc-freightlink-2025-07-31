from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date
from enums import Recurrence_Frequency, Recurrence_Days

from enums import EquipmentType,Trip_Type, Load_Type, Priority_Level, TrailerLength, TrailerType, TruckType

class Admin_Bulk_Create_Route(Base):
    last_shipment_id
    pickup_date: Date
    number_of_trucks_required: int
    rate: int
    commission: int