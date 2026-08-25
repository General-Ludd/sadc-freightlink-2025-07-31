from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import date, datetime

from enums import EquipmentType, Load_Type, Priority_Level, TrailerLength, TrailerType, TruckType, Recurrence_Frequency, HazchemClass

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
    under_bond: bool
    rib_requirements: bool
    packaging_quantity: Optional[str] = None
    packaging_type: Optional[str] = None
    pickup_number: Optional[str] = None
    pickup_notes: Optional[str] = None
    delivery_number: Optional[str] = None
    delivery_notes: Optional[str] = None
    per_shipment_offer_rate: int

class Broker_Exchange_FTL_Lane_Booking(BaseModel):
    consignor_id: int
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
    per_shipment_consignor_billable: Optional[int] = None

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





from pydantic import BaseModel, Field
from typing import Optional


class TenderStopCreate(BaseModel):

    stop_sequence: int = Field(..., ge=1, le=5)
    address: str = Field(..., min_length=1, max_length=500)


class TenderStopUpdate(BaseModel):

    stop_sequence: Optional[int] = Field(None, ge=1, le=5)
    address: Optional[str] = Field(None, min_length=1, max_length=500)
    facility_name: Optional[str] = None


class TenderStopResponse(BaseModel):

    id: int
    tender_id: int
    stop_sequence: int
    address: str

    class Config:
        from_attributes = True

class TenderVehicleConfigCreate(BaseModel):

    configuration_type: str = Field(..., max_length=30)

    truck_type: str = Field(..., max_length=150)
    equipment_type: str = Field(..., max_length=150)

    trailer_type: Optional[str] = Field(
        None,
        max_length=150
    )

    trailer_length: Optional[str] = Field(
        None,
        max_length=150
    )


class TenderVehicleConfigUpdate(BaseModel):

    configuration_type: Optional[str] = Field(
        None,
        max_length=30
    )

    truck_type: Optional[str] = Field(
        None,
        max_length=150
    )

    equipment_type: Optional[str] = Field(
        None,
        max_length=150
    )

    trailer_type: Optional[str] = Field(
        None,
        max_length=150
    )

    trailer_length: Optional[str] = Field(
        None,
        max_length=150
    )

    is_active: Optional[bool] = None


class TenderVehicleConfigResponse(BaseModel):

    id: int
    tender_id: int

    configuration_type: str

    truck_type: str
    equipment_type: str
    trailer_type: Optional[str]
    trailer_length: Optional[str]

    is_active: bool

    class Config:
        from_attributes = True

class TenderVolumeProfileCreate(BaseModel):

    volume_entry_method: str = Field(
        ...,
        max_length=30
    )

    period_sequence: int = Field(
        ...,
        ge=1
    )

    period_label: Optional[str] = Field(
        None,
        max_length=50
    )

    period_start_date: Optional[date] = None

    period_end_date: Optional[date] = None

    day_of_week: Optional[str] = Field(
        None,
        max_length=20
    )

    expected_loads: int = Field(
        ...,
        ge=0
    )


class TenderVolumeProfileUpdate(BaseModel):

    volume_entry_method: Optional[str] = Field(
        None,
        max_length=30
    )

    period_sequence: Optional[int] = Field(
        None,
        ge=1
    )

    period_label: Optional[str] = Field(
        None,
        max_length=50
    )

    period_start_date: Optional[date] = None

    period_end_date: Optional[date] = None

    day_of_week: Optional[str] = Field(
        None,
        max_length=20
    )

    expected_loads: Optional[int] = Field(
        None,
        ge=0
    )


class TenderVolumeProfileResponse(BaseModel):

    id: int
    tender_id: int

    volume_entry_method: str

    period_sequence: int
    period_label: Optional[str]

    period_start_date: Optional[date]
    period_end_date: Optional[date]

    day_of_week: Optional[str]

    expected_loads: int

    class Config:
        from_attributes = True

class TenderAccessorialCreate(BaseModel):

    charge_type: str = Field(
        ...,
        max_length=100
    )

    treatment: str = Field(
        ...,
        max_length=100
    )

    threshold_value: Optional[float] = Field(
        None,
        ge=0
    )

    threshold_unit: Optional[str] = Field(
        None,
        max_length=50
    )

    notes: Optional[str] = None


class TenderAccessorialUpdate(BaseModel):

    charge_type: Optional[str] = Field(
        None,
        max_length=100
    )

    treatment: Optional[str] = Field(
        None,
        max_length=100
    )

    threshold_value: Optional[float] = Field(
        None,
        ge=0
    )

    threshold_unit: Optional[str] = Field(
        None,
        max_length=50
    )

    notes: Optional[str] = None


class TenderAccessorialResponse(BaseModel):

    id: int
    tender_id: int

    charge_type: str
    treatment: str

    threshold_value: Optional[float]
    threshold_unit: Optional[str]

    notes: Optional[str]

    class Config:
        from_attributes = True


