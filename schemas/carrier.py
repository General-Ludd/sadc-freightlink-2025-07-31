from typing import Optional
from pydantic import BaseModel, EmailStr
from enum import Enum as PyEnum
from enums import CarrierType

class CreateFleetCarrier(BaseModel):
    name: str
    registration_number: int
    dot_number: int
    insurance_policy_number: int
    policy_insurer: str
    address: str
    email: EmailStr
    phone_number: str
    type: CarrierType
    bank_name: str
    branch_code: str
    account_number: int


class CarrierCreate(BaseModel):
    legal_business_name: str
    country_of_incorporation: str
    business_registration_number: str
    git_insurance_policy_number: str
    git_cover_amount: int
    name_of_git_cover_insurance_company: str
    liability_insurance_policy_number: str
    liability_insurance_cover_amount: int
    name_of_liability_cover_insurance_company: str
    business_address: str
    business_email: str
    business_phone_number: str
    business_registration_certificate: str
    proof_of_address: str
    brnc_certificate: Optional[str] = None
    git_insurance_certificate: str
    liability_insurance_certificate: str

class CarrierCompanyResponse(BaseModel):
    id: int
    type: str
    legal_business_name: str
    country_of_incorporation: str
    business_registration_number: str
    git_insurance_policy_number: str
    git_cover_amount: int
    name_of_git_cover_insurance_company: str
    liability_insurance_policy_number: str
    liability_insurance_cover_amount: int
    name_of_liability_cover_insurance_company: str
    business_address: str
    business_email: str
    business_phone_number: str
    business_registration_certificate: str
    proof_of_address: str
    brnc_certificate: Optional[str] = None
    git_insurance_certificate: str
    liability_insurance_certificate: str
    number_of_vehicles: int
    number_of_trailers: int
    number_of_drivers: int
    number_of_completed_shipments: int
    number_of_completed_dedicated_lanes: int
    number_of_ongoing_dedicated_lanes: int
    rating: float
    is_verified: bool
    status: str