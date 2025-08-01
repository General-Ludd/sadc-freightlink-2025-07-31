from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import date

from enums import EquipmentType, Load_Type, Priority_Level, TrailerLength, TrailerType, TruckType, Recurrence_Frequency

class Exchange_FTL_Lane_Booking(BaseModel):
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

    ##Recurrence Information##
    start_date: date
    end_date: date
    recurrence_frequency: str
    recurrence_days: List[str] = []
    skip_weekends: bool
    shipments_per_interval: int

    priority_level: Priority_Level
    customer_reference_number: Optional[str] = None
    average_shipment_weight: int
    commodity: str
    temperature_control: str
    hazardous_materials: bool
    packaging_quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[str] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    per_shipment_offer_rate: int


class Exchange_Ftl_Lane_Summary_Response(BaseModel):
    id: int
    type: str
    priority_level: str
    auction_status: str
    origin_city_province: str
    start_date: date
    end_date: date
    distance: int
    destination_city_province: str
    contract_offer_price: int
    leading_contract_bid_amount: int
    number_of_bids_submitted: int

class Exchange_Ftl_Lane_Response(BaseModel):
    id: int
    type: str
    trip_type: str
    load_type: str
    shipper_company_id: int
    shipper_user_id: int
    required_truck_type: str
    equipment_type: str
    trailer_type: str
    trailer_length: str
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
    packaging_quantity: Optional [str] = None
    packaging_type: Optional [str] = None
    pickup_number: Optional [str] = None
    pickup_notes: Optional [str] = None
    delivery_number: Optional [str] = None
    delivery_notes: Optional [str] = None
    distance: int
    estimated_transit_time: str
    route_preview_embed: str
    contract_offer_rate: int
    per_shipment_offer_rate: int
    suggested_contract_rate: int
    suggested_per_shipment_rate: int
    leading_bid_id: Optional [int] = None
    leading_contract_bid_amount: Optional [int] = None
    leading_per_shipment_bid_amount: Optional [int] = None ### Update in database
    winning_bid_per_shipment_rate: Optional [int] = None
    winning_bid_contract_rate: Optional [int] = None
    number_of_bids_submitted: Optional [int] = None
    payment_terms: str

    # Recurrence Details
    recurrence_frequency: str  # How often shipments occur
    recurrence_days: str # Days (e.g., "Monday, Wednesday, Friday")
    skip_weekends: bool
    shipments_per_interval: int  # Number of shipments in each recurrence interval
    total_shipments: int  # Total number of shipments in the contract
    start_date: date  # Start date of the contract
    end_date: date  # Optional end date (if known)
    shipment_dates: List[date]
    payment_dates: List[date]
    # Status and Meta
    auction_status: str
    is_active: bool  # Whether the contract is active