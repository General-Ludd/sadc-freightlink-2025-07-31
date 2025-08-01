from pydantic import BaseModel, EmailStr
from typing import Dict, Any, Optional, List
from datetime import datetime, date, time

class Exchange_Ftl_Loadboard_Summary_Response(BaseModel):
    exchange_id: int
    type: str
    priority_level: str
    status: str
    origin_city_province: str
    pickup_date: date
    pickup_appointment: str
    destination_city_province: str
    delivery_appointment: str
    shipment_rate: int

class Exchange_Ftl_Load_Board_Response(BaseModel):
    exchange_id: int
    type: str
    trip_type: str
    load_type: str
    minimum_weight_bracket: int
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    shipment_rate: int
    leading_bid_id: Optional [int] = None
    distance: int
    rate_per_km: int
    rate_per_ton: int
    payment_terms: str
    payment_date: date
    status: str
    required_truck_type: str
    equipment_type: str
    trailer_type: Optional [str] = None
    trailer_length: Optional [str] = None
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
    pickup_appointment: str
    pickup_facility_name: str
    pickup_scheduling_type: str  # e.g., "First come, First served"
    pickup_start_time: time
    pickup_end_time: time
    pickup_facility_notes: str
    pickup_first_name: str
    pickup_last_name: str
    pickup_phone_number: str
    pickup_email: str
    delivery_appointment: str
    delivery_facility_name: str
    delivery_scheduling_type: str  # e.g., "First come, First served"
    delivery_start_time: time
    delivery_end_time: time
    delivery_facility_notes: str
    delivery_first_name: str
    delivery_last_name: str
    delivery_phone_number: str
    delivery_email: str
