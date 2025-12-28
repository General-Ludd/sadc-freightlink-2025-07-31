from sqlalchemy import Column, Integer, String, Boolean, DECIMAL, Date, Text, JSON, TIMESTAMP, ForeignKey, UniqueConstraint, Index, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from datetime import datetime

# Import Base from your existing models
# from your_database_file import Base

class RouteWaypoint(Base):
    """Stores the analyzed route (border crossings, ports)"""
    __tablename__ = "route_waypoints"
    
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("ftl_shipments.id", ondelete="CASCADE"), nullable=False)
    sequence = Column(Integer, nullable=False)
    country_code = Column(String(2), nullable=False)
    location_name = Column(String(200), nullable=False)  # 'Beitbridge Border Post', 'Durban Harbour'
    waypoint_type = Column(String(50), nullable=False)  # 'ORIGIN', 'DESTINATION', 'BORDER_CROSSING', 'PORT'
    latitude = Column(DECIMAL(9, 6), nullable=True)
    longitude = Column(DECIMAL(9, 6), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # Relationships
    shipment = relationship("FTL_SHIPMENT", back_populates="route_waypoints")
    
    # Index for performance
    __table_args__ = (
        Index("idx_waypoint_shipment_sequence", "shipment_id", "sequence"),
        UniqueConstraint("shipment_id", "sequence", name="uq_shipment_sequence"),
    )
    
    def __repr__(self):
        return f"<RouteWaypoint(id={self.id}, shipment_id={self.shipment_id}, type='{self.waypoint_type}')>"


class ShipmentCustomsEvent(Base):
    """The main table tracking each import/export/transit event"""
    __tablename__ = "shipment_customs_events"
    
    # Define ENUMs for event types and status
    EVENT_TYPE_ENUM = PG_ENUM(
        'EXPORT', 'IMPORT', 'TRANSIT_BOND', 'WAREHOUSE_ENTRY', 'WAREHOUSE_EXIT',
        name='customs_event_type_enum',
        create_type=True
    )
    
    STATUS_ENUM = PG_ENUM(
        'PENDING', 'DOCS_SUBMITTED', 'UNDER_REVIEW', 'CLEARED', 'HELD', 
        'REJECTED', 'CANCELLED',
        name='customs_event_status_enum',
        create_type=True
    )
    
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("ftl_shipments.id", ondelete="CASCADE"), nullable=False)
    sequence = Column(Integer, nullable=False)
    country_code = Column(String(2), nullable=False)
    border_point = Column(String(150), nullable=False)
    event_type = Column(EVENT_TYPE_ENUM, nullable=False)
    status = Column(STATUS_ENUM, default='PENDING', nullable=False)
    
    # Agent assignment
    assigned_firm_id = Column(Integer, ForeignKey("customs_brokerage_firms.id"), nullable=True)
    shipper_handled = Column(Boolean, default=False, nullable=False)
    
    # Timing
    estimated_clearance_date = Column(Date, nullable=True)
    submitted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    cleared_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Financials
    estimated_fee_amount = Column(DECIMAL(12, 2), nullable=True)
    estimated_duty_amount = Column(DECIMAL(12, 2), nullable=True)
    actual_fee_amount = Column(DECIMAL(12, 2), nullable=True)
    actual_duty_amount = Column(DECIMAL(12, 2), nullable=True)
    currency_code = Column(String(3), default='USD', nullable=False)
    
    # References
    declaration_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    shipment = relationship("FTL_SHIPMENT", back_populates="customs_events")
    assigned_firm = relationship("CustomsBrokerageFirm", back_populates="assigned_events")
    documents = relationship("CustomsDocument", back_populates="customs_event", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_customs_event_shipment_status", "shipment_id", "status"),
        Index("idx_customs_event_assigned_firm", "assigned_firm_id", "status"),
        UniqueConstraint("shipment_id", "sequence", name="uq_shipment_event_sequence"),
    )
    
    def __repr__(self):
        return f"<ShipmentCustomsEvent(id={self.id}, shipment_id={self.shipment_id}, type='{self.event_type}')>"


class CustomsDocument(Base):
    """Manages documents for each customs event"""
    __tablename__ = "customs_documents"
    
    DOC_TYPE_ENUM = PG_ENUM(
        'COMMERCIAL_INVOICE', 'PACKING_LIST', 'CERTIFICATE_OF_ORIGIN', 'BILL_OF_LADING',
        'AIR_WAYBILL', 'IMPORT_PERMIT', 'EXPORT_PERMIT', 'CUSTOMS_DECLARATION',
        'INSURANCE_CERTIFICATE', 'OTHER', 'CTN_CERTIFICATE',
        name='customs_document_type_enum',
        create_type=True
    )
    
    id = Column(Integer, primary_key=True, index=True)
    customs_event_id = Column(Integer, ForeignKey("shipment_customs_events.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(DOC_TYPE_ENUM, nullable=False)
    document_name = Column(String(200), nullable=False)
    file_url = Column(String(1000), nullable=False)
    uploaded_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    
    # Relationships
    customs_event = relationship("ShipmentCustomsEvent", back_populates="documents")
    
    def __repr__(self):
        return f"<CustomsDocument(id={self.id}, event_id={self.customs_event_id}, type='{self.document_type}')>"