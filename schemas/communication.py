from typing import Optional
from pydantic import BaseModel, EmailStr

class Contact_Us(BaseModel):
    name: str
    company_name: str
    phone_number: str
    email: EmailStr
    subject: str
    description: str