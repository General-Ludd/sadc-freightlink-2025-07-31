from sqlalchemy import Boolean, Column, Integer, Float, Numeric, String, ForeignKey, DateTime, Enum, Date, Time, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY
from models.base import Base
from datetime import datetime

class Ftl_Load_Board(Base):
    __tablename__ = "ftl_load_board"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, nullable=False)
    type = Column(String)
    trip_type = Column(String, nullable=False)
    load_type = Column(String, nullable=False)
    minimum_weight_bracket = Column(Integer, nullable=False)
    minimum_git_cover_amount = Column(Integer, default=0, nullable=True)
    minimum_liability_cover_amount = Column(Integer, default=0, nullable=True)
    shipment_rate = Column(Integer, nullable=False)
    distance = Column(Integer, nullable=False)
    rate_per_km = Column(Integer, nullable=False)
    rate_per_ton = Column(Integer, nullable=False)
    payment_terms = Column(String, nullable=False)
    payment_date = Column(String)
    status = Column(Enum("Available", "Assigned", "Cancelled", "Failed"), default="Available")
    required_truck_type = Column(String, nullable=True)
    equipment_type = Column(String, nullable=True)
    trailer_type = Column(String, nullable=True)
    trailer_length = Column(String, nullable=True)
    origin_address = Column(String)
    complete_origin_address = Column(String)
    origin_city_province = Column(String)
    origin_country = Column(String)
    origin_region = Column(String)
    stop_1_address = Column(String, nullable=True)
    stop_2_address = Column(String, nullable=True)
    stop_3_address = Column(String, nullable=True)
    stop_4_address = Column(String, nullable=True)
    stop_5_address = Column(String, nullable=True)
    destination_address = Column(String)
    complete_destination_address = Column(String)
    destination_city_province = Column(String)
    destination_country = Column(String)
    destination_region = Column(String)
    route_preview_embed = Column(String)
    pickup_date = Column(Date)
    priority_level = Column(String, nullable=True)
    customer_reference_number = Column(String)
    shipment_weight = Column(Integer)
    commodity = Column(String)
    temperature_control = Column(String)
    hazardous_metarials = Column(String, nullable=False)
    under_bond = Column(String, nullable=False) ########### Add to DB
    rib_requirements = Column(Boolean, default=False) ####### Add to DB
    packaging_quantity = Column(String)
    packaging_type = Column(String)
    pickup_number = Column(String)
    pickup_notes = Column(String)
    delivery_number = Column(String)
    delivery_notes = Column(String)
    estimated_transit_time = Column(String)
    eta_date = Column(Date)
    eta_window = Column(String)
    pickup_appointment = Column(String)
    pickup_facility_name = Column(String, nullable=True)
    pickup_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    pickup_start_time = Column(Time, nullable=False)
    pickup_end_time = Column(Time, nullable=False)
    pickup_facility_notes = Column(String, nullable=True)
    pickup_first_name = Column(String, nullable=False)
    pickup_last_name = Column(String, nullable=False)
    pickup_phone_number = Column(String, nullable=False)
    pickup_email = Column(String, nullable=False)
    delivery_appointment = Column(String)
    stop_1_facility_id = Column(Integer, nullable=True)
    stop_2_facility_id = Column(Integer, nullable=True)
    stop_3_facility_id = Column(Integer, nullable=True)
    stop_4_facility_id = Column(Integer, nullable=True)
    stop_5_facility_id = Column(Integer, nullable=True)
    delivery_facility_name = Column(String, nullable=True)
    delivery_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    delivery_start_time = Column(Time, nullable=False)
    delivery_end_time = Column(Time, nullable=False)
    delivery_facility_notes = Column(String, nullable=True)
    delivery_first_name = Column(String, nullable=False)
    delivery_last_name = Column(String, nullable=False)
    delivery_phone_number = Column(String, nullable=False)
    delivery_email = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

