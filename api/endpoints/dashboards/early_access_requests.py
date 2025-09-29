from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.early_access_requests import (
    EnterpriseShipperEarlyAccess, WarehouseEarlyAccess,
    CustomsBrokerEarlyAccess, FuelSupplierEarlyAccess,
    TruckServiceFacilityEarlyAccess
)
from schemas.early_access_requests import (
    EnterpriseShipperCreate, EnterpriseShipperResponse,
    WarehouseCreate, WarehouseResponse,
    CustomsBrokerCreate, CustomsBrokerResponse,
    FuelSupplierCreate, FuelSupplierResponse,
    TruckServiceFacilityCreate, TruckServiceFacilityResponse
)

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Enterprise Shippers ---
@router.post("/enterprise-shipper", response_model=EnterpriseShipperResponse, status_code=status.HTTP_201_CREATED)
def register_enterprise_shipper(data: EnterpriseShipperCreate, db: Session = Depends(get_db)):
    entry = EnterpriseShipperEarlyAccess(**data.dict(exclude_unset=True))
    if data.shipment_types:
        entry.shipment_types = ",".join(data.shipment_types)
    if data.main_shipping_lanes:
        entry.main_shipping_lanes = ",".join(data.main_shipping_lanes)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# --- Warehouse ---
@router.post("/warehouse", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def register_warehouse(data: WarehouseCreate, db: Session = Depends(get_db)):
    entry = WarehouseEarlyAccess(**data.dict(exclude_unset=True))
    if data.certifications:
        entry.certifications = ",".join(data.certifications)
    if data.services:
        entry.services = ",".join(data.services)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# --- Customs Broker ---
@router.post("/customs-broker", response_model=CustomsBrokerResponse, status_code=status.HTTP_201_CREATED)
def register_customs_broker(data: CustomsBrokerCreate, db: Session = Depends(get_db)):
    entry = CustomsBrokerEarlyAccess(**data.dict(exclude_unset=True))
    if data.regions_served:
        entry.regions_served = ",".join(data.regions_served)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# --- Fuel Supplier ---
@router.post("/fuel-supplier", response_model=FuelSupplierResponse, status_code=status.HTTP_201_CREATED)
def register_fuel_supplier(data: FuelSupplierCreate, db: Session = Depends(get_db)):
    entry = FuelSupplierEarlyAccess(**data.dict(exclude_unset=True))
    if data.fuel_types:
        entry.fuel_types = ",".join(data.fuel_types)
    if data.coverage_regions:
        entry.coverage_regions = ",".join(data.coverage_regions)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

# --- Truck Service Facility ---
@router.post("/truck-service", response_model=TruckServiceFacilityResponse, status_code=status.HTTP_201_CREATED)
def register_truck_service(data: TruckServiceFacilityCreate, db: Session = Depends(get_db)):
    entry = TruckServiceFacilityEarlyAccess(**data.dict(exclude_unset=True))
    if data.amenities:
        entry.amenities = ",".join(data.amenities)
    if data.available_services:
        entry.available_services = ",".join(data.available_services)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry