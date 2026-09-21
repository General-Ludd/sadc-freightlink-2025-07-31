from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================
# SHARED COMMERCIAL OFFER
# ============================================================

class CommercialOfferCreate(BaseModel):
    rate: float = Field(
        ...,
        ge=0,
        description="Proposed carrier rate"
    )

    rate_basis: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Example: Per Load, Per Ton, Per Trip"
    )

    vat_rate: float = Field(
        15.0,
        ge=0,
        le=100,
        description="VAT percentage"
    )

    trucks_required: int = Field(
        ...,
        ge=1,
        description="Number of trucks required"
    )

    loads_per_interval: int = Field(
        ...,
        ge=0,
        description="Number of loads required per interval"
    )

    tonnage_per_interval: float = Field(
        ...,
        ge=0,
        description="Total tonnage required per interval"
    )

    shipments_per_interval: int = Field(
        ...,
        ge=0,
        description="Number of shipments required per interval"
    )

    interval_period: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Example: Daily, Weekly, Monthly"
    )

    currency: str = Field(
        "ZAR",
        min_length=3,
        max_length=3
    )


# ============================================================
# COMMON DOCUMENT ROUTE
# ============================================================

class DocumentRouteCreate(BaseModel):
    origin: str = Field(..., min_length=1, max_length=500)
    destination: str = Field(..., min_length=1, max_length=500)

    return_origin: Optional[str] = None
    return_destination: Optional[str] = None

    distance_outbound: Optional[str] = None
    distance_return: Optional[str] = None

    border_route: Optional[str] = None


# ============================================================
# CARGO
# ============================================================

class DocumentCargoCreate(BaseModel):
    outbound: Optional[str] = None
    return_cargo: Optional[str] = None

    weight: Optional[str] = None
    packaging: Optional[str] = None


# ============================================================
# VOLUME
# ============================================================

class DocumentVolumeCreate(BaseModel):
    outbound_loads: Optional[int] = Field(None, ge=0)
    return_loads: Optional[int] = Field(None, ge=0)

    annual_loads: Optional[int] = Field(None, ge=0)


# ============================================================
# PAYMENT
# ============================================================

class DocumentPaymentCreate(BaseModel):
    terms: Optional[str] = None
    structure: Optional[str] = None


# ============================================================
# COST ALLOCATION
# ============================================================

class CostAllocationCreate(BaseModel):
    included: List[str] = []
    client_account: List[str] = []
    carrier_account: List[str] = []


# ============================================================
# TURNAROUND
# ============================================================

class TurnaroundCreate(BaseModel):
    free_loading_hours: Optional[int] = Field(None, ge=0)
    free_offloading_hours: Optional[int] = Field(None, ge=0)

    standing_time_rate: Optional[float] = Field(None, ge=0)

    standing_time_basis: Optional[str] = None


# ============================================================
# TRANSIT
# ============================================================

class TransitCreate(BaseModel):
    outbound: Optional[str] = None
    return_transit: Optional[str] = None
    round_trip: Optional[str] = None


# ============================================================
# CLIENT-MANDATED DOCUMENT
# ============================================================

class ClientMandatedTransporterOfferCreate(BaseModel):

    # ----------------------------------------
    # Document
    # ----------------------------------------

    title: str = Field(
        "Transporter Rate Invitation",
        max_length=200
    )

    reference: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    issue_date: Optional[str] = None

    submission_deadline: Optional[str] = None

    rate_validity: Optional[str] = None

    # ----------------------------------------
    # Client
    # ----------------------------------------

    client_id: int = Field(
        ...,
        description="Client corporation ID"
    )

    # ----------------------------------------
    # Tender information
    # ----------------------------------------

    equipment: Optional[str] = None

    route: DocumentRouteCreate

    cargo: Optional[DocumentCargoCreate] = None

    volume: Optional[DocumentVolumeCreate] = None

    payment: Optional[DocumentPaymentCreate] = None

    cost_allocation: Optional[CostAllocationCreate] = None

    operational_requirements: List[str] = []

    insurance: List[str] = []

    documentation: List[str] = []

    transit: Optional[TransitCreate] = None

    turnaround: Optional[TurnaroundCreate] = None

    # ----------------------------------------
    # ADMIN ENTERED COMMERCIAL OFFER
    # ----------------------------------------

    commercial_offer: CommercialOfferCreate

    # ----------------------------------------
    # Acceptance
    # ----------------------------------------

    special_conditions: Optional[str] = None


# ============================================================
# SADC FREIGHTLINK CONFIDENTIAL TENDER
# ============================================================

class SADCFreightlinkTenderCreate(BaseModel):

    # ----------------------------------------
    # Document
    # ----------------------------------------

    title: str = Field(
        "SADC FREIGHTLINK Transportation Tender",
        max_length=200
    )

    reference: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    issue_date: Optional[str] = None

    submission_deadline: Optional[str] = None

    contract_start: Optional[str] = None

    contract_end: Optional[str] = None

    tender_type: Optional[str] = None

    # ----------------------------------------
    # IMPORTANT:
    # NO CLIENT ID
    # NO CLIENT NAME
    # NO CLIENT LOGO
    # ----------------------------------------

    equipment: Optional[str] = None

    operating_model: Optional[str] = None

    route: DocumentRouteCreate

    cargo: Optional[DocumentCargoCreate] = None

    volume: Optional[DocumentVolumeCreate] = None

    payment: Optional[DocumentPaymentCreate] = None

    cost_allocation: Optional[CostAllocationCreate] = None

    operational_requirements: List[str] = []

    insurance: List[str] = []

    documentation: List[str] = []

    transit: Optional[TransitCreate] = None

    turnaround: Optional[TurnaroundCreate] = None

    tender_conditions: List[str] = []

    # ----------------------------------------
    # ADMIN ENTERED CARRIER RATE
    # ----------------------------------------

    commercial_offer: CommercialOfferCreate

    # ----------------------------------------
    # SADC CONTACT
    # ----------------------------------------

    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None