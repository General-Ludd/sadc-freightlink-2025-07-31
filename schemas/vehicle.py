from pydantic import BaseModel
from typing import Optional
from datetime import date
from enums import EquipmentType, TrailerLength, TrailerType, TruckType, Axle_Configuration

class Vehicle_Info(BaseModel):
    id: int

class VehicleCreate(BaseModel):
    type: TruckType
    make: str
    model: str
    year: int
    color: str
    axle_configuration: Axle_Configuration
    vin: str
    license_plate: str
    license_expiry_date: date
    tare_weight: int
    gvm_weight: int
    tracker_providers_name: str
    tracker_providers_country: str
    tracker_id: str
    tracker_login_username: str
    tracker_login_password: str
    equipment_type: Optional[str] = None
    vrc_or_leasing: str
    vehicle_license_disk: str
    vehicle_road_worthy_certificate: Optional[str] = None
    vehicle_tracking_certificate: str
    front_angle_image: str
    rear_angle_image: str
    left_angle_image: str
    right_angle_image: str

class Vehicles_Summary_Response(BaseModel):
    id: int
    status: str
    current_shipment_id: Optional [int] = None
    location_description: Optional [str] = None
    make: str
    model: str
    year: int
    color: str
    license_plate: str
    axle_configuration: str
    license_expiry_date: date
    type: str
    equipment_type: Optional [str] = None
    trailer_type: Optional [str] = None
    trailer_length: Optional [str] = None
    driver_first_name: Optional [str] = None
    driver_last_name: Optional [str] = None

class VehicleUpdate(BaseModel):
    license_plate: Optional[str] = None
    license_expiry_date: Optional[date] = None
    tracker_providers_name: Optional[str] = None
    tracker_providers_country: Optional[str] = None
    tracker_id: Optional[str] = None
    tracker_login_username: Optional[str] = None
    tracker_login_password: Optional[str] = None
    tracker_api_username: Optional[str] = None
    tracker_api_token: Optional[str] = None
    equipment_type: Optional[str] = None
    vrc_or_leasing: Optional[str] = None
    vehicle_license_disk: Optional[str] = None
    vehicle_road_worthy_certificate: Optional[str] = None
    vehicle_tracking_certificate: Optional[str] = None
    front_angle_image: Optional[str] = None
    rear_angle_image: Optional[str] = None
    left_angle_image: Optional[str] = None
    right_angle_image: Optional[str] = None
    # Add other fields as needed

class VehicleResponse(BaseModel):
    id: int
    type: str
    make: str
    model: str
    year: int
    color: str
    axle_configuration: str
    vin: str
    license_plate: str
    license_expiry_date: date
    tare_weight: int
    gvm_weight: int
    tracker_providers_name: Optional[str] = None
    tracker_providers_country: Optional[str] = None
    tracker_id: Optional[str] = None
    tracker_login_username: Optional[str] = None
    tracker_login_password: Optional[str] = None
    tracker_api_username: Optional[str] = None
    tracker_api_token: Optional[str] = None
    payload_capacity: int
    trailer_id: Optional[int] = None
    equipment_type: Optional[str] = None
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None
    primary_driver_id: Optional[int] = None
    owner_id: int
    company_name: int
    company_type: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed: Optional[int] = None
    heading: Optional[int] = None
    location_description: Optional[str] = None
    current_shipment_id: Optional[int] = None
    current_shipment_type: Optional[str] = None
    total_shipments_completed: int
    vrc_or_leasing: str
    vehicle_license_disk: str
    vehicle_road_worthy_certificate: Optional[str] = None
    vehicle_tracking_certificate: Optional[str] = None
    front_angle_image: Optional[str] = None
    rear_angle_image: Optional[str] = None
    left_angle_image: Optional[str] = None
    right_angle_image: Optional[str] = None
    is_verified: bool
    status: str #Update in Database
    service_status: str #################Update in database

    class Config:
        orm_mode = True

class CarrierShipmentVehicleInfo(BaseModel):
    id: int
    make: str
    model: str
    year: int
    license_plate: str
    color: str
    vin: str
    axle_configuration: str
    license_expiry: date
    type: str
    equipment_type: Optional[str] = None
    trailer_type: Optional[str] = None
    trailer_length: Optional[str] = None

class Vehicle_Schedule_Response(BaseModel):
    id: int
    status: str
    shipment_id: int
    shipment_type: str
    origin: str
    destination: str
    pickup_appointment: str
    eta: str
    distance: int
    rate: int
    commodity: str
    weight: int

class DriverVehicleSummaryResponse(BaseModel):
    id: str  # e.g., "VEH-001"
    verification_status: str
    service_status: str
    make: str
    model: str
    year: int
    color: str
    license_plate: str
    license_expiry_date: date
    axle_configuration: str
    equipment_type: str
    trailer_type: str
    trailer_length: str
    trailer_id: Optional[str] = None