class Power_Load_Board(Base):
    __tablename__ = "power_load_board"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, nullable=False)
    type = Column(String) #########update in database
    trip_type = Column(String) #########update in database
    load_type = Column(String) #########update in database
    minimum_weight_bracket = Column(Integer, nullable=False)
    minimum_git_cover_amount = Column(Integer, default=0, nullable=True)
    minimum_liability_cover_amount = Column(Integer, default=0, nullable=True)
    shipment_rate = Column(Integer, nullable=False)
    distance = Column(Integer, nullable=False)
    rate_per_km = Column(Integer, nullable=False)
    rate_per_ton = Column(Integer, nullable=False)
    payment_terms = Column(String, nullable=False)
    payment_date = Column(Date)
    status = Column(Enum("Available", "Assigned"), default="Available")
    required_truck_type = Column(String, nullable=True)
    axle_configuration = Column(String, nullable=False)
    trailer_make = Column(String, nullable=True)
    trailer_model = Column(String, nullable=True)
    trailer_year = Column(Integer, nullable=True)
    trailer_color = Column(String, nullable=True)
    trailer_equipment_type = Column(String, nullable=True)
    trailer_type = Column(String, nullable=True)
    trailer_length = Column(String, nullable=True)
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
    route_preview_embed = Column(String)
    pickup_date = Column(Date)
    priority_level = Column(String, nullable=True)
    customer_reference_number = Column(String)
    shipment_weight = Column(Integer)
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
    eta_date = Column(Date)
    eta_window = Column(String)
    pickup_appointment = Column(String)#########update in database
    pickup_facility_name = Column(String, nullable=True)
    pickup_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    pickup_start_time = Column(Time, nullable=False)
    pickup_end_time = Column(Time, nullable=False)
    pickup_facility_notes = Column(String, nullable=True)
    pickup_first_name = Column(String, nullable=False)
    pickup_last_name = Column(String, nullable=False)
    pickup_phone_number = Column(String, nullable=False)
    pickup_email = Column(String, nullable=False)
    delivery_appointment = Column(String)#########update in database
    delivery_facility_name = Column(String, nullable=True)
    delivery_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    delivery_start_time = Column(Time, nullable=False)
    delivery_end_time = Column(Time, nullable=False)
    delivery_facility_notes = Column(String, nullable=True)
    delivery_first_name = Column(String, nullable=False)
    delivery_last_name = Column(String, nullable=False)
    delivery_phone_number = Column(String, nullable=False)
    delivery_email = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

