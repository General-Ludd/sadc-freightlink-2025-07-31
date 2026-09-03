from sqlalchemy import Boolean, Integer, String, Column, Float, Date, DateTime, Enum, func, Numeric, Text, Time
from models.base import Base
from utils.sast_datetime import get_sast_time

class Client_Shipment(Base):
    __tablename__ = "client_shipments"

    id = Column(Integer, primary_key=True, index=True)
    tracking_status = Column(String, nullable=True)
    is_subshipment = Column(Boolean, default=False, nullable=False)
    auction_id = Column(Integer, nullable=True, index=True)
    client_lane_id = Column(Integer, nullable=True, index=True)
    carrier_lane_id = Column(Integer, nullable=True, index=True)
    booking_source = Column(String(50), nullable=False, default="One-Off")
    shipment_reference = Column(String(100), unique=True, index=True)
    booking_reference = Column(String(100), nullable=True, index=True)
    trip_type = Column(String, nullable=False)
    load_type = Column(String, nullable=False)
    client_id = Column(Integer, nullable=False)
    client_user_id = Column(Integer, nullable=False)
    rate = Column(Numeric(14, 2), nullable=False)
    pricing_basis = Column(String(50), nullable=False)
    vat_included = Column(Boolean, nullable=False)
    payment_terms = Column(String, nullable=False)
    invoice_id = Column(Integer, nullable=True)
    invoice_due_date = Column(Date, nullable=True)
    invoice_status = Column(String, nullable=True)
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
    estimated_transit_time = Column(String)
    eta_date = Column(Date)
    eta_window = Column(String)
    route_preview_embed = Column(String)
    polyline = Column(String)
    status = Column(String(50), nullable=False, default="Booked")
    trip_status = Column(String(50), nullable=False, default="Schedule")
    pod_document = Column(String, nullable=True)
    carrier_id = Column(Integer)
    vehicle_id = Column(Integer)
    driver_id = Column(Integer)
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
    # OPERATIONAL REQUIREMENTS
    # ============================================================
    minimum_weight_bracket_kg = Column(Integer, nullable=False)
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

    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)


class Client_Shipment_Stop(Base):
    __tablename__ = "client_shipment_stops"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(
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

class Client_Shipment_Vehicle_Requirement(Base):
    __tablename__ = "client_shipment_vehicle_requirements"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, nullable=False, index=True)

    configuration_type = Column(String(30), nullable=False)
    truck_type = Column(String(150), nullable=False)
    equipment_type = Column(String(150), nullable=False)
    trailer_type = Column(String(150), nullable=True)
    trailer_length = Column(String(150), nullable=True)

    is_required = Column(Boolean, default=True, nullable=False)

class FTL_SHIPMENT(Base):
    __tablename__ = "ftl_shipments"

    id = Column(Integer, primary_key=True, index=True)
    is_subshipment = Column(Boolean, default=False, nullable=False)
    dedicated_lane_id = Column(Integer, nullable=True)
    type = Column(String, default="FTL")
    trip_type = Column(String, nullable=False)
    load_type = Column(String, nullable=False)
    shipper_company_id = Column(Integer)
    shipper_user_id = Column(Integer)
    consignor_id = Column(Integer)
    payment_terms = Column(String, nullable=False)
    invoice_id = Column(Integer, nullable=False)
    invoice_due_date = Column(Date, nullable=True)
    invoice_status = Column(String, nullable=False)
    minimum_git_cover_amount = Column(Integer, default=0, nullable=True)
    minimum_liability_cover_amount = Column(Integer, default=0, nullable=True)
    required_truck_type = Column(String, nullable=False)
    equipment_type = Column(String, nullable=False)
    trailer_type = Column(String, nullable=True)
    trailer_length = Column(String, nullable=True)
    minimum_weight_bracket = Column(Integer, nullable=False)
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
    pickup_date = Column(Date)
    pickup_appointment = Column(String)
    priority_level = Column(String, nullable=True)
    pickup_facility_id = Column(Integer)
    stop_1_facility_id = Column(Integer, nullable=True)
    stop_2_facility_id = Column(Integer, nullable=True)
    stop_3_facility_id = Column(Integer, nullable=True)
    stop_4_facility_id = Column(Integer, nullable=True)
    stop_5_facility_id = Column(Integer, nullable=True)
    delivery_facility_id = Column(Integer)
    customer_reference_number = Column(String)
    shipment_weight = Column(Integer)
    commodity = Column(String)
    temperature_control = Column(String)
    hazardous_materials = Column(String, nullable=False)
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
    eta_date = Column(Date)
    eta_window = Column(String)
    route_preview_embed = Column(String)
    polyline = Column(String)
    quote = Column(Integer)
    shipment_status = Column(String, nullable=True)
    trip_status = Column(String, nullable=True)
    pod_document = Column(String, nullable=True)
    carrier_id = Column(Integer)
    carrier_name = Column(String, default="SADC FREIGHTLINK Sub-contractor")
    carrier_git_cover_amount = Column(Integer, nullable=True)
    carrier_liability_cover_amount = Column(Integer, nullable=True)
    vehicle_id = Column(Integer)
    vehicle_make = Column(String)
    vehicle_model = Column(String)
    vehicle_year = Column(String)
    vehicle_color = Column(String)
    vehicle_license_plate = Column(String)
    vehicle_vin = Column(String, nullable=True)
    vehicle_type = Column(String, nullable=True)
    vehicle_equipment_type = Column(String, nullable=True)
    vehicle_trailer_type = Column(String, nullable=True)
    vehicle_trailer_length = Column(String, nullable=True)
    vehicle_tare_weight = Column(Integer, nullable=True)
    vehicle_gvm_weight = Column(Integer, nullable=True)
    vehicle_payload_capacity = Column(Integer, nullable=True)
    driver_id = Column(Integer)
    driver_first_name = Column(String)
    driver_last_name = Column(String)
    driver_license_number = Column(String)
    driver_email = Column(String)
    driver_phone_number = Column(String)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class shipment_status_Update(Base):
    __tablename__ = "shipment_status_updates"

    id = Column(Integer, index=True, primary_key=True)
    shipment_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    trip_status = Column(String, nullable=False)
    location_description = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)

class FTL_Shipment_Docs(Base):
    __tablename__ = "ftl_shipment_docs"

    id = Column(Integer, index=True, primary_key=True)
    shipment_id = Column(Integer)
    commercial_invoice = Column(String, nullable=True)
    packaging_list = Column(String, nullable=True)
    customs_declaration_form = Column(String, nullable=True)
    import_or_export_permits = Column(String, nullable=True)
    certificate_of_origin = Column(String, nullable=True)
    da5501orsad500 = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)


class FTL_Shipment_Dispute(Base):
    __tablename__ = "ftl_shipment_disputes"

    id = Column(Integer, index=True, primary_key=True)
    filed_by_shipper = Column(Boolean)
    shipment_id = Column(Integer, nullable=False)
    shipment_type = Column(String, nullable=False)
    shipper_company_id = Column(Integer, nullable=False)
    carrier_company_id = Column(Integer, nullable=False)
    dispute_reason = Column(String, nullable=False)
    additional_details = Column(String, nullable=True)
    shipment_status = Column(String, nullable=False)#####Update in database
    status = Column(Enum("Open", "Closed"), default="Open")
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)
