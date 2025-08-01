from pydantic import BaseModel, EmailStr
from typing import Dict, Any, Optional, List
from datetime import datetime, date, time

class AssignShipmentRequest(BaseModel):
    shipment_id: int
    vehicle_id: int

class IndividualLoadboardShipmentRequest(BaseModel):
    id: int

class Individual_lane_id(BaseModel):
    shipment_id: int

class LoadBoardEntryCreate(BaseModel):
    shipment_id: int
    type: str
    trip_type: str
    load_type: str
    minimum_weight_bracket: int
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    shipment_rate: int
    distance: int
    rate_per_km: int
    rate_per_ton: int
    payment_terms: str
    payment_date: date
    required_truck_type: str
    equipment_type: str
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None
    origin_address: str
    destination_address: str
    pickup_date: date
    priority_level: str
    customer_reference_number: Optional[str] = None
    shipment_weight: Optional[int] = None
    commodity: str
    temperature_control: str
    hazardous_metarials: bool
    packaging_quantity: Optional[int] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[str] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    estimated_transit_time: str
    pickup_facility_name: str
    pickup_scheduling_type: str
    pickup_start_time: time
    pickup_end_time: time
    pickup_facility_notes: Optional[str]
    pickup_first_name: str
    pickup_last_name: str
    pickup_phone_number: str
    pickup_email: EmailStr
    delivery_facility_name: str
    delivery_scheduling_type: str
    delivery_start_time: time
    delivery_end_time: time
    delivery_facility_notes: Optional[str]
    delivery_first_name: str
    delivery_last_name: str
    delivery_phone_number: str
    delivery_email: EmailStr

class SpotFTLLoadBoardSummaryResponse(BaseModel):
    shipment_id: int
    shipment_rate: int
    trip_type: Optional[str] = None
    origin_city_province: str
    pickup_date: date
    pickup_appointment: str
    pickup_facility_rating: Optional[float] = None
    route_preview_embed: str
    destination_city_province: str
    eta_date: date
    eta_window: str
    delivery_facility_rating: Optional[float] = None
    distance: int
    rate_per_km: int
    required_truck_type: str
    equipment_type: str
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None
    minimum_weight_bracket: int
    commodity: str

