from sqlalchemy import Boolean, Column, Integer, Float, String, ForeignKey, DateTime, Enum, Date, Time, Text, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from models.base import Base
from datetime import datetime

class Assigned_Ftl_Lanes(Base):
    __tablename__ = "assigned_ftl_lanes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lane_id = Column(Integer, nullable=False)
    type = Column(String, default="FTL")
    trip_type = Column(String)
    load_type =  Column(String)
    carrier_id = Column(Integer, nullable=False)
    carrier_name = Column(String, nullable=False)

    # Contract Details
    contract_rate = Column(Integer, nullable=False)
    rate_per_shipment = Column(Integer)
    payment_terms = Column(String, nullable=False)
    invoice_id = Column(Integer, nullable=False)
    invoice_due_date = Column(Date, nullable=True)
    invoice_status = Column(String, nullable=False)
    payment_dates = Column(ARRAY(Date), nullable=True)
    complete_origin_address = Column(String)
    complete_destination_address = Column(String)
    distance = Column(Integer, nullable=False)
    rate_per_km = Column(Integer, nullable=False)
    rate_per_ton = Column(Integer, nullable=False)
    minimum_git_cover_amount = Column(Integer, default=0, nullable=True)
    minimum_liability_cover_amount = Column(Integer, default=0, nullable=True)
    status = Column(Enum("Assigned", "In-Progress", "Completed", "Cancelled"), default="Assigned")
    total_shipment_completed = Column(Integer, default=0)

    # Slot Details
    slots_assigned = Column(Integer, nullable=False, default=0)

    # Recurrence Details
    recurrence_frequency = Column(Enum("Daily", "Weekly", "Forth Nightly", "Monthly"))  # How often shipments occur
    recurrence_days = Column(String) # Days (e.g., "Monday, Wednesday, Friday")
    skip_weekends = Column(Boolean, default=True)
    shipments_per_interval = Column(Integer)  # Number of shipments in each recurrence interval
    total_shipments = Column(Integer)  # Total number of shipments in the contract
    start_date = Column(Date, nullable=False)  # Start date of the contract
    end_date = Column(Date, nullable=True)  # Optional end date (if known)
    shipment_dates = Column(ARRAY(Date), nullable=True)

    # Shipment Details
    required_truck_type = Column(String, nullable=True)
    equipment_type = Column(String, nullable=True)
    trailer_type = Column(String, nullable=True)
    trailer_length = Column(String, nullable=True)
    minimum_weight_bracket = Column(Integer, nullable=False)
    origin_address = Column(String)
    origin_city_province = Column(String)
    origin_country = Column(String)
    origin_region = Column(String)
    pickup_appointment = Column(String)
    destination_address = Column(String)
    destination_city_province = Column(String)
    destination_country = Column(String)
    destinationn_region = Column(String)
    delivery_appointment = Column(String)
    route_preview_embed = Column(String, nullable=True)
    priority_level = Column(String, nullable=True)
    customer_reference_number = Column(String)
    average_shipment_weight = Column(Integer)
    commodity = Column(String)
    temperature_control = Column(String)
    hazardous_materials = Column(Boolean, nullable=False)
    packaging_quantity = Column(String)
    packaging_type = Column(String)
    pickup_number = Column(String)
    pickup_notes = Column(String)
    delivery_number = Column(String)
    delivery_notes = Column(String)
    estimated_transit_time = Column(String)

    pickup_facility_id = Column(Integer)
    delivery_facility_id = Column(Integer)
    text_pickup_date = Column(String, nullable=True)
    text_eta_date = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

class Carrier_Lane(Base):
    __tablename__ = "carrier_lanes"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, nullable=True)
    client_lane_id = Column(Integer, nullable=False)
    carrier_id = Column(Integer, nullable=False)
    bidder_user_id = Column(Integer, nullable=False)
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
    rate_per_shipment = Column(Numeric(14, 2), nullable=True)
    contract_rate = Column(Numeric(14, 2), nullable=True)
    slots_per_interval = Column(Integer, nullable=False)
    total_slots = Column(Integer, nullable=False)
    vat_treatment = Column(String(30), nullable=False)
    rate_validity = Column(String(50), nullable=False)

    # ============================================================
    # RATE INCLUSION GUIDELINES
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