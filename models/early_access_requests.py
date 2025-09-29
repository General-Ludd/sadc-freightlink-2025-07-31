from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from models.base import Base

# Base model for shared fields
class EarlyAccessBaseMixin:
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    registration_number = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)
    country = Column(String, nullable=False)
    city = Column(String, nullable=False)
    website = Column(String, nullable=True)

    contact_name = Column(String, nullable=False)
    contact_role = Column(String, nullable=False)
    contact_email = Column(String, nullable=False)
    contact_phone = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

# --- Enterprise Shipper ---
class EnterpriseShipperEarlyAccess(Base, EarlyAccessBaseMixin):
    __tablename__ = "early_access_enterprise_shippers"
    industry = Column(String, nullable=False)
    average_monthly_loads = Column(Integer, nullable=True)
    shipment_types = Column(Text, nullable=True)  # Comma-separated
    main_shipping_lanes = Column(Text, nullable=True)

# --- Warehouse & Storage ---
class WarehouseEarlyAccess(Base, EarlyAccessBaseMixin):
    __tablename__ = "early_access_warehouses"
    facility_type = Column(String, nullable=False)
    capacity_pallets = Column(Integer, nullable=True)
    certifications = Column(Text, nullable=True)  # Comma-separated
    services = Column(Text, nullable=True)  # Comma-separated

# --- Customs Broker ---
class CustomsBrokerEarlyAccess(Base, EarlyAccessBaseMixin):
    __tablename__ = "early_access_customs_brokers"
    license_number = Column(String, nullable=True)
    regions_served = Column(Text, nullable=True)  # Comma-separated
    specialization = Column(String, nullable=True)

# --- Fuel Supplier ---
class FuelSupplierEarlyAccess(Base, EarlyAccessBaseMixin):
    __tablename__ = "early_access_fuel_suppliers"
    fuel_types = Column(Text, nullable=True)  # Comma-separated
    supply_capacity = Column(String, nullable=True)
    coverage_regions = Column(Text, nullable=True)

# --- Truck Stop / Service Facility ---
class TruckServiceFacilityEarlyAccess(Base, EarlyAccessBaseMixin):
    __tablename__ = "early_access_truck_services"
    location_coordinates = Column(String, nullable=True)
    parking_capacity = Column(Integer, nullable=True)
    amenities = Column(Text, nullable=True)  # Comma-separated
    available_services = Column(Text, nullable=True)