from datetime import date, datetime
from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    id_number: int
    address: str
    email: EmailStr
    phone_number: str
    password: str

class CarrierDirectorCreate(BaseModel):
    first_name: str
    last_name: str
    id_number: str
    address: str
    email: EmailStr
    phone_number: str
    password: str

class CarrierUsers(BaseModel):
    role: Optional[str] = None
    first_name: str
    last_name: str
    nationality: str
    id_number: str
    home_address: str
    email: EmailStr
    phone_number: str
    id_document: str
    proof_of_address: str
    password_hash: str

class CarrierUserResponse(BaseModel):
    id: int
    role: Optional[str] = None
    first_name: str
    last_name: str
    nationality: str
    id_number: str
    home_address: str
    email: EmailStr
    phone_number: str
    id_document: str
    proof_of_address: str
    company_id: int
    company_name: str
    company_type: str
    is_director: bool
    is_verified: bool
    status: str

class DriverCreate(BaseModel):
    first_name: str
    last_name: str
    nationality: str
    id_number: str
    license_number: str
    license_expiry_date: date
    prdp_number: str
    prdp_expiry_date: date
    address: str
    email: EmailStr
    phone_number: str
    password_hash: str
    id_document: str
    license_document: str
    prdp_document: str
    proof_of_address: str

class Driver_Info(BaseModel):
    id: int

class Drivers_Summary_Response(BaseModel):
    id: int
    is_verified: bool
    service_status: str
    location_description: Optional [str] = None
    first_name: str
    last_name: str
    id_number: str
    license_number: str
    prdp_number: str
    phone_number: str
    email: EmailStr
    current_vehicle_id: Optional [int] = None
    vehicle_is_verified: bool
    vehicle_make: Optional [str] = None
    vehicle_model: Optional [str] = None
    vehicle_year: Optional [int] = None
    vehicle_license_plate: Optional [str] = None
    vehicle_license_expiry_date: Optional [date] = None
    vehicle_axle_configuration: Optional [str] = None
    vehicle_equipment_type: Optional [str] = None
    vehicle_trailer_type: Optional [str] = None
    vehicle_trailer_length: Optional [str] = None

class DriverResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    nationality: str
    id_number: str
    license_number: str
    license_expiry_date: date
    prdp_number: Optional [str] = None
    prdp_expiry_date: Optional [date] = None
    passport_numeber: Optional [str] = None
    address: str
    email: EmailStr
    phone_number: str
    company_id: int
    company_name: str
    company_type: str
    current_vehicle_id: Optional[int] = None
    id_document: str
    license_document: str
    prdp_document: Optional [str] = None
    passport_document: Optional [str] = None
    proof_of_address: str
    is_verified: bool
    status: str
    service_status: str
    total_shipments_completed: int
    total_disance_driven: int
    created_at: datetime

class DriverUpdate(BaseModel):
    address: Optional [str] = None
    proof_of_address: Optional [str] = None
    license_number: Optional [str] = None
    license_expiry_date: Optional [date] = None
    license_document: Optional [str] = None
    prdp_number: Optional [str] = None
    prdp_expiry_date: Optional [date] = None
    prdp_document: Optional [str] = None
    email: Optional [EmailStr] = None
    phone_number: Optional [str] = None

    class Config:
        orm_mode = True

#//////////////////////////////////////////////\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\#
#////////////////////////////////////////////USER\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\#
#//////////////////////////////////////////////\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\#
class DirectorCreate(BaseModel):
    first_name: str
    last_name: str
    nationality: str
    id_number: str
    home_address: str
    phone_number: str
    email: EmailStr
    password: str
    id_document: str
    proof_of_address: str

class ShipperUserResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    nationality: str
    id_number: str
    home_address: str
    email: EmailStr
    phone_number: str
    id_document: str
    proof_of_address: str
    company_id: int
    is_director: bool
    is_verified: bool

class DirectorResponse(DirectorCreate):
    id: int
    company_id: int
    first_name: str
    last_name: str
    id_number: str
    nationality: str
    home_address: str
    phone_number: str
    email: EmailStr
    id_document: Optional[str] = None
    proof_of_address: Optional[str] = None
    is_director: bool
    is_verified: bool
    status: str
    
class Config:
    orm_mode = True