from sqlalchemy import Integer, String, Column, Boolean, Date, DateTime, Enum, func, Text, Numeric
from sqlalchemy.dialects.postgresql import ARRAY
from models.base import Base
from utils.sast_datetime import get_sast_time

class Client_Lane(Base):
    __tablename__ = "client_lanes"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, nullable=True)
    client_id = Column(Integer, nullable=False)
    publisher_user_id = Column(Integer, nullable=False)
    lane_title = Column(String(255), nullable=False)
    lane_length_category = Column(String(50), nullable=False)
    lane_category = Column(String(100), nullable=False)
    scope_description = Column(Text, nullable=False)
    business_unit = Column(String(100), nullable=False)
    cost_centre_project_code = Column(String(100), nullable=False)
    parent_lane_id = Column(Integer, nullable=True)
    lane_reference = Column(String(100), unique=True, index=True)
    contract_status = Column(Enum("Draft", "Awarded", "Active", "Suspended", "Expired", "Cancelled", "Completed", name="lane_contract_status"), default="Draft", nullable=False)
    contract_start_date = Column(Date, nullable=False)  # Start date of the contract
    contract_end_date = Column(Date, nullable=True)  # Optional end date (if known)
    actual_distance_km = Column(Integer, nullable=True)
    polyline = Column(String(2000), nullable=True)
    border_customs_responsibility = Column(String(50), nullable=True) ##ADD
    priority_level = Column(String(20), nullable=True) ##ADD
    load_type = Column(String(50), nullable=True) ##ADD
    customer_reference = Column(String(100), nullable=True) ##ADD


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
    # ============================================================
    # PROCUREMENT / COMMERCIAL BASELINE
    # ============================================================

    pricing_basis = Column(String(50), nullable=False)
    incumbent_transport_rate_per_shipment = Column(Numeric(14, 2), nullable=True)
    incumbent_contract_rate = Column(Numeric(14, 2), nullable=True)
    procurement_target_rate = Column(Numeric(14, 2), nullable=True)
    procurement_target_contract_rate = Column(Numeric(14, 2), nullable=True)
    awarded_rate_per_shipment = Column(Numeric(14, 2), nullable=True)
    awarded_contract_rate = Column(Numeric(14, 2), nullable=True)
    awarded_rate_per_shipment_savings = Column(Numeric(14, 2), nullable=True)
    awarded_savings_contract_value = Column(Numeric(16, 2), nullable=True)
    vat_treatment = Column(String(30), nullable=False)
    rate_validity = Column(String(50), nullable=False)

    # ============================================================
    # RATE INCLUSION GUIDELINES
    # ============================================================

    fuel_treatment_type = Column(String(100), nullable=True)
    base_diesel_price = Column(Numeric(10, 4), nullable=True)
    fuel_review_period = Column(String(50), nullable=True)
    fuel_component_percentage = Column(Numeric(5, 2), nullable=True)

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
    # PAYMENT & INVOICING
    # ============================================================

    payment_terms = Column(String, nullable=False)
    invoice_submission_frequency = Column(String(50), nullable=True)
    invoice_submission_deadline = Column(String(100), nullable=True)

    # ============================================================
    # ROUTING / COMMERCIAL OPERATIONS SCOPE
    # ============================================================
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

    # ============================================================
    # INSURANCE REQUIREMENTS
    # ============================================================

    minimum_git_cover_amount = Column(Numeric(15, 2), nullable=False)
    minimum_liability_cover_amount = Column(Numeric(15, 2), nullable=False)
    git_all_risk_required = Column(Boolean, default=False, nullable=False)
    git_first_loss_required = Column(Boolean, default=False, nullable=False)
    git_driver_fidelity_required = Column(Boolean, default=False, nullable=False)

    # ============================================================
    # DOCUMENTATION & RISK
    # ============================================================

    delivery_documentation_sla = Column(String(100), nullable=True)
    claims_risk_policy = Column(String(100), nullable=True)
    claims_risk_requirements = Column(Text, nullable=True)

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
    # EQUIPMENT COMPLIANCE
    # ============================================================

    tarpaulin_compliance_required = Column(Boolean, default=False, nullable=False)
    corner_plates_required = Column(Boolean, default=False, nullable=False)
    chock_blocks_required = Column(Boolean, default=False, nullable=False)
    ratchets_belts_required = Column(Boolean, default=False, nullable=False)
    other_equipment_requirements = Column(Text, nullable=True)

class Lane_Stop(Base):

    __tablename__ = "lane_stops"

    id = Column(Integer, primary_key=True, index=True)
    lane_id = Column(Integer, nullable=False, index=True)

    stop_sequence = Column(Integer, nullable=False)
    address = Column(Text, nullable=False)
    complete_address = Column(String)
    city_province = Column(String)
    country = Column(String)
    region = Column(String)

class Lane_Vehicle_Config(Base):

    __tablename__ = "lane_vehicle_configs"

    id = Column(Integer, primary_key=True, index=True)
    lane_id = Column(Integer, nullable=False, index=True)

    configuration_type = Column(String(30), nullable=False)

    truck_type = Column(String(150), nullable=False)
    equipment_type = Column(String(150), nullable=False)
    trailer_type = Column(String(150), nullable=True)
    trailer_length = Column(String(150), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

class Lane_Volume_Profile(Base):

    __tablename__ = "lane_volume_profiles"

    id = Column(Integer, primary_key=True, index=True)
    lane_id = Column(Integer, nullable=False, index=True)

    volume_entry_method = Column(String(30), nullable=False)

    period_sequence = Column(Integer, nullable=False)
    period_label = Column(String(50), nullable=True)

    period_start_date = Column(Date, nullable=True)
    period_end_date = Column(Date, nullable=True)

    day_of_week = Column(String(20), nullable=True)

    expected_loads = Column(Integer, nullable=False)

class Lane_Accessorial(Base):

    __tablename__ = "lane_accessorials"

    id = Column(Integer, primary_key=True, index=True)
    lane_id = Column(Integer, nullable=False, index=True)

    charge_type = Column(String(100), nullable=False)
    treatment = Column(String(100), nullable=False)

    threshold_value = Column(Numeric(12, 2), nullable=True)
    threshold_unit = Column(String(50), nullable=True)

    notes = Column(Text, nullable=True)


################################################################################################################
class Lane_Assignment_Summary(Base):
    __tablename__ = "lane_assignment_summary"

    id = Column(Integer, primary_key=True, index=True)
    lane_id = Column(Integer, nullable=False, index=True)
    lane_type = Column(String, nullable=False, index=True)
    total_slots = Column(Integer, nullable=False)
    total_assigned_slots = Column(Integer, nullable=False, default=0)
    unique_carriers_assigned = Column(Integer, nullable=False, default=0)
    status = Column(Enum("Booked", "Partially Assigned", "Fully Assigned", "Closed"), default="Booked")
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class FTL_Lane_Dispute(Base):
    __tablename__ = "ftl_lane_disputes"

    id = Column(Integer, index=True, primary_key=True)
    filed_by_shipper = Column(Boolean)
    lane_id = Column(Integer, nullable=False)
    lane_type = Column(String, default="FTL", nullable=False)
    shipper_company_id = Column(Integer, nullable=False)
    carrier_company_id = Column(Integer, nullable=False)
    dispute_reason = Column(String, nullable=False)
    additional_details = Column(String, nullable=True)
    lane_status = Column(String, nullable=False)#####Update in database
    status = Column(Enum("Open", "Closed"), default="Open")
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)