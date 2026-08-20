from sqlalchemy import ARRAY, Boolean, Integer, String, Column, Float, Date, DateTime, Enum, func
from models.base import Base
from utils.sast_datetime import get_sast_time

class FTL_Lane_Exchange(Base):
    __tablename__ = "ftl_lane_exchanges"

    id = Column(Integer, primary_key=True, index=True)
    consignor_id = Column(Integer, nullable=True)
    type = Column(String)
    trip_type = Column(String, nullable=False)
    load_type = Column(String, nullable=False)
    shipper_company_id = Column(Integer)
    shipper_user_id = Column(Integer)
    required_truck_type = Column(String, nullable=True)
    equipment_type = Column(String, nullable=True)
    trailer_type = Column(String, nullable=True)
    trailer_length = Column(String, nullable=True)
    minimum_weight_bracket = Column(Integer, nullable=True)
    minimum_git_cover_amount = Column(Integer, default=0, nullable=True)
    minimum_liability_cover_amount = Column(Integer, default=0, nullable=True)
    origin_address = Column(String)
    complete_origin_address = Column(String)
    origin_city_province = Column(String)
    origin_country = Column(String)
    origin_region = Column(String)
    destination_address = Column(String)
    complete_destination_address = Column(String)
    destination_city_province = Column(String)
    destination_country = Column(String)
    destination_region = Column(String)
    priority_level = Column(String)
    pickup_facility_id = Column(Integer)
    delivery_facility_id = Column(Integer)
    customer_reference_number = Column(String)
    average_shipment_weight = Column(Integer)
    commodity = Column(String)
    temperature_control = Column(String)
    hazardous_materials = Column(Boolean, nullable=False)
    under_bond = Column(Boolean, default=False) ########### Add to DB
    rib_requirements = Column(Boolean, default=False) ####### Add to DB
    packaging_quantity = Column(String)
    packaging_type = Column(String)
    pickup_number = Column(String)
    pickup_notes = Column(String)
    delivery_number = Column(String)
    delivery_notes = Column(String)
    distance = Column(Integer, nullable=True)
    estimated_transit_time = Column(String)
    route_preview_embed = Column(String)
    contract_offer_rate = Column(Integer)
    per_shipment_offer_rate = Column(Integer)
    contract_consignor_billable = Column(Integer)
    per_shipment_consignor_billable = Column(Integer)
    backed_contract_offer_rate = Column(Integer)
    backed_per_shipment_offer_rate = Column(Integer)
    suggested_contract_rate = Column(Integer)
    suggested_per_shipment_rate = Column(Integer)
    leading_bid_id = Column(Integer)
    leading_contract_bid_amount = Column(Integer)
    leading_per_shipment_bid_amount = Column(Integer, nullable=True) ### Update in database
    winning_bid_per_shipment_rate = Column(Integer, nullable=True)
    winning_bid_contract_rate = Column(Integer, nullable=True)
    number_of_bids_submitted = Column(Integer, default=0)
    payment_terms = Column(String)

    # Recurrence Details
    recurrence_frequency = Column(Enum("Daily", "Weekly", "Fortnightly", "Monthly"))  # How often shipments occur
    recurrence_days = Column(String) # Days (e.g., "Monday, Wednesday, Friday")
    skip_weekends = Column(Boolean, default=True)
    shipments_per_interval = Column(Integer)  # Number of shipments in each recurrence interval
    total_shipments = Column(Integer)  # Total number of shipments in the contract
    start_date = Column(Date, nullable=False)  # Start date of the contract
    # --- New Slot-Based Fields ---
    total_slots = Column(Integer, nullable=False)  # total number of slots (mirrors shipments_per_interval)
    available_slots = Column(Integer, nullable=False)  # dynamic: total_slots - assigned_slots
    each_slot_size = Column(Integer, nullable=False)
    assigned_slots = Column(Integer, default=0, nullable=False)

    end_date = Column(Date, nullable=True)  # Optional end date (if known)
    shipment_dates = Column(ARRAY(Date), nullable=True)
    payment_dates = Column(ARRAY(Date), nullable=True)
    # Status and Meta
    exchange_end_time = Column(DateTime)
    auction_status = Column(Enum("Open", "Closed", "Cancelled"), default="Open")
    is_active = Column(Boolean, default=True)  # Whether the contract is active
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, Float, Numeric, ForeignKey
from sqlalchemy.orm import relationship

