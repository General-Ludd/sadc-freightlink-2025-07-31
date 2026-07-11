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

class FacilityCreation(BaseModel):
    facility_name: str
    country: str
    facility_address: str
    facility_email: str
    facility_phone_number: str
    facility_proof_of_address: str

from pydantic import BaseModel, EmailStr
from datetime import date
from typing import Optional

class CorporationBase(BaseModel):
    legal_business_name: str
    country_of_incorporation: str
    business_registration_number: str
    business_address: str
    business_email: EmailStr
    business_phone_number: str
    business_registration_certificate: Optional[str] = None
    business_proof_of_address: Optional[str] = None
    tax_clearence_certificate: Optional[str] = None

class CorporationProfile(BaseModel):
    commodities: str
    commodity_description: str
    maximum_git_insurance_required: int
    number_of_transport_providers_currently_used: int
    primary_routes: str
    tautliners: bool
    flatbeds: bool
    dropsides: bool
    flatbeds_with_twistlocks: bool
    skeletals: bool
    pantechs: bool
    bottom_dumpers: bool
    side_tippers: bool
    low_beds: bool
    timber_trailers: bool
    sugar_cane_trailers: bool

class CorporationUpdate(BaseModel):
    legal_business_name: Optional[str] = None
    business_address: Optional[str] = None
    business_email: Optional[EmailStr] = None
    business_phone_number: Optional[str] = None
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

class ConsignorCreate(BaseModel):
    status: Optional[str]
    priority_level: Optional[str]
    company_name: str
    client_type: Optional[str]
    business_sector: Optional[str]
    company_website: Optional[str]
    business_address: str
    contact_person_name: str
    position: Optional[str]
    phone_number: str
    email: str
    preferred_contact_method: Optional[str]
    client_notes: Optional[str]