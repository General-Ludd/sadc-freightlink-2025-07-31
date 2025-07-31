from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date

from enums import Axle_Configuration, Load_Type, Priority_Level, TruckType

class Spot_FTL_Power_Shipment_Create(BaseModel):
    shipper_company_id: int
    shipper_user_id: int
    required_truck_type: str
    trailer_id: int
    trailer_license_plate: str
    trailer_vin: str
    equipment_type: str
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None
    minimum_weight_bracket: int
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

class Power_Shipment_Booking(BaseModel):
    consignor_id: Optional [int] = None
    load_type: Load_Type
    required_truck_type: TruckType
    axle_configuration: Axle_Configuration
    minimum_weight_bracket: int
    minimum_git_cover_amount: Optional[int] = None
    minimum_liability_cover_amount: Optional[int] = None
    trailer_id: int
    origin_address: str
    destination_address: str
    pickup_date: date
    priority_level: Priority_Level
    customer_reference_number: Optional[str] = None
    shipment_weight: Optional[int] = None
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[str] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[str] = None
    delivery_notes: Optional[str] = None

class Power_Shipments_Summary_Response(BaseModel):
    id: int
    is_subshipment: bool
    lane_id: Optional [int] = None
    type: str
    priority_level: str
    shipment_status: str
    origin_city_province: str
    pickup_date: date
    pickup_appointment: str
    destination_city_province: str
    eta_date: date
    eta_window: str

class POWER_SHIPMENT_RESPONSE(BaseModel):
    id: int
    is_subshipment: bool
    dedicated_lane_id: int
    type: str
    trip_type: str
    load_type: str
    shipper_company_id: int
    shipper_user_id: int
    payment_terms: str
    invoice_id: int
    invoice_due_date: date # Update in database
    invoice_status: str
    minimum_git_cover_amount: int
    minimum_liability_cover_amount: int
    required_truck_type: str
    axle_configuration: str
    minimum_weight_bracket: int
    trailer_id: int
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
    pickup_date: date
    priority_level: str
    pickup_facility_id: int
    delivery_facility_id: int
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
    distance: int
    estimated_transit_time: str
    quote: int
    route_preview_embed: str
    shipment_status: str
    trip_status: str
    pod_document: str
    carrier_id: Optional [int] = None
    carrier_name: Optional [str] = None
    carrier_git_cover_amount: Optional [int] = None # Update in database
    carrier_liability_cover_amount: Optional [int] = None# Update in database
    vehicle_id: Optional [int] = None
    vehicle_make: Optional [str] = None
    vehicle_model: Optional [str] = None
    vehicle_year: Optional [int] = None
    vehicle_color: Optional [str] = None
    vehicle_license_plate: Optional [str] = None
    vehicle_vin: Optional [str] = None # Update in database
    vehicle_type: Optional [str] = None # Update in database
    vehicle_axle_configuration: Optional [str] = None
    driver_id: Optional [int] = None
    driver_first_name: Optional [str] = None # Update in database
    driver_last_name: Optional [str] = None # Update in database
    driver_license_number: Optional [str] = None # Update in database
    driver_email: Optional [str] = None # Update in database
    driver_phone_number: Optional [str] = None # Update in database

class POWER_Shipment_docs_create(BaseModel):
    commercial_invoice: Optional[str] = None
    packaging_list: Optional[str] = None
    customs_declaration_form: Optional[str] = None
    import_or_export_permits: Optional[str] = None
    certificate_of_origin: Optional[str] = None
    da5501orsad500: Optional[str] = None