class Dedicated_lanes_LoadBoard(Base):
    __tablename__ = "dedicated_lanes_loadboard"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, nullable=False)
    type = Column(String)
    trip_type = Column(String)
    load_type = Column(String)
    minimum_weight_bracket = Column(Integer, nullable=False)
    minimum_git_cover_amount = Column(Integer, default=0, nullable=True)
    minimum_liability_cover_amount = Column(Integer, default=0, nullable=True)
    total_slots = Column(Integer, nullable=False, default=0)
    per_slot_size = Column(Integer, nullable=False, default=1) 
    available_slots = Column(Integer, nullable=False, default=0)
    assigned_slots = Column(Integer, nullable=False, default=0)
    contract_rate = Column(Integer, nullable=False)
    distance = Column(Integer, nullable=False)
    rate_per_km = Column(Integer, nullable=False)
    rate_per_ton = Column(Integer, nullable=False)
    payment_terms = Column(String, nullable=False)
    recurrence_frequency = Column(String)  # How often shipments occur
    recurrence_days = Column(ARRAY(String)) # Days (e.g., "Monday, Wednesday, Friday")
    skip_weekends = Column(Boolean)
    shipments_per_interval = Column(Integer) # Number of shipments in each recurrence interval
    total_shipments = Column(Integer)  # Total number of shipments in the contract
    rate_per_shipment = Column(Integer)
    start_date = Column(Date, nullable=False)  # Start date of the contract
    end_date = Column(Date, nullable=True)  # Optional end date (if known)
    shipment_dates = Column(ARRAY(Date))
    payment_dates = Column(ARRAY(Date))
    status = Column(Enum("Available", "Assigned"), default="Available")
    required_truck_type = Column(String, nullable=False)
    equipment_type = Column(String, nullable=False)
    trailer_type = Column(String, nullable=True)
    trailer_length = Column(String, nullable=True)
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
    route_preview_embed = Column(String)
    customer_reference_number = Column(String)
    average_shipment_weight = Column(Integer)
    commodity = Column(String)
    temperature_control = Column(String)
    hazardous_materials = Column(Boolean, nullable=False)
    under_bond = Column(String, nullable=False) ########### Add to DB
    rib_requirements = Column(Boolean, default=False) ####### Add to DB
    packaging_quantity = Column(String)
    packaging_type = Column(String)
    pickup_number = Column(String)
    pickup_notes = Column(String)
    delivery_number = Column(String)
    delivery_notes = Column(String)
    estimated_transit_time = Column(String)
    pickup_facility_name = Column(String, nullable=True)
    pickup_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    pickup_start_time = Column(Time, nullable=False)
    pickup_end_time = Column(Time, nullable=False)
    pickup_facility_notes = Column(String, nullable=True)
    pickup_first_name = Column(String, nullable=False)
    pickup_last_name = Column(String, nullable=False)
    pickup_phone_number = Column(String, nullable=False)
    pickup_email = Column(String, nullable=False)
    delivery_facility_name = Column(String, nullable=True)
    delivery_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    delivery_start_time = Column(Time, nullable=False)
    delivery_end_time = Column(Time, nullable=False)
    delivery_facility_notes = Column(String, nullable=True)
    delivery_first_name = Column(String, nullable=False)
    delivery_last_name = Column(String, nullable=False)
    delivery_phone_number = Column(String, nullable=False)
    delivery_email = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

class Dedicated_Power_lanes_LoadBoard(Base):
    __tablename__ = "dedicated_power_lanes_loadboard"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, nullable=False)
    minimum_weight_bracket = Column(Integer, nullable=False)
    contract_price = Column(Integer, nullable=False)
    minimum_git_cover = Column(Integer, nullable=False)
    distance = Column(Integer, nullable=False)
    rate_per_km = Column(Integer, nullable=False)
    rate_per_ton = Column(Integer, nullable=False)
    payment_date = Column(String, nullable=False)
    recurrence_frequency = Column(String)  # How often shipments occur
    recurrence_days = Column(ARRAY(String)) # Days (e.g., "Monday, Wednesday, Friday")
    skip_weekends = Column(Boolean)
    shipments_per_interval = Column(Integer) # Number of shipments in each recurrence interval
    total_shipments = Column(Integer)  # Total number of shipments in the contract
    price_per_shipment = Column(Integer)
    start_date = Column(Date, nullable=False)  # Start date of the contract
    end_date = Column(Date, nullable=True)  # Optional end date (if known)
    shipment_dates = Column(ARRAY(Date))
    status = Column(Enum("Available", "Assigned"), default="Available")
    required_truck_type = Column(String, nullable=False)
    equipment_type = Column(String, nullable=False)
    trailer_type = Column(String, nullable=True)
    trailer_length = Column(String, nullable=True)
    origin_address = Column(String)
    complete_origin_address = Column(String)
    origin_city_province = Column(String)
    destination_address = Column(String)
    complete_destination_address = Column(String)
    destination_city_province = Column(String)
    route_preview_embed = Column(String)
    customer_reference_number = Column(String)
    shipment_weight = Column(Integer)
    commodity = Column(String)
    packaging_quantity = Column(String)
    packaging_type = Column(String)
    pickup_number = Column(Integer)
    pickup_notes = Column(String)
    delivery_number = Column(Integer)
    delivery_notes = Column(String)
    estimated_transit_time = Column(String)
    pickup_facility_name = Column(String, nullable=True)
    pickup_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    pickup_start_time = Column(Time, nullable=False)
    pickup_end_time = Column(Time, nullable=False)
    pickup_facility_notes = Column(String, nullable=True)
    pickup_first_name = Column(String, nullable=False)
    pickup_last_name = Column(String, nullable=False)
    pickup_phone_number = Column(String, nullable=False)
    pickup_email = Column(String, nullable=False)
    delivery_facility_name = Column(String, nullable=True)
    delivery_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    delivery_start_time = Column(Time, nullable=False)
    delivery_end_time = Column(Time, nullable=False)
    delivery_facility_notes = Column(String, nullable=True)
    delivery_first_name = Column(String, nullable=False)
    delivery_last_name = Column(String, nullable=False)
    delivery_phone_number = Column(String, nullable=False)
    delivery_email = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

