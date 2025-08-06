from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, datetime

from sqlalchemy import true

from enums import EquipmentType, Load_Type, Priority_Level, TrailerLength, TrailerType, TruckType

class FTL_Shipment_Booking(BaseModel):
    consignor_id: Optional [int] = None
    required_truck_type: TruckType
    equipment_type: EquipmentType
    trailer_type: Optional[TrailerType] = None
    trailer_length: Optional[TrailerLength] = None
    minimum_weight_bracket: int
    minimum_git_cover_amount: Optional[int] = None
    minimum_liability_cover_amount: Optional[int] = None
    origin_address: str
    destination_address: str
    pickup_date: date
    priority_level: Priority_Level
    customer_reference_number: Optional[str] = None
    shipment_weight: int
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[str] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[str] = None
    delivery_notes: Optional[str] = None

class FTL_Shipments_Summary_Response(BaseModel):
    id: int
    type: str
    priority_level: str
    shipment_status: str
    origin_city_province: str
    pickup_date: date
    pickup_appointment: str
    destination_city_province: str
    eta_date: date
    eta_window: str

class FTL_Shipment_Response(BaseModel):
    id: int
    is_subshipment: bool
    dedicated_lane_id: Optional [int] = None
    shipment_status: str
    trip_status: str
    pod_document: Optional [str] = None
    payment_terms: str
    invoice_id: int
    invoice_due_date: date
    invoice_status: str
    type: str
    trip_type: str
    load_type: Load_Type
    required_truck_type: TruckType
    equipment_type: EquipmentType
    trailer_type: Optional[TrailerType] = None
    trailer_length: Optional[TrailerLength] = None
    minimum_weight_bracket: int
    minimum_git_cover_amount: Optional[int] = None
    minimum_liability_cover_amount: Optional[int] = None
    complete_origin_address: str
    origin_city_province: str
    origin_country: str
    origin_region: str
    complete_destination_address: str
    destination_city_province: str
    destination_country: str
    destination_region: str
    distance: int
    estimated_transit_time: str
    route_preview_embed: str
    pickup_date: date
    priority_level: Priority_Level
    customer_reference_number: Optional[str] = None
    shipment_weight: int
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: Optional[int] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[str] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    carrier_id: Optional[int] = None
    carrier_name: Optional[str] = None
    carrier_git_cover_amount: Optional[int] = None
    carrier_liability_cover_amount: Optional[int] = None
    vehicle_id: Optional[int] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_color: Optional[str] = None
    vehicle_license_plate: Optional[str] = None
    vehicle_vin: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_equipment_type: Optional[str] = None
    vehicle_trailer_type: Optional[str] = None
    vehicle_trailer_length: Optional[str] = None
    vehicle_tare_weight: Optional[int] = None
    vehicle_gvm_weight: Optional[int] = None
    vehicle_payload_capacity: Optional[int] = None
    driver_id: Optional[int] = None
    driver_first_name: Optional[str] = None
    driver_last_name: Optional[str] = None
    driver_license_number: Optional[str] = None
    driver_email: Optional[str] = None
    driver_phone_number: Optional[str] = None

class FTL_Shipment_docs_create(BaseModel):
    commercial_invoice: Optional[str] = None
    packaging_list: Optional[str] = None
    customs_declaration_form: Optional[str] = None
    import_or_export_permits: Optional[str] = None
    certificate_of_origin: Optional[str] = None
    da5501orsad500: Optional[str] = None

class Shipment_docs_Response(BaseModel):
    commercial_invoice: Optional[str] = None
    packaging_list: Optional[str] = None
    customs_declaration_form: Optional[str] = None
    import_or_export_permits: Optional[str] = None
    certificate_of_origin: Optional[str] = None
    da5501orsad500: Optional[str] = None

class AssignedFTLShipmentsResponse(BaseModel):
    id: int
    shipment_id: int
    is_subshipment: bool
    lane_id: Optional[int] = None
    type: str
    pod_document: Optional[str] = None
    invoice_id: int
    invoice_due_date: date
    invoice_status: str
    trip_type: str
    load_type: str
    carrier_id: int
    carrier_name: str
    vehicle_id: Optional[int] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_license_plate: Optional[str] = None
    live_location: Optional[str] = None
    driver_id: Optional[int] = None
    driver_first_name: Optional[str] = None
    driver_last_name: Optional[str] = None
    accepted_for: Optional[str] = None
    accepted_at: Optional[str] = None
    minimum_weight_bracket: int
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    shipment_rate: int
    distance: int
    rate_per_km: int
    rate_per_ton: int
    payment_terms: int
    status: str
    trip_status: str
    required_truck_type: str
    equipment_type: str
    trailer_type: str
    trailer_length: str
    origin_address: str
    origin_address_completed: str
    origin_address_city_provice: str
    origin_country: str
    origin_region: str
    pickup_appointment: str
    destination_address: str
    destination_address_completed: str
    destination_address_city_provice: str
    destination_country: str
    destinationn_region: str
    delivery_appointment: str
    route_preview_embed: str
    pickup_date: date
    priority_level: str
    customer_reference_number: str
    shipment_weight: int
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: Optional[int] = None
    packaging_type: str
    pickup_number: Optional[str] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    estimated_transit_time: str
    pickup_facility_id: int
    pickup_facility_rating: float
    delivery_facility_id: int
    delivery_facility_rating: float
    text_pickup_date: str
    text_eta_date: str


class FTL_Shipment_Dispute_Create(BaseModel):
    shipment_id: int
    dispute_reason: str
    additional_details: Optional [str] = None

class Shipment_Dispute_Response(BaseModel):
    id: int
    filed_by_shipper: bool
    shipment_id: int
    shipper_company_id: int
    carrier_company_id: int
    dispute_reason: str
    additional_details: Optional [str] = None
    status: str
    created_at: datetime
