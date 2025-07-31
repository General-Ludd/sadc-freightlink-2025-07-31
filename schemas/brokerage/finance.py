from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import date, datetime

from enums import PaymentTerms

class VehicleRate(BaseModel):
    id: int
    name: str
    base_rate: float
    weight_factor: float

class BrokerageTransactionCreate(BaseModel):
    shipment_id: int
    booking_amount: int
    platform_commission: int
    transaction_fee: int
    true_platform_earnings: int
    carrier_payout: int
    payment_method: str

class BrokerageTransactionResponse(BrokerageTransactionCreate):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class Shipper_Financial_Account_Create(BaseModel):
    payment_terms: PaymentTerms
    years_in_business: Optional[str] = None
    nature_of_business: Optional[str] = None
    annual_turnover: Optional[int] = None
    annual_cash_flow: Optional[int] = None
    credit_score: Optional[int] = None
    bank_name: Optional[str] = None
    branch_code: Optional[str] = None
    account_number: Optional[int] = None
    account_type: Optional[str] = None
    projected_monthly_bookings: Optional[int] = None
    account_confirmation_letter: Optional[str] = None
    suretyship: Optional[str] = None
    tax_clearance_certificate: Optional[str] = None
    audited_financial_statement: Optional[str] = None
    bank_statement: Optional[str] = None
    business_credit_score_report: Optional[str] = None

class Carrier_FinancialAccount_Create(BaseModel):
    bank_name: str
    branch_code: str
    account_number: int
    account_confirmation_letter: str

class CarrierFinancialAccountResponse(BaseModel):
    id: int
    legal_business_name: str
    business_country_of_incorporation: str
    business_registration_number: str
    business_address: str
    business_email: str
    business_phone_number: str
    directors_first_name: str
    directors_last_name: str
    directors_nationality: str
    directors_id_number: str
    directors_address: str
    directors_phone_number: str
    directors_email_address: str
    bank_name: str
    branch_code: str
    account_number: int
    account_confirmation_letter: str
    paid_invoices_amount: int
    outstanding_invoices_amount: int
    earned_from_contracts: int
    total_contracts: int
    total_shipments_completed: int
    total_earned: int
    holding_balance: int
    current_balance: int
    total_withdrawn: int
    status: str
    is_verified: bool


############################################SHIPPER###########################################
class Shipper_Financial_Account_Response(BaseModel):
    id: int
    payment_terms: str
    company_name: str
    business_country_of_incorporation: str
    business_registration_number: str
    business_address: str
    business_email: str
    business_phone_number: str
    directors_first_name: str
    directors_last_name: str
    directors_nationality: str
    directors_id_number: str
    directors_home_address: str
    directors_phone_number: str
    directors_email_address: str
    years_in_business: Optional[str] = None
    nature_of_business: Optional[str] = None
    annual_turnover: Optional[int] = None
    annual_cash_flow: Optional[int] = None
    credit_score: Optional[int] = None
    bank_name: Optional[str] = None
    branch_code: Optional[str] = None
    account_number: Optional[int] = None
    account_type: Optional[str] = None
    projected_monthly_bookings: Optional[int] = None
    account_confirmation_letter: Optional[str] = None
    suretyship: Optional[str] = None
    tax_clearance_certificate: Optional[str] = None
    audited_financial_statement: Optional[str] = None
    bank_statement: Optional[str] = None
    business_credit_score_report: Optional[str] = None
    total_spent: int
    average_spend: int
    credit_balance: int
    total_outstanding: int
    total_paid: int
    num_paid_invoices: int
    ongoing_interim_invoices: int
    num_outstanding_invoices: int
    num_overdue_invoices: int
    spending_limit: int
    is_verified: bool

class Service_Invoices_Summary_Response(BaseModel):
    id: int
    status: str
    is_subinvoice: bool
    invoice_type: str
    shipment_id: int
    billing_date: date
    due_date: date
    due_amount: int

class Individual_Sevice_Invoices_Request(BaseModel):
    id: int

class Individual_Service_Invoice_Response(BaseModel):
    id: int
    invoice_type: str
    contract_id: Optional [int] = None
    contract_type: Optional [str] = None
    shipment_id: int
    shipment_type: str
    parent_invoice_id: Optional [int] = None  # For sub-invoices ##
    billing_date: date
    is_subinvoice: bool
    due_date: date
    description: str
    status: str
    is_paid: bool
    is_applied: bool

    #Shipper Information
    company_id: int
    financial_account_id: int
    payment_terms: str
    business_name: str
    contact_person_name: str
    business_email: str
    billing_address: str

    #Platform Information
    platform_name: str
    platform_email: str
    platform_address: str
    platform_bank: str
    platform_bank_account: str
    payment_reference: str

    #shipment information
    origin_address: str
    destination_address: str
    pickup_date: date
    distance: int
    transit_time: str

    #Charges
    base_amount: int
    other_surcharges: Optional [int] = None
    late_fees: Optional [int] = None
    vat: Optional [int] = None
    total: int
    due_amount: int
    paid_amount: Optional [int] = None