class ExchangeLoadBoard(Base):
    __tablename__ = "exchange_loadboard"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, nullable=False)
    minimum_weight_bracket = Column(Integer, nullable=False)
    suggested_bid = Column(Integer, nullable=False)
    opening_bid = Column(Integer, nullable=False)
    distance = Column(Integer, nullable=False)
    rate_per_km = Column(Integer, nullable=False)
    rate_per_ton = Column(Integer, nullable=False)
    payout_method = Column(Integer, nullable=False)
    status = Column(Enum("Assigned", "bidding_open"), default="bidding open")
    required_truck_type = Column(String, nullable=True)
    equipment_type = Column(String, nullable=True)
    trailer_type = Column(String, nullable=True)
    trailer_length = Column(String, nullable=True)
    origin_address = Column(String)
    destination_address = Column(String)
    pickup_date = Column(Date)
    priority_level = Column(String, nullable=True)
    customer_reference_number = Column(String)
    shipment_weight = Column(Integer)
    commodity = Column(String)
    packaging_quantity = Column(String)
    packaging_type = Column(String)
    pickup_number = Column(Integer)
    pickup_notes = Column(String)
    delivery_number = Column(Integer)
    delivery_notes = Column(String)
    estimated_transit_time = Column(String)
    exchange_opening = Column(DateTime, nullable=False)
    exchange_closing = Column(DateTime, nullable=False)
    is_bidding_open = Column(Boolean, default=False)
    suggested_price = Column(Integer, nullable=False)
    starting_bid = Column(Integer, nullable=False)
    pickup_facility_name = Column(String, nullable=True)
    pickup_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    pickup_start_time = Column(Time, nullable=False)
    pickup_end_time = Column(Time, nullable=False)
    pickup_facility_notes = Column(String, nullable=True)
    pickup_first_name = Column(String, nullable=False)
    pickup_last_name = Column(String, nullable=False)
    pickup_phone_number = Column(String, nullable=False)
    pickup_email = Column(String, nullable=False)
    delivery_facility_name = Column(String, nullable=True)
    delivery_scheduling_type = Column(String, nullable=False)  # e.g., "First come, First served"
    delivery_start_time = Column(Time, nullable=False)
    delivery_end_time = Column(Time, nullable=False)
    delivery_facility_notes = Column(String, nullable=True)
    delivery_first_name = Column(String, nullable=False)
    delivery_last_name = Column(String, nullable=False)
    delivery_phone_number = Column(String, nullable=False)
    delivery_email = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


