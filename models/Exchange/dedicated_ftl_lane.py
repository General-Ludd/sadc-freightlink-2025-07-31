from sqlalchemy import ARRAY, Boolean, Integer, String, Column, Float, Date, DateTime, Enum, func
from models.base import Base
from utils.sast_datetime import get_sast_time

class FTL_Lane_Exchange(Base):
    __tablename__ = "ftl_lane_exchanges"

    id = Column(Integer, primary_key=True, index=True)
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
    end_date = Column(Date, nullable=True)  # Optional end date (if known)
    shipment_dates = Column(ARRAY(Date), nullable=True)
    payment_dates = Column(ARRAY(Date), nullable=True)
    # Status and Meta
    auction_status = Column(Enum("Open", "Closed"), default="Open")
    is_active = Column(Boolean, default=True)  # Whether the contract is active
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())