from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date

from enums import Axle_Configuration, EquipmentType, Load_Type, Priority_Level, TrailerLength, TrailerType, TruckType

class Exchange_Power_Shipment_Booking(BaseModel):
    load_type: Load_Type
    required_truck_type: TruckType
    axle_configuration: Axle_Configuration
    trailer_id: int
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
    offer_rate: int
    automatically_accept_lower_bid: bool
    allow_carrier_to_book_at_current_or_lower_offer_rate: bool

class Exchange_Power_Shipments_Summary_Response(BaseModel):
    id: int
    type: str
    priority_level: str
    auction_status: str
    origin_city_province: str
    pickup_date: date
    distance: int
    destination_city_province: str
    offer_price: int
    number_of_bids_submitted: int

class exchange_power_shipment_response(BaseModel):
    id: int
    exchange_type: str
    type: str
    trip_type: str
    load_type : str
    shipper_company_id: int
    shipper_user_id: int
    required_truck_type: str
    axle_configuration: str
    trailer_id: int
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
    pickup_date: date
    priority_level: str
    pickup_facility_id: int
    delivery_facility_id: int
    customer_reference_number: str
    shipment_weight: int
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: Optional [str] = None
    packaging_type: Optional [str] = None
    pickup_number: Optional [str] = None
    pickup_notes: Optional [str] = None
    delivery_number: Optional [str] = None
    delivery_notes: Optional [str] = None
    distance: int
    estimated_transit_time: str
    offer_rate: int
    backed_offer_rate: int ### Update in database
    suggested_rate: int
    leading_bid_id: Optional [int] = None
    leading_bid_amount: Optional [int] = None ### Update in database
    winning_bid_price: Optional [int] = None
    number_of_bids_submitted: int
    route_preview_embed: str
    auction_status: str
    trip_savings: Optional [int] = None
    exchange_savings: Optional [int] = None
