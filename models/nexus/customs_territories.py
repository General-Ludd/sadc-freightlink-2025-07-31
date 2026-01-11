from sqlalchemy import Column, Integer, String, Boolean, DECIMAL, Float, Date, Text, JSON, TIMESTAMP, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from models.base import Base
from datetime import datetime

class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)
    iso_code = Column(String(2), unique=True, nullable=False)   # ZA, NA, ZW, ZM, CD
    name = Column(String(100), unique=True, nullable=False)
    currency_code = Column(String(3), nullable=False)
    is_sadc_member = Column(Boolean, default=False, nullable=False)
    is_comesa_member = Column(Boolean, default=False, nullable=False)
    is_sacu_member = Column(Boolean, default=False, nullable=False)
    standard_vat_rate = Column(DECIMAL(5, 2))
    requires_ctn = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    trade_agreements = relationship("CountryTradeAgreement", back_populates="country", cascade="all, delete-orphan")
    tariff_schedules = relationship("TariffSchedule", back_populates="country", cascade="all, delete-orphan")
    trade_defense_measures = relationship("TradeDefenseMeasure", back_populates="country", cascade="all, delete-orphan")
    customs_procedures = relationship("CustomsProcedure", back_populates="country", cascade="all, delete-orphan")

class Customs_Duty_Authority(Base):
    __tablename__ = "customs_duty_authorities"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, nullable=False)
    country = Column(String(50), nullable=False)
    agency_name = Column(String(50), nullable=False)
    agency_code = Column(String(50), nullable=False)
    bank_name = Column(String(50), nullable=True)
    branch_code = Column(String(50), nullable=True)
    bank_account_number = Column(String(50), nullable=True)
    account_type = Column(String(50), nullable=True)
    website = Column(String(50), nullable=False)
    email = Column(String(50), nullable=True)
    phone_number = Column(String(50), nullable=False)

class CountryTradeAgreement(Base):
    __tablename__ = "country_trade_agreements"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)

    agreement_name = Column(String(150), nullable=False)
    agreement_code = Column(String(50))
    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(Date, nullable=False)
    notes = Column(Text)

    country = relationship("Country", back_populates="trade_agreements")

    __table_args__ = (
        UniqueConstraint("country_id", "agreement_name", name="uq_country_agreement"),
    )


class BorderPost(Base):
    __tablename__ = "border_posts"

    id = Column(Integer, primary_key=True, index=True)
    from_country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    to_country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)

    border_name = Column(String(150), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    is_port = Column(Boolean, default=False)
    fee_type = Column(String(50), nullable=False)
    vehicle_category = Column(String(50), nullable=False)

    amount_zar = Column(DECIMAL(12, 2), nullable=False)

    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "from_country_id",
            "to_country_id",
            "border_name",
            "fee_type",
            "vehicle_category",
            "effective_date",
            name="uq_border_fee"
        ),
    )


class BorderClearanceProfile(Base):
    __tablename__ = "border_clearance_profiles"

    id = Column(Integer, primary_key=True, index=True)

    border_post_id = Column(
        Integer,
        ForeignKey("border_posts.id", ondelete="CASCADE"),
        nullable=False
    )

    clearance_leg = Column(
        String(20),
        nullable=False
    )
    # ENUM conceptually:
    # ZA_EXIT | ZA_ENTRY | FOREIGN_EXIT | FOREIGN_ENTRY

    avg_clearance_hours = Column(Integer, nullable=False)
    peak_delay_hours = Column(Integer, nullable=True)

    weekend_multiplier = Column(DECIMAL(4, 2), default=1.00, nullable=False)
    night_operations_allowed = Column(Boolean, default=False, nullable=False)

    congestion_level = Column(
        String(20),
        nullable=False
    )
    # LOW | MEDIUM | HIGH | SEVERE

    notes = Column(Text)

    is_active = Column(Boolean, default=True, nullable=False)

    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "border_post_id",
            "clearance_leg",
            "effective_date",
            name="uq_border_leg_clearance_profile"
        ),
    )


