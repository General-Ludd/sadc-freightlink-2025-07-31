from typing import List, Optional
from pydantic import BaseModel


class ProspectBranchCreate(BaseModel):
    branch_name: str
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    division: Optional[str] = None
    description: Optional[str] = None

class ProspectBranchUpdate(BaseModel):
    branch_name: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    country: Optional[str] = None
    division: Optional[str] = None
    description: Optional[str] = None

class ProspectContactCreate(BaseModel):
    branch_id: Optional[int] = None
    location: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    contact_status: Optional[str] = "PROSPECT"
    notes: Optional[str] = None

class ProspectContactUpdate(BaseModel):
    branch_id: Optional[int] = None
    location: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    contact_status: Optional[str] = None
    notes: Optional[str] = None

class ContactInteractionCreate(BaseModel):
    contact_id: Optional[int] = None
    interaction_type: str
    interaction_direction: Optional[str] = None
    subject: Optional[str] = None
    notes: Optional[str] = None
    outcome: Optional[str] = None
    interaction_date: Optional[datetime] = None
    next_action: Optional[str] = None
    next_follow_up_at: Optional[datetime] = None

class ContactInteractionUpdate(BaseModel):
    interaction_type: Optional[str] = None
    interaction_direction: Optional[str] = None
    subject: Optional[str] = None
    notes: Optional[str] = None
    outcome: Optional[str] = None
    interaction_date: Optional[datetime] = None
    next_action: Optional[str] = None
    next_follow_up_at: Optional[datetime] = None

class FreightProfileCreate(BaseModel):
    commodity: Optional[str] = None
    estimated_volumes: Optional[int] = None
    interval: Optional[str] = None
    core_routes: Optional[str] = None
    current_carrier_model: Optional[str] = None
    equipment: Optional[str] = None
    pain_point: Optional[str] = None
    frequency: Optional[str] = None
    procurement_model: Optional[str] = None

class FreightProfileUpdate(BaseModel):
    commodity: Optional[str] = None
    estimated_volumes: Optional[int] = None
    interval: Optional[str] = None
    core_routes: Optional[str] = None
    current_carrier_model: Optional[str] = None
    equipment: Optional[str] = None
    pain_point: Optional[str] = None
    frequency: Optional[str] = None
    procurement_model: Optional[str] = None

class ProspectCreate(BaseModel):
    company_name: str
    industry: Optional[str] = None
    website: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = "ACTIVE"
    current_stage: Optional[str] = "PROSPECT"
    notes: Optional[str] = None

    branches: Optional[List[ProspectBranchCreate]] = None
    contacts: Optional[List[ProspectContactCreate]] = None
    freight_profile: Optional[FreightProfileCreate] = None