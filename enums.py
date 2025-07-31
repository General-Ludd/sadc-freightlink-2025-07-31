# enums.py
from enum import Enum

class PaymentTerms(str, Enum):
    PAB = "PAB"
    NET_7 = "NET_7"
    NET_10 = "NET_10"
    NET_15 = "NET_15"
    EOM = "EOM"

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
    PARTIALLY_PAID = "PARTIALLY_PAID"
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
    BROKER = "Broker"

class FacilityType(str, Enum):
    SUBSIDIARY_FACILITY = "Subsidiary facility"
    OUTPOST_FACILITY = "Outpost facility"

class SchedulingType(str, Enum):
    FIRST_COME_FIRST_SERVED = "First come, First served"
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
    Tr_Axle = "Tri-Axle"
    Superlink = "Superlink"

class TrailerLength(str,Enum):
    _6m_x_12m = "6m x 12m"
    _7m_x_11m = "7m x 11m"
    _13m = "13m"
    _14m = "14m"

class EquipmentType(str, Enum):
    SIDE_TIPPER = "Side-Tipper"
    TAUTLINER = "TautLiner"
    FLATDECK = "Flatdeck"
    DROPSIDE_TIPPER = "Dropside Tipper"
    DROPSIDE = "Dropside"
    END_TIPPER = "End Tipper"
    BOTTOM_DUMP = "Bottom Dump"
    MOVING_FLOORS = "Moving Floors"
    REFRIGERATOR = "Refrigerator"
    STEP_DECK = "Step Deck"
    SUGAR_CANE = "Sugar Cane"
    TIMBER_CARRIER = "Timber Carrier"
    SKELETAL_TRAILER = "Skeletal Trailer"
    LOWBED = "Lowbed"
    ROCK_DUMPER = "Rock Dumper"
    FLATBED = "flatbed"


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
    SINGLESTOP = "Single-Stop"
    MULTISTOP = "Multi-Stop"

class Load_Type(str, Enum):
    LIVELOADING = "Live Loading"
    LIVELOADINGANDUNLOADING = "Live Loading & Unloading"
    LIVEUNLOADING = "Live Unloading"
    DROPANDHOOK = "Drop & Hook"

class Priority_Level(str, Enum):
    LOW = "Low"
    NORMAL = "Normal"
    HIGH = "High"