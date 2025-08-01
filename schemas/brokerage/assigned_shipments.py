from pydantic import BaseModel, EmailStr
from typing import Dict, Any, Optional, List
from datetime import datetime, date, time

class Assigned_Shipments_SummaryResponse(BaseModel):
    id: int
    type: str
    status: str
    shipment_rate: int
    is_subshipment: bool
    lane_id: Optional [int] = None
    origin_city_province: str
    pickup_date: date
    pickup_start_time: time
    destination_city_province: str
    eta_date: date
    eta_window: str
    distance: int
    vehicle_id: Optional [int] = None
    vehicle_make: Optional [str] = None
    vehicle_model: Optional [str] = None
    driver_id: Optional [int] = None
    driver_first_name: Optional [str] = None
    driver_last_name: Optional [str] = None
    driver_phone_number: Optional [str] = None

class Driver_Assigned_Ftl_ShipmentsSummaryResponse(BaseModel):
    id: int
    type: str
    status: str
    is_subshipment: bool
    lane_id: Optional [int] = None
    origin_city_province: str
    pickup_date: date
    destination_city_province: str
    distance: int
    vehicle_id: int
    driver_id: int

class GetAssigned_Spot_Ftl_ShipmentRequest(BaseModel):
    id: int

class Assigned_Spot_Ftl_ShipmentResponse(BaseModel):
    id: int
    shipment_id: int
    is_subshipment: bool
    lane_id: Optional [int] = None
    type: str
    pod_document: Optional [str]
    invoice_id: int
    invoice_due_date: date
    invoice_status: str
    trip_type: str
    load_type: str
    carrier_id: int
    carrier_name: str
    vehicle_id: Optional [int] = None
    live_location: Optional [str] = None
    driver_id: Optional [int] = None
    accepted_for: Optional [str] = None
    accepted_at: Optional [str] = None
    minimum_weight_bracket: int
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    shipment_rate: int
    distance: int
    rate_per_km: int
    rate_per_ton: int
    payment_terms: str
    status: str
    trip_status: str
    required_truck_type: str
    equipment_type: str
    trailer_type: Optional [str] = None
    trailer_length: Optional [str] = None
    origin_address: str
    origin_address_completed: str
    origin_city_province: str
    origin_country: str
    origin_region: str
    destination_address: str
    destination_address_completed: str
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
    hazardous_materials: str
    packaging_quantity: str
    packaging_type: str
    pickup_number: str
    pickup_notes: str
    delivery_number: str
    delivery_notes: str
    estimated_transit_time: str
    pickup_facility_id: int
    pickup_facility_rating: Optional [float] = None
    delivery_facility_id: int
    delivery_facility_rating: Optional [float] = None
    text_pickup_date: Optional [str] = None
    text_eta_date: Optional [str] = None

class Driver_Assigned_Spot_Ftl_ShipmentResponse(BaseModel):
    id: int
    shipment_id: int
    is_subshipment: bool
    lane_id: Optional [int] = None
    type: str
    pod_document: Optional [str] = None
    invoice_id: int
    invoice_due_date: date
    invoice_status: str
    trip_type: str
    load_type: str
    carrier_id: int
    carrier_name: str
    vehicle_id: Optional [int] = None
    driver_id: Optional [int] = None
    accepted_for: Optional [str] = None
    accepted_at: Optional [str] = None
    minimum_weight_bracket: int
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    distance: int
    status: str
    trip_status: str
    required_truck_type: str
    equipment_type: str
    trailer_type: Optional [str] = None
    trailer_length: Optional [str] = None
    origin_address: str
    origin_address_completed: str
    origin_city_province: str
    origin_country: str
    origin_region: str
    destination_address: str
    destination_address_completed: str
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
    hazardous_materials: str
    packaging_quantity: str
    packaging_type: str
    pickup_number: str
    pickup_notes: str
    delivery_number: str
    delivery_notes: str
    estimated_transit_time: str
    pickup_facility_id: int
    pickup_facility_rating: Optional [float] = None
    delivery_facility_id: int
    delivery_facility_rating: Optional [float] = None
    text_pickup_date: Optional [str] = None
    text_eta_date: Optional [str] = None

class UpdateShipmentStatus(BaseModel):
    id: int
    status: str