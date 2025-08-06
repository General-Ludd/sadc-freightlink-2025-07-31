from sqlalchemy import Boolean, Integer, String, Column, Float, Date, DateTime, Enum, func
from models.base import Base
from utils.sast_datetime import get_sast_time

class POWER_SHIPMENT(Base):
    __tablename__ = "power_shipments"

    id = Column(Integer, index=True, primary_key=True, autoincrement=True)
    is_subshipment = Column(Boolean, default=False, nullable=False)
    dedicated_lane_id = Column(Integer, nullable=True)
    type = Column(String)
    trip_type = Column(String, nullable=False)
    load_type = Column(String, nullable=False)
    shipper_company_id = Column(Integer)
    shipper_user_id = Column(Integer)
    consignor_id = Column(Integer)
    payment_terms = Column(String, nullable=False)
    invoice_id = Column(Integer, nullable=False)
    invoice_due_date = Column(Date, nullable=False) # Update in database
    invoice_status = Column(String, nullable=False)
    minimum_git_cover_amount = Column(Integer, default=0, nullable=True)
    minimum_liability_cover_amount = Column(Integer, default=0, nullable=True)
    required_truck_type = Column(String, nullable=False)
    axle_configuration = Column(String, nullable=False)
    minimum_weight_bracket = Column(Integer, nullable=True)
    trailer_id = Column(Integer, nullable=False)
    trailer_make = Column(String, nullable=True)
    trailer_model = Column(String, nullable=True)
    trailer_year = Column(Integer, nullable=True)
    trailer_color = Column(String, nullable=True)
    trailer_license_plate = Column(String, nullable=False)
    trailer_vin = Column(String, nullable=False)
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
    pickup_date = Column(Date)
    pickup_appointment = Column(String)
    priority_level = Column(String, nullable=True)
    pickup_facility_id = Column(Integer)
    delivery_facility_id = Column(Integer)
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
    distance = Column(Integer, nullable=True)
    estimated_transit_time = Column(String)
    eta_date = Column(Date)
    eta_window = Column(String)
    quote = Column(Integer)
    route_preview_embed = Column(String)
    polyline = Column(String)
    shipment_status = Column(String)
    trip_status = Column(String)
    pod_document = Column(String, nullable=True)
    carrier_id = Column(Integer)
    carrier_name = Column(String)
    carrier_git_cover_amount = Column(Integer) # Update in database
    carrier_liability_cover_amount = Column(Integer)# Update in database
    vehicle_id = Column(Integer)
    vehicle_make = Column(String)
    vehicle_model = Column(String)
    vehicle_year = Column(Integer)
    vehicle_color = Column(String)
    vehicle_license_plate = Column(String)
    vehicle_vin = Column(String) # Update in database
    vehicle_type = Column(String) # Update in database
    vehicle_axle_configuration = Column(String)
    driver_id = Column(Integer)
    driver_first_name = Column(String) # Update in database
    driver_last_name = Column(String) # Update in database
    driver_license_number = Column(String) # Update in database
    driver_email = Column(String) # Update in database
    driver_phone_number = Column(String) # Update in database
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class POWER_Shipment_Docs(Base):
    __tablename__ = "power_shipment_docs"

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

class POWER_Shipment_Dispute(Base):
    __tablename__ = "power_shipment_disputes"

    id = Column(Integer, index=True, primary_key=True)
    filed_by_shipper = Column(Boolean)
    shipment_id = Column(Integer, nullable=False)
    shipper_company_id = Column(Integer, nullable=False)
    carrier_company_id = Column(Integer, nullable=False)
    dispute_reason = Column(String, nullable=False)
    additional_details = Column(String, nullable=True)
    status = Column(Enum("Open", "Closed"), default="Open")
    created_at = Column(DateTime(timezone=True), default=get_sast_time)
    updated_at = Column(DateTime(timezone=True), default=get_sast_time, onupdate=get_sast_time)