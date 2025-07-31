from pydantic import BaseModel, EmailStr
from enum import Enum as PyEnum
from enums import ShipperType
from enums import FacilityType
from typing import Optional

class ShipperCreate(BaseModel):
    name: str
    registration_number: str
    address: str
    email: EmailStr
    phone_number: str
    type: ShipperType

class FacilityCreate(BaseModel):
    name: str
    facility_code: str
    registration_number: str = None  # Optional for outpost
    address: str
    email: str
    phone_number: str
    parent_company_id: int = None  # Optional
    facility_type: FacilityType
    is_verified: bool = False

from pydantic import BaseModel, EmailStr
from datetime import date
from typing import Optional

class CorporationBase(BaseModel):
    legal_business_name: str
    country_of_incorporation: str
    business_registration_number: int
    business_address: str
    business_email: EmailStr
    business_phone_number: str
    business_registration_certificate: Optional[str] = None
    business_proof_of_address: Optional[str] = None
    tax_clearence_certificate: Optional[str] = None

class CorporationCreate(CorporationBase):
    """Schema for creating a corporation, accepting file URLs."""
    business_registration_certificate: Optional[str] = None
    business_proof_of_address: Optional[str] = None
    tax_clearance_certificate: Optional[str] = None

class CorporationResponse(CorporationBase):
    """Response schema including uploaded document URLs."""
    id: int
    type: str
    business_registration_certificate: Optional[str]
    business_proof_of_address: Optional[str]
    tax_clearance_certificate: Optional[str]
    is_verified: bool
    status: str
    created_at: date

    class Config:
        orm_mode = True
