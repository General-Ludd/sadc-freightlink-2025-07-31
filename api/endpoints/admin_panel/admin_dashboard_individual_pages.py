from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from db.database import SessionLocal
from models.shipper import Corporation
from models.user import Director, CarrierUser, Driver
from models.carrier import Carrier
from models.vehicle import Vehicle, Trailer, ShipperTrailer
from models.brokerage.finance import FinancialAccounts, CarrierFinancialAccounts, Withdrawal_Request, Shipment_Invoice, Interim_Invoice, Invoices
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from schemas.brokerage.finance import Individual_Sevice_Invoices_Request
from schemas.vehicle import Individual_Shipper_Trailer_Response, Shipper_Trailers_Summary_Response, ShipperTrailerCreate
from services.vehicle_service import create_shipper_trailer
from utils.auth import get_current_user

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/admin/shipper-company/{id}")
def admin_get_shipper_company_id(
    id: int,
    db: Session = Depends(get_db)
):
    try:
        shipper_company = db.query(Corporation).filter(Corporation.id == id).first()
        financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == shipper_company.id).first()
        shipper_users = db.query(Director).filter(Director.company_id == shipper_company.id).all()
        
        return {
            "company_information": {
                "company_id": shipper_company.id,
                "type": shipper_company.type,
                "legal_business_name": shipper_company.legal_business_name,
                "country_of_incorporation": shipper_company.country_of_incorporation,
                "business_registration_number": shipper_company.business_registration_number,
                "business_address": shipper_company.business_address,
                "business_email": shipper_company.business_email,
                "business_phone_number": shipper_company.business_phone_number,
                "is_verified": shipper_company.is_verified,
                "status": shipper_company.status,
                "created_at": shipper_company.created_at,
                "updated_at": shipper_company.updated_at,
                "company_documents": {
                    "business_registration_certificate": shipper_company.business_registration_certificate,
                    "business_proof_of_address": shipper_company.business_proof_of_address,
                    "tax_clearance_certificate": shipper_company.tax_clearance_certificate
                }
            },

            "financial_account": {
                "account_id": financial_account.id,
                "company_name": financial_account.company_name,
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
                "credit_balance": financial_account.credit_balance,
                "total_paid": financial_account.total_paid,
                "paid_invoices": financial_account.num_paid_invoices,
                "outstanding_invoices": financial_account.num_outstanding_invoices,
                "over_due_invoices": financial_account.num_overdue_invoices,
                "ongoing_interim_invoices": financial_account.ongoing_interim_invoices,
                "verification_status": financial_account.is_verified,
                "status": financial_account.status,
                "created_at": financial_account.created_at,
                "financial_account_documents": {
                    "account_confirmation_letter": financial_account.account_confirmation_letter,
                    "bank_statement": financial_account.bank_statement,
                    "tax_clearance_certificate": financial_account.tax_clearance_certificate,
                    "business_credit_score_report": financial_account.business_credit_score_report,
                    "audited_financial_statements": financial_account.audited_financial_statements,
                    "surityship": financial_account.suretyship
                }
            },

            "users": [{
                "name": f"{shipper_user.first_name} - {shipper_user.last_name}",
                "id": shipper_user.id,
                "id_number": shipper_user.id_number,
                "is_director": shipper_user.is_director,
                "verification_status": shipper_user.is_verified,
                "status": shipper_user.status
            } for shipper_user in shipper_users]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/financial-account/{id}")
def admin_get_shipper_and_broker_financial_account_id(
    id: int,
    db: Session = Depends(get_db)
):
    try:
        financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == id).first()
        shipper_company = db.query(Corporation).filter(Corporation.id == financial_account.id).first()
        service_invoices = db.query(Shipment_Invoice).filter(Shipment_Invoice.financial_account_id == financial_account.id).all()
        interim_invoices = db.query(Interim_Invoice).filter(Interim_Invoice.financial_account_id == financial_account.id).all()
        lane_invoices = db.query(Invoices).filter(Invoices.financial_account_id == financial_account.id).all()

        return {
            "financial_account": {
                "account_id": financial_account.id,
                "company_name": financial_account.company_name,
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
                "credit_balance": financial_account.credit_balance,
                "total_paid": financial_account.total_paid,
                "paid_invoices": financial_account.num_paid_invoices,
                "outstanding_invoices": financial_account.num_outstanding_invoices,
                "over_due_invoices": financial_account.num_overdue_invoices,
                "ongoing_interim_invoices": financial_account.ongoing_interim_invoices,
                "verification_status": financial_account.is_verified,
                "status": financial_account.status,
                "created_at": financial_account.created_at,
                "financial_account_documents": {
                    "account_confirmation_letter": financial_account.account_confirmation_letter,
                    "bank_statement": financial_account.bank_statement,
                    "tax_clearance_certificate": financial_account.tax_clearance_certificate,
                    "business_credit_score_report": financial_account.business_credit_score_report,
                    "audited_financial_statements": financial_account.audited_financial_statements,
                    "surityship": financial_account.suretyship
                }
            },

            "company_information": {
                "company_id": shipper_company.id,
                "type": shipper_company.type,
                "legal_business_name": shipper_company.legal_business_name,
                "country_of_incorporation": shipper_company.country_of_incorporation,
                "business_registration_number": shipper_company.business_registration_number,
                "business_address": shipper_company.business_address,
                "business_email": shipper_company.business_email,
                "business_phone_number": shipper_company.business_phone_number,
                "is_verified": shipper_company.is_verified,
                "status": shipper_company.status,
                "created_at": shipper_company.created_at,
                "updated_at": shipper_company.updated_at,
                "company_documents": {
                    "business_registration_certificate": shipper_company.business_registration_certificate,
                    "business_proof_of_address": shipper_company.business_proof_of_address,
                    "tax_clearance_certificate": shipper_company.tax_clearance_certificate
                }
            },

            "service_invoices": [{
                "id": service_invoice.id,
                "shipment": f"{service_invoice.shipment_type}-{service_invoice.shipment_id}",
                "is_sub_invoice": service_invoice.is_subinvoice,
                "billing_date": service_invoice.billing_date,
                "due_date": service_invoice.due_date,
                "description": service_invoice.description,
            } for service_invoice in service_invoices],

            "interim_invoices": [{
                "id": interim_invoice.id,
                "status": interim_invoice.status,
                "lane": f"{interim_invoice.lane_type}-{interim_invoice.lane_id}",
                "is_applied": interim_invoice.is_applied,
                "is_sub_invoice": interim_invoice.is_subinvoice,
                "due_date": interim_invoice.due_date,
                "due_amount": interim_invoice.due_amount,
                "description": interim_invoice.description
            } for interim_invoice in interim_invoices],

            "lane_invoices": [{
                "id": lane_invoice.id,
                "status": lane_invoice.status,
                "lane": f"{lane_invoice.lane_type}-{lane_invoice.lane_id}",
                "due_date": lane_invoice.due_date,
                "amount": lane_invoice.due_amount,
                "description": lane_invoice.description
            } for lane_invoice in lane_invoices]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/carrier-company/{id}")
def admin_get_carrier_company_id(
    id: int,
    db: Session = Depends(get_db)
):
    try:
        carrier = db.query(Carrier).filter(Carrier.id == id).first()
        financial_account = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.id == carrier.id).first()
        carrier_users = db.query(CarrierUser).filter(CarrierUser.company_id == carrier.id).all()
        vehicles = db.query(Vehicle).filter(Vehicle.owner_id == carrier.id).all()
        trailers = db.query(Trailer).filter(Trailer.owner_id == carrier.id).all()

        return {
            "company_information": {
                "company_id": carrier.id,
                "type": carrier.type,
                "legal_business_name": carrier.legal_business_name,
                "country_of_incorporation": carrier.country_of_incorporation,
                "business_registration_number": carrier.business_registration_number,
                "git_policy_insurer": carrier.name_of_git_cover_insurance_company,
                "git_insurance_policy_number": carrier.git_insurance_policy_number,
                "git_cover_amount": carrier.git_cover_amount,
                "liability_policy_insurer": carrier.name_of_liability_cover_insurance_company,
                "liability_insurance_policy_number": carrier.liability_insurance_policy_number,
                "liability_cover_amount": carrier.liability_insurance_cover_amount,
                "business_address": carrier.business_address,
                "business_email": carrier.business_email,
                "business_phone_number": carrier.business_phone_number,
                "number_of_vehicles": carrier.number_of_vehicles,
                "number_of_trailers": carrer.number_of_trailers,
                "number_of_drivers": carrier.number_of_drivers,
                "number_of_completed_shipments": carrier.number_of_completed_shipments,
                "number_of_completed_lanes": carrier.number_of_completed_dedicated_lanes,
                "number_of_in_progress_lane": carrier.number_of_ongoing_dedicated_lanes,
                "rating": carrier.rating,
                "verification_status": carrier.is_verified,
                "status": carrier.status,
                "created_at": carrier.created_at,
                "updated_at": carrier.updated_at,
                "company_documents": {
                    "business_registration_certificate": carrier.business_registration_certificate,
                    "git_insurance_certificate": carrier.git_insurance_certificate,
                    "business_proof_of_address": carrier.proof_of_address,
                    "liability_insurance_certificate": carrier.liability_insurance_certificate,
                }
            },

            "financial_account_information": {
                "id": financial_account.id,
                "company_name": financial_account.legal_business_name,
                "bank_name": financial_account.bank_name,
                "branch_code": financial_account.branch_code,
                "account_number": financial_account.account_number,
                "paid_invoices_amount": financial_account.paid_invoices_amount,
                "outstanding_invoices": financial_account.outstanding_invoices_amount,
                "earned_from_contract_lanes": financial_account.earned_from_contracts,
                "total_number_of_contracts": financial_account.total_contracts,
                "total_shipments_completed": financial_account.total_shipments_completed,
                "total_earned": financial_account.total_earned,
                "holding_balance": financial_account.holding_balance,
                "current_balance": financial_account.current_balance,
                "total_withdrawn": financial_account.total_withdrawn,
                "status": financial_account.status,
                "verification_status": financial_account.is_verified,
                "created_at": financial_account.created_at,
                "updated_at": financial_account.updated_at,
                "financial_account_documents": {
                    "account_confirmation_letter": financial_account.account_confirmation_letter
                }
            },

            "users": [{
                "name": f"{carrier_user.first_name} - {carrier_user.last_name}",
                "id": carrier_user.id,
                "company_id": carrier_user.company_id,
                "role": carrier_user.role,
                "nationality": carrier_user.nationality,
                "id_number": carrier_user.id_number,
                "position": carrier_user.is_director,
                "verification_status": carrier_user.is_verified,
                "status": carrier_user.status,
            } for carrier_user in carrier_users],

            "vehicles": [{
                "make_and_year": f"{vehicle.make}-{vehicle.year}",
                "id": vehicle.id,
                "color": vehicle.color,
                "type": vehicle.type,
                "axle_configuration": vehicle.axle_configuration,
                "equipment_type": vehicle.equipment_type,
                "payload_capacity": vehicle.payload_capacity,
                "trailer_type": vehicle.trailer_type,
                "trailer_length": vehicle.trailer_length,
                "company_id": vehicle.owner_id,
                "verification_status": vehicle.is_verified,
                "status": vehicle.status
            } for vehicle in vehicles],

            "trailers": [{
                "make_and_model": f"{trailer.make}-{trailer.model}",
                "id": trailer.id,
                "company_id": trailer.owner_id,
                "year": trailer.year,
                "color": trailer.color,
                "license_plate": trailer.license_plate,
                "payload_capacity": trailer.payload_capacity,
                "vehicle_id": trailer.vehicle_id,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "verification_status": trailer.verification_status,
                "staus": trailer.status
            } for trailer in trailers]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/carrier-financial-account/{id}")
def admin_get_carrier_financial_account(
    id: int,
    db: Session = Depends(get_db)
):
    try:
        financial_account = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.id == id).first()
        carrier = db.query(Carrier).filter(Carrier.id == financial_account.id).first()
        service_invoices = db.query(Load_Invoice).filter(Load_Invoice.carrier_financial_account_id == financial_account.id).all()
        interim_invoices = db.query(Lane_Interim_Invoice).filter(Lane_Interim_Invoice.carrier_financial_account_id == financial_account.id).all()
        lane_invoices = db.query(Lane_Invoice).filter(Lane_Invoice.company_id == financial_account.id).all()

        return {
            "financial_account_information": {
                "id": financial_account.id,
                "company_name": financial_account.legal_business_name,
                "bank_name": financial_account.bank_name,
                "branch_code": financial_account.branch_code,
                "account_number": financial_account.account_number,
                "paid_invoices_amount": financial_account.paid_invoices_amount,
                "outstanding_invoices": financial_account.outstanding_invoices_amount,
                "earned_from_contract_lanes": financial_account.earned_from_contracts,
                "total_number_of_contracts": financial_account.total_contracts,
                "total_shipments_completed": financial_account.total_shipments_completed,
                "total_earned": financial_account.total_earned,
                "holding_balance": financial_account.holding_balance,
                "current_balance": financial_account.current_balance,
                "total_withdrawn": financial_account.total_withdrawn,
                "status": financial_account.status,
                "verification_status": financial_account.is_verified,
                "created_at": financial_account.created_at,
                "updated_at": financial_account.updated_at,
                "financial_account_documents": {
                    "account_confirmation_letter": financial_account.account_confirmation_letter
                }
            },

            "company_information": {
                "company_id": carrier.id,
                "type": carrier.type,
                "legal_business_name": carrier.legal_business_name,
                "country_of_incorporation": carrier.country_of_incorporation,
                "business_registration_number": carrier.business_registration_number,
                "git_policy_insurer": carrier.name_of_git_cover_insurance_company,
                "git_insurance_policy_number": carrier.git_insurance_policy_number,
                "git_cover_amount": carrier.git_cover_amount,
                "liability_policy_insurer": carrier.name_of_liability_cover_insurance_company,
                "liability_insurance_policy_number": carrier.liability_insurance_policy_number,
                "liability_cover_amount": carrier.liability_insurance_cover_amount,
                "business_address": carrier.business_address,
                "business_email": carrier.business_email,
                "business_phone_number": carrier.business_phone_number,
                "number_of_vehicles": carrier.number_of_vehicles,
                "number_of_trailers": carrer.number_of_trailers,
                "number_of_drivers": carrier.number_of_drivers,
                "number_of_completed_shipments": carrier.number_of_completed_shipments,
                "number_of_completed_lanes": carrier.number_of_completed_dedicated_lanes,
                "number_of_in_progress_lane": carrier.number_of_ongoing_dedicated_lanes,
                "rating": carrier.rating,
                "verification_status": carrier.is_verified,
                "status": carrier.status,
                "created_at": carrier.created_at,
                "updated_at": carrier.updated_at,
                "company_documents": {
                    "business_registration_certificate": carrier.business_registration_certificate,
                    "git_insurance_certificate": carrier.git_insurance_certificate,
                    "business_proof_of_address": carrier.proof_of_address,
                    "liability_insurance_certificate": carrier.liability_insurance_certificate,
                }
            },

            "service_invoices": [{
                "id": service_invoice.id,
                "status": service_invoice.status,
                "shipment": f"{service_invoice.shipment_type} - {service_invoice.shipment_id}",
                "is_sub_invoice": service_invoice.is_subinvoice,
                "billing_date": service_invoice.billing_date,
                "due_date": service_invoice.due_date,
                "due_amount": service_invoice.due_amount,
                "description": service_invoice.description,
            } for service_invoice in service_invoices],

            "interim_invoices": [{
                "id": interim_invoice.id,
                "status": interim_invoice.status,
                "lane": f"{interim_invoice.contract_type}-{interim_invoice.contract_id}",
                "is_applied": interim_invoice.is_applied,
                "is_sub_invoice": interim_invoice.is_subinvoice,
                "due_date": interim_invoice.due_date,
                "due_amount": interim_invoice.due_amount,
                "description": interim_invoice.description
            } for interim_invoice in interim_invoices],

            "lane_invoices": [{
                "id": lane_invoice.id,
                "status": lane_invoice.status,
                "lane": f"{lane_invoice.lane_type}-{lane_invoice.contract_id}",
                "due_date": lane_invoice.due_date,
                "amount": lane_invoice.due_amount,
                "description": lane_invoice.description
            } for lane_invoice in lane_invoices],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