class LoadBoardEntryResponse(LoadBoardEntryCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class PowerLoadBoardEntry(BaseModel):
    shipment_id: int
    minimum_weight_bracket: int
    shipment_rate: int
    distance: int
    rate_per_km: int
    rate_per_ton: int
    payment_terms: str
    required_truck_type: str
    axle_configuration: str
    trailer_equipment_type: str
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None
    origin_address: str
    destination_address: str
    pickup_date: date
    priority_level: str
    customer_reference_number: Optional[str] = None
    shipment_weight: Optional[int] = None
    commodity: str
    packaging_quantity: Optional[int] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[int] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[int] = None
    delivery_notes: Optional[str] = None
    estimated_transit_time: str
    pickup_facility_name: str
    pickup_scheduling_type: str
    pickup_start_time: time
    pickup_end_time: time
    pickup_facility_notes: Optional[str]
    pickup_first_name: str
    pickup_last_name: str
    pickup_phone_number: str
    pickup_email: EmailStr
    delivery_facility_name: str
    delivery_scheduling_type: str
    delivery_start_time: time
    delivery_end_time: time
    delivery_facility_notes: Optional[str]
    delivery_first_name: str
    delivery_last_name: str
    delivery_phone_number: str
    delivery_email: EmailStr

class SpotPowerLoadBoardSummaryResponse(BaseModel):
    shipment_id: int
    shipment_rate: int
    load_type: Optional[str] = None
    origin_city_province: str
    pickup_date: date
    pickup_appointment: str
    pickup_facility_rating: Optional[float] = None
    route_preview_embed: str
    destination_city_province: str
    eta_date: date
    eta_window: str
    delivery_facility_rating: Optional[float] = None
    distance: int
    rate_per_km: int
    required_truck_type: str
    axle_configuration: str
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None

class IndividualSpotPowerLoadboardShipmentResponse(BaseModel):
    shipment_id: int
    minimum_weight_bracket: int
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    shipment_rate: int
    distance: int
    rate_per_km: int
    rate_per_ton: int
    payment_terms: str
    status: str
    required_truck_type: str
    axle_configuration: str
    trailer_make: str
    trailer_model: str
    trailer_year: int
    trailer_color: str
    trailer_equipment_type: str
    trailer_type: str
    trailer_length: str
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
    route_preview_embed: str
    pickup_date: date
    priority_level: str
    customer_reference_number: str
    shipment_weight: int
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: str
    packaging_type: str
    pickup_number: str
    pickup_notes: str
    delivery_number: str
    delivery_notes: str
    estimated_transit_time: str
    pickup_facility_name: str
    pickup_scheduling_type: str # e.g., "First come, First served"
    pickup_start_time: time
    pickup_end_time: time
    pickup_facility_notes: str
    pickup_first_name: str
    pickup_last_name: str
    pickup_phone_number: str
    pickup_email: str
    delivery_facility_name: Optional[str]
    delivery_scheduling_type: Optional[str] # e.g., "First come, First served"
    delivery_start_time: Optional[time]
    delivery_end_time: Optional[time]
    delivery_facility_notes: Optional[str]
    delivery_first_name: Optional[str]
    delivery_last_name: Optional[str]
    delivery_phone_number: Optional[str]
    delivery_email: Optional[str]

class SpotPowerLoadBoardEntryResponse(LoadBoardEntryCreate):
    id: int
    created_at: datetime

class FTL_lane_LoadBoard_Entry(BaseModel):
    shipment_id: int
    minimum_weight_bracket: int
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    contract_rate: int
    distance: int
    rate_per_km: int
    rate_per_ton: int
    payment_terms: str
    recurrence_frequency: str
    recurrence_days: List[str] = []
    skip_weekends: bool
    shipments_per_interval: int
    total_shipments: int
    rate_per_shipment: int
    start_date: date
    end_date: date
    shipment_dates: List[date] = []
    required_truck_type: str
    equipment_type: str
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None
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
    route_preview_embed: str
    customer_reference_number: Optional[str] = None
    average_shipment_weight: Optional[int] = None
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: Optional[int] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[int] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[int] = None
    delivery_notes: Optional[str] = None
    estimated_transit_time: str
    pickup_facility_name: str
    pickup_scheduling_type: str
    pickup_start_time: time
    pickup_end_time: time
    pickup_facility_notes: Optional[str]
    pickup_first_name: str
    pickup_last_name: str
    pickup_phone_number: str
    pickup_email: EmailStr
    delivery_facility_name: str
    delivery_scheduling_type: str
    delivery_start_time: time
    delivery_end_time: time
    delivery_facility_notes: Optional[str]
    delivery_first_name: str
    delivery_last_name: str
    delivery_phone_number: str
    delivery_email: EmailStr

class FTL_Lane_LoadBoard_Summary_Response(BaseModel):
    shipment_id: int
    status: str
    type: Optional[str]
    trip_type: Optional[str]
    load_type: Optional[str]
    origin_city_province: Optional[str]
    destination_city_province: Optional[str]
    distance: int
    route_preview_embed: Optional[str]
    required_truck_type: str
    equipment_type: str
    trailer_type: str
    trailer_length: str
    minimum_weight_bracket: int
    commodity: str
    packaging_type: str
    average_shipment_weight: int
    start_date: date
    end_date: date
    recurrence_frequency: str
    shipments_per_interval: int
    total_shipments: int
    rate_per_shipment: int
    contract_rate: int

class FTL_Lane_Loadboard_Individual_Shipment_Response(BaseModel):
    shipment_id: int
    trip_type: str
    load_type: str
    minimum_weight_bracket: int
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    contract_rate: int
    distance: int
    rate_per_km: int
    rate_per_ton: int
    payment_terms: str
    recurrence_frequency: str  # How often shipments occur
    recurrence_days: List[str] # Days (e.g., "Monday, Wednesday, Friday")
    skip_weekends: bool
    shipments_per_interval: int # Number of shipments in each recurrence interval
    total_shipments: int  # Total number of shipments in the contract
    rate_per_shipment: int
    start_date: date  # Start date of the contract
    end_date: date  # Optional end date (if known)
    shipment_dates: List[date]
    status: str
    required_truck_type: str
    equipment_type: str
    trailer_type: str
    trailer_length: str
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
    route_preview_embed: str
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
    estimated_transit_time: str
    pickup_facility_name: str
    pickup_scheduling_type: str # e.g., "First come, First served"
    pickup_start_time: time
    pickup_end_time: time
    pickup_facility_notes: str
    pickup_first_name: str
    pickup_last_name: str
    pickup_phone_number: str
    pickup_email: str
    delivery_facility_name: str
    delivery_scheduling_type: str  # e.g., "First come, First served"
    delivery_start_time: time
    delivery_end_time: time
    delivery_facility_notes: str
    delivery_first_name: str
    delivery_last_name: str
    delivery_phone_number: str
    delivery_email: str

class Dedicated_Power_lane_LoadBoard_Entry(BaseModel):
    shipment_id: int
    minimum_weight_bracket: int
    contract_price: int
    minimum_git_cover: int
    distance: int
    rate_per_km: int
    rate_per_ton: int
    payment_date: str
    recurrence_frequency: str
    recurrence_days: List[str] = []
    skip_weekends: bool
    shipments_per_interval: int
    total_shipments: int
    price_per_shipment: int
    start_date: date
    end_date: date
    shipment_dates: List[date] = []
    required_truck_type: str
    equipment_type: str
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None
    origin_address: str
    destination_address: str
    customer_reference_number: Optional[str] = None
    shipment_weight: Optional[int] = None
    commodity: str
    packaging_quantity: Optional[int] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[int] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[int] = None
    delivery_notes: Optional[str] = None
    estimated_transit_time: str
    pickup_facility_name: str
    pickup_scheduling_type: str
    pickup_start_time: time
    pickup_end_time: time
    pickup_facility_notes: Optional[str]
    pickup_first_name: str
    pickup_last_name: str
    pickup_phone_number: str
    pickup_email: EmailStr
    delivery_facility_name: str
    delivery_scheduling_type: str
    delivery_start_time: time
    delivery_end_time: time
    delivery_facility_notes: Optional[str]
    delivery_first_name: str
    delivery_last_name: str
    delivery_phone_number: str
    delivery_email: EmailStr