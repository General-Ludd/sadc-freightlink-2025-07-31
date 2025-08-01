from pydantic import BaseModel, EmailStr
from typing import Dict, Any, Optional, List
from datetime import datetime, date, time

class Dedicated_Ftl_Lane_Summary_Response(BaseModel):
    id: int
    lane_id: int
    type: str
    status: str
    contract_rate: int
    origin_city_province: str
    destination_city_province: str
    distance: int
    recurrence_frequency: str
    shipments_per_interval: int
    start_date: date
    end_date: date
    total_shipments_completed: int

class Individual_Ftl_Lane_Response(BaseModel):
    lane_id: int
    type: str
    trip_type: str
    load_type: str
    carrier_id: int
    carrier_name: str

    # Contract Details
    contract_rate: int
    rate_per_shipment: int
    payment_terms: str
    invoice_id: int
    invoice_due_date: date
    invoice_status: str
    payment_dates: List [date]
    completed_origin_address: str
    completed_destination_address: str
    distance: int
    rate_per_km: int
    rate_per_ton: int
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    status: str
    total_shipment_completed: int

    # Recurrence Details
    recurrence_frequency: str
    recurrence_days: List [str]
    skip_weekends: bool
    shipments_per_interval: int
    total_shipments: int # Total number of shipments in the contract
    start_date: date
    end_date: date
    shipment_dates: List [date]

    # Shipment Details
    required_truck_type: str
    equipment_type: str
    trailer_type: str
    trailer_length: str
    minimum_weight_bracket: int
    origin_address: str
    origin_address_city_provice: str
    origin_country: str
    origin_region: str
    pickup_appointment: str
    destination_address: str
    destination_address_city_provice: str
    destination_country: str
    destinationn_region: str
    delivery_appointment: str
    route_preview_embed: str
    priority_level: str
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
    pickup_facility_id: int
    delivery_facility_id: int