class TariffSchedule(Base):
    __tablename__ = "tariff_schedules"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)

    hs_code = Column(String(12), nullable=False)
    hs_description = Column(Text, nullable=False)
    mfn_rate = Column(DECIMAL(10, 2), nullable=False)
    preferential_rate = Column(DECIMAL(10, 2))
    agreement_source = Column(String(150))
    uom = Column(String(20))
    excise_duty_rate = Column(DECIMAL(10, 2))

    start_date = Column(Date, nullable=False)
    end_date = Column(Date)

    country = relationship("Country", back_populates="tariff_schedules")

    __table_args__ = (
        UniqueConstraint("country_id", "hs_code", "start_date", name="uq_country_hs_start"),
        Index("idx_tariff_country_hs", "country_id", "hs_code"),
    )

class TradeDefenseMeasure(Base):
    __tablename__ = "trade_defense_measures"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)

    measure_type = Column(String(50), nullable=False)  # ANTI_DUMPING, SAFEGUARD, COUNTERVAILING
    hs_code = Column(String(12), nullable=False)
    exporting_country_iso = Column(String(2))
    description = Column(Text, nullable=False)
    duty_rate = Column(DECIMAL(10, 2), nullable=False)

    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)
    legal_reference = Column(Text)

    country = relationship("Country", back_populates="trade_defense_measures")

    __table_args__ = (
        UniqueConstraint(
            "country_id",
            "measure_type",
            "hs_code",
            "exporting_country_iso",
            "effective_date",
            name="uq_trade_measure"
        ),
    )

class CountrySpecialFee(Base):
    __tablename__ = "country_special_fees"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)

    fee_code = Column(String(50), nullable=False)
    fee_name = Column(String(150), nullable=False)

    amount_zar = Column(DECIMAL(12, 2))
    percentage_rate = Column(DECIMAL(5, 4))
    threshold_amount_zar = Column(DECIMAL(12, 2))

    description = Column(Text)
    payable_to = Column(String(200))
    is_mandatory = Column(Boolean, default=False, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("country_id", "fee_code", "effective_date", name="uq_country_fee"),
    )

class TransitBondFee(Base):
    __tablename__ = "transit_bond_fees"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)

    amount_zar = Column(DECIMAL(12, 2), nullable=False)
    bond_validity_days = Column(Integer, default=14, nullable=False)

    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)

    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("country_id", "effective_date", name="uq_transit_bond"),
    )

class CustomsProcedure(Base):
    __tablename__ = "customs_procedures"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)

    procedure_type = Column(String(100), nullable=False)
    required_documents_shipper = Column(JSON, nullable=False, default=list)
    required_documents_agent = Column(JSON, nullable=False, default=list)
    required_documents_carrier = Column(JSON, nullable=False, default=list)

    process_description = Column(Text)
    standard_processing_days = Column(Integer)

    is_electronic_filing_mandatory = Column(Boolean, default=True, nullable=False)

    authority_name = Column(String(200))
    authority_website = Column(String(500))

    country = relationship("Country", back_populates="customs_procedures")

    __table_args__ = (
        UniqueConstraint("country_id", "procedure_type", name="uq_country_procedure"),
    )

class ExciseTaxRate(Base):
    __tablename__ = "excise_tax_rates"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)

    commodity_type = Column(String(100), nullable=False)
    hs_code_pattern = Column(String(50))
    tax_rate = Column(DECIMAL(5, 4), nullable=False)

    description = Column(Text)
    is_additional_to_duty = Column(Boolean, default=True, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("country_id", "commodity_type", "effective_date", name="uq_excise"),
    )

class AntiDumpingMeasure(Base):
    __tablename__ = "anti_dumping_measures"
    id = Column(Integer, primary_key=True, index=True)
    country_iso = Column(String(2), nullable=False)
    hs_code_pattern = Column(String(50), nullable=False)
    exporting_country_iso = Column(String(2))
    duty_rate = Column(DECIMAL(5, 4), nullable=False)
    description = Column(Text)
    legal_reference = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(Date, nullable=False)
    expiry_date = Column(Date)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint('country_iso', 'hs_code_pattern', 
                                       'exporting_country_iso', 'effective_date'),)

class CurrencyExchangeRate(Base):
    __tablename__ = "currency_exchange_rates"

    id = Column(Integer, primary_key=True, index=True)

    from_currency = Column(String(3), nullable=False)
    to_currency = Column(String(3), nullable=False)

    exchange_rate = Column(DECIMAL(10, 4), nullable=False)

    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date)

    source = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("from_currency", "to_currency", "valid_from", name="uq_fx_rate"),
    )