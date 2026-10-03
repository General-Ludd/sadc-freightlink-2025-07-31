# enums.py
from enum import Enum

class ShipperShipmentStatus(str, Enum):
    BOOKED = "Booked"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In-Progress"
    COMPLETED = "Completed"
    DELAYED = "Delayed"
    CANCELLED = "Cancelled"

class CarrierShipmentStatus(str, Enum):
    INPROGRESS = "In-progress"
    COMPLETED = "Completed"
    DELAYED = "Delayed"
    CANCELLED = "Cancelled"

class TrailerAvailabilityStatus(str, Enum):
    AVAILABLE = "Available"
    IN_USE = "In Use"
    MAINTENANCE = "Maintenance"

class UserStatus(str, Enum):
    UNVERIFIED = "Un-verified"
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    UNDER_INVESTIGATION = "Under-Investigation"
    DELETED = "Deleted"

class PaymentTerms(str, Enum):
    PAB = "PAB"
    SEVENTY_THIRTY = "70%/30%"
    NET_7 = "NET-7"
    NET_10 = "NET-10"
    NET_15 = "NET-15"
    NET_30 = "30 Days from statement"
    NET_45 = "45 Days from statement"
    NET_60 = "60 Days from statement"
    EOM = "EOM"
    COD = "Cash on delivery"

class Recurrence_Frequency(str, Enum):
    DAILY = "Daily"
    WEEKLY = "Weekly"

class Recurrence_Days(str, Enum):
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDARY = "Sunday"