class Lane_Tender_RFQ(Base):

    __tablename__ = "ftl_lane_tenders"

    # ============================================================
    # PRIMARY / TENDER HIERARCHY
    # ============================================================

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, nullable=False)
    publisher_user_id = Column(Integer, nullable=False)
    is_sub_tender = Column(Boolean, default=False, nullable=False)
    parent_tender_id = Column(Integer, ForeignKey("ftl_lane_tenders.id"), nullable=True)

    # ============================================================
    # SECTION 1 — TENDER SCOPE & ROUTING INFORMATION
    # ============================================================

    tender_title = Column(String(255), nullable=False)
    scope_description = Column(Text, nullable=False)
    business_unit = Column(String(100), nullable=False)
    cost_centre_project_code = Column(String(100), nullable=False)
    tender_length_category = Column(String(50), nullable=False)
    tender_category = Column(String(100), nullable=False)

    contract_start_date = Column(Date, nullable=False)
    contract_end_date = Column(Date, nullable=False)

    origin_address = Column(Text, nullable=False)
    complete_origin_address = Column(String)
    origin_city_province = Column(String)
    origin_country = Column(String)
    origin_region = Column(String)
    destination_address = Column(Text, nullable=False)
    complete_destination_address = Column(String)
    destination_city_province = Column(String)
    destination_country = Column(String)
    destination_region = Column(String)

    border_customs_responsibility = Column(String(50), nullable=True)

    estimated_distance_km = Column(Integer, nullable=False)
    actual_distance_km = Column(Integer, nullable=True)
    polyline = Column(String(2000), nullable=True)

    priority_level = Column(String(20), nullable=False)
    load_type = Column(String(50), nullable=False)

    customer_reference = Column(String(100), nullable=True)

    # ============================================================
    # SECTION 2 — LOAD REQUIREMENTS & CARGO
    # ============================================================

    commodity = Column(Text, nullable=False)

    average_shipment_weight_kg = Column(Integer, nullable=False)
    minimum_weight_bracket_kg = Column(Integer, nullable=False)

    packaging_type = Column(String(100), nullable=True)
    packaging_quantity = Column(String(100), nullable=True)

    temperature_control = Column(String(100), nullable=True)
    target_temperature_spec = Column(String(100), nullable=True)

    hazardous_materials = Column(Boolean, default=False, nullable=False)
    hazchem_classification = Column(String(100), nullable=True)

    under_bond = Column(Boolean, default=False, nullable=False)
    rib_requirements = Column(Boolean, default=False, nullable=False)

    minimum_git_cover_amount = Column(Numeric(15, 2), nullable=False)
    minimum_liability_cover_amount = Column(Numeric(15, 2), nullable=False)

    # ============================================================
    # SECTION 3 — SEASONALITY & VOLUME PROFILE
    # ============================================================

    volume_entry_method = Column(String(30), nullable=False)
    volume_commitment = Column(String(50), nullable=False)

    # ============================================================
    # SECTION 4 — PRICING & COMMERCIAL ENGINE
    # ============================================================

    pricing_basis = Column(String(50), nullable=False)
    incumbent_transport_rate_per_shipment = Column(Numeric(14, 2), nullable=False)
    incumbent_contract_rate = Column(Numeric(14, 2), nullable=False)
    procurement_target_rate = Column(Numeric(14, 2), nullable=False)
    procurement_target_contract_rate = Column(Numeric(14, 2), nullable=False)
    rate_direction = Column(String(50), nullable=False)

    # ============================================================
    # RATE INCLUDES
    # ============================================================

    rate_includes_fuel = Column(Boolean, default=False, nullable=False)
    rate_includes_driver = Column(Boolean, default=False, nullable=False)
    rate_includes_maintenance = Column(Boolean, default=False, nullable=False)
    rate_includes_insurance = Column(Boolean, default=False, nullable=False)
    rate_includes_tolls = Column(Boolean, default=False, nullable=False)
    rate_includes_border_charges = Column(Boolean, default=False, nullable=False)
    rate_includes_empty_return = Column(Boolean, default=False, nullable=False)
    rate_includes_waiting_time = Column(Boolean, default=False, nullable=False)
    rate_includes_loading_assistance = Column(Boolean, default=False, nullable=False)
    rate_includes_offloading_assistance = Column(Boolean, default=False, nullable=False)

    # ============================================================
    # ACCESSORIAL / COMMERCIAL TREATMENT
    # ============================================================

    fuel_treatment_type = Column(String(100), nullable=False)

    base_diesel_price = Column(Numeric(10, 4), nullable=True)
    fuel_review_period = Column(String(50), nullable=True)
    fuel_component_percentage = Column(Numeric(5, 2), nullable=True)

    vat_treatment = Column(String(30), nullable=False)
    rate_validity = Column(String(50), nullable=False)

    # ============================================================
    # PAYMENT & INVOICING
    # ============================================================

    payment_terms = Column(String(50), nullable=True)
    custom_payment_terms = Column(Text, nullable=True)

    invoice_submission_frequency = Column(String(50), nullable=True)
    invoice_submission_deadline = Column(String(100), nullable=True)

    # ============================================================
    # TENDER PROCESS
    # ============================================================

    tender_closing_date = Column(DateTime, nullable=False)
    questions_deadline = Column(DateTime, nullable=True)

    # ============================================================
    # OPERATIONAL REQUIREMENTS
    # ============================================================

    vehicle_tracking_required = Column(Boolean, default=False, nullable=False)
    all_time_hour_control_room = Column(Boolean, default=False, nullable=False)
    driver_mobile_phone = Column(Boolean, default=False, nullable=False)
    clean_compliant_equipment = Column(Boolean, default=False, nullable=False)
    pallet_management = Column(Boolean, default=False, nullable=False)
    pod_submission_local = Column(String, nullable=False)
    pod_submission_long_haul = Column(String, nullable=False)
    pod_submission_cross_border = Column(String, nullable=False)

    subcontracting_policy = Column(String(50), nullable=True)

    # ============================================================
    # DOCUMENTATION & RISK
    # ============================================================

    delivery_documentation_sla = Column(String(100), nullable=True)

    claims_risk_policy = Column(String(100), nullable=True)
    claims_risk_requirements = Column(Text, nullable=True)

    # ============================================================
    # INSURANCE REQUIREMENTS
    # ============================================================

    git_all_risk_required = Column(Boolean, default=False, nullable=False)
    git_first_loss_required = Column(Boolean, default=False, nullable=False)
    git_driver_fidelity_required = Column(Boolean, default=False, nullable=False)

    # ============================================================
    # EQUIPMENT COMPLIANCE
    # ============================================================

    tarpaulin_compliance_required = Column(Boolean, default=False, nullable=False)
    corner_plates_required = Column(Boolean, default=False, nullable=False)
    chock_blocks_required = Column(Boolean, default=False, nullable=False)
    ratchets_belts_required = Column(Boolean, default=False, nullable=False)

    other_equipment_requirements = Column(Text, nullable=True)

    # ============================================================
    # BID EVALUATION
    # ============================================================

    evaluation_price_enabled = Column(Boolean, default=True, nullable=False)
    evaluation_capacity_enabled = Column(Boolean, default=True, nullable=False)
    evaluation_service_enabled = Column(Boolean, default=True, nullable=False)
    evaluation_compliance_enabled = Column(Boolean, default=True, nullable=False)
    evaluation_flexibility_enabled = Column(Boolean, default=True, nullable=False)

    # ============================================================
    # TENDER STATUS
    # ============================================================

    status = Column(Enum("Draft", "Active", "Evaluating", "Awarded", "Cancelled", default="draft"), nullable=False)
    proposed_rounds = Column(Integer, default=2, nullable=False)
    current_tender_round = Column(Integer, default=1, nullable=False),
    is_active = Column(Boolean, default=True),

    # ============================================================
    # RELATIONSHIPS
    # ============================================================

    stops = relationship(
        "Lane_Tender_RFQ_Stop",
        back_populates="tender",
        cascade="all, delete-orphan",
        order_by="Lane_Tender_RFQ_Stop.stop_sequence"
    )

    vehicle_configurations = relationship(
        "Lane_Tender_RFQ_Vehicle_Config",
        back_populates="tender",
        cascade="all, delete-orphan"
    )

    volume_profiles = relationship(
        "Lane_Tender_RFQ_Volume_Profile",
        back_populates="tender",
        cascade="all, delete-orphan",
        order_by="Lane_Tender_RFQ_Volume_Profile.period_sequence"
    )

    accessorials = relationship(
        "Lane_Tender_RFQ_Accessorial",
        back_populates="tender",
        cascade="all, delete-orphan"
    )


