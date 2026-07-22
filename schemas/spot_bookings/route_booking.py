from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date
from enums import Recurrence_Frequency, Recurrence_Days

from enums import EquipmentType,Trip_Type, Load_Type, Priority_Level, TrailerLength, TrailerType, TruckType

class Admin_Bulk_Create_Route(BaseModel):
    client_id: int
    user_id: int
    previous_shipment_id: int
    pickup_date: date
    number_of_trucks_required: int
    rate: int
    commission: int