from sqlalchemy import Boolean, Column, Integer, Float, String, ForeignKey, DateTime, Enum, Date, Time
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
    status = Column(Enum("Assigned", "In-Progress", "Completed"), default="Assigned")
    total_shipment_completed = Column(Integer, default=0)

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