class InvoiceStatus(str, Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"

class InvoiceType(str, Enum):
    ROOT = "ROOT"           # Full contract invoice
    INTERIM = "INTERIM"     # Monthly/Weekly invoice
    SHIPMENT = "SHIPMENT"   # Shipment-level invoice

class LoggedInStatus(str, Enum):
    OFFLINE = "Offline"
    ONLINE = "Online"

class Axle_Configuration(str, Enum):
    _8x6 = "8x6"
    _6x4 = "6x4"
    _4x4 = "4x4"
    _4x2 = "4x2"

class ShipperType(str, Enum):
    ENTERPRISE = "Enterprise"
    FACILITY = "Facility"
    STANDARD = "Standard"
    BROKER = "Brokerage Firm"

class FacilityType(str, Enum):
    SUBSIDIARY_FACILITY = "Subsidiary facility"
    OUTPOST_FACILITY = "Outpost facility"

class SchedulingType(str, Enum):
    FIRST_COME_FIRST_SERVED = "First come, First served"
    APPOINTMENT_REQUIRED = "Appointment Required"
    APPOINTMENT_ALREADY_SCHEDULED = "Appointment already scheduled"
    SCHEDULE_FOR_ME = "Schedule an appointment for me"

class CarrierType(str, Enum):
    FLEET = "Fleet"
    OWNEROPERATOR = "Owner-Operator"

class Lorry(str, Enum):
    LORRY = "Lorry"

class TruckType(str, Enum):
    LORRY = "Lorry"
    RIGID = "Rigid"

class TrailerType(str, Enum):
    TRI_AXLE = "Tri-Axle"
    SUPERLINK = "Superlink"
    INTERLINK = "Interlink"
    EXTENDABLE = "Extendable / Stretch"

class TrailerLength(str, Enum):
    TRI_AXLE_12M = "Tri-Axle 12m"
    TRI_AXLE_13_5M = "Tri-Axle 13.5m"
    TRI_AXLE_14M = "Tri-Axle 14m"
    TRI_AXLE_15M = "Tri-Axle 15m"
    SUPERLINK_5_2M_10_8M = "Superlink 5.2m + 10.8m"
    SUPERLINK_6M_12M = "Superlink 6m + 12m"
    SUPERLINK_7M_11M = "Superlink 7m + 11m"
    CUSTOM_SUPERLINK = "Custom Superlink"

class EquipmentType(str, Enum):
    TAUTLINER = "Tautliner"
    PANTECH = "Pantech"
    DROP_SIDE = "Drop-Side"
    DROP_SIDE_TIPPER = "Drop-Side Tipper"
    FLATDECK = "Flatdeck"
    FLATBED = "Flatbed"
    WALKING_FLOOR = "Walking Floor"
    MOVING_FLOOR = "Moving Floor"
    LOWBED = "Lowbed"
    STEPDECK = "Stepdeck"
    EXTENDABLE_FLATBED = "Extendable Flatbed"
    EXTENDABLE_LOWBED = "Extendable Lowbed"
    HEAVY_HAUL_TRAILER = "Heavy Haul Trailer"
    SKELETAL_TRAILER = "Skeletal Trailer"
    CONTAINER_CHASSIS = "Container Chassis"
    REFRIGERATED_REEFER = "Refrigerated / Reefer"
    FREEZER_TRAILER = "Freezer Trailer"

    SIDE_TIPPER_18_CUBE = "Side-Tipper 18 Cube"
    SIDE_TIPPER_20_CUBE = "Side-Tipper 20 Cube"
    SIDE_TIPPER_22_5_CUBE = "Side-Tipper 22.5 Cube"
    SIDE_TIPPER_25_CUBE = "Side-Tipper 25 Cube"
    SIDE_TIPPER_28_CUBE = "Side-Tipper 28 Cube"
    SIDE_TIPPER_30_CUBE = "Side-Tipper 30 Cube"
    SIDE_TIPPER_34_CUBE = "Side-Tipper 34 Cube"
    SIDE_TIPPER_35_CUBE = "Side-Tipper 35 Cube"
    SIDE_TIPPER_40_CUBE = "Side-Tipper 40 Cube"
    SIDE_TIPPER_45_CUBE = "Side-Tipper 45 Cube"
    SIDE_TIPPER_50_CUBE = "Side-Tipper 50 Cube"
    SIDE_TIPPER_52_CUBE = "Side-Tipper 52 Cube"

    BACK_END_TIPPER_10_CUBE = "Back-End Tipper 10 Cube"
    BACK_END_TIPPER_15_CUBE = "Back-End Tipper 15 Cube"
    BACK_END_TIPPER_20_CUBE = "Back-End Tipper 20 Cube"
    BACK_END_TIPPER_25_CUBE = "Back-End Tipper 25 Cube"
    BACK_END_TIPPER_30_CUBE = "Back-End Tipper 30 Cube"
    BACK_END_TIPPER_35_CUBE = "Back-End Tipper 35 Cube"
    BACK_END_TIPPER_40_CUBE = "Back-End Tipper 40 Cube"

    BULK_TIPPER_20_CUBE = "Bulk Tipper 20 Cube"
    BULK_TIPPER_25_CUBE = "Bulk Tipper 25 Cube"
    BULK_TIPPER_30_CUBE = "Bulk Tipper 30 Cube"
    BULK_TIPPER_35_CUBE = "Bulk Tipper 35 Cube"
    BULK_TIPPER_40_CUBE = "Bulk Tipper 40 Cube"

    GRAIN_CARRIER_30_CUBE = "Grain Carrier 30 Cube"
    GRAIN_CARRIER_35_CUBE = "Grain Carrier 35 Cube"
    GRAIN_CARRIER_40_CUBE = "Grain Carrier 40 Cube"
    GRAIN_CARRIER_45_CUBE = "Grain Carrier 45 Cube"
    GRAIN_CARRIER_50_CUBE = "Grain Carrier 50 Cube"

    CEMENT_BULKER_30_CUBE = "Cement Bulker 30 Cube"
    CEMENT_BULKER_35_CUBE = "Cement Bulker 35 Cube"
    CEMENT_BULKER_40_CUBE = "Cement Bulker 40 Cube"
    CEMENT_BULKER_45_CUBE = "Cement Bulker 45 Cube"
    CEMENT_BULKER_50_CUBE = "Cement Bulker 50 Cube"

    FUEL_TANKER_10_000_LITRE = "Fuel Tanker 10,000 Litre"
    FUEL_TANKER_15_000_LITRE = "Fuel Tanker 15,000 Litre"
    FUEL_TANKER_20_000_LITRE = "Fuel Tanker 20,000 Litre"
    FUEL_TANKER_25_000_LITRE = "Fuel Tanker 25,000 Litre"
    FUEL_TANKER_30_000_LITRE = "Fuel Tanker 30,000 Litre"
    FUEL_TANKER_35_000_LITRE = "Fuel Tanker 35,000 Litre"
    FUEL_TANKER_40_000_LITRE = "Fuel Tanker 40,000 Litre"
    FUEL_TANKER_45_000_LITRE = "Fuel Tanker 45,000 Litre"
    FUEL_TANKER_50_000_LITRE = "Fuel Tanker 50,000 Litre"

    CHEMICAL_TANKER_10_000_LITRE = "Chemical Tanker 10,000 Litre"
    CHEMICAL_TANKER_15_000_LITRE = "Chemical Tanker 15,000 Litre"
    CHEMICAL_TANKER_20_000_LITRE = "Chemical Tanker 20,000 Litre"
    CHEMICAL_TANKER_25_000_LITRE = "Chemical Tanker 25,000 Litre"
    CHEMICAL_TANKER_30_000_LITRE = "Chemical Tanker 30,000 Litre"
    CHEMICAL_TANKER_35_000_LITRE = "Chemical Tanker 35,000 Litre"
    CHEMICAL_TANKER_40_000_LITRE = "Chemical Tanker 40,000 Litre"
    CHEMICAL_TANKER_45_000_LITRE = "Chemical Tanker 45,000 Litre"

    LIQUID_TANKER_10_000_LITRE = "Liquid Tanker 10,000 Litre"
    LIQUID_TANKER_15_000_LITRE = "Liquid Tanker 15,000 Litre"
    LIQUID_TANKER_20_000_LITRE = "Liquid Tanker 20,000 Litre"
    LIQUID_TANKER_25_000_LITRE = "Liquid Tanker 25,000 Litre"
    LIQUID_TANKER_30_000_LITRE = "Liquid Tanker 30,000 Litre"
    LIQUID_TANKER_35_000_LITRE = "Liquid Tanker 35,000 Litre"
    LIQUID_TANKER_40_000_LITRE = "Liquid Tanker 40,000 Litre"
    LIQUID_TANKER_45_000_LITRE = "Liquid Tanker 45,000 Litre"
    LIQUID_TANKER_50_000_LITRE = "Liquid Tanker 50,000 Litre"

    FOOD_GRADE_TANKER_10_000_LITRE = "Food-Grade Tanker 10,000 Litre"
    FOOD_GRADE_TANKER_15_000_LITRE = "Food-Grade Tanker 15,000 Litre"
    FOOD_GRADE_TANKER_20_000_LITRE = "Food-Grade Tanker 20,000 Litre"
    FOOD_GRADE_TANKER_25_000_LITRE = "Food-Grade Tanker 25,000 Litre"
    FOOD_GRADE_TANKER_30_000_LITRE = "Food-Grade Tanker 30,000 Litre"
    FOOD_GRADE_TANKER_35_000_LITRE = "Food-Grade Tanker 35,000 Litre"
    FOOD_GRADE_TANKER_40_000_LITRE = "Food-Grade Tanker 40,000 Litre"
    FOOD_GRADE_TANKER_45_000_LITRE = "Food-Grade Tanker 45,000 Litre"

    WATER_TANKER_5_000_LITRE = "Water Tanker 5,000 Litre"
    WATER_TANKER_10_000_LITRE = "Water Tanker 10,000 Litre"
    WATER_TANKER_15_000_LITRE = "Water Tanker 15,000 Litre"
    WATER_TANKER_20_000_LITRE = "Water Tanker 20,000 Litre"
    WATER_TANKER_25_000_LITRE = "Water Tanker 25,000 Litre"
    WATER_TANKER_30_000_LITRE = "Water Tanker 30,000 Litre"
    WATER_TANKER_35_000_LITRE = "Water Tanker 35,000 Litre"
    WATER_TANKER_40_000_LITRE = "Water Tanker 40,000 Litre"
    WATER_TANKER_45_000_LITRE = "Water Tanker 45,000 Litre"

    MILK_TANKER_10_000_LITRE = "Milk Tanker 10,000 Litre"
    MILK_TANKER_15_000_LITRE = "Milk Tanker 15,000 Litre"
    MILK_TANKER_20_000_LITRE = "Milk Tanker 20,000 Litre"
    MILK_TANKER_25_000_LITRE = "Milk Tanker 25,000 Litre"
    MILK_TANKER_30_000_LITRE = "Milk Tanker 30,000 Litre"
    MILK_TANKER_35_000_LITRE = "Milk Tanker 35,000 Litre"
    MILK_TANKER_40_000_LITRE = "Milk Tanker 40,000 Litre"

    GAS_TANKER_10_000_LITRE = "Gas Tanker 10,000 Litre"
    GAS_TANKER_15_000_LITRE = "Gas Tanker 15,000 Litre"
    GAS_TANKER_20_000_LITRE = "Gas Tanker 20,000 Litre"
    GAS_TANKER_25_000_LITRE = "Gas Tanker 25,000 Litre"
    GAS_TANKER_30_000_LITRE = "Gas Tanker 30,000 Litre"
    GAS_TANKER_35_000_LITRE = "Gas Tanker 35,000 Litre"
    GAS_TANKER_40_000_LITRE = "Gas Tanker 40,000 Litre"

    BITUMEN_TANKER_10_000_LITRE = "Bitumen Tanker 10,000 Litre"
    BITUMEN_TANKER_15_000_LITRE = "Bitumen Tanker 15,000 Litre"
    BITUMEN_TANKER_20_000_LITRE = "Bitumen Tanker 20,000 Litre"
    BITUMEN_TANKER_25_000_LITRE = "Bitumen Tanker 25,000 Litre"
    BITUMEN_TANKER_30_000_LITRE = "Bitumen Tanker 30,000 Litre"
    BITUMEN_TANKER_35_000_LITRE = "Bitumen Tanker 35,000 Litre"
    BITUMEN_TANKER_40_000_LITRE = "Bitumen Tanker 40,000 Litre"

    VACUUM_TANKER_5_000_LITRE = "Vacuum Tanker 5,000 Litre"
    VACUUM_TANKER_10_000_LITRE = "Vacuum Tanker 10,000 Litre"
    VACUUM_TANKER_15_000_LITRE = "Vacuum Tanker 15,000 Litre"
    VACUUM_TANKER_20_000_LITRE = "Vacuum Tanker 20,000 Litre"
    VACUUM_TANKER_25_000_LITRE = "Vacuum Tanker 25,000 Litre"

    LIVESTOCK_TRAILER = "Livestock Trailer"
    CAR_CARRIER = "Car Carrier"
    TIMBER_TRAILER = "Timber Trailer"
    LOG_TRAILER = "Log Trailer"
    SCRAP_TRAILER = "Scrap Trailer"
    WASTE_TRAILER = "Waste Trailer"
    HOOKLIFT = "Hooklift"
    ROLL_ON_ROLL_OFF_TRAILER = "Roll-on/Roll-off Trailer"
    CRANE_HIAB = "Crane / Hiab"
    BRICK_CARRIER = "Brick Carrier"
    PIPE_CARRIER = "Pipe Carrier"
    POLE_TRAILER = "Pole Trailer"
    ABNORMAL_LOAD_TRAILER = "Abnormal Load Trailer"
    SPECIALISED_HEAVY_HAULAGE = "Specialised Heavy Haulage"

class RigidTruckEquipmentType(str, Enum):
    FLATBED = "flatbed"
    TAUTLINER = "tautliner"
    END_TIPPER = "end tipper"
    SIDE_LOARDER = "side loader"
    BRICK_CARRIER = "brick carrier"
    SINGLE_CAR_CARRIER = "single car carrier"

class RigidEquipmentType(str, Enum):
    RIGID_FLATBED = "rigid_flatbed"
    RIGID_TAUTLINER = "rigid_tautliner"
    RIGID_SIDETIPPER = "rigid_side-tipper"

class SuperlinkEquipmentType(str, Enum):
    SUPERLINK_FLATBED = "superlink_flatbed"
    SUPERLINK_TAUTLINER = "superlink_tautliner"
    SUPERLINK_SIDETIPPER = "sside-tipper"

class LoginStatus(str, Enum):
    ONLINE = "Online"
    OFFLINE = "Offline"

class WareHouseType(str, Enum):
    COMMERCIAL = "Commercial"
    BONDED = "Bonded"

class Countries(str, Enum):
    RSA = "South Africa"
    DRC = "Democratic Republic of Congo"
    ZIM = "Zimbabwe"
    MLW = "Malawi"

class RSA_Provinces(str, Enum):
    KZN = "Kwa-Zulu-Natal"
    EC = "Eastern Cape"
    WC = "Western Cape"
    GP = "Gauteng"
    MP = "Mpumalanga"
    NW = "North West"
    NC = "Northern Cape"

# FINANCE
class TransactionType(str, Enum):
    SHIPMENT_BOOKING = "Shipment Booking"
    DETENTION_FEES = "Detention Fees"
    PORT_FEES = "Port Fees"
    CUSTOMS = "Customs Fees"
    CUSTOMS_BROKERAGE = "Customs Brokerage"

class Shipment_Mode(str, Enum):
    FTL = "FTL"
    POWER = "POWER"
    DEDICATEDFTLLANE = "Dedicated FTL Lane"
    DEDICATEDPOWERLANE = "Dedicated POWER Lane"

class Trip_Type(str, Enum):
    ONE_WAY = "One-Way"
    ONE_WAY_MULTI_STOP = "One Way Multi-Stop"
    ONE_WAY_BUNDLE = "One Way Bundle"
    ROUND_TRIP = "Round Trip"
    ROUND_TRIP_MULTI_STOP = "Round Trip Multi-Stop"
    ROUND_TRIP_BUNDLE = "Round Trip Bundle"

class Load_Type(str, Enum):
    LIVELOADING = "Live Loading"
    LIVELOADINGANDUNLOADING = "Live Loading & Unloading"
    LIVEUNLOADING = "Live Unloading"
    DROPANDHOOK = "Drop & Hook"

class Priority_Level(str, Enum):
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"

class Account_Status(str, Enum):
    UNVERIFIED = "Un-verified"
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    UNDER_INVESTIGATION = "Under-Investigation"
    DELETED = "Deleted"

class VehicleDocsClass(str, Enum):
    VEHICLE_REGISTRATION_CERTIFICATE = "Vehicle Registration Certificate"
    LEASING_CERTIFICATE = "Vehicle Leasing Certificate"
    LICENSE_DISK = "License Disk"
    ROADWORTHINESS = "Road Worthiness Certificate"
    TRACKING_CERTIFICATE = "Tracking Certificate"
    FRONT_ANGLE_IMAGE = "Front Angle Image"
    REAR_ANGLE_IMAGE = "Rear Angle Image"
    LEFT_ANGLE_IMAGE = "Left Angle Image"
    RIGHT_ANGLE_IMAGE = "Right Angle Image"

class HazchemClass(Enum):
    """Represents the 9 standard classes of Dangerous Goods / Hazchem."""

    CLASS_1 = "1.Explosives"
    CLASS_2 = "2.Gases"
    CLASS_3 = "3.Flammable Liquids"
    CLASS_4 = "4.Flammable Solids"
    CLASS_5 = "5.Oxidizing Substances and Organic Peroxides"
    CLASS_6 = "6.Toxic and Infectious Substances"
    CLASS_7 = "7.Radioactive Material"
    CLASS_8 = "8.Corrosive Substances"
    CLASS_9 = "9.Miscellaneous Dangerous Goods"

    @property
    def description(self) -> str:
        """Returns a human-readable description of the main class."""
        mapping = {
            HazchemClass.CLASS_1: "Explosives",
            HazchemClass.CLASS_2: "Gases",
            HazchemClass.CLASS_3: "Flammable Liquids",
            HazchemClass.CLASS_4: "Flammable Solids",
            HazchemClass.CLASS_5: "Oxidizing Substances and Organic Peroxides",
            HazchemClass.CLASS_6: "Toxic and Infectious Substances",
            HazchemClass.CLASS_7: "Radioactive Material",
            HazchemClass.CLASS_8: "Corrosive Substances",
            HazchemClass.CLASS_9: "Miscellaneous Dangerous Goods",
        }
        return mapping[self]

class PricingBasis(Enum):
    PER_TRIP_LOAD = "Rate per Trip / Load"
    RATE_PER_CONTAINER = "Rate per Container"
    RATE_PER_TON = "Rate per Ton"
    RATE_PER_KM = "Rate per Km"

class RateDirectionTarget(Enum):
    REDUCE = "Reduce"
    MAINTAIN = "Maintain"
    DYNAMIC = "Dynamic"

