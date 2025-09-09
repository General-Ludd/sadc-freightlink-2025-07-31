from typing import List
from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from db.database import SessionLocal
from models.shipper import Corporation, Consignor
from models.carrier import Carrier
from models.brokerage.finance import FinancialAccounts, Shipment_Invoice, Interim_Invoice, Invoices, CarrierFinancialAccounts, Load_Invoice, Lane_Interim_Invoice, Lane_Invoice
from utils.auth import get_current_user
from utils.administration_auth import verify_admin_password, get_current_admin
from utils.admin_jwt_handler import create_admin_access_token

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/client-financial-account/{id}")
def admin_fetch_shipper_financial_account_information(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == id).first()
        if not financial_account:
            raise HTTPException(status_code=404, detail="Financial account not found")

        company = db.query(Corporation).filter(Corporation.id == financial_account.id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company account not found")

        service_invoices = db.query(Shipment_Invoice).filter(Shipment_Invoice.financial_account_id == financial_account.id).all()
        interim_invoices = db.query(interim_invoice).filter(interim_invoice.financial_account_id == financial_account.id).all()
        lane_invoices = db.query(Invoices).filter(Invoices.financial_account_id == financial_account.id).all()

        return {
            "financial_account_information": {
                "account_id": financial_account.id,
                "company_name": company.legal_business_name,
                "payment_terms": financial_account.payment_terms,
                "years_in_business": financial_account.years_in_business,
                "nature_of_business": financial_account.nature_of_business,
                "annual_turnover": financial_account.annual_turnover,
                "annual_cashflow": financial_account.annual_cash_flow,
                "credit_score": financial_account.credit_score,
                "projected_monthly_bookings": financial_account.projected_monthly_bookings,
                "spending_limit": financial_account.spending_limit,
                "bank_name": financial_account.bank_name,
                "branch_code": financial_account.branch_code,
                "account_number": financial_account.account_number,
                "account_type": financial_account.account_type,
                "total_spent": financial_account.total_spent,
                "average_spend": financial_account.average_spend,
                "total_outstanding": financial_account.total_outstanding,
                "credit_amount": financial_account.credit_balance,
                "total_paid": financial_account.total_paid,
                "paid_invoices": financial_account.num_paid_invoices,
                "outstanding_invoices": financial_account.num_outstanding_invoices,
                "overdue_invoices": financial_account.num_overdue_invoices,
                "ongoing_interim_invoice": financial_account.ongoing_interim_invoices,
                "is_verified": financial_account.is_verified,
                "status": financial_account.status,
                "created_at": financial_account.created_at,
                "financial_invoices": {
                    "account_confirmation_letter": financial_account.account_confirmation_letter,
                    "tax_clearance_certificate": financial_account.tax_clearance_certificate,
                    "audited_financial_statements": financial_account.audited_financial_statement,
                    "bank_statement": financial_account.bank_statement,
                    "business_credit_score_report": financial_account.business_credit_score_report,
                    "surityship": financial_account.suretyship,
                },
            },
            "company_information": {
                "company_id": company.id,
                "type": company.type,
                "legal_business_name": company.legal_business_name,
                "country_of_incorporation": company.country_of_incorporation,
                "business_registration_number": company.business_registration_number,
                "business_address": company.business_address,
                "business_email": company.business_email,
                "business_phone_number": company.business_phone_number,
                "is_verified": company.is_verified,
                "status": company.status,
                "created_at": company.created_at,
                "updated_at": company.updated_at,
                "documents": {
                    "business_registration_certificate": company.business_registration_certificate,
                    "business_proof_of_address": company.business_proof_of_address,
                    "tax_clearance_certificate": company.tax_clearance_certificate,
                },
            },
            "invoices": {
                "service_invoices": [{
                    "id": service_invoice.id,
                    "status": service_invoice.status,
                    "shipment": f"{service_invoice.shipment_id} ({service_invoice.shipment_type})",
                    "billing_date": service_invoice.billing_date,
                    "due_date": service_invoice.due_date,
                    "due_amount": service_invoice.due_amount,
                } for service_invoice in service_invoices],
                "interim_invoices": [{
                    "id": interim_invoice.id,
                    "status": interim_invoice.status,
                    "lane": f"{interim_invoice.shipment_id} ({interim_invoice.shipment_type})",
                    "is_sub_invoices": interim_invoice.is_subinvoice,
                    "due_date": interim_invoice.due_date,
                    "due_amount": interim_invoice.due_amount,
                } for interim_invoice in interim_invoices],
                "lane_invoices": [{
                    "id": lane_invoice.id,
                    "status": lane_invoice.status,
                    "lane": f"{lane_invoice.shipment_id} ({lane_invoice.shipment_type})",
                    "period": f"{lane_invoice.billing_date} - {lane_invoice.due_date}",
                    "due_date": lane_invoice.due_date,
                    "due_amount": lane_invoice.due_amount,
                } for lane_invoice in lane_invoices]
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/finance/carrier-financial-account/{id}")
def admin_get_carrier_financial_account_information(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        financial_account = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.id == id).first()
        if not financial_account:
            raise HTTPException(status_code=404, detail="Financial account not found")
        company = db.query(Carrier).filter(Carrier.id == financial_account.id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company account not found")
        
        service_invoices = db.query(Load_Invoice).filter(Load_Invoice.carrier_financial_account_id == financial_account.id).all()
        interim_invoices = db.query(Lane_Interim_Invoice).filter(Lane_Interim_Invoice.carrier_financial_account_id == financial_account.id).all()
        lane_invoices = db.query(Lane_Invoice).filter(Lane_Invoice.carrier_financial_account_id == financial_account.id).all()

        return {
            "financial_account_information": {
                "account_id": financial_account.id,
                "company_name": financial_account.legal_business_name,
                "bank_name": financial_account.bank_name,
                "bank_country": financial_account.bank_country,
                "branch_code": financial_account.branch_code,
                "account_type": financial_account.account_type,
                "account_number": financial_account.account_number,
                "paid_invoices_amount": financial_account.paid_invoices_amount,
                "outstanding_invoices_amount": financial_account.outstanding_invoices_amount,
                "earned_from_contract_lanes": financial_account.earned_from_contracts,
                "total_number_of_contracts": financial_account.total_contracts,
                "total_shipments_completed": financial_account.total_shipments_completed,
                "total_earned": financial_account.total_earned,
                "holding_balance": financial_account.holding_balance,
                "current_balance": financial_account.current_balance,
                "total_withdrawn": financial_account.total_withdrawn,
                "status": financial_account.status,
                "is_verified": financial_account.is_verified,
                "documents": {
                    "account_confirmation_letter": financial_account.account_confirmation_letter,
                },
            },
            "company_information": {
                "company_id": company.id,
                "type": company.type,
                "legal_business_name": company.legal_business_name,
                "country_of_incorporation": company.country_of_incorporation,
                "business_registration_number": company.business_registration_number,
                "git_policy_insurer": company.name_of_git_cover_insurance_company,
                "git_insurance_policy_number": company.git_insurance_policy_number,
                "git_cover_amount": company.git_cover_amount,
                "liability_policy_insurer": company.name_of_liability_cover_insurance_company,
                "liability_insurance_policy_number": company.liability_insurance_policy_number,
                "liability_cover_amount": company.liability_insurance_cover_amount,
                "business_address": company.business_address,
                "business_email": company.business_email,
                "business_phone_number": company.business_phone_number,
                "number_of_vehicles": company.number_of_vehicles,
                "number_of_trailers": company.number_of_trailers,
                "number_of_drivers": company.number_of_drivers,
                "number_of_shipments_completed": company.number_of_completed_shipments,
                "number_of_completed_lanes": company.number_of_completed_dedicated_lanes,
                "rating": f"{company.rating}/5",
                "number_of_in_progress_lanes": company.number_of_ongoing_dedicated_lanes,
                "is_verified": company.is_verified,
                "status": company.status,
                "created_at": company.created_at,
                "updated_at": company.updated_at,
                "company_documents": {
                    "business_registration_certificate": company.business_registration_certificate,
                    "business_proof_of_address": company.proof_of_address,
                    "brnc_certificate": company.brnc_certificate,
                    "git_insurance_certificate": company.git_insurance_certificate,
                    "liability_insurance_certificate": company.liability_insurance_certificate,                
                },
            },
            "invoices": {
                "service_invoices": [{
                    "id": service_invoice.id,
                    "status": service_invoice.status,
                    "shipment": f"{service_invoice.shipment_id} ({service_invoice.shipment_type})",
                    "is_subinvoice": service_invoice.is_subinvoice,
                    "billing_date": service_invoice.billing_date,
                    "due_date": service_invoice.due_date,
                    "due_amount": service_invoice.due_amount
                } for service_invoice in service_invoices],
                "interim_invoices": [{
                    "id": interim_invoice.id,
                    "status": interim_invoice.status,
                    "lane": f"{interim_invoice.shipment_id} ({interim_invoice.shipment_type})",
                    "is_subinvoice": interim_invoice.is_subinvoice,
                    "is_applied": interim_invoice.is_applied,
                    "due_date": interim_invoice.due_date,
                    "due_amount": interim_invoice.due_amount,
                } for interim_invoice in interim_invoices],
                "lane_invoices": [{
                    "id": lane_invoice.id,
                    "status": lane_invoice.status,
                    "lane": f"{lane_invoice.shipment_id} ({lane_invoice.shipment_type})",
                    "due_date": lane_invoice.due_date,
                    "due_amount": lane_invoice.due_amount,
                } for lane_invoice in lane_invoices]
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))