class TrailerCreate(BaseModel):
    make: str
    model: str
    year: int
    color: str
    vin: str
    license_plate: str
    license_expiry_date: date
    tare_weight: int
    gvm_weight: int
    equipment_type: EquipmentType
    trailer_type: TrailerType
    trailer_length: TrailerLength
    vrc_leasing: str
    license_disk: str
    road_worthy_certificate: Optional[str] = None
    front_angle_image: str
    rear_angle_image: str
    left_angle_image: str
    right_angle_image: str

class Trailers_Summary_Response(BaseModel):
    id: int
    status: str
    make: str
    model: str
    year: int
    license_plate: str
    license_expiry_date: date
    equipment_type: str
    trailer_type: str
    trailer_length: str
    tare_weight: int
    gvm_weight: int
    payload_capacity: int
    truck_id: Optional [int] = None
    truck_status: Optional [str] = None
    truck_make: Optional [str] = None
    truck_model: Optional [str] = None
    truck_year: Optional [int] = None
    truck_color: Optional [str] = None
    truck_license_plate: Optional [str] = None
    truck_license_expiry_date: date
    truck_tare_weight: Optional [int] = None
    truck_payload_capacity: Optional [int] = None

class TrailerUpdate(BaseModel):
    license_plate: Optional[str] = None
    license_expiry_date: Optional[date] = None
    vrc_or_leasing: Optional[str] = None
    vehicle_license_disk: Optional[str] = None
    road_worthy_certificate: Optional[str] = None
    front_angle_image: Optional[str] = None
    rear_angle_image: Optional[str] = None
    left_angle_image: Optional[str] = None
    right_angle_image: Optional[str] = None
    # Add other fields as needed


class TrailerResponse(TrailerCreate):
    id: int
    truck_id: Optional[int] = None
    owner_id: int
    company_name: Optional[str] = None
    company_type: Optional[str] = None
    make: str
    model: str
    year: int
    color: str
    vin: str
    license_plate: str
    license_expiry_date: date
    tare_weight: int
    gvm_weight: int
    payload_capacity: int
    equipment_type: str
    trailer_type: str
    trailer_length: str
    vrc_leasing: str
    license_disk: str
    road_worthy_certificate: Optional[str] = None
    front_angle_image: str
    rear_angle_image: str
    left_angle_image: str
    right_angle_image: str
    is_verified: bool
    status: str

    class Config:
        orm_mode = True

class ShipperTrailerCreate(BaseModel):
    make: str
    model: str
    year: int
    color: str
    vin: str
    license_plate: str
    license_expiry_date: date
    tare_weight: int
    gvm_weight: int
    equipment_type: EquipmentType
    trailer_type: TrailerType
    trailer_length: TrailerLength
    vrc_leasing: str
    license_disk: str
    road_worthy_certificate: Optional[str] = None
    front_angle_image: str
    rear_angle_image: str
    left_angle_image: str
    right_angle_image: str

class Shipper_Trailers_Summary_Response(BaseModel):
    id: int
    availability_status: str ####Add in database and function
    make: str
    model: str
    year: int
    license_plate: str
    equipment_type: str
    trailer_type: str
    trailer_length: str
    is_verified: bool
    current_shipment_id: Optional [int] = None ####Add in database and function
    current_shipment_status: Optional [str] = None ####Add in database and function

class Individual_Shipper_Trailer_Response(BaseModel):
    id: int
    make: str
    model: str
    year: int
    color: str
    equipment_type: str
    trailer_type: str
    trailer_length: str
    vin: str
    license_plate: str
    license_expiry_date: date
    tare_weight: int
    gvm_weight: int
    payload_capacity: int
    owner_id: int
    company_name: str
    company_type: str
    truck_id: Optional [int] = None
    current_shipment_id: Optional [int] = None ####Add in database and function
    current_shipment_status: Optional [str] = None ####Add in database and function
    vrc_leasing: str
    license_disk: str
    road_worthy_certificate: Optional [str]
    front_angle_image: str
    rear_angle_image: str
    left_angle_image: str
    right_angle_image: str
    is_verified: bool
    is_vehicle: bool
    status: str
    availability_status: str ####Add in database and function


class Fleet_Trailer_Truck_response(BaseModel):
    id: int
    is_verified: bool
    company_name: str
    make: str
    model: str
    year: int
    color: str
    vin: str
    license_plate: str
    license_expiry_date: date
    tare_weight: int
    gvm_weight: int
    payload_capacity: int
    location_description: str
    shipment_id: Optional [int] = None
    shipment_type: Optional [str] = None
    shipment_status: Optional [str] = None
    origin: Optional [str] = None
    destination: Optional [str] = None