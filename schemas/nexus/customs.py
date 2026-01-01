from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import Optional, List, Any
from decimal import Decimal

# ----- 1. Country Model -----
class CountryBase(BaseModel):
    iso_code: str = Field(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 code")
    name: str = Field(..., max_length=100)
    currency_code: str = Field(..., min_length=3, max_length=3)
    is_sadc_member: bool = False
    is_comesa_memeber: bool = False
    is_sacu_member: bool = False
    standard_vat_rate: Optional[Decimal] = None
    requires_ctn: bool = False
    is_active: bool = False

class CountryCreate(CountryBase):
    pass

class CountryUpdate(BaseModel):
    # All fields optional for updates
    name: Optional[str] = Field(None, max_length=100)
    currency_code: Optional[str] = Field(None, min_length=3, max_length=3)
    is_sadc_member: Optional[bool] = None
    is_comesa_member: Optional[bool] = None
    is_sacu_member: Optional[bool] = None
    standard_vat_rate: Optional[Decimal] = None
    requires_ctn: Optional[bool] = None
    is_active: Optional[Bool] = None

class Customs_Duty_Authority_Base(BaseModel):
    agency_name: str
    agency_code: str
    bank_name: Optional[str] = None
    branch_code: Optional[str] = None
    bank_account_number: Optional[str] = None
    account_type: Optional[str] = None
    website: str
    email: Optional[str] = None
    phone_number: str

# ----- 2. Trade Agreement Model -----
class CountryTradeAgreementBase(BaseModel):
    agreement_name: str = Field(..., max_length=150)
    agreement_code: Optional[str] = Field(None, max_length=50)
    is_active: bool = True
    effective_date: date
    notes: Optional[str] = None

class CountryTradeAgreementCreate(CountryTradeAgreementBase):
    country_id: int

class CountryTradeAgreementUpdate(BaseModel):
    agreement_name: Optional[str] = Field(None, max_length=150)
    is_active: Optional[bool] = None
    notes: Optional[str] = None

class CountryTradeAgreement(CountryTradeAgreementBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    country_id: int

# ----- 3. Tariff Schedule Model -----
class TariffScheduleBase(BaseModel):
    hs_code: str = Field(..., max_length=12)
    hs_description: str
    mfn_rate: Decimal = Field(..., ge=0)
    preferential_rate: Optional[Decimal] = Field(None, ge=0)
    agreement_source: Optional[str] = Field(None, max_length=150)
    uom: Optional[str] = Field(None, max_length=20)
    excise_duty_rate: Optional[Decimal] = Field(None, ge=0)
    start_date: date
    end_date: Optional[date] = None

class TariffScheduleCreate(TariffScheduleBase):
    country_id: int

class TariffSchedule(TariffScheduleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    country_id: int

# ----- 4. Trade Defense Measure Model -----
class TradeDefenseMeasureBase(BaseModel):
    measure_type: str = Field(..., max_length=50)
    hs_code: str = Field(..., max_length=12)
    exporting_country_iso: Optional[str] = Field(None, min_length=2, max_length=2)
    description: str
    duty_rate: Decimal = Field(..., ge=0)
    effective_date: date
    expiry_date: Optional[date] = None
    legal_reference: Optional[str] = None

class TradeDefenseMeasureCreate(TradeDefenseMeasureBase):
    country_id: int

\\\\class TradeDefenseMeasure(TradeDefenseMeasureBase):
    model_config = ConfigDict(from_attributes=True)-
    id: int
    country_id: int

# ----- 5. Customs Procedure Model -----
class CustomsProcedureBase(BaseModel):
    procedure_type: str = Field(..., max_length=100)
    required_documents: List[Any] = Field(default_factory=list)  # JSON list
    process_description: Optional[str] = None
    standard_processing_days: Optional[int] = Field(None, ge=0)
    is_electronic_filing_mandatory: bool = True
    authority_name: Optional[str] = Field(None, max_length=200)
    authority_website: Optional[str] = Field(None, max_length=500)

class CustomsProcedureCreate(CustomsProcedureBase):
    country_id: int

class CustomsProcedureUpdate(BaseModel):
    required_documents: Optional[List[Any]] = None
    process_description: Optional[str] = None
    standard_processing_days: Optional[int] = Field(None, ge=0)

class CustomsProcedure(CustomsProcedureBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    country_id: int

# Handle forward references for nested relationships
Country.model_rebuild()