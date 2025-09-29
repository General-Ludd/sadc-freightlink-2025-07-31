from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# Shared Base
class EarlyAccessBaseSchema(BaseModel):
    company_name: str
    registration_number: Optional[str]
    tax_id: Optional[str]
    country: str
    city: str
    website: Optional[str]

    contact_name: str
    contact_role: str
    contact_email: EmailStr
    contact_phone: str

# --- Enterprise Shipper ---
class EnterpriseShipperCreate(EarlyAccessBaseSchema):
    industry: str
    average_monthly_loads: Optional[int]
    shipment_types: Optional[List[str]]
    main_shipping_lanes: Optional[List[str]]

class EnterpriseShipperResponse(EnterpriseShipperCreate):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

# --- Warehouse ---
class WarehouseCreate(EarlyAccessBaseSchema):
    facility_type: str
    capacity_pallets: Optional[int]
    certifications: Optional[List[str]]
    services: Optional[List[str]]

class WarehouseResponse(WarehouseCreate):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

# --- Customs Broker ---
class CustomsBrokerCreate(EarlyAccessBaseSchema):
    license_number: Optional[str]
    regions_served: Optional[List[str]]
    specialization: Optional[str]

class CustomsBrokerResponse(CustomsBrokerCreate):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

# --- Fuel Supplier ---
class FuelSupplierCreate(EarlyAccessBaseSchema):
    fuel_types: Optional[List[str]]
    supply_capacity: Optional[str]
    coverage_regions: Optional[List[str]]

class FuelSupplierResponse(FuelSupplierCreate):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

# --- Truck Service Facility ---
class TruckServiceFacilityCreate(EarlyAccessBaseSchema):
    location_coordinates: Optional[str]
    parking_capacity: Optional[int]
    amenities: Optional[List[str]]
    available_services: Optional[List[str]]

class TruckServiceFacilityResponse(TruckServiceFacilityCreate):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True