class Lane_Tender_RFQ_Stop(Base):

    __tablename__ = "ftl_lane_tender_stops"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("ftl_lane_tenders.id"), nullable=False, index=True)

    stop_sequence = Column(Integer, nullable=False)
    address = Column(Text, nullable=False)
    complete_address = Column(String)
    city_province = Column(String)
    country = Column(String)
    region = Column(String)

    tender = relationship(
        "Lane_Tender_RFQ",
        back_populates="stops"
    )

class Lane_Tender_RFQ_Vehicle_Config(Base):

    __tablename__ = "ftl_lane_tender_vehicle_configs"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("ftl_lane_tenders.id"), nullable=False, index=True)

    configuration_type = Column(String(30), nullable=False)

    truck_type = Column(String(150), nullable=False)
    equipment_type = Column(String(150), nullable=False)
    trailer_type = Column(String(150), nullable=True)
    trailer_length = Column(String(150), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    tender = relationship(
        "Lane_Tender_RFQ",
        back_populates="vehicle_configurations"
    )

class Lane_Tender_RFQ_Volume_Profile(Base):

    __tablename__ = "ftl_lane_tender_volume_profiles"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("ftl_lane_tenders.id"), nullable=False, index=True)

    volume_entry_method = Column(String(30), nullable=False)

    period_sequence = Column(Integer, nullable=False)
    period_label = Column(String(50), nullable=True)

    period_start_date = Column(Date, nullable=True)
    period_end_date = Column(Date, nullable=True)

    day_of_week = Column(String(20), nullable=True)

    expected_loads = Column(Integer, nullable=False)

    tender = relationship(
        "Lane_Tender_RFQ",
        back_populates="volume_profiles"
    )

class Lane_Tender_RFQ_Accessorial(Base):

    __tablename__ = "ftl_lane_tender_accessorials"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("ftl_lane_tenders.id"), nullable=False, index=True)

    charge_type = Column(String(100), nullable=False)
    treatment = Column(String(100), nullable=False)

    threshold_value = Column(Numeric(12, 2), nullable=True)
    threshold_unit = Column(String(50), nullable=True)

    notes = Column(Text, nullable=True)

    tender = relationship(
        "Lane_Tender_RFQ",
        back_populates="accessorials"
    )