class Lane_Tender_Loadboard(Base):

    __tablename__ = "ftl_lane_tender_loadboard"

    # ============================================================
    # PRIMARY / RELATIONSHIP
    # ============================================================

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("ftl_lane_tenders.id"), nullable=False, unique=True, index=True)

    # ============================================================
    # LOAD BOARD STATUS
    # ============================================================

    status = Column(String(50), default="draft", nullable=False, index=True)
    published_at = Column(DateTime, nullable=True)
    bid_opening_date = Column(DateTime, nullable=True)
    bid_closing_date = Column(DateTime, nullable=False)
    questions_deadline = Column(DateTime, nullable=True)

    # ============================================================
    # TENDER IDENTITY
    # ============================================================

    tender_title = Column(String(255), nullable=False)
    tender_category = Column(String(100), nullable=False)
    tender_length_category = Column(String(50), nullable=False)
    scope_description = Column(String, nullable=False)

    # ============================================================
    # CONTRACT PERIOD
    # ============================================================

    contract_start_date = Column(Date, nullable=False)
    contract_end_date = Column(Date, nullable=False)

    # ============================================================
    # ROUTING
    # ============================================================

    origin_address = Column(String, nullable=False)
    origin_city_province = Column(String(150), nullable=True)
    origin_country = Column(String(100), nullable=True)
    origin_region = Column(String(100), nullable=True)

    destination_address = Column(String, nullable=False)
    destination_city_province = Column(String(150), nullable=True)
    destination_country = Column(String(100), nullable=True)
    destination_region = Column(String(100), nullable=True)

    estimated_distance_km = Column(Integer, nullable=False)
    actual_distance_km = Column(Integer, nullable=True)
    polyline = Column(String(2000), nullable=True)

    border_customs_responsibility = Column(String(50), nullable=True)

    # ============================================================
    # CARGO
    # ============================================================

    commodity = Column(String, nullable=False)
    load_type = Column(String(50), nullable=False)

    average_shipment_weight_kg = Column(Integer, nullable=False)
    minimum_weight_bracket_kg = Column(Integer, nullable=False)

    packaging_type = Column(String(100), nullable=True)
    packaging_quantity = Column(String(100), nullable=True)

    temperature_control = Column(String(100), nullable=True)
    target_temperature_spec = Column(String(100), nullable=True)

    hazardous_materials = Column(Boolean, default=False, nullable=False)
    hazchem_classification = Column(String(100), nullable=True)

    under_bond = Column(Boolean, default=False, nullable=False)

    # ============================================================
    # VOLUME
    # ============================================================

    volume_entry_method = Column(String(30), nullable=False)
    volume_commitment = Column(String(50), nullable=False)

    # ============================================================
    # PRICING
    # ============================================================

    pricing_basis = Column(String(50), nullable=False)
    rate_direction = Column(String(50), nullable=False)

    # ============================================================
    # RATE INCLUSIONS
    # ============================================================

    rate_includes_fuel = Column(Boolean, default=False, nullable=False)
    rate_includes_driver = Column(Boolean, default=False, nullable=False)
    rate_includes_maintenance = Column(Boolean, default=False, nullable=False)
    rate_includes_insurance = Column(Boolean, default=False, nullable=False)
    rate_includes_tolls = Column(Boolean, default=False, nullable=False)
    rate_includes_empty_return = Column(Boolean, default=False, nullable=False)
    rate_includes_waiting_time = Column(Boolean, default=False, nullable=False)
    rate_includes_loading_assistance = Column(Boolean, default=False, nullable=False)
    rate_includes_offloading_assistance = Column(Boolean, default=False, nullable=False)

    # ============================================================
    # FUEL
    # ============================================================

    fuel_treatment_type = Column(String(100), nullable=False)
    base_diesel_price = Column(Numeric(10, 4), nullable=True)
    fuel_review_period = Column(String(50), nullable=True)
    fuel_component_percentage = Column(Numeric(5, 2), nullable=True)

    # ============================================================
    # VAT / COMMERCIAL
    # ============================================================

    vat_included = Column(Boolean)
    rate_validity = Column(String(50), nullable=False)

    payment_terms = Column(String(50), nullable=True)
    custom_payment_terms = Column(String, nullable=True)

    invoice_submission_frequency = Column(String(50), nullable=True)
    invoice_submission_deadline = Column(String(100), nullable=True)

    # ============================================================
    # OPERATIONAL REQUIREMENTS
    # ============================================================

    vehicle_tracking_required = Column(Boolean, default=False, nullable=False)
    all_time_hour_control_room = Column(Boolean, default=False, nullable=False)
    driver_mobile_phone = Column(Boolean, default=False, nullable=False)
    clean_compliant_equipment = Column(Boolean, default=False, nullable=False)
    pallet_management = Column(Boolean, default=False, nullable=False)

    pod_submission_local = Column(String(100), nullable=True)
    pod_submission_long_haul = Column(String(100), nullable=True)
    pod_submission_cross_border = Column(String(100), nullable=True)

    subcontracting_policy = Column(String(50), nullable=True)

    # ============================================================
    # DOCUMENTATION / RISK
    # ============================================================

    delivery_documentation_sla = Column(String(100), nullable=True)
    claims_risk_policy = Column(String(100), nullable=True)
    claims_risk_requirements = Column(String, nullable=True)

    # ============================================================
    # INSURANCE
    # ============================================================

    minimum_git_cover_amount = Column(Numeric(15, 2), nullable=False)
    minimum_liability_cover_amount = Column(Numeric(15, 2), nullable=False)

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

    other_equipment_requirements = Column(String, nullable=True)

    # ============================================================
    # BID EVALUATION — PUBLIC FLAGS ONLY
    # ============================================================

    evaluation_price_enabled = Column(Boolean, default=True, nullable=False)
    evaluation_capacity_enabled = Column(Boolean, default=True, nullable=False)
    evaluation_service_enabled = Column(Boolean, default=True, nullable=False)
    evaluation_compliance_enabled = Column(Boolean, default=True, nullable=False)
    evaluation_flexibility_enabled = Column(Boolean, default=True, nullable=False)

    # ============================================================
    # LOAD BOARD DISPLAY
    # ============================================================

    is_featured = Column(Boolean, default=False, nullable=False)
    is_visible_to_carriers = Column(Boolean, default=True, nullable=False, index=True)

    # ============================================================
    # TIMESTAMPS
    # ============================================================

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

class Shipment_Auction_Loadboard(Base):
    __tablename__ = "shipment_auctions_loadboard"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, nullable=False)
    trip_type = Column(String, nullable=False)
    load_type = Column(String, nullable=False)
    payment_terms = Column(String, nullable=False)
    number_of_trucks_required = Column(Integer, nullable=False)
    slots_remaining = Column(Integer)
    pickup_date = Column(Date)
    priority_level = Column(String, nullable=True)
    shipment_weight = Column(Integer)
    commodity = Column(String)
    temperature_control = Column(String)
    target_temperature_spec = Column(String(100), nullable=True)
    hazardous_materials = Column(Boolean, default=False, nullable=False)
    hazchem_classification = Column(String)
    under_bond = Column(Boolean, default=False) ########### Add to DB
    rib_requirements = Column(Boolean, default=False) ####### Add to DB
    packaging_quantity = Column(Integer)
    packaging_type = Column(String)
    distance = Column(Numeric(10, 2), nullable=True)
    eta_date = Column(Date)
    estimated_transit_time = Column(String)
    polyline = Column(String)
    status = Column(String(50), nullable=False, default="Active")
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
    # Exchange & Bidding
    # ============================================================
    auction_closing_date = Column(DateTime, nullable=False)
    pricing_basis = Column(String(50), nullable=False)
    vat_included = Column(String(30), nullable=False)
    benchmark_rate = Column(Numeric(14, 2), nullable=False)
    book_now_rate = Column(Numeric(14, 2), nullable=False)
    benchmark_rate_service_fee = Column(Numeric(14, 2), nullable=False)
    bidding_activated = Column(Boolean)
    rate_direction = Column(String(50), nullable=False)
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
    # ============================================================
    # INSURANCE REQUIREMENTS
    # ============================================================
    minimum_git_cover_amount = Column(Integer, default=0, nullable=True)
    minimum_liability_cover_amount = Column(Integer, default=0, nullable=True)
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
    # LOAD BOARD DISPLAY
    # ============================================================

    is_featured = Column(Boolean, default=False, nullable=False)
    is_visible_to_carriers = Column(Boolean, default=True, nullable=False, index=True)

    # ============================================================
    # TIMESTAMPS
    # ============================================================

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)