class TenderCreate(BaseModel):

    # ============================================================
    # SECTION 1 — TENDER SCOPE & ROUTING
    # ============================================================

    tender_title: str = Field(
        ...,
        min_length=1,
        max_length=255
    )

    scope_description: str = Field(
        ...,
        min_length=1
    )

    business_unit: str = Field(
        ...,
        max_length=100
    )

    cost_centre_project_code: str = Field(
        ...,
        max_length=100
    )

    tender_length_category: str = Field(
        ...,
        max_length=50
    )

    tender_category: str = Field(
        ...,
        max_length=100
    )

    contract_start_date: date
    contract_end_date: date

    origin: TenderStopUpdate

    destination: TenderStopUpdate

    border_customs_responsibility: Optional[str] = Field(
        None,
        max_length=50
    )

    estimated_distance_km: Optional[int] = None

    priority_level: str = Field(
        ...,
        max_length=20
    )

    load_type: str = Field(
        ...,
        max_length=50
    )

    customer_reference: Optional[str] = Field(
        None,
        max_length=100
    )

    # ============================================================
    # SECTION 2 — CARGO
    # ============================================================

    commodity: str = Field(
        ...,
        min_length=1
    )

    average_shipment_weight_kg: int = Field(
        ...,
        gt=0
    )

    minimum_weight_bracket_kg: int = Field(
        ...,
        gt=0
    )

    packaging_type: Optional[str] = Field(
        None,
        max_length=100
    )

    packaging_quantity: Optional[str] = Field(
        None,
        max_length=100
    )

    temperature_control: Optional[str] = Field(
        None,
        max_length=100
    )

    target_temperature_spec: Optional[str] = Field(
        None,
        max_length=100
    )

    hazardous_materials: bool = False

    hazchem_classification: Optional[HazchemClass] = Field(
        None,
        max_length=100
    )

    under_bond: bool = False

    rib_requirements: bool = False

    minimum_git_cover_amount: float = Field(
        ...,
        ge=0
    )

    minimum_liability_cover_amount: float = Field(
        ...,
        ge=0
    )

    # ============================================================
    # SECTION 3 — VOLUME
    # ============================================================

    volume_entry_method: str = Field(
        ...,
        max_length=30
    )

    volume_commitment: str = Field(
        ...,
        max_length=50
    )

    # ============================================================
    # SECTION 4 — PRICING
    # ============================================================

    pricing_basis: str = Field(
        ...,
        max_length=50
    )

    incumbent_transport_rate_per_shipment: float = Field(
        ...,
        ge=0
    )
    procurement_target_rate: float = Field(
        ...,
        ge=0
    )

    rate_direction: str = Field(
        ...,
        max_length=50
    )

    # ============================================================
    # RATE INCLUDES
    # ============================================================

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

    # ============================================================
    # FUEL
    # ============================================================

    fuel_treatment_type: str = Field(
        ...,
        max_length=100
    )

    base_diesel_price: Optional[float] = Field(
        None,
        ge=0
    )

    fuel_review_period: Optional[str] = Field(
        None,
        max_length=50
    )

    fuel_component_percentage: Optional[float] = Field(
        None,
        ge=0,
        le=100
    )

    # ============================================================
    # VAT / RATE VALIDITY
    # ============================================================

    vat_treatment: str = Field(
        ...,
        max_length=30
    )

    rate_validity: str = Field(
        ...,
        max_length=50
    )

    # ============================================================
    # TENDER PROCESS
    # ============================================================

    tender_closing_date: datetime

    questions_deadline: Optional[datetime] = None

    # ============================================================
    # OPERATIONAL REQUIREMENTS
    # ============================================================

    vehicle_tracking_required: bool = False

    all_time_hour_control_room: bool = False

    driver_mobile_phone: bool = False

    clean_compliant_equipment: bool = False

    pallet_management: bool = False

    pod_submission_local: Optional[str] = Field(
        None,
        max_length=100
    )

    pod_submission_long_haul: Optional[str] = Field(
        None,
        max_length=100
    )

    pod_submission_cross_border: Optional[str] = Field(
        None,
        max_length=100
    )

    subcontracting_policy: Optional[str] = Field(
        None,
        max_length=50
    )

    # ============================================================
    # DOCUMENTATION
    # ============================================================

    delivery_documentation_sla: Optional[str] = Field(
        None,
        max_length=100
    )

    claims_risk_policy: Optional[str] = Field(
        None,
        max_length=100
    )

    claims_risk_requirements: Optional[str] = None

    # ============================================================
    # INSURANCE
    # ============================================================

    git_all_risk_required: bool = False
    git_first_loss_required: bool = False
    git_driver_fidelity_required: bool = False

    # ============================================================
    # EQUIPMENT COMPLIANCE
    # ============================================================

    tarpaulin_compliance_required: bool = False
    corner_plates_required: bool = False
    chock_blocks_required: bool = False
    ratchets_belts_required: bool = False

    other_equipment_requirements: Optional[str] = None

    # ============================================================
    # BID EVALUATION
    # ============================================================

    evaluation_price_enabled: bool = True
    evaluation_capacity_enabled: bool = True
    evaluation_service_enabled: bool = True
    evaluation_compliance_enabled: bool = True
    evaluation_flexibility_enabled: bool = True

    # ============================================================
    # CHILD RECORDS
    # ============================================================

    stops: list[TenderStopCreate] = []
    vehicle_configurations: list[TenderVehicleConfigCreate] = []
    volume_profiles: list[TenderVolumeProfileCreate] = []
    accessorials: list[TenderAccessorialCreate] = []