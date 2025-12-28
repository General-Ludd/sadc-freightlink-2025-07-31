from sqlalchemy import Column, Integer, String, Boolean, DECIMAL, Date, Text, JSON, TIMESTAMP, ForeignKey, UniqueConstraint, Index, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from datetime import datetime

# Import Base from your existing models
# from your_database_file import Base

class CustomsBrokerageFirm(Base):
    """Licensed customs brokerage company (to be expanded later)"""
    __tablename__ = "customs_brokerage_firms"
    
    id = Column(Integer, primary_key=True, index=True)
    legal_business_name = Column(String(200), nullable=False, unique=True)
    trading_name = Column(String(200), nullable=True)
    country_of_incorporation = Column(Sting, nullable=False)
    business_registration_number = Column(String(50), nullable=True)
    business_address = Column(String, nullable=False)
    primary_contact_email = Column(String(150), nullable=False)
    primary_contact_phone = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    business_registration_certificate = Column(String, nullable=False)
    business_proof_of_address = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    status = Column(Enum("Un-verified", "Active", "Under Investigation", "Suspended"), default="Un-verified")
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    service_areas = relationship("CustomsBrokerageFirmServiceArea", back_populates="firm", cascade="all, delete-orphan")
    assigned_events = relationship("ShipmentCustomsEvent", back_populates="assigned_firm")
    
    def __repr__(self):
        return f"<CustomsBrokerageFirm(id={self.id}, name='{self.legal_name}')>"

class CustomsBrokerageFirmCredential(Base):
    """Stores firm's permits, bonds, client codes per country (For Phase 4)"""
    __tablename__ = "customs_brokerage_firm_credentials"
    
    CREDENTIAL_TYPE_ENUM = PG_ENUM(
        'CUSTOMS_CLIENT_CODE', 'BUSINESS_REGISTRATION', 'SARS_RCTG_PERMIT', 
        'FINANCIAL_GUARANTEE_BOND', 'PORT_OPERATOR_LICENSE', 'OTHER',
        name='firm_credential_type_enum',
        create_type=True
    )
    
    id = Column(Integer, primary_key=True, index=True)
    firm_id = Column(Integer, ForeignKey("customs_brokerage_firms.id", ondelete="CASCADE"), nullable=False)
    country_iso = Column(String(2), nullable=False)  # The country that issued the permit
    credential_type = Column(CREDENTIAL_TYPE_ENUM, nullable=False)
    credential_value = Column(String(500), nullable=False)  # The actual license/registration number
    document_url = Column(String(1000), nullable=True)  # Link to scanned certificate
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    verified_by_admin_id = Column(Integer, nullable=True)  # Your platform admin who verified it
    expiry_date = Column(Date, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # Relationships
    firm = relationship("CustomsBrokerageFirm")
    
    __table_args__ = (
        UniqueConstraint("firm_id", "country_iso", "credential_type", name="uq_firm_country_cred_type"),
    )
    
    def __repr__(self):
        return f"<FirmCredential(id={self.id}, firm_id={self.firm_id}, type='{self.credential_type}')>"


class CustomsClearingAgent(Base):
    """Employees of a brokerage firm who work on the platform."""
    __tablename__ = "customs_clearing_agents"
    
    id = Column(Integer, primary_key=True, index=True)
    firm_id = Column(Integer, ForeignKey("customs_brokerage_firms.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Links to your main user table
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    nationality = Column(String, nullable=False)
    id_number = Column(String, nullable=False)
    email = Column(String(150), nullable=False)
    phone_number = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # Relationships
    firm = relationship("CustomsBrokerageFirm")
    # Assuming you have a User model: user = relationship("User")
    
    __table_args__ = (
        UniqueConstraint("firm_id", "user_id", name="uq_firm_user"),
        UniqueConstraint("email", name="uq_agent_email"),
    )
    
    def __repr__(self):
        return f"<CustomsClearingAgent(id={self.id}, name='{self.first_name} {self.last_name}')>"


class CustomsBrokerageFirmServiceArea(Base):
    """Defines where/what services a firm offers"""
    __tablename__ = "customs_brokerage_firm_service_areas"
    
    id = Column(Integer, primary_key=True, index=True)
    firm_id = Column(Integer, ForeignKey("customs_brokerage_firms.id", ondelete="CASCADE"), nullable=False)
    country_iso = Column(String(2), nullable=False)
    border_point = Column(String(150), nullable=False)  # Specific border post, port, or airport
    service_types = Column(JSON, nullable=False, default=list)  # ['IMPORT', 'EXPORT', 'BONDED_TRANSIT']
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    firm = relationship("CustomsBrokerageFirm", back_populates="service_areas")
    
    # Unique constraint
    __table_args__ = (
        UniqueConstraint("firm_id", "country_iso", "border_point", name="uq_firm_country_border"),
    )
    
    def __repr__(self):
        return f"<ServiceArea(id={self.id}, firm_id={self.firm_id}, border='{self.border_point}')>"
