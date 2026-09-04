from sqlalchemy import Boolean, Integer, String, Column, Float, Date, DateTime, Enum, func, Numeric, Text, Time
from models.base import Base
from utils.sast_datetime import get_sast_time

class Client_Shipment_Auction(Base):
    __tablename__ = "client_shipment_auctions"

    id = Column(Integer, primary_key=True, index=True)

    shipment_reference = Column(String(100), unique=True, index=True)
    booking_reference = Column(String(100), nullable=True, index=True)
    trip_type = Column(String, nullable=False)
    load_type = Column(String, nullable=False)
    number_of_trucks_required = Column(Integer, nullable=False)
    slots_remaining = Column(Integer)
    client_id = Column(Integer, nullable=False)
    client_user_id = Column(Integer, nullable=False)
    payment_terms = Column(String, nullable=False)
    pickup_date = Column(Date)
    priority_level = Column(String, nullable=True)
    customer_reference_number = Column(String)
    shipment_weight = Column(Integer)
    commodity = Column(String)
    temperature_control = Column(String)
    target_temperature_spec = Column(String(100), nullable=True)
    hazardous_materials = Column(Boolean, default=False, nullable=False)
    hazchem_classification = Column(String, nullable=True)
    under_bond = Column(Boolean, default=False) ########### Add to DB
    rib_requirements = Column(Boolean, default=False) ####### Add to DB
    packaging_quantity = Column(Integer)
    packaging_type = Column(String)
    distance = Column(Numeric(10, 2), nullable=True)
    eta_date = Column(Date, nullable=True)
    estimated_transit_time = Column(String)
    route_preview_embed = Column(String)
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
    vat_included = Column(Boolean, nullable=False)
    book_now_rate = Column(Numeric(14, 2), nullable=False)
    procurement_target_rate = Column(Numeric(14, 2), nullable=False)
    bidding_activated = Column(Boolean, default=True)
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
    minimum_weight_bracket = Column(Integer)
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
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Client_Shipment_Auction_Stop(Base):
    __tablename__ = "client_shipment_auction_stops"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(
        Integer, nullable=False, index=True
    )  # Links to your Auction/Shipment ID
    # -------------------------------------------------------------------------
    # ROUTING & SEQUENCE (Origin = 0, Stops = 1+, Destination = Max)
    # -------------------------------------------------------------------------
    stop_sequence = Column(Integer, nullable=False)
    stop_type = Column(
        String(30), nullable=False
    )  # 'Origin', 'Intermediate', 'Destination'
    # -------------------------------------------------------------------------
    # GEOLOCATION & ADDRESS FIELDS
    # -------------------------------------------------------------------------
    address = Column(
        Text, nullable=False
    )  # Original lookup string sent by client
    complete_address = Column(String, nullable=True)  # Clean Google-verified
    city_province = Column(String, nullable=True)
    country = Column(String, nullable=True)
    region = Column(String, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    # -------------------------------------------------------------------------
    # MERGED FACILITY DATA FIELDS
    # -------------------------------------------------------------------------
    facility_name = Column(String(150), nullable=False)
    scheduling_type = Column(
        String(50), nullable=False, default="FCFS"
    )  # 'Appointment', 'FCFS', 'Window'
    # Operational Availability Window (Dumping facility operational window matching dates)
    operating_start_time = Column(Time, nullable=True)  # Operating hours start
    operating_end_time = Column(Time, nullable=True)  # Operating hours end
    # Weekday availability flags for validation engines
    open_monday = Column(Boolean, default=True)
    open_tuesday = Column(Boolean, default=True)
    open_wednesday = Column(Boolean, default=True)
    open_thursday = Column(Boolean, default=True)
    open_friday = Column(Boolean, default=True)
    open_saturday = Column(Boolean, default=False)
    open_sunday = Column(Boolean, default=False)
    # Contact Person Details
    contact_first_name = Column(String(100), nullable=True)
    contact_last_name = Column(String(100), nullable=True)
    contact_phone_number = Column(String(30), nullable=True)
    contact_email = Column(String(100), nullable=True)
    # -------------------------------------------------------------------------
    # TRACKING METRICS
    # -------------------------------------------------------------------------
    reference_number = Column(String, nullable=True)
    arrival_time = Column(DateTime, nullable=True)  # Actual arrival
    departure_time = Column(DateTime, nullable=True)  # Actual departure
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Client_Shipment_Auction_Vehicle_Requirement(Base):
    __tablename__ = "client_shipment_auction_vehicle_configs"

    id = Column(Integer, primary_key=True, index=True)
    auction_id = Column(Integer, nullable=False, index=True)

    configuration_type = Column(String(30), nullable=False)
    truck_type = Column(String(150), nullable=False)
    equipment_type = Column(String(150), nullable=False)
    trailer_type = Column(String(150), nullable=True)
    trailer_length = Column(String(150), nullable=True)

    is_required = Column(Boolean, default=True, nullable=False)

class FTL_SHIPMENT_EXCHANGE(Base):
    __tablename__ = "ftl_shipment_exchanges"

    id = Column(Integer, index=True, primary_key=True)
    consignor_id = Column(Integer, nullable=True)
    automatically_accept_lower_bid = Column(Boolean, default=True)
    allow_carrier_to_book_at_current_or_lower_offer_rate = Column(Boolean, default=True)
    exchange_type = Column(String, default="Open", nullable=False)
    type = Column(String, default="FTL")
    trip_type = Column(String, nullable=False)
    load_type = Column(String, nullable=False)
    shipper_company_id = Column(Integer)
    shipper_user_id = Column(Integer)
    required_truck_type = Column(String, nullable=True)
    equipment_type = Column(String, nullable=True)
    trailer_type = Column(String, nullable=True)
    trailer_length = Column(String, nullable=True)
    minimum_weight_bracket = Column(Integer, nullable=True)
    minimum_git_cover_amount = Column(Integer, nullable=False)
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
    pickup_date = Column(Date)
    priority_level = Column(String, nullable=True)
    pickup_facility_id = Column(Integer)
    delivery_facility_id = Column(Integer)
    customer_reference_number = Column(String)
    shipment_weight = Column(Integer)
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
    consignor_billable = Column(Integer, nullable=True)
    offer_price = Column(Integer)
    backed_offer_price = Column(Integer, nullable=False) ### Update in database
    suggested_price = Column(Integer)
    leading_bid_id = Column(Integer)
    leading_bid_amount = Column(Integer, nullable=True) ### Update in database
    winning_bid_price = Column(Integer, nullable=True)
    number_of_bids_submitted = Column(Integer, default=0)
    route_preview_embed = Column(String)
    auction_status = Column(Enum("Open", "Closed", "Cancelled"), default="Open")
    end_time = Column(DateTime)
    trip_savings = Column(Integer)
    exchange_savings = Column(Integer)
    payment_terms = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())