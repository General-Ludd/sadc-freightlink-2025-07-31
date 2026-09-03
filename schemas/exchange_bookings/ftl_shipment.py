from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from decimal import Decimal
from datetime import date, datetime, timedelta, time

from enums import EquipmentType, Load_Type, Priority_Level, TrailerLength, TrailerType, TruckType, SchedulingType, HazchemClass

class Exchange_FTL_Shipment_Booking(BaseModel):
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
    under_bond: bool
    rib_requirements: bool
    packaging_quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[str] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    offer_price: int
    automatically_accept_lower_bid: bool
    allow_carrier_to_book_at_current_or_lower_offer_rate: bool

class Broker_Exchange_FTL_Shipment_Booking(BaseModel):
    consignor_id : Optional[int] = None
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
    consignor_billable: Optional[int] = None
    offer_price: int
    automatically_accept_lower_bid: bool
    allow_carrier_to_book_at_current_or_lower_offer_rate: bool

class Exchange_Ftl_Shipments_Summary_Response(BaseModel):
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

class Exchange_FTL_Shipment_Response(BaseModel):
    id: int
    exchange_type: str
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
    offer_price: int
    suggested_price: int
    leading_bid_id: Optional [int] = None
    winning_bid_price: Optional [int] = None
    number_of_bids_submitted: Optional [int] = None
    route_preview_embed: str
    auction_status: str


#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
#######################################################################################################################################
# ============================================================
# CLIENT SHIPMENT AUCTION STOP SCHEMAS
# ============================================================

class EmbeddedContactCreate(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    phone_number: str = Field(..., max_length=30)
    email: Optional[EmailStr] = Field(None, max_length=100)


# 2. The Consolidated Stop Creation Schema
class ClientShipmentAuctionStopCreate(BaseModel):
    address: str = Field(
        ...,
        description="The unverified physical lookup string sent by the client.",
    )
    stop_sequence: int = Field(..., ge=0)
    facility_name: str = Field(..., max_length=150)
    scheduling_type: SchedulingType

    # Operating availability window parameters
    operating_start_time: Optional[time] = None
    operating_end_time: Optional[time] = None

    # Operational day flags
    open_monday: bool = True
    open_tuesday: bool = True
    open_wednesday: bool = True
    open_thursday: bool = True
    open_friday: bool = True
    open_saturday: bool = False
    open_sunday: bool = False

    # Metadata & Tracking references
    reference_number: Optional[str] = None
    notes: Optional[str] = None

    # Embedded facility manager contact detail packet
    contact: Optional[EmbeddedContactCreate] = None


class ClientShipmentAuctionStopUpdate(BaseModel):
    stop_sequence: Optional[int] = Field(None, ge=1)
    stop_type: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = None
    complete_address: Optional[str] = None
    city_province: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    facility_id: Optional[int] = None
    appointment_date: Optional[date] = None
    appointment_time: Optional[str] = None
    reference_number: Optional[str] = None
    notes: Optional[str] = None


class ClientShipmentAuctionStopResponse(BaseModel):
    id: int
    shipment_id: int
    stop_sequence: int
    stop_type: str
    address: str
    complete_address: Optional[str]
    city_province: Optional[str]
    country: Optional[str]
    region: Optional[str]
    facility_id: Optional[int]
    appointment_date: Optional[date]
    appointment_time: Optional[str]
    reference_number: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


# ============================================================
# VEHICLE REQUIREMENT SCHEMAS
# ============================================================

class ClientShipmentAuctionVehicleRequirementCreate(BaseModel):
    configuration_type: str = Field(..., max_length=30)
    truck_type: str = Field(..., max_length=150)
    equipment_type: str = Field(..., max_length=150)
    trailer_type: Optional[str] = Field(None, max_length=150)
    trailer_length: Optional[str] = Field(None, max_length=150)


class ClientShipmentAuctionVehicleRequirementUpdate(BaseModel):
    configuration_type: Optional[str] = Field(None, max_length=30)
    truck_type: Optional[str] = Field(None, max_length=150)
    equipment_type: Optional[str] = Field(None, max_length=150)
    trailer_type: Optional[str] = Field(None, max_length=150)
    trailer_length: Optional[str] = Field(None, max_length=150)
    is_required: Optional[bool] = None


class ClientShipmentAuctionVehicleRequirementResponse(BaseModel):
    id: int
    shipment_id: int
    configuration_type: str
    truck_type: str
    equipment_type: str
    trailer_type: Optional[str]
    trailer_length: Optional[str]
    is_required: bool

    class Config:
        from_attributes = True


# ============================================================
# MAIN CLIENT SHIPMENT AUCTION SCHEMAS
# ============================================================

class ClientShipmentAuctionCreate(BaseModel):
    shipment_reference: str = Field(..., max_length=100)
    booking_reference: Optional[str] = Field(None, max_length=100)
    trip_type: str
    load_type: str
    origin: ClientShipmentAuctionStopCreate
    destination: ClientShipmentAuctionStopCreate
    number_of_trucks_required: int
    pickup_date: Optional[date] = None
    priority_level: Optional[str] = None
    customer_reference_number: Optional[str] = None
    shipment_weight: int
    commodity: Optional[str] = None
    temperature_control: Optional[str] = None
    target_temperature_spec: Optional[str] = Field(None, max_length=100)
    hazardous_materials: bool = False
    hazchem_classification: Optional[HazchemClass] = None
    under_bond: bool = False
    rib_requirements: bool = False
    packaging_quantity: Optional[int] = None
    packaging_type: Optional[str] = None

    # RATE INCLUDES
    rate_includes_fuel: bool = False
    rate_includes_driver: bool = False
    rate_includes_maintenance: bool = False
    rate_includes_insurance: bool = False
    rate_includes_tolls: bool = False
    rate_includes_border_charges: bool = False
    rate_includes_empty_return: bool = False
    rate_includes_waiting_time: bool = False
    rate_includes_loading_assistance: bool = False
    rate_includes_offloading_assistance: bool = False

    # Exchange & Bidding
    auction_closing_date: datetime
    pricing_basis: str = Field(..., max_length=50)
    vat_included: bool
    book_now_rate: Decimal = Field(..., max_digits=14, decimal_places=2)
    procurement_target_rate: Decimal = Field(..., max_digits=14, decimal_places=2)
    bidding_activated: bool = True
    rate_direction: str = Field(..., max_length=50)

    # OPERATIONAL REQUIREMENTS
    vehicle_tracking_required: bool = False
    all_time_hour_control_room: bool = False
    driver_mobile_phone: bool = False
    clean_compliant_equipment: bool = False
    pallet_management: bool = False
    pod_submission_local: str
    pod_submission_long_haul: str
    pod_submission_cross_border: str

    # INSURANCE REQUIREMENTS
    minimum_git_cover_amount: Optional[int] = 0
    minimum_liability_cover_amount: Optional[int] = 0
    minimum_weight_bracket: int
    git_all_risk_required: bool = False
    git_first_loss_required: bool = False
    git_driver_fidelity_required: bool = False

    # EQUIPMENT COMPLIANCE
    tarpaulin_compliance_required: bool = False
    corner_plates_required: bool = False
    chock_blocks_required: bool = False
    ratchets_belts_required: bool = False
    other_equipment_requirements: Optional[str] = None
    stops: list[ClientShipmentAuctionStopCreate] = []
    vehicle_configurations: list[ClientShipmentAuctionVehicleRequirementCreate] = []


class ClientShipmentAuctionUpdate(BaseModel):
    shipment_reference: Optional[str] = Field(None, max_length=100)
    booking_reference: Optional[str] = Field(None, max_length=100)
    trip_type: Optional[str] = None
    load_type: Optional[str] = None
    client_id: Optional[int] = None
    client_user_id: Optional[int] = None
    rate: Optional[Decimal] = Field(None, max_digits=14, decimal_places=2)
    pricing_basis: Optional[str] = Field(None, max_length=50)
    vat_treatment: Optional[str] = Field(None, max_length=30)
    payment_terms: Optional[str] = None
    invoice_id: Optional[int] = None
    invoice_due_date: Optional[date] = None
    invoice_status: Optional[str] = None
    origin_address: Optional[str] = None
    complete_origin_address: Optional[str] = None
    origin_city_province: Optional[str] = None
    origin_country: Optional[str] = None
    origin_region: Optional[str] = None
    destination_address: Optional[str] = None
    complete_destination_address: Optional[str] = None
    destination_city_province: Optional[str] = None
    destination_country: Optional[str] = None
    destination_region: Optional[str] = None
    pickup_date: Optional[date] = None
    priority_level: Optional[str] = None
    pickup_facility_id: Optional[int] = None
    delivery_facility_id: Optional[int] = None
    customer_reference_number: Optional[str] = None
    shipment_weight: Optional[int] = None
    commodity: Optional[str] = None
    temperature_control: Optional[str] = None
    target_temperature_spec: Optional[str] = None
    hazardous_materials: Optional[bool] = None
    hazchem_classification: Optional[HazchemClass] = None
    under_bond: Optional[bool] = None
    rib_requirements: Optional[bool] = None
    packaging_quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    distance: Optional[int] = None
    estimated_transit_time: Optional[str] = None
    eta_date: Optional[date] = None
    eta_window: Optional[str] = None
    route_preview_embed: Optional[str] = None
    polyline: Optional[str] = None
    status: Optional[str] = Field(None, max_length=50)
    trip_status: Optional[str] = Field(None, max_length=50)
    pod_document: Optional[str] = None
    carrier_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    driver_id: Optional[int] = None

    # RATE INCLUDES
    rate_includes_fuel: Optional[bool] = None
    rate_includes_driver: Optional[bool] = None
    rate_includes_maintenance: Optional[bool] = None
    rate_includes_insurance: Optional[bool] = None
    rate_includes_tolls: Optional[bool] = None
    rate_includes_border_charges: Optional[bool] = None
    rate_includes_empty_return: Optional[bool] = None
    rate_includes_waiting_time: Optional[bool] = None
    rate_includes_loading_assistance: Optional[bool] = None
    rate_includes_offloading_assistance: Optional[bool] = None

    # OPERATIONAL REQUIREMENTS
    vehicle_tracking_required: Optional[bool] = None
    all_time_hour_control_room: Optional[bool] = None
    driver_mobile_phone: Optional[bool] = None
    clean_compliant_equipment: Optional[bool] = None
    pallet_management: Optional[bool] = None
    pod_submission_local: Optional[str] = None
