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
    is_comesa_member: bool = False  # Fixed typo: memeber -> member
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
    is_comesa_member: Optional[bool] = None  # Fixed typo
    is_sacu_member: Optional[bool] = None
    standard_vat_rate: Optional[Decimal] = None
    requires_ctn: Optional[bool] = None
    is_active: Optional[bool] = None  # Fixed: Bool -> bool

# ----- 2. Customs Duty Authority Model -----
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

# ----- 3. Trade Agreement Model -----
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

# ----- 4. Tariff Schedule Model -----
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

# ----- 5. Trade Defense Measure Model -----
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

# ----- 6. Country Special Fee Model -----
class CountrySpecialFeeBase(BaseModel):
    fee_code: str = Field(..., max_length=50)
    fee_name: str = Field(..., max_length=150)
    amount_zar: Optional[Decimal] = Field(None, ge=0)
    percentage_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    threshold_amount_zar: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    payable_to: Optional[str] = Field(None, max_length=200)
    is_mandatory: bool = False
    is_active: bool = True
    effective_date: date
    expiry_date: Optional[date] = None

class CountrySpecialFeeCreate(CountrySpecialFeeBase):
    country_id: int

# ----- 7. Transit Bond Fee Model -----
class TransitBondFeeBase(BaseModel):
    amount_zar: Decimal = Field(..., ge=0)
    bond_validity_days: int = Field(..., ge=1)
    description: Optional[str] = None
    is_active: bool = True
    effective_date: date
    expiry_date: Optional[date] = None

class TransitBondFeeCreate(TransitBondFeeBase):
    country_id: int

# ----- 8. Border Post Model -----
class BorderPostBase(BaseModel):
    from_country_id: int
    to_country_id: int
    border_name: str = Field(..., max_length=150)
    is_port: bool = False
    fee_type: str = Field(..., max_length=50)
    vehicle_category: str = Field(..., max_length=50)
    amount_zar: Decimal = Field(..., ge=0)
    description: Optional[str] = None
    is_active: bool = True
    effective_date: date
    expiry_date: Optional[date] = None

class BorderPostCreate(BorderPostBase):
    pass

class BorderPostUpdate(BaseModel):
    border_name: Optional[str] = Field(None, max_length=150)
    is_active: Optional[bool] = None
    amount_zar: Optional[Decimal] = Field(None, ge=0)
    description: Optional[str] = None
    expiry_date: Optional[date] = None