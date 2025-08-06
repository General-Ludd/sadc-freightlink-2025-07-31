from models.base import Base
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import ARRAY, Date
from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, Float, String, ForeignKey, Enum, DateTime, Boolean, Numeric
from decimal import Decimal

class BillingAnchor(Base):
    __tablename__ = "billing_anchors"

    id = Column(Integer, primary_key=True, index=True)
    payment_term = Column(String, index=True)  # e.g. 'NET 7', 'NET 15', 'EOM'
    anchor_date = Column(DateTime, index=True)  # The date this group of accounts is due
    label = Column(String, nullable=True)  # Optional: e.g. "January EOM", "Week 1", etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)

class VehicleRate(Base):
    __tablename__ = "vehicle_rates"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    base_rate = Column(Integer, nullable=False)
    weight_factor = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

class PlatformCommission(Base):
    __tablename__ = "platform_commissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False) # Spot_FTL, Exchange_FTL, PTL, LTL
    commission = Column(Integer, nullable=False) # 10.0 = 10%
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

class PaymentMethods(Base):
    __tablename__ = "payment_methods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False) # e.g Instant EFT, Credit/Debit Card
    transaction_fee = Column(Integer, nullable=False) # e.g 0.032 = 3.2%, 0.01 = 1%
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    
class BrokerageLedger(Base):
    __tablename__ = "brokerage_ledger"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, nullable=False)
    shipment_status = Column(String, default="Booked", nullable=True)
    pod_document = Column(String, nullable=True)
    shipment_type = Column(String, nullable=False)
    shipper_company_id = Column(Integer)
    shipper_type = Column(String, nullable=False)
    shipper_company_name = Column(String)
    booking_amount = Column(Integer, nullable=False)
    shipment_invoice_id = Column(Integer, nullable=False)
    shipment_invoice_due_date = Column(Date, nullable=False)
    shipment_invoice_status = Column(String, nullable=False)
    platform_commission = Column(Integer, nullable=False)
    transaction_fee = Column(Integer, nullable=False)
    true_platform_earnings = Column(Integer, nullable=False)
    payment_terms = Column(String, nullable=False)
    carrier_id = Column(Integer, nullable=True)
    carrier_company_type = Column(String, nullable=True)
    carrier_company_name = Column(String)
    carrier_payable = Column(Integer, nullable=False)
    load_invoice_id = Column(Integer, nullable=False)
    load_invoice_due_date = Column(Date, nullable=False)
    load_invoice_status = Column(String, nullable=False)
    vehicle_id = Column(Integer, nullable=True)
    vehicle_make = Column(String, nullable=True)
    vehicle_model = Column(String, nullable=True)
    vehicle_year = Column(String, nullable=True)
    vehicle_color = Column(String, nullable=True)
    vehicle_license_plate = Column(String, nullable=True)
    vehicle_vin = Column(String, nullable=True)
    driver_id = Column(Integer, nullable=True)
    driver_first_name = Column(String, nullable=True)
    driver_last_name = Column(String, nullable=True)
    driver_id_number = Column(String, nullable=True)
    driver_license_number = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    brokerage_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

class Dedicated_Lane_BrokerageLedger(Base):
    __tablename__ = "contract_lanes_brokerage_ledger"

    # Contract-Level Details
    id = Column(Integer, primary_key=True, index=True)  # Contract/ledger ID
    shipper_company_id = Column(Integer)
    shipper_company_name = Column(String)
    shipper_type = Column(String)
    shipper_company_registration_number = Column(String)
    shipper_company_country_of_incorporation = Column(String)
    contract_id = Column(Integer, index=True)
    lane_type = Column(String, nullable=False)
    lane_status = Column(String, nullable=False)
    contract_invoice_id = Column(Integer, nullable=False)
    contract_invoice_due_date = Column(Date, nullable=False)
    contract_invoice_status = Column(String, nullable=False)
    contract_booking_amount = Column(Integer, nullable=False)  # Total booking amount for the contract
    contract_platform_commission = Column(Integer, nullable=False)  # Total commission for the contract
    contract_transaction_fee = Column(Integer, nullable=False)  # Total transaction fee for the contract
    contract_true_platform_earnings = Column(Integer, nullable=False)  # Net earnings after transaction fees
    contract_carrier_payable = Column(Integer, nullable=False)  # Total payout to carrier
    payment_terms = Column(String, nullable=False)  # Payment method for the contract
    # Shipment-Level Breakdown (Contract broken into shipments)
    total_shipments = Column(Integer, nullable=False)  # Number of shipments in the contract
    booking_amount_per_shipment = Column(Integer, nullable=False)  # Booking amount per shipment
    platform_commission_per_shipment = Column(Integer, nullable=False)  # Commission per shipment
    transaction_fee_per_shipment = Column(Integer, nullable=False)  # Transaction fee per shipment
    true_platform_earnings_per_shipment = Column(Integer, nullable=False)  # Net earnings per shipment
    carrier_payable_per_shipment = Column(Integer, nullable=False)  # Payout to carrier per shipment
    lane_minimum_git_cover_amount = Column(Integer, nullable=True)
    lane_minimum_liability_cover_amount = Column(Integer, nullable=True)
    payment_dates = Column(ARRAY(Date))
    contract_start_date = Column(Date)
    contract_end_date = Column(Date)
    carrier_id = Column(Integer, nullable=False)
    carrier_company_name = Column(String)
    carrier_company_registration_number = Column(String)
    carrier_country_of_incorporation = Column(String)
    carrier_fleet_size = Column(Integer, nullable=True)
    num_shipments_completed = Column(Integer, default=0)
    carrier_lane_invoice_id = Column(Integer, nullable=False)
    carrier_lane_invoice_due_date = Column(Date, nullable=False)
    carrier_lane_invoice_status = Column(String, nullable=False)
    num_of_invoices_paid = Column(Integer, default=0)
    contract_amount_paid = Column(Integer, default=0)
    carrier_payable_paid = Column(Integer,  default=0)
    platform_commission_generated = Column(Integer)
    accepted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class LateFeeRates(Base):
    __tablename__ = "late_fee_rates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False) #invoices, detention_time, delayed_transit_times
    rate = Column(Integer, nullable=False) # 250
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Payment(Base):
    __tablename__ = "payments_ledger"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer)
    amount = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer)
    company_id = Column(Integer)
    financial_account_id = Column(Integer)
    date_of_booking= Column(Date, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    due_amount = Column(Integer, nullable=True)
    paid_amount = Column(Integer, default=0, nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String)
    late_fees = Column(Integer, default=0, nullable=True)
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Invoices(Base):
    __tablename__ = "invoice"

    id = Column(Integer, primary_key=True, index=True)
    invoice_type = Column(String, default="Contract Lane")
    contract_id = Column(Integer)
    contract_type = Column(String)
    parent_invoice_id = Column(Integer, ForeignKey("invoice.id"), nullable=True)  # For sub-invoices ##
    billing_date = Column(Date)
    due_date = Column(Date, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String)
    is_paid = Column(Boolean, default=False)

    #Shipper Information
    company_id = Column(Integer)
    financial_account_id = Column(Integer)
    payment_terms = Column(String, nullable=True)
    business_name = Column(String)
    contact_person_name = Column(String)
    business_email = Column(String)
    billing_address = Column(String)

    #Platform Information
    platform_name = Column(String, default="SADC FREIGHTLINK")
    platform_email = Column(String, default="billing@sadcfreightlink.com")
    platform_address = Column(String, default="Precent, 1 Bridgeway, Century City, Cape Town, 7441")
    platform_bank = Column(String, default="NEDBANK (RSA)") 
    platform_bank_account = Column(Integer, default=1317232429)
    payment_reference = Column(String)

    #Charges
    base_amount = Column(Integer)
    toll_fees = Column(Integer)
    other_surcharges = Column(Integer)
    vat = Column(Integer)
    total = Column(Integer)
    due_amount = Column(Integer, nullable=True)
    paid_amount = Column(Integer, default=0, nullable=True)
    late_fees = Column(Integer, default=0, nullable=True)
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Interim_Invoice(Base):
    __tablename__ = "interim_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_type = Column(String, default="Interim")
    contract_id = Column(Integer)
    contract_type = Column(String)
    parent_invoice_id = Column(Integer, nullable=True)  # For sub-invoices ##
    billing_date = Column(Date)
    is_subinvoice = Column(Boolean,default=True)
    due_date = Column(Date, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String)
    is_paid = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)

    #Shipper Information
    company_id = Column(Integer)
    financial_account_id = Column(Integer)
    payment_terms = Column(String, nullable=True)
    business_name = Column(String)
    contact_person_name = Column(String)
    business_email = Column(String)
    billing_address = Column(String)

    #Platform Information
    platform_name = Column(String, default="SADC FREIGHTLINK")
    platform_email = Column(String, default="billing@sadcfreightlink.com")
    platform_address = Column(String, default="Precent, 1 Bridgeway, Century City, Cape Town, 7441")
    platform_bank = Column(String, default="NEDBANK (RSA)") 
    platform_bank_account = Column(String, default="1317232429")
    payment_reference = Column(String)

    #Charges
    base_amount = Column(Integer, default=0)
    other_surcharges = Column(Integer, default=0)
    late_fees = Column(Integer, default=0, nullable=True)
    vat = Column(Integer, default=0)
    total = Column(Integer, default=0)
    due_amount = Column(Integer, default=0, nullable=True)
    paid_amount = Column(Integer, default=0, nullable=True)
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Shipment_Invoice(Base):
    __tablename__ = "shipment_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_type = Column(String, default="Service")
    contract_id = Column(Integer)
    contract_type = Column(String)
    shipment_id = Column(Integer)
    shipment_type = Column(String)
    parent_invoice_id = Column(Integer, nullable=True)  # For sub-invoices ##
    billing_date = Column(Date)
    is_subinvoice = Column(Boolean,default=False)
    due_date = Column(Date, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String)
    is_paid = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)

    #Shipper Information
    company_id = Column(Integer)
    financial_account_id = Column(Integer)
    payment_terms = Column(String, nullable=True)
    business_name = Column(String)
    contact_person_name = Column(String)
    business_email = Column(String)
    billing_address = Column(String)

    #Platform Information
    platform_name = Column(String, default="SADC FREIGHTLINK")
    platform_email = Column(String, default="billing@sadcfreightlink.com")
    platform_address = Column(String, default="Precent, 1 Bridgeway, Century City, Cape Town, 7441")
    platform_bank = Column(String, default="NEDBANK (RSA)") 
    platform_bank_account = Column(String, default="1317232429")
    payment_reference = Column(String)

    #shipment information
    origin_address = Column(String)
    destination_address = Column(String)
    pickup_date = Column(Date)
    distance = Column(Integer)
    transit_time = Column(String)

    #Charges
    base_amount = Column(Integer, default=0)
    other_surcharges = Column(Integer, default=0)
    late_fees = Column(Integer, default=0, nullable=True)
    vat = Column(Integer, default=0)
    total = Column(Integer, default=0)
    due_amount = Column(Integer, default=0, nullable=True)
    paid_amount = Column(Integer, default=0, nullable=True)
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Lane_Invoice(Base):
    __tablename__ = "carrier_lane_invoices"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer)
    lane_type = Column(String, nullable=False)
    invoice_type = Column(String)
    billing_date = Column(Date)
    due_date = Column(Date, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String)
    is_paid = Column(Boolean, default=False)

    #Carrier Information
    company_id = Column(Integer)
    carrier_company_name = Column(String)
    business_email = Column(String)
    business_address = Column(String)
    contact_person_name = Column(String)
    carrier_financial_account_id = Column(Integer)
    payment_terms = Column(String, nullable=True)
    carrier_bank = Column(String) 
    carrier_bank_account = Column(Integer)
    payment_reference = Column(String)

    #Charges
    base_amount = Column(Integer)
    toll_fees = Column(Integer)
    other_surcharges = Column(Integer)
    due_amount = Column(Integer, nullable=True)
    paid_amount = Column(Integer, default=0, nullable=True)
    late_fees = Column(Integer, default=0, nullable=True)
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Lane_Interim_Invoice(Base):
    __tablename__ = "carrier_lane_interim_invoices"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer)
    contract_type = Column(String)
    invoice_type = Column(String, default="Interim")
    is_subinvoice = Column(Boolean,default=True)
    parent_invoice_id = Column(Integer, nullable=True) # For sub-invoices ##
    billing_date = Column(Date)
    original_due_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String)
    is_paid = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)

    #Carrier Company Information
    carrier_company_id = Column(Integer)
    carrier_name = Column(String)
    carrier_email = Column(String)
    carrier_address = Column(String)
    carrier_financial_account_id = Column(Integer)
    invoice_payment_terms = Column(String, nullable=True)
    carrier_bank = Column(String) 
    carrier_bank_account = Column(String)
    payment_reference = Column(String)

    #Charges
    base_amount = Column(Integer, default=0)
    other_surcharges = Column(Integer, default=0)
    detention_fees = Column(Integer, default=0, nullable=True)
    due_amount = Column(Integer, default=0, nullable=True)
    paid_out_amount = Column(Integer, default=0, nullable=True)
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Load_Invoice(Base):
    __tablename__ = "carrier_load_invoices"

    id = Column(Integer, primary_key=True, index=True)
    contract_id = Column(Integer)
    contract_type = Column(String)
    shipment_id = Column(Integer)
    shipment_type = Column(String)
    invoice_type = Column(String, default="Load invoice")
    is_subinvoice = Column(Boolean,default=False)
    parent_invoice_id = Column(Integer, nullable=True)  # For sub-invoices ##
    billing_date = Column(Date)
    due_date = Column(Date, nullable=True)
    description = Column(String, nullable=True)
    status = Column(String)
    is_paid = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)

    #Carrier Information
    carrier_company_id = Column(Integer)
    carrier_financial_account_id = Column(Integer)
    carrier_company_name = Column(String)
    payment_terms = Column(String, nullable=True)
    carrier_bank = Column(String) 
    carrier_bank_account = Column(String)
    payment_reference = Column(String)
    contact_person_name = Column(String)
    carrier_email = Column(String)
    carrier_address = Column(String) 

    #shipment information
    origin_address = Column(String)
    destination_address = Column(String)
    pickup_date = Column(Date)
    distance = Column(Integer)
    transit_time = Column(String)

    #Charges
    base_amount = Column(Integer, default=0)
    other_surcharges = Column(Integer, default=0)
    detention_fees = Column(Integer, default=0, nullable=True)
    due_amount = Column(Integer, default=0, nullable=True)
    paid_out_amount = Column(Integer, default=0, nullable=True)
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Invoicea(Base):
    __tablename__ = "invoicea"

    id = Column(Integer, primary_key=True)
    financial_account_id = Column(Integer, ForeignKey("financial_accounts.id"), nullable=False)
    
    parent_invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)  # For sub-invoices
    invoice_type = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    due_date = Column(DateTime, nullable=False)
    description = Column(String, nullable=True)

    status = Column(String)
    is_paid = Column(Boolean, default=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ContractInvoice(Base):
    __tablename__ = "contract_invoices"
    id = Column(Integer, primary_key=True, index=True)
    shipper_company_id = Column(Integer, ForeignKey("shippers.id"))
    invoice_period_start = Column(Date)
    invoice_period_end = Column(Date)
    due_date = Column(Date)
    total_amount = Column(Float)
    payment_terms = Column(String)
    is_paid = Column(Boolean, default=False)

    sub_invoices = relationship("ShipmentSubInvoice", back_populates="parent_invoice")


class ShipmentSubInvoice(Base):
    __tablename__ = "shipment_sub_invoices"
    id = Column(Integer, primary_key=True, index=True)
    parent_invoice_id = Column(Integer, ForeignKey("contract_invoices.id"))
    shipment_id = Column(Integer, ForeignKey("ftl_shipments.id"))
    amount = Column(Float)
    is_paid = Column(Boolean, default=False)
    due_date = Column(Date)

    parent_invoice = relationship("ContractInvoice", back_populates="sub_invoices")


class Contract(Base):
    __tablename__ = "lane_contracts"

    id = Column(Integer, primary_key=True, index=True)
    lane_id = Column(Integer, nullable=False)
    lane_type = Column(Integer, nullable=False)
    shipper_company_id = Column(Integer, nullable=False)
    shipper_country_of_incorporation = Column(String, nullable=False)
    shipper_legal_business_name = Column(String, nullable=False)
    shipper_user_id = Column(Integer, nullable=False)
    director_name = Column(String, nullable=False)
    directors_id_number = Column(Integer, nullable=False)
    start_date = Column(Date)
    end_date = Column(Date)
    recurrence_frequency = Column(String)
    recurrence_days = Column(String)
    total_num_of_shipments = Column(Integer)
    shipments_per_interval = Column(Integer)
    average_weight_per_shipment = Column(Integer)
    shipment_dates = Column(ARRAY(Date), nullable=True)
    minimum_git_cover_amount = Column(Integer)
    minimum_liability_cover_amount = Column(Integer)
    payment_terms = Column(String, nullable=False)
    payment_dates = Column(ARRAY(Date), nullable=True)
    contract_value_amount = Column(Integer, nullable=False)
    platform_commission_amount = Column(Integer, nullable=False)
    carrier_commission_amount = Column(Integer, nullable=False)
    shipper_to_platform_contract_doc = Column(String, nullable=False)
    platform_to_shipper_contract_doc = Column(String, nullable=True)
    platform_to_carrier_contract_doc = Column(String, nullable=True)
    carrier_to_platform_contract_doc = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    carrier_company_id = Column(Integer, nullable=True)
    carrier_country_of_Incorporation = Column(String, nullable=True)
    carrier_legal_business_name = Column(String, nullable=True)
    carrier_director_user_id = Column(Integer, nullable=True)
    carrier_director_name = Column(String, nullable=True)
    carrier_directors_id_number = Column(Integer, nullable=True)
    created_at = Column(Date, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


from enums import InvoiceStatus, InvoiceType, PaymentTerms

class FinancialAccounts(Base):
    __tablename__ = "financial_accounts"

    id = Column(Integer, primary_key=True, index=True)
    payment_terms = Column(Enum(PaymentTerms), nullable=False)
    company_name = Column(String, nullable=False)
    business_country_of_incorporation = Column(String, nullable=False)
    business_registration_number = Column(String, nullable=False)
    business_address = Column(String, nullable=False)
    business_email = Column(String, nullable=False)
    business_phone_number = Column(String, nullable=False)
    directors_first_name = Column(String, nullable=False)
    directors_last_name = Column(String, nullable=False)
    directors_nationality = Column(String, nullable=False)
    directors_id_number = Column(String, nullable=False)
    directors_home_address = Column(String, nullable=False)
    directors_phone_number = Column(String, nullable=False)
    directors_email_address = Column(String, nullable=False)
    years_in_business = Column(String, nullable=True)
    nature_of_business = Column(String, nullable=True)
    annual_turnover = Column(Integer, nullable=True)
    annual_cash_flow = Column(Integer, nullable=True)
    credit_score = Column(Integer, nullable=True)
    bank_name = Column(String, nullable=True)
    branch_code = Column(String, nullable=True)
    account_number = Column(Integer, nullable=True)
    account_type = Column(String, nullable=True)
    projected_monthly_bookings = Column(Integer, default=0, nullable=True)
    account_confirmation_letter = Column(String, nullable=True)
    tax_clearance_certificate = Column(String, nullable=True)
    audited_financial_statement = Column(String, nullable=True)
    bank_statement = Column(String, nullable=True)
    business_credit_score_report = Column(String, nullable=True)
    suretyship = Column(String, nullable=True)
    total_spent = Column(Integer, default=0)
    average_spend = Column(Integer, default=0)
    credit_balance = Column(Integer, default=0)
    total_outstanding = Column(Integer, default=0)
    total_paid = Column(Integer, default=0)
    num_paid_invoices = Column(Integer, default=0)
    ongoing_interim_invoices = Column(Integer, default=0)
    num_outstanding_invoices = Column(Integer, default=0)
    num_overdue_invoices = Column(Integer, default=0)
    spending_limit = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)
    status = Column(Enum("Un-verified", "Active", "Under Investigation", "Suspended", "Deleted"), default="Un-verified") #Update in Database
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class CarrierFinancialAccounts(Base):
    __tablename__ = "carrier_financial_accounts"

    id = Column(Integer, primary_key=True, index=True)
    legal_business_name = Column(String, nullable=False)
    business_country_of_incorporation = Column(String, nullable=False)
    business_registration_number = Column(String, nullable=False)
    business_address = Column(String, nullable=False)
    business_email = Column(String, nullable=False)
    business_phone_number = Column(String, nullable=False)
    directors_first_name = Column(String, nullable=False)
    directors_last_name = Column(String, nullable=False)
    directors_nationality = Column(String, nullable=False)
    directors_id_number = Column(String, nullable=False)
    directors_address = Column(String, nullable=False)
    directors_phone_number = Column(String, nullable=False)
    directors_email_address = Column(String, nullable=False)
    bank_name = Column(String, nullable=True)
    branch_code = Column(String, nullable=True)
    account_number = Column(Integer, nullable=True)
    account_confirmation_letter = Column(String, nullable=True)
    paid_invoices_amount = Column(Integer, default=0)
    outstanding_invoices_amount = Column(Integer, default=0)
    earned_from_contracts = Column(Integer, default=0)
    total_contracts = Column(Integer, default=0)
    total_shipments_completed = Column(Integer, default=0)
    total_earned = Column(Integer, default=0)
    holding_balance = Column(Integer, default=0)
    current_balance = Column(Integer, default=0)
    total_withdrawn = Column(Integer, default=0)
    status = Column(Enum("Un-verified", "Active", "Under Investigation", "Suspended", "Deleted"), default="Un-verified") #Update in Database
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class PlatformCreditAccount(Base):
    __tablename__ = "platform_account"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    registration_number = Column(String, nullable=False)
    address = Column(String, nullable=False)
    bank_name = Column(String, nullable=True)
    branch_code = Column(String, nullable=True)
    account_number = Column(Integer, nullable=True)
    account_confirmation_letter = Column(String, nullable=True)
    current_credit_balance = Column(Integer, default=0)
    total_outstanding = Column(Integer, default=0)
    total_settled = Column(Integer, default=0)

class PlatformEscrowAccount(Base):
    __tablename__ = "platform_escrow_account"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, nullable=False)
    registration_number = Column(String, nullable=False)
    address = Column(String, nullable=False)
    bank_name = Column(String, nullable=True)
    branch_code = Column(String, nullable=True)
    account_number = Column(Integer, nullable=True)
    account_confirmation_letter = Column(String, nullable=True)
    current_balance = Column(Integer, default=0)
    total_earned = Column(Integer, default=0)
    total_withdrawn = Column(Integer, default=0)

class Spot_Escrow(Base):
    __tablename__ = "escrow"

    id = Column(Integer, primary_key=True, index=True)
    escrow_status = Column(Enum("In Escrow", "Released"), default="In Escrow")
    shipment_id = Column(Integer, index=True)
    shipper_invoice_id = Column(Integer, index=True)
    shipper_invoice_status = Column(String, nullable=False)
    shipment_status = Column(Enum("In Progress", "Complete", "Disputed"), default="In Progress")
    amount = Column(Integer, primary_key=True, index=True)
    recepient_carrier_invoice_id = Column(Integer, index=True)
    recepient_carrier_invoice_status = Column(String, nullable=False)
    recepient_carrier_financial_account_id = Column(Integer, index=True)
    recepient_carrier_id = Column(Integer, index=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, nullable=False, index=True)
    type = Column(String, nullable=False)
    amount = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    

class BrokerageCommission(Base):
    __tablename__ = "brokerage_commissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # e.g., "ltl", "ftl"
    type = Column(String, nullable=False) # e.g., "Brokerage", "Exchange"
    commission_rate = Column(Float, nullable=False)  # Percentage rate
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class Withdrawal_Request(Base):
    __tablename__ = "withdrawal_requests"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum("Standard Withdrawal", "Expedited Withdrawal"), default="Standard Withdrawal")
    carrier_company_name = Column(String, nullable=False)
    financial_account_id = Column(Integer, index=True)
    financial_account_current_balance = Column(Integer)
    bank_name = Column(String, nullable=False)
    bank_country = Column(String, nullable=False)
    branch_code = Column(String, nullable=False)
    bank_account_number = Column(String, nullable=False)
    requested_amount = Column(Integer)
    withdrawal_fee = Column(Integer)
    to_be_paid_out = Column(Integer)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())