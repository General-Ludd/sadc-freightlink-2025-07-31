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
from models.brokerage.loadboard import Ftl_Load_Board, Power_Load_Board, Dedicated_lanes_LoadBoard
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Ftl_Lane_LoadBoard
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from schemas.brokerage.finance import Individual_Sevice_Invoices_Request
from schemas.vehicle import Individual_Shipper_Trailer_Response, Shipper_Trailers_Summary_Response, ShipperTrailerCreate
from services.vehicle_service import create_shipper_trailer
from utils.auth import get_current_user
from utils.administration_auth import get_current_admin

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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
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
                    "audited_financial_statements": financial_account.audited_financial_statement,
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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        carrier = db.query(Carrier).filter(Carrier.id == id).first()
        financial_account = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.id == carrier.id).first()
        carrier_users = db.query(CarrierUser).filter(CarrierUser.company_id == carrier.id).all()
        vehicles = db.query(Vehicle).filter(Vehicle.owner_id == carrier.id).all()
        trailers = db.query(Trailer).filter(Trailer.owner_id == carrier.id).all()
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(Assigned_Spot_Ftl_Shipments.carrier_id == carrier.id).all()
        power_shipments = db.query(Assigned_Power_Shipments).filter(Assigned_Power_Shipments.carrier_id == carrier.id).all()
        ftl_lanes = db.query(Assigned_Ftl_Lanes).filter(Assigned_Ftl_Lanes.carrier_id == carrier.id).all()

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
                "number_of_trailers": carrier.number_of_trailers,
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
                "is_director": carrier_user.is_director,
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
            } for trailer in trailers],

            "activity": {
                "shipments": {
                    "ftl_shipments": [{
                        "id": ftl_shipment.shipment_id,
                        "origin": ftl_shipment.origin_city_province,
                        "destination": ftl_shipment.destination_city_province,
                        "distance": ftl_shipment.distance,
                        "status": ftl_shipment.status,
                        "required_truck_type": ftl_shipment.required_truck_type,
                        "equipment_type": ftl_shipment.equipment_type,
                        "trailer_type": ftl_shipment.trailer_type if ftl_shipment.trailer_type else None,
                        "trailer_length": ftl_shipment.trailer_length if ftl_shipment.trailer_length else None,
                        "weight_bracket": ftl_shipment.minimum_weight_bracket,
                        "shipment_weight": ftl_shipment.shipment_weight,
                        "hazardous_materials": ftl_shipment.hazardous_materials,
                        "rate": ftl_shipment.shipment_rate
                    } for ftl_shipment in ftl_shipments],

                    "power_shipments": [{
                        "id": power_shipment.shipment_id,
                        "origin": power_shipment.origin_city_province,
                        "destination": power_shipment.destination_city_province,
                        "distance": power_shipment.distance,
                        "status": power_shipment.status,
                        "required_truck_type": power_shipment.required_truck_type,
                        "axle_configuration": power_shipment.axle_configuration,
                        "weight_bracket": power_shipment.minimum_weight_bracket,
                        "shipment_weight": power_shipment.shipment_weight,
                        "rate": power_shipment.shipment_rate
                    } for power_shipment in power_shipments],
                },
                "lanes": {
                    "ftl_lanes": [{
                        "id": ftl_lane.lane_id,
                        "origin": ftl_lane.origin_city_province,
                        "destination": ftl_lane.destination_city_province,
                        "distance": ftl_lane.distance,
                        "status": ftl_lane.status,
                        "required_truck_type": ftl_lane.required_truck_type,
                        "equipment_type": ftl_lane.equipment_type,
                        "trailer_type": f"{ftl_lane.trailer_type if ftl_lane.trailer_type else None} ({ftl_lane.trailer_length if ftl_lane.trailer_length else None})",
                        "start_date": ftl_lane.start_date,
                        "end_date": ftl_lane.end_date,
                        "recurrence_frequency": ftl_lane.recurrence_frequency,
                        "recurrence_days": ftl_lane.recurrence_days,
                        "shipments_per_interval": ftl_lane.shipments_per_interval,
                        "total_shipments": ftl_lane.total_shipments,
                        "per_shipment_rate": ftl_lane.rate_per_shipment,
                        "contract_rate": ftl_lane.contract_rate
                    } for ftl_lane in ftl_lanes],
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/carrier-financial-account/{id}")
def admin_get_carrier_financial_account(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin)
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
                "number_of_trailers": carrier.number_of_trailers,
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

@router.get("/admin/spot-ftl-loadboard/{id}")
def admin_get_ftl_shipment_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        client_booking_shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == id).first()
        shipment = db.query(Ftl_Load_Board).filter(Ftl_Load_Board.shipment_id == client_booking_shipment.id).first()

        return {
            "shipment_details": {
                "id": shipment.shipment_id,
                "type": shipment.type,
                "load_type": shipment.load_type,
                "trip_type": shipment.trip_type,
                "status": shipment.status,
                "required_truck_type": shipment.required_truck_type,
                "equipment_type": shipment.equipment_type,
                "trailer_type": shipment.trailer_type if shipment.trailer_type else "N/A",
                "trailer_length": shipment.trailer_length if shipment.trailer_length else "N/A",
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "minimum_git_cover_amount": shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": shipment.minimum_liability_cover_amount,
                "origin": shipment.origin_city_province,
                "destination": shipment.destination_city_province,
                "distance": shipment.distance,
                "pickup_date": shipment.pickup_date,
                "eta_data": shipment.eta_date,
                "payment_terms": shipment.payment_terms,
                "payment_date": shipment.payment_date,
                "minimum_transit_time": shipment.estimated_transit_time,
                "route_preview": shipment.route_preview_embed,
                "commodity": shipment.commodity,
                "temperature_control": shipment.temperature_control,
                "hazardous_materails": shipment.hazardous_metarials,
                "packaging_quantity": shipment.packaging_quantity,
                "packaging_type": shipment.packaging_type,
                "pickup_number": shipment.pickup_number,
                "pickup_notes": shipment.pickup_notes,
                "delivery_number": shipment.delivery_number,
                "delivery_notes": shipment.delivery_notes,
            },

            "financial_data": {
                "loadboard_rates": {
                    "rate": shipment.shipment_rate,
                    "rate_per_km": shipment.rate_per_km,
                    "rate_per_ton": shipment.rate_per_ton,
                },
                "booking_rates": {
                    "rate": client_booking_shipment.quote,
                    "rate_per_km": (client_booking_shipment.quote / shipment.distance),
                    "rate_per_ton": (client_booking_shipment.quote / (shipment.minimum_weight_bracket / 1000)),
                },
                "platform_commission": {
                    "commission_rate": client_booking_shipment.quote - shipment.shipment_rate,
                    "commission_rate_per_km": (client_booking_shipment.quote - shipment.shipment_rate) / shipment.distance,
                    "rate_per_ton": (client_booking_shipment.quote - shipment.shipment_rate) / (shipment.minimum_weight_bracket / 1000),
                }
            },

            "pickup_facility": {
                "name": shipment.pickup_facility_name,
                "address": shipment.origin_address,
                "scheduling_type": shipment.pickup_scheduling_type,
                "operating_hours": f"{shipment.pickup_start_time} - {shipment.pickup_end_time}",
                "contact_person": f"{shipment.pickup_first_name} {shipment.pickup_last_name}",
                "phone_number": shipment.pickup_phone_number,
                "email": shipment.pickup_email,
            },
            "delivery_facility": {
                "name": shipment.delivery_facility_name,
                "address": shipment.destination_address,
                "scheduling_type": shipment.delivery_scheduling_type,
                "operating_hours": f"{shipment.delivery_start_time} - {shipment.delivery_end_time}",
                "contact_person": f"{shipment.delivery_first_name} {shipment.delivery_last_name}",
                "phone_number": shipment.delivery_phone_number,
                "email": shipment.delivery_email,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/spot-ftl-lane-loadboard/{id}")
def get_individual_loadboard_ftl_lane(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # Query all records from the "dedicated_lanes_loadboard" table
        client_booking_lane = db.query(FTL_Lane).filter(FTL_Lane.id == id).first()

        lane = db.query(Dedicated_lanes_LoadBoard).filter(Dedicated_lanes_LoadBoard.shipment_id == client_booking_lane.id).first()
        if not lane:
            raise HTTPException(status_code=404, detail="Lane not found")
            
        return {
            "lane_information": {
                "id": lane.shipment_id,
                "status": lane.status,
                "type": lane.type,
                "load_type": lane.load_type,
                "trip_type": lane.trip_type,
                "origin": lane.origin_city_province,
                "destination": lane.destination_city_province,
                "distance": lane.distance,
                "minimum_transit_time": lane.estimated_transit_time,
                "route_preview": lane.route_preview_embed,
                "required_truck_type": lane.required_truck_type,
                "equipment_type": lane.equipment_type,
                "trailer_type": lane.trailer_type if lane.trailer_type else "N/A",
                "trailer_length": lane.trailer_length if lane.trailer_length else "N/A",
                "minimum_weight_bracket": lane.minimum_weight_bracket,
                "average_shipment_weight": lane.average_shipment_weight,
                "minimum_git_cover_amount": lane.minimum_git_cover_amount,
                "minimum_liability_cover_amount": lane.minimum_liability_cover_amount,
                "commodity": lane.commodity,
                "temperature_control": lane.temperature_control,
                "hazardous_materials": lane.hazardous_materials,
                "packaging_quantity": lane.packaging_quantity,
                "packaging_type": lane.packaging_type,
                "pickup_number": lane.pickup_number,
                "pickup_notes": lane.pickup_notes,
                "delivery_number": lane.delivery_number,
                "delivery_notes": lane.delivery_notes,
            },
            "contract_information": {
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "recurrence_frequency": lane.recurrence_frequency,
                "recurrence_days": lane.recurrence_days,
                "slots_per_interval": lane.shipments_per_interval,
                "total_shipments": lane.total_shipments,
                "per_shipment_rate": lane.rate_per_shipment,
                "per_slot_contract_rate": (lane.rate_per_shipment * lane.per_slot_size),
                "distance_per_shipment": lane.distance,
                "rate_per_km": lane.rate_per_km,
                "rate_per_ton": lane.rate_per_ton,
                "payment_terms": lane.payment_terms,
                "shipment_dates": lane.shipment_dates,
                "payment_dates": lane.payment_dates,
                "total_slots": lane.total_slots,
                "available_slots": lane.available_slots,
                "total_shipments_per_slot": lane.per_slot_size,
            },

            # Financial transparency section
            "financial_data": {
                "loadboard_rates": {
                    "rate_per_slot": lane.rate_per_shipment * lane.per_slot_size,
                    "rate_per_shipment": lane.rate_per_shipment,
                    "rate_per_km": lane.rate_per_km,
                    "rate_per_ton": lane.rate_per_ton,
                },
                "client_booking_rates": {
                    "contract_rate": client_booking_lane.contract_quote,
                    "per_slot_rate": client_booking_lane.contract_quote / client_booking_lane.shipments_per_interval,
                    "rate_per_shipment": client_booking_lane.contract_quote,
                    "rate_per_km": client_booking_lane.contract_quote / distance,
                    "rate_per_ton": client_booking_lane.contract_quote / weight,
                },
                "platform_commission": {
                    "commission_per_shipment": client_booking_lane.contract_quote - lane.rate_per_shipment,
                    "commission_per_km": (client_booking_lane.contract_quote - lane.rate_per_shipment) / distance,
                    "commission_per_ton": (client_booking_lane.contract_quote - lane.rate_per_shipment) / weight,
                }
            },

            "pickup_facility": {
                "name": lane.pickup_facility_name,
                "address": lane.origin_address,
                "scheduling_type": lane.pickup_scheduling_type,
                "operating_hours": f"{lane.pickup_start_time} - {lane.pickup_end_time}",
                "contact_person": f"{lane.pickup_first_name} {lane.pickup_last_name}",
                "phone_number": lane.pickup_phone_number,
                "email": lane.pickup_email,
            },
            "delivery_facility": {
                "name": lane.delivery_facility_name,
                "address": lane.destination_address,
                "scheduling_type": lane.delivery_scheduling_type,
                "operating_hours": f"{lane.delivery_start_time} - {lane.delivery_end_time}",
                "contact_person": f"{lane.delivery_first_name} {lane.delivery_last_name}",
                "phone_number": lane.delivery_phone_number,
                "email": lane.delivery_email,
            },
        }
    except Exception as e:
        return {"error": str(e)}