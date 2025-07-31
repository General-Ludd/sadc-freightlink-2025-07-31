from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date

from enums import EquipmentType, Load_Type, Priority_Level, TrailerLength, TrailerType, TruckType

class individual_shipment_or_lane_request(BaseModel):
    id: int

class FTL_Lane_Create(BaseModel):
    load_type: Load_Type
    required_truck_type: TruckType
    equipment_type: EquipmentType
    trailer_type: Optional[TrailerType] = None
    trailer_length: Optional[TrailerLength] = None
    minimum_weight_bracket: int
    minimum_git_cover_amount: Optional[int] = None
    minimum_liability_cover_amount: Optional[int] = None
    origin_address: str
    destination_address: str
    customer_reference_number: Optional[str] = None
    average_shipment_weight: Optional[int] = None
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[str] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    recurrence_frequency: str  # How often shipments occur
    recurrence_days: List[str] = [] # Days (e.g., "Monday, Wednesday, Friday")
    skip_weekends: bool
    shipments_per_interval: int  # Number of shipments in each recurrence interval
    start_date: date  # Start date of the contract
    end_date: date  # Optional end date (if known)
    priority_level: Priority_Level

class Ftl_Lanes_Summary_Response(BaseModel):
    id: int
    type: str
    status: str
    contract_quote: int
    origin_city_province: str
    destination_city_province: str
    distance: int
    recurrence_frequency: str
    shipments_per_interval: int
    start_date: date
    end_date: date

class Individual_FTL_Lane_Response(BaseModel):
    id: int 
    type: str
    trip_type: str
    load_type: str
    shipper_company_id: int 
    shipper_user_id: int 
    payment_terms: str
    invoice_id: int 
    invoice_due_date: date 
    invoice_status: str
    required_truck_type: str
    equipment_type: str
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None
    minimum_weight_bracket: int 
    minimum_git_cover_amount: int 
    minimum_liability_cover_amount: int 
    origin_address: str
    complete_origin_address: str
    origin_city_province: str
    origin_country: str
    origin_region: str
    destination_address: str
    complete_destination_address: str
    destination_city_province: str
    destination_country: str
    destination_region: str
    priority_level: str
    pickup_facility_id: int 
    delivery_facility_id: int 
    customer_reference_number: str
    average_shipment_weight: int 
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: str
    packaging_type: str
    pickup_number: str
    pickup_notes: str
    delivery_number: str
    delivery_notes: str
    distance: int 
    estimated_transit_time: str
    route_preview_embed: str
    contract_quote: int 
    qoute_per_shipment: int 

    # Recurrence Details
    recurrence_frequency: str # How often shipments occur
    recurrence_days: List [str] # Days (e.g., "Monday, Wednesday, Friday")
    skip_weekends: bool
    shipments_per_interval: int   # Number of shipments in each recurrence interval
    total_shipments: int  # Total number of shipments in the contract
    start_date: date  # Start date of the contract
    end_date: date  # Optional end date (if known)
    shipment_dates: List [date]
    payment_dates: List [date]
    # Status and Meta
    status: str
    carrier_id: Optional [int] = None
    carrier_git_cover_amount: Optional [int] = None
    carrier_liability_cover_amount: Optional [int] = None
    carrier_fleet_size: Optional [int] = None
    is_active: bool  # Whether the contract is active