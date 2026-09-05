from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from db.database import SessionLocal
from models.shipper import Corporation, Consignor
from models.user import Director, CarrierUser, Driver
from models.carrier import Carrier
from models.vehicle import Vehicle, Vehicle_Schedule, Trailer, ShipperTrailer
from models.brokerage.finance import FinancialAccounts, CarrierFinancialAccounts, Withdrawal_Request, Shipment_Invoice, Interim_Invoice, Invoices
from models.spot_bookings.dedicated_lane_ftl_shipment import Client_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.brokerage.loadboard import Ftl_Load_Board, Power_Load_Board, Dedicated_lanes_LoadBoard
from models.Exchange.auction import Exchange_FTL_Shipment_Bid, Exchange_FTL_Lane_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Ftl_Lane_LoadBoard
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from models.spot_bookings.shipment_facility import ShipmentFacility, ContactPerson
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
        if not shipper_company:
            raise HTTPException(status_code=404, detail="Shipper company not found")

        financial_account = (
            db.query(FinancialAccounts)
            .filter(FinancialAccounts.id == shipper_company.id)
            .first()
        )

        shipper_users = (
            db.query(Director)
            .filter(Director.company_id == shipper_company.id)
            .all()
        )

        ftl_shipments = (
            db.query(Client_Shipment)
            .filter(Client_Shipment.client_id == shipper_company.id)
            .all()
        )

        ftl_lanes = (
            db.query(Client_Lane)
            .filter(Client_Lane.client_id == shipper_company.id)
            .all()
        )

        shipment_data = []

        for shipment in ftl_shipments:
            stops = (
                db.query(Client_Shipment_Stop)
                .filter(Client_Shipment_Stop.shipment_id == shipment.id)
                .order_by(Client_Shipment_Stop.stop_sequence.asc())
                .all()
            )

            configs = (
                db.query(Client_Shipment_Vehicle_Requirement)
                .filter(
                    Client_Shipment_Vehicle_Requirement.shipment_id == shipment.id
                )
                .all()
            )

            origin = stops[0] if stops else None
            destination = stops[-1] if stops else None

            shipment_data.append({
                "id": shipment.id,
                "shipment_reference": shipment.shipment_reference,
                "booking_reference": shipment.booking_reference,
                "origin": (
                    origin.city_province
                    if origin
                    else None
                ),
                "destination": (
                    destination.city_province
                    if destination
                    else None
                ),
                "distance": shipment.distance,
                "status": shipment.status,
                "trip_status": shipment.trip_status,
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
                "pickup_date": shipment.pickup_date,

                "required_equipment": [
                    {
                        "configuration_type": config.configuration_type,
                        "truck_type": config.truck_type,
                        "equipment_type": config.equipment_type,
                        "trailer_type": config.trailer_type,
                        "trailer_length": config.trailer_length
                    }
                    for config in configs
                ],

                "weight_bracket": shipment.minimum_weight_bracket_kg,
                "shipment_weight": shipment.shipment_weight,
                "hazardous_materials": shipment.hazardous_materials,
                "commodity": shipment.commodity,
                "rate": shipment.rate
            })

        lane_data = []

        for lane in ftl_lanes:
            lane_data.append({
                "id": lane.id,
                "origin": getattr(lane, "origin_city_province", None),
                "destination": getattr(lane, "destination_city_province", None),
                "distance": lane.distance,
                "status": lane.status,
                "required_truck_type": getattr(lane, "required_truck_type", None),
                "equipment_type": getattr(lane, "equipment_type", None),
                "trailer_type": getattr(lane, "trailer_type", None),
                "trailer_length": getattr(lane, "trailer_length", None),
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "recurrence_frequency": lane.recurrence_frequency,
                "recurrence_days": lane.recurrence_days,
                "shipments_per_interval": lane.shipments_per_interval,
                "total_shipments": lane.total_shipments,
                "per_shipment_rate": lane.qoute_per_shipment,
                "contract_rate": lane.contract_quote
            })

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
                "account_id": financial_account.id if financial_account else None,
                "company_name": financial_account.company_name if financial_account else None,
                "payment_terms": financial_account.payment_terms if financial_account else None,
                "years_in_business": financial_account.years_in_business if financial_account else None,
                "nature_of_business": financial_account.nature_of_business if financial_account else None,
                "annual_turnover": financial_account.annual_turnover if financial_account else None,
                "annual_cashflow": financial_account.annual_cash_flow if financial_account else None,
                "credit_score": financial_account.credit_score if financial_account else None,
                "projected_monthly_bookings": financial_account.projected_monthly_bookings if financial_account else None,
                "spending_limit": financial_account.spending_limit if financial_account else None,
                "bank_name": financial_account.bank_name if financial_account else None,
                "branch_code": financial_account.branch_code if financial_account else None,
                "account_number": financial_account.account_number if financial_account else None,
                "account_type": financial_account.account_type if financial_account else None,
                "total_spent": financial_account.total_spent if financial_account else None,
                "average_spend": financial_account.average_spend if financial_account else None,
                "total_outstanding": financial_account.total_outstanding if financial_account else None,
                "credit_balance": financial_account.credit_balance if financial_account else None,
                "total_paid": financial_account.total_paid if financial_account else None,
                "paid_invoices": financial_account.num_paid_invoices if financial_account else None,
                "outstanding_invoices": financial_account.num_outstanding_invoices if financial_account else None,
                "over_due_invoices": financial_account.num_overdue_invoices if financial_account else None,
                "ongoing_interim_invoices": financial_account.ongoing_interim_invoices if financial_account else None,
                "verification_status": financial_account.is_verified if financial_account else None,
                "status": financial_account.status if financial_account else None,
                "created_at": financial_account.created_at if financial_account else None,
                "financial_account_documents": {
                    "account_confirmation_letter": financial_account.account_confirmation_letter if financial_account else None,
                    "bank_statement": financial_account.bank_statement if financial_account else None,
                    "tax_clearance_certificate": financial_account.tax_clearance_certificate if financial_account else None,
                    "business_credit_score_report": financial_account.business_credit_score_report if financial_account else None,
                    "surityship": financial_account.suretyship if financial_account else None
                }
            },

            "users": [
                {
                    "name": f"{user.first_name} - {user.last_name}",
                    "id": user.id,
                    "id_number": user.id_number,
                    "is_director": user.is_director,
                    "verification_status": user.is_verified,
                    "status": user.status
                }
                for user in shipper_users
            ],

            "activity": {
                "shipments": {
                    "ftl_shipments": shipment_data
                },
                "lanes": {
                    "ftl_lanes": lane_data
                }
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/brokerage-firm/{id}")
def admin_get_brokergae_firm_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        shipper_company = db.query(Corporation).filter(Corporation.id == id).first()
        financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == shipper_company.id).first()
        shipper_users = db.query(Director).filter(Director.company_id == shipper_company.id).all()
        ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_company_id == shipper_company.id).all()
        power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipper_company_id == shipper_company.id).all()
        ftl_lanes = db.query(FTL_Lane).filter(FTL_Lane.shipper_company_id == shipper_company.id).all()
        clients = db.query(Consignor).filter(Consignor.brokerage_firm_id == shipper_company.id).all()
        
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
            } for shipper_user in shipper_users],

            "clients": [{
                "id": client.id,
                "company_name": client.company_name,
                "client_type": client.client_type,
                "business_sector": client.business_sector,
                "business_address": client.business_address,
                "contact_person": client.contact_person_name,
                "contact_person_position": client.position,
                "phone_number": client.phone_number,
                "email": client.email,
                "preferred_contact_method": clienet.preferred_contact_method,
                "shipments": client.shipments,
                "lane": client.contract_lanes,
                "revenue_generated": client.revenue_generated
            } for client in clients],

            "activity": {
                "shipments": {
                    "ftl_shipments": [{
                        "id": ftl_shipment.id,
                        "origin": ftl_shipment.origin_city_province,
                        "destination": ftl_shipment.destination_city_province,
                        "distance": ftl_shipment.distance,
                        "status": ftl_shipment.shipment_status,
                        "required_truck_type": ftl_shipment.required_truck_type,
                        "equipment_type": ftl_shipment.equipment_type,
                        "trailer_type": ftl_shipment.trailer_type if ftl_shipment.trailer_type else None,
                        "trailer_length": ftl_shipment.trailer_length if ftl_shipment.trailer_length else None,
                        "weight_bracket": ftl_shipment.minimum_weight_bracket,
                        "shipment_weight": ftl_shipment.shipment_weight,
                        "hazardous_materials": ftl_shipment.hazardous_materials,
                        "rate": ftl_shipment.quote
                    } for ftl_shipment in ftl_shipments],

                    "power_shipments": [{
                        "id": power_shipment.id,
                        "origin": power_shipment.origin_city_province,
                        "destination": power_shipment.destination_city_province,
                        "distance": power_shipment.distance,
                        "status": power_shipment.status,
                        "required_truck_type": power_shipment.required_truck_type,
                        "axle_configuration": power_shipment.axle_configuration,
                        "weight_bracket": power_shipment.minimum_weight_bracket,
                        "shipment_weight": power_shipment.shipment_weight,
                        "rate": power_shipment.quote
                    } for power_shipment in power_shipments],
                },
                "lanes": {
                    "ftl_lanes": [{
                        "id": ftl_lane.id,
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
                        "per_shipment_rate": ftl_lane.qoute_per_shipment,
                        "contract_rate": ftl_lane.contract_quote
                    } for ftl_lane in ftl_lanes],
                },
            },
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

@router.get("/admin/user/{id}")
def admin_get_user_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1. Get user id
        user = db.query(Director).filter(Director.id == id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Driver not found")
        shipper_company = db.query(Corporation).filter(Corporation.id == user.company_id).first()
        ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_user_id == user.id).all()
        power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipper_user_id == user.id).all()
        ftl_lanes = db.query(FTL_Lane).filter(FTL_Lane.shipper_user_id == user.id).all()

        return{
            "user_information": {
                "name": f"{user.first_name}-{user.last_name}",
                "id": user.id,
                "company_id": user.company_id,
                "is_director": user.is_director,
                "nationality": user.nationality,
                "id_number": user.id_number,
                "address": user.home_address,
                "email": user.email,
                "phone_number": user.phone_number,
                "is_verified": user.is_verified,
                "status": user.status,
                "created_at": user.created_at,
                "documents": {
                    "id_document": user.id_document,
                    "proof_of_address": user.proof_of_address,
                },
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
            
            "activity": {
                "shipments": {
                    "ftl_shipments": [{
                        "id": ftl_shipment.id,
                        "origin": ftl_shipment.origin_city_province,
                        "destination": ftl_shipment.destination_city_province,
                        "distance": ftl_shipment.distance,
                        "status": ftl_shipment.shipment_status,
                        "required_truck_type": ftl_shipment.required_truck_type,
                        "equipment_type": ftl_shipment.equipment_type,
                        "trailer_type": ftl_shipment.trailer_type if ftl_shipment.trailer_type else None,
                        "trailer_length": ftl_shipment.trailer_length if ftl_shipment.trailer_length else None,
                        "weight_bracket": ftl_shipment.minimum_weight_bracket,
                        "shipment_weight": ftl_shipment.shipment_weight,
                        "hazardous_materials": ftl_shipment.hazardous_materials,
                        "rate": ftl_shipment.quote
                    } for ftl_shipment in ftl_shipments],

                    "power_shipments": [{
                        "id": power_shipment.id,
                        "origin": power_shipment.origin_city_province,
                        "destination": power_shipment.destination_city_province,
                        "distance": power_shipment.distance,
                        "status": power_shipment.status,
                        "required_truck_type": power_shipment.required_truck_type,
                        "axle_configuration": power_shipment.axle_configuration,
                        "weight_bracket": power_shipment.minimum_weight_bracket,
                        "shipment_weight": power_shipment.shipment_weight,
                        "rate": power_shipment.quote
                    } for power_shipment in power_shipments],
                },
                "lanes": {
                    "ftl_lanes": [{
                        "id": ftl_lane.id,
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
                        "per_shipment_rate": ftl_lane.qoute_per_shipment,
                        "contract_rate": ftl_lane.contract_quote
                    } for ftl_lane in ftl_lanes],
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/carrier-user/{id}")
def admin_get_carrier_user_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1. Get the carrier user
        carrier_user = db.query(CarrierUser).filter(CarrierUser.id == id).first()
        carrier = db.query(Carrier).filter(Carrier.id == carrier_user.company_id).first()

        return{
            "user_information": {
                "is_director": carrier_user.is_director,
                "role": carrier_user.role,
                "name": f"{carrier_user.first_name}-{carrier_user.last_name}",
                "id": carrier_user.id,
                "nationality": carrier_user.nationality,
                "id_number": carrier_user.id_number,
                "home_address": carrier_user.home_address,
                "email": carrier_user.email,
                "phone_number": carrier_user.phone_number,
                "is_verified": carrier_user.is_verified,
                "status": carrier_user.status,
                "created_at": carrier_user.created_at,
                "documents": {
                    "id_document": carrier_user.id_document,
                    "proof_of_address": carrier_user.proof_of_address,
                }
            },

            "carrier_company_information": {
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
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/driver/{id}")
def admin_get_driver_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # 1. Get the driver
        driver = db.query(Driver).filter(Driver.id == id).first()
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")

        carrier = db.query(Carrier).filter(Carrier.id == driver.company_id).first()

        # 2. Initialize
        vehicle = None
        shipment = None

        # 3. Get driver's current vehicle (if exists)
        if driver.current_vehicle_id:
            vehicle = db.query(Vehicle).filter(Vehicle.id == driver.current_vehicle_id).first()

            # 4. If vehicle has active shipment, fetch it
            if vehicle and vehicle.current_shipment_id and vehicle.current_shipment_type:
                if vehicle.current_shipment_type.upper() == "FTL":
                    shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
                        Assigned_Spot_Ftl_Shipments.id == vehicle.current_shipment_id
                    ).first()
                elif vehicle.current_shipment_type.upper() == "POWER":
                    shipment = db.query(Assigned_Power_Shipments).filter(
                        Assigned_Power_Shipments.id == vehicle.current_shipment_id
                    ).first()

        return {
            "driver_information": {
                "id": driver.id,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "nationality": driver.nationality,
                "id_number": driver.id_number,
                "license_number": driver.license_number,
                "license_expiry_date": driver.license_expiry_date,
                "prdp_number": driver.prdp_number,
                "prdp_expiry_date": driver.prdp_expiry_date,
                "passport_number": driver.passport_number,
                "address": driver.address,
                "email": driver.email,
                "phone_number": driver.phone_number,
                "company_id": driver.company_id,
                "company_name": driver.company_name,
                "company_type": driver.company_type,
                "current_vehicle_id": driver.current_vehicle_id,
                "id_document": driver.id_document,
                "license_document": driver.license_document,
                "prdp_document": driver.prdp_document,
                "passport_document": driver.passport_document,
                "proof_of_address": driver.proof_of_address,
                "is_verified": driver.is_verified,
                "status": driver.status,
                "service_status": driver.service_status,
                "total_shipments_completed": driver.total_shipments_completed,
                "total_distance_driven": driver.total_distance_driven
            },
            "assigned_vehicle_information": {
                "id": vehicle.id,
                "verification_status": vehicle.is_verified,
                "status": vehicle.status,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "color": vehicle.color,
                "vin": vehicle.vin,
                "license_plate": vehicle.license_plate,
                "license_expiry_date": vehicle.license_expiry_date,
                "type": vehicle.type,
                "equipment_type": vehicle.equipment_type,
                "trailer_type": vehicle.trailer_type,
                "trailer_length": vehicle.trailer_length,
                "tare_weight": vehicle.tare_weight,
                "gvm_weight": vehicle.gvm_weight,
                "payload_capacity": vehicle.payload_capacity,
            } if vehicle else None,
            "current_shipment_information": {
                "id": shipment.id,
                "status": shipment.status,
                "trip_status": shipment.trip_status,
                "type": shipment.type,
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
                "origin": shipment.origin_city_province,
                "destination": shipment.destination_city_province,
                "pickup_date": shipment.pickup_date,
                "distance": shipment.distance,
                "minimum_transit_time": shipment.estimated_transit_time,
                "shipment_weight": shipment.shipment_weight,
                "temperature_control": shipment.temperature_control,
            } if shipment else None,
            "carrier_company_information": {
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
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/vehicle/{id}") # Tested
def admin_get_single_truck(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        truck = db.query(Vehicle).filter(
            Vehicle.id == id
        ).first()
        if not truck:
            raise HTTPException(
                status_code=404,
                detail=f"Truck with ID {id} not found or not authorized"
            )

        carrier = db.query(Carrier).filter(Carrier.id == truck.owner_id).first()

        vehicle_schedules = db.query(Vehicle_Schedule).filter(
            Vehicle_Schedule.vehicle_id == truck.id,
            Vehicle_Schedule.past == False
        ).all()

        trailer = None
        if truck.trailer_id:
            trailer = db.query(Trailer).filter(Trailer.id == truck.trailer_id).first()

        driver = None
        if truck.primary_driver_id:
            driver = db.query(Driver).filter(Driver.id == truck.primary_driver_id).first()

        shipment = None
        if truck.current_shipment_id and truck.current_shipment_type:
            if truck.current_shipment_type.lower() == "ftl":
                shipment = db.query(Assigned_Spot_Ftl_Shipments).filter(
                    Assigned_Spot_Ftl_Shipments.shipment_id == truck.current_shipment_id
                ).first()
            elif truck.current_shipment_type.lower() == "power":
                shipment = db.query(Assigned_Power_Shipments).filter(
                    Assigned_Power_Shipments.shipment_id == truck.current_shipment_id
                ).first()

        return {
            "vehicle_information": {
                "id": truck.id,
                "verification_status": truck.is_verified,
                "status": truck.status,
                "availability_status": truck.service_status,
                "type": truck.type,
                "axle_configuration": truck.axle_configuration,
                "equipment_type": truck.equipment_type,
                "trailer_type": truck.trailer_type or "N/A",
                "trailer_length": truck.trailer_length or "N/A",
                "make": truck.make,
                "model": truck.model,
                "year": truck.year,
                "color": truck.color,
                "license_plate": truck.license_plate,
                "license_expiry_date": truck.license_expiry_date,
                "tare_weight": truck.tare_weight,
                "gvm_weight": truck.gvm_weight,
                "payload_capacity": truck.payload_capacity,
            },
            "tracker_details": {
                "tracker_company_name": truck.tracker_providers_name,
                "tracker_company_country": truck.tracker_providers_country,
                "tracker_device_id": truck.tracker_id,
                "tracking_account_login_username": truck.tracker_login_username,
                "tracking_account_login_password": truck.tracker_login_password,
            },
            "vehicle_documents": {
                "vehicle_registration_or_leasing_certificate": truck.vrc_or_leasing,
                "vehicle_license_disc": truck.vehicle_license_disk,
                "vehicle_roadworthy_certificate": truck.vehicle_road_worthy_certificate,
                "vehicle_tracking_certificate": truck.vehicle_tracking_certificate,
            },
            "vehicle_images": {
                "front_angle": truck.front_angle_image,
                "rear_angle": truck.rear_angle_image,
                "left_angle": truck.left_angle_image,
                "right_angle": truck.right_angle_image,
            },
            "vehicle_schedule": [{
                "shipment_id": schedule.shipment_id,
                "shipment_type": schedule.shipment_type,
                "status": schedule.status,
                "origin": schedule.origin,
                "destination": schedule.destination,
                "pickup_date": schedule.pickup_date,
                "pickup_appointment": schedule.pickup_appointment,
                "eta": schedule.eta_date,
                "distance": schedule.distance,
                "rate": schedule.rate,
            } for schedule in vehicle_schedules],
            "trailer_information": {
                "id": trailer.id if trailer else "N/A",
                "verification_status": trailer.is_verified if trailer else "N/A",
                "status": trailer.status if trailer else "N/A",
                "make": trailer.make if trailer else "N/A",
                "model": trailer.model if trailer else "N/A",
                "year": trailer.year if trailer else "N/A",
                "color": trailer.color if trailer else "N/A",
                "equipment_type": trailer.equipment_type if trailer else "N/A",
                "trailer_type": trailer.trailer_type if trailer else "N/A",
                "trailer_length": trailer.trailer_length if trailer else "N/A",
                "license_plate": trailer.license_plate if trailer else "N/A",
                "license_expiry_date": trailer.license_expiry_date if trailer else "N/A",
                "tare_weight": trailer.tare_weight if trailer else "N/A",
                "gvm_weight": trailer.gvm_weight if trailer else "N/A",
                "payload_capacity": trailer.payload_capacity if trailer else "N/A",
            },
            "driver_information": {
                "id": driver.id if driver else "N/A",
                "verification_status": driver.is_verified if driver else "N/A",
                "status": driver.status if driver else "N/A",
                "first_name": driver.first_name if driver else "N/A",
                "last_name": driver.last_name if driver else "N/A",
                "nationality": driver.nationality if driver else "N/A",
                "id_number": driver.id_number if driver else "N/A",
                "phone_number": driver.phone_number if driver else "N/A",
                "email": driver.email if driver else "N/A",
                "license_number": driver.license_number if driver else "N/A",
                "license_expiry_date": driver.license_expiry_date if driver else "N/A",
                "distance_driven": driver.total_distance_driven if driver else "N/A",
                "total_shipments_fulfilled": driver.total_shipments_completed if driver else "N/A",
            },
            "current_shipment_information": {
                "id": shipment.shipment_id if shipment else "N/A",
                "status": shipment.status if shipment else "N/A",
                "trip_status": shipment.trip_status if shipment else "N/A",
                "type": shipment.type if shipment else "N/A",
                "origin": shipment.origin_city_province if shipment else "N/A",
                "destination": shipment.destination_city_province if shipment else "N/A",
                "pickup_date": shipment.pickup_date if shipment else "N/A",
                "distance": shipment.distance if shipment else "N/A",
                "estimated_transit_time": shipment.estimated_transit_time if shipment else "N/A",
                "rate_per_km": shipment.rate_per_km if shipment else "N/A",
                "rate_per_ton": shipment.rate_per_ton if shipment else "N/A",
            },
            "carrier_company_information": {
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
                },
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/tracking/vehicle/{vehicle_id}")
def admin_get_vehicle_location(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        
        return {
            "vehicle_location_data": {
                "latitude": vehicle.latitude,
                "longitude": vehicle.longitude,
                "speed": vehicle.speed,
                "heading": vehicle.heading,
                "location_description": vehicle.location_description
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/fleet-trailer/{id}")  # Tested
def admin_get_single_trailer(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # Fetch trailer
        trailer = db.query(Trailer).filter(
            Trailer.id == id
        ).first()

        carrier = db.query(Carrier).filter(Carrier.id == trailer.owner_id).first()

        if not trailer:
            raise HTTPException(
                status_code=404,
                detail=f"Trailer with ID {id} not found or not authorized"
            )

        # Fetch assigned truck if available
        truck = None
        if trailer.truck_id:
            truck = db.query(Vehicle).filter(Vehicle.id == trailer.truck_id).first()

        return {
            "trailer_information": {
                "id": trailer.id,
                "verification_status": trailer.is_verified,
                "status": trailer.status,
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.year,
                "color": trailer.color,
                "vin": trailer.vin,
                "license_plate": trailer.license_plate,
                "license_expiry_date": trailer.license_expiry_date,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "tare_weight": trailer.tare_weight,
                "gvm_weight": trailer.gvm_weight,
                "payload_capacity": trailer.payload_capacity,
                "current_truck_id": trailer.truck_id
            },
            "trailer_documents": {
                "registration_certificate_or_leasing_certificate": trailer.vrc_leasing,
                "license_disc": trailer.license_disk,
                "roadworthy_certificate": trailer.road_worthy_certificate,
            },
            "trailer_images": {
                "front_angle": trailer.front_angle_image,
                "rear_angle": trailer.rear_angle_image,
                "left_angle": trailer.left_angle_image,
                "right_angle": trailer.right_angle_image,
            },
            "assigned_vehicle_information": (
                {
                    "id": truck.id,
                    "verification_status": truck.is_verified,
                    "status": truck.status,
                    "type": truck.type,
                    "axle_configuration": truck.axle_configuration,
                    "make": truck.make,
                    "model": truck.model,
                    "year": truck.year,
                    "color": truck.color,
                    "vin": truck.vin,
                    "license_plate": truck.license_plate,
                    "license_expiry_date": truck.license_expiry_date,
                    "tare_weight": truck.tare_weight,
                    "gvm_weight": truck.gvm_weight,
                    "payload_capacity": truck.payload_capacity
                }
                if truck else None
            ),
            "carrier_company_information": {
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
                },
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/shipper-trailer/{id}")  # Tested
def admin_get_single_shipper_trailer(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        trailer = db.query(ShipperTrailer).filter(
            ShipperTrailer.id == id
        ).first()

        shipper_company = db.query(Corporation).filter(Corporation.id == trailer.owner_id).first()

        if not trailer:
            raise HTTPException(
                status_code=404,
                detail=f"Trailer with ID {id} not found or User not authorized"
            )

        # --- Truck lookup ---
        truck = None
        if trailer.truck_id:
            truck = db.query(Vehicle).filter(Vehicle.id == trailer.truck_id).first()

        # --- Shipment lookup ---
        shipment = None
        if truck and truck.current_shipment_id:
            if truck.current_shipment_type == "FTL":
                shipment = db.query(FTL_SHIPMENT).filter(
                    FTL_SHIPMENT.id == truck.current_shipment_id
                ).first()
            else:
                shipment = db.query(POWER_SHIPMENT).filter(
                    POWER_SHIPMENT.id == truck.current_shipment_id
                ).first()

        return {
            "trailer_information": {
                "id": trailer.id,
                "owned_by": f"SADC FREIGHTLINK Client-{trailer.owner_id}",
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.year,
                "color": trailer.color,
                "vin": trailer.vin,
                "license_plate": trailer.license_plate,
                "license_expiry_date": trailer.license_expiry_date,
                "tare_weight": trailer.tare_weight,
                "gvm_weight": trailer.gvm_weight,
                "equipment_type": trailer.equipment_type,
                "trailer_length": trailer.trailer_length,
                "trailer_type": trailer.trailer_type,
                "connected_truck_id": trailer.truck_id or "N/A"
            },

            "trailer_documents": {
                "registration_certificate": trailer.vrc_leasing,
                "license_disc": trailer.license_disk,
                "road_worthy_certificate": trailer.road_worthy_certificate
            },

            "trailer_pictures": {
                "front_angle_image": trailer.front_angle_image,
                "rear_angle_image": trailer.rear_angle_image,
                "left_angle_image": trailer.left_angle_image,
                "right_angle_image": trailer.right_angle_image
            },

            "attached_truck_information": {
                "truck_id": truck.id if truck else "N/A",
                "verification_status": truck.is_verified if truck else "N/A",
                "owned_by": f"SADC FREIGHTLINK Carrier-{truck.owner_id}" if truck else "N/A",
                "make": truck.make if truck else "N/A",
                "model": truck.model if truck else "N/A",
                "year": truck.year if truck else "N/A",
                "color": truck.color if truck else "N/A",
                "vin": truck.vin if truck else "N/A",
                "license_plate": truck.license_plate if truck else "N/A",
                "license_expiry_date": truck.license_expiry_date if truck else "N/A",
                "tare_weight": truck.tare_weight if truck else "N/A",
                "gvm_weight": truck.gvm_weight if truck else "N/A",
                "payload_capacity": truck.payload_capacity if truck else "N/A",
                "last_known_location": truck.location_description if truck else "N/A",
            },

            "current_shipment_information": {
                "shipment_id": shipment.id if shipment else "N/A",
                "shipment_status": shipment.shipment_status if shipment else "N/A",
                "origin": shipment.origin_city_province if shipment else "N/A",
                "destination": shipment.destination_city_province if shipment else "N/A"
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

        # ============================================================
        # 1. GET CLIENT BOOKING SHIPMENT
        # ============================================================

        client_booking_shipment = (
            db.query(FTL_SHIPMENT)
            .filter(FTL_SHIPMENT.id == id)
            .first()
        )

        if not client_booking_shipment:
            raise HTTPException(
                status_code=404,
                detail=f"FTL Shipment {id} not found"
            )

        # ============================================================
        # 2. GET LOADBOARD SHIPMENT
        # ============================================================

        shipment = (
            db.query(Ftl_Load_Board)
            .filter(
                Ftl_Load_Board.shipment_id == client_booking_shipment.id
            )
            .first()
        )

        if not shipment:
            raise HTTPException(
                status_code=404,
                detail=f"Loadboard entry for shipment {id} not found"
            )

        # ============================================================
        # 3. BUILD DYNAMIC STOP ADDRESSES
        # ============================================================
        #
        # Only addresses that actually exist are returned.
        #
        # Example:
        #
        # Origin
        # Stop 1
        # Stop 2
        # Destination
        #
        # If there are no stops:
        #
        # Origin
        # Destination
        #
        # ============================================================

        stop_addresses = []

        for stop_number in range(1, 6):

            stop_address = getattr(
                shipment,
                f"stop_{stop_number}_address",
                None
            )

            if stop_address:
                stop_addresses.append({
                    "stop_number": stop_number,
                    "address": stop_address
                })

        # ============================================================
        # 4. BUILD DYNAMIC STOP FACILITIES + CONTACTS
        # ============================================================
        #
        # The loadboard stores ONLY the facility ID for stops.
        #
        # stop_1_facility_id
        # stop_2_facility_id
        # ...
        #
        # We use that facility ID to:
        #
        # 1. Query the facility
        # 2. Query ContactPerson using facility_id
        #
        # ============================================================

        stop_facilities = []

        for stop_number in range(1, 6):

            # Get the stop address
            stop_address = getattr(
                shipment,
                f"stop_{stop_number}_address",
                None
            )

            # Get the corresponding facility ID
            stop_facility_id = getattr(
                shipment,
                f"stop_{stop_number}_facility_id",
                None
            )

            # If neither exists, skip this stop
            if not stop_address and not stop_facility_id:
                continue

            facility = None
            contact = None

            # --------------------------------------------------------
            # Query facility
            # --------------------------------------------------------

            if stop_facility_id:

                facility = (
                    db.query(ShipmentFacility)
                    .filter(
                        ShipmentFacility.id == stop_facility_id
                    )
                    .first()
                )

                # ----------------------------------------------------
                # Query contact person using facility ID
                # ----------------------------------------------------

                if facility:

                    contact = (
                        db.query(ContactPerson)
                        .filter(
                            ContactPerson.id == facility.contact_person
                        )
                        .first()
                    )

            # --------------------------------------------------------
            # Build stop facility response
            # --------------------------------------------------------

            stop_facilities.append({

                "stop_number": stop_number,

                "address": stop_address,

                "facility": {
                    "id": facility.id if facility else stop_facility_id,

                    "name": (
                        facility.name
                        if facility
                        else None
                    ),

                    "scheduling_type": (
                        facility.scheduling_type
                        if facility
                        else None
                    ),

                    "start_time": (
                        str(facility.start_time)
                        if facility and facility.start_time
                        else None
                    ),

                    "end_time": (
                        str(facility.end_time)
                        if facility and facility.end_time
                        else None
                    ),

                    "facility_notes": (
                        facility.facility_notes
                        if facility
                        else None
                    ),
                },

                "contact": {

                    "first_name": (
                        contact.first_name
                        if contact
                        else None
                    ),

                    "last_name": (
                        contact.last_name
                        if contact
                        else None
                    ),

                    "phone_number": (
                        contact.phone_number
                        if contact
                        else None
                    ),

                    "email": (
                        contact.email
                        if contact
                        else None
                    ),
                }
            })

        # ============================================================
        # 5. RETURN RESPONSE
        # ============================================================

        return {

            # ========================================================
            # SHIPMENT DETAILS
            # ========================================================

            "shipment_details": {

                "id": shipment.shipment_id,

                "type": shipment.type,

                "load_type": shipment.load_type,

                "trip_type": shipment.trip_type,

                "status": shipment.status,

                "required_truck_type": shipment.required_truck_type,

                "equipment_type": shipment.equipment_type,

                "trailer_type": (
                    shipment.trailer_type
                    if shipment.trailer_type
                    else "N/A"
                ),

                "trailer_length": (
                    shipment.trailer_length
                    if shipment.trailer_length
                    else "N/A"
                ),

                "minimum_weight_bracket": (
                    shipment.minimum_weight_bracket
                ),

                "minimum_git_cover_amount": (
                    shipment.minimum_git_cover_amount
                ),

                "minimum_liability_cover_amount": (
                    shipment.minimum_liability_cover_amount
                ),

                # ----------------------------------------------------
                # ORIGIN ADDRESS
                # ----------------------------------------------------

                "origin": shipment.origin_address,

                # ----------------------------------------------------
                # DYNAMIC STOP ADDRESSES
                #
                # ONLY stop addresses appear here.
                # Facility/contact information is NOT placed here.
                # ----------------------------------------------------

                "stops": stop_addresses,

                # ----------------------------------------------------
                # DESTINATION ADDRESS
                # ----------------------------------------------------

                "destination": shipment.destination_address,

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

            # ========================================================
            # FINANCIAL DATA
            # ========================================================

            "financial_data": {

                "loadboard_rates": {

                    "rate": shipment.shipment_rate,

                    "rate_per_km": shipment.rate_per_km,

                    "rate_per_ton": shipment.rate_per_ton,
                },

                "booking_rates": {

                    "rate": client_booking_shipment.quote,

                    "rate_per_km": (
                        client_booking_shipment.quote / shipment.distance
                        if shipment.distance
                        else 0
                    ),

                    "rate_per_ton": (
                        client_booking_shipment.quote
                        / (shipment.minimum_weight_bracket / 1000)
                        if shipment.minimum_weight_bracket
                        else 0
                    ),
                },

                "platform_commission": {

                    "commission_rate": (
                        client_booking_shipment.quote
                        - shipment.shipment_rate
                    ),

                    "commission_rate_per_km": (
                        (
                            client_booking_shipment.quote
                            - shipment.shipment_rate
                        )
                        / shipment.distance
                        if shipment.distance
                        else 0
                    ),

                    "rate_per_ton": (
                        (
                            client_booking_shipment.quote
                            - shipment.shipment_rate
                        )
                        / (shipment.minimum_weight_bracket / 1000)
                        if shipment.minimum_weight_bracket
                        else 0
                    ),
                }
            },

            # ========================================================
            # PICKUP FACILITY + CONTACT
            # ========================================================

            "pickup_facility": {

                "name": shipment.pickup_facility_name,

                "address": shipment.origin_address,

                "scheduling_type": shipment.pickup_scheduling_type,

                "operating_hours": (
                    f"{shipment.pickup_start_time} - "
                    f"{shipment.pickup_end_time}"
                ),

                "facility_notes": shipment.pickup_facility_notes,

                "contact_person": (
                    f"{shipment.pickup_first_name} "
                    f"{shipment.pickup_last_name}"
                ),

                "phone_number": shipment.pickup_phone_number,

                "email": shipment.pickup_email,
            },

            # ========================================================
            # DYNAMIC STOP FACILITIES + CONTACTS
            #
            # This is BETWEEN pickup and delivery facilities.
            #
            # ========================================================

            "stop_facilities": stop_facilities,

            # ========================================================
            # DELIVERY FACILITY + CONTACT
            # ========================================================

            "delivery_facility": {

                "name": shipment.delivery_facility_name,

                "address": shipment.destination_address,

                "scheduling_type": shipment.delivery_scheduling_type,

                "operating_hours": (
                    f"{shipment.delivery_start_time} - "
                    f"{shipment.delivery_end_time}"
                ),

                "facility_notes": shipment.delivery_facility_notes,

                "contact_person": (
                    f"{shipment.delivery_first_name} "
                    f"{shipment.delivery_last_name}"
                ),

                "phone_number": shipment.delivery_phone_number,

                "email": shipment.delivery_email,
            },
        }

    except HTTPException:
        raise

    except Exception as e:

        print("============================================================")
        print("ERROR IN admin_get_ftl_shipment_id")
        print("============================================================")
        print(f"Shipment ID: {id}")
        print(f"Error: {str(e)}")
        print("============================================================")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/admin/exchange-ftl-load/{id}")
def admin_get_exchange_ftl_load_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin)
):
    try:
        loadboard_shipment = db.query(Exchange_Ftl_Load_Board).filter(Exchange_Ftl_Load_Board.exchange_id == id).first()
        bids = db.query(Exchange_FTL_Shipment_Bid).filter(Exchange_FTL_Shipment_Bid.exchange_id == loadboard_shipment.exchange_id).all()

        return {
            "ftl_exchange": {
                "id": loadboard_shipment.exchange_id,
                "shipment_type": loadboard_shipment.type,
                "trip_type": loadboard_shipment.trip_type,
                "load_type": loadboard_shipment.load_type,
                "required_truck_type": loadboard_shipment.required_truck_type,
                "equipment_type": loadboard_shipment.equipment_type,
                "trailer_type": loadboard_shipment.trailer_type,
                "trailer_length": loadboard_shipment.trailer_length,
                "minimum_weight_bracket": loadboard_shipment.minimum_weight_bracket,
                "shipment_weight": loadboard_shipment.shipment_weight,
                "commodity": loadboard_shipment.commodity,
                "distance": loadboard_shipment.distance,
                "estimated_transit_time": loadboard_shipment.estimated_transit_time,
                "origin": loadboard_shipment.origin_city_province,
                "destination": loadboard_shipment.destination_city_province,
                "route_preview_embed": loadboard_shipment.route_preview_embed,
                "pickup_date": loadboard_shipment.pickup_date,
                "priority_level": loadboard_shipment.priority_level,
                "customer_reference": loadboard_shipment.customer_reference_number,
                "payment_terms": loadboard_shipment.payment_terms,
                "minimum_git_cover_amount": loadboard_shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": loadboard_shipment.minimum_liability_cover_amount,
                "packaging_quantity": loadboard_shipment.packaging_quantity,
                "packaging_type": loadboard_shipment.packaging_type,
                "temperature_control": loadboard_shipment.temperature_control,
                "hazardous_materials": loadboard_shipment.hazardous_materials,
                "pickup_number": loadboard_shipment.pickup_number,
                "pickup_notes": loadboard_shipment.pickup_notes,
                "delivery_number": loadboard_shipment.delivery_number,
                "delivery_notes": loadboard_shipment.delivery_notes,
                "allow_booking": loadboard_shipment.automatically_accept_lower_bid,
                "end_time": loadboard_shipment.exchange_end_time,

                "exchange_information": {
                    "exchange_offer": loadboard_shipment.shipment_rate,
                    "leading_bid": loadboard_shipment.leading_bid_amount,
                    "payment_terms": loadboard_shipment.payment_terms,
                    "rate_per_km": loadboard_shipment.rate_per_km,
                    "rate_per_ton": loadboard_shipment.rate_per_ton,
                    "bids": [{
                        "carrier_bid_amount": bid.bid_amount,
                        "shipper_baked_amount": bid.baked_bid_amount,
                        "platform_bid_commission": (bid.baked_bid_amount - bid.bid_amount),
                        "bid_status": bid.status,
                        "submitted_at": bid.submitted_at,
                    } for bid in bids]
                },

                "pickup_facility": {
                    "facility_name": loadboard_shipment.pickup_facility_name,
                    "pickup_date": loadboard_shipment.pickup_date,
                    "time_window": loadboard_shipment.pickup_appointment,
                    "scheduling_type": loadboard_shipment.pickup_scheduling_type,
                    "contact_name": f"{loadboard_shipment.pickup_first_name} - {loadboard_shipment.pickup_last_name}",
                    "email": loadboard_shipment.pickup_email,
                    "contact_phone": loadboard_shipment.pickup_phone_number,
                    "notes": loadboard_shipment.pickup_notes,
                },

                "delivery_facility": {
                    "facility_name": loadboard_shipment.delivery_facility_name,
                    "eta_date": loadboard_shipment.eta_date,
                    "time_window": loadboard_shipment.delivery_appointment,
                    "eta_window": loadboard_shipment.eta_window,
                    "scheduling_type": loadboard_shipment.delivery_scheduling_type,
                    "contact_name": f"{loadboard_shipment.delivery_first_name} - {loadboard_shipment.delivery_last_name}",
                    "email": loadboard_shipment.delivery_email,
                    "contact_phone": loadboard_shipment.delivery_phone_number,
                    "notes": loadboard_shipment.delivery_notes,
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/exchange-ftl-lane/{id}")
def admin_get_exchange_ftl_lane(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        loadboard_lane = db.query(Exchange_Ftl_Lane_LoadBoard).filter(Exchange_Ftl_Lane_LoadBoard.exchange_id == id).first()
        bids = db.query(Exchange_FTL_Lane_Bid).filter(Exchange_FTL_Lane_Bid.exchange_id == loadboard_lane.exchange_id).all()

        return {
            "lane_information":{
                "id": loadboard_lane.exchange_id,
                "shipment_type": loadboard_lane.type,
                "trip_type": loadboard_lane.trip_type,
                "load_type": loadboard_lane.load_type,
                "required_truck_type": loadboard_lane.required_truck_type,
                "equipment_type": loadboard_lane.equipment_type,
                "trailer_type": loadboard_lane.trailer_type,
                "trailer_length": loadboard_lane.trailer_length,
                "minimum_weight_bracket": loadboard_lane.minimum_weight_bracket,
                "average_shipment_weight": loadboard_lane.average_shipment_weight,
                "commodity": loadboard_lane.commodity,
                "priority_level": loadboard_lane.priority_level,
                "customer_reference": loadboard_lane.customer_reference_number,
                "distance": loadboard_lane.distance,
                "estimated_transit_time": loadboard_lane.estimated_transit_time,
                "payment_terms": loadboard_lane.payment_terms,
                "route_preview_embed": loadboard_lane.route_preview_embed,
                "minimum_git_cover_amount": loadboard_lane.minimum_git_cover_amount,
                "minimum_liability_cover_amount": loadboard_lane.minimum_liability_cover_amount,
                "packaging_quantity": loadboard_lane.packaging_quantity,
                "packaging_type": loadboard_lane.packaging_type,
                "temperature_control": loadboard_lane.temperature_control,
                "hazardous_materials": loadboard_lane.hazardous_materials,
                "origin": loadboard_lane.origin_city_province,
                "destination": loadboard_lane.destination_city_province,
                "pickup_number": loadboard_lane.pickup_number,
                "delivery_number": loadboard_lane.delivery_number,
                "pickup_notes": loadboard_lane.pickup_notes,
                "delivery_notes": loadboard_lane.delivery_notes,
                "allow_booking": loadboard_lane.automatically_accept_lower_bid,
                "auction_status": loadboard_lane.status,

                "exchange_information": {
                    "per_shipment_offer_rate": loadboard_lane.per_shipment_offer_rate,
                    "per_slot_contract_offer_rate": loadboard_lane.contract_offer_rate / loadboard_lane.shipments_per_interval,
                    "per_shipment_leading_bid": loadboard_lane.leading_per_shipment_offer_bid_amount,
                    "per_slot_contract_leading_bid": loadboard_lane.leading_per_shipment_offer_bid_amount * loadboard_lane.each_slot_size if loadboard_lane.leading_per_shipment_offer_bid_amount else None,
                    "active_bidders": loadboard_lane.number_of_bids_submitted,
                    "auction_end_time": loadboard_lane.exchange_end_time,
                
                "bids": [{
                    "bid_id": bid.id,
                    "carrier_per_shipment_bid": bid.per_shipment_bid_amount,
                    "carrier_per_slot_contract_bid": bid.per_shipment_bid_amount * loadboard_lane.each_slot_size if bid.per_shipment_bid_amount else None,
                    "shipper_per_shipment_bid": bid.baked_per_shipment_bid_amount,
                    "shipper_per_slot_contract_bid": bid.baked_contract_bid_amount,
                    "platform_per_shipment_commission": (bid.baked_per_shipment_bid_amount - bid.per_shipment_bid_amount),
                    "platform_per_slot_contract_bid": (bid.baked_contract_bid_amount - bid.contract_bid_amount),
                    "requested_slots": bid.requested_slots,
                    "bid_status": bid.status,
                    "submitted_at": bid.submitted_at,
                } for bid in bids]
                },

                "contract_details": {
                    "contract_start_date": loadboard_lane.start_date,
                    "contract_end_date": loadboard_lane.end_date,
                    "recurrence_frequency": loadboard_lane.recurrence_frequency,
                    "recurrence_days": loadboard_lane.recurrence_days,
                    "slots_per_interval": loadboard_lane.shipments_per_interval,
                    "available_slots": loadboard_lane.available_slots,
                    "total_shipments_per_slot": loadboard_lane.total_shipments / loadboard_lane.shipments_per_interval,
                    "payment_terms": loadboard_lane.payment_terms,
                    "shipment_schedule": loadboard_lane.shipment_dates,
                    "payment_schedule": loadboard_lane.payment_dates,
                },

                "pickup_facility": {
                    "facility_name": loadboard_lane.pickup_facility_name,
                    "time_window": loadboard_lane.pickup_appointment,
                    "scheduling_type": loadboard_lane.pickup_scheduling_type,
                    "contact_name": f"{loadboard_lane.pickup_first_name} - {loadboard_lane.pickup_last_name}",
                    "email": loadboard_lane.pickup_email,
                    "contact_phone": loadboard_lane.pickup_phone_number,
                    "notes": loadboard_lane.pickup_notes,
                },

                "delivery_facility": {
                    "facility_name": loadboard_lane.delivery_facility_name,
                    "time_window": loadboard_lane.delivery_appointment,
                    "scheduling_type": loadboard_lane.delivery_scheduling_type,
                    "contact_name": f"{loadboard_lane.delivery_first_name} - {loadboard_lane.delivery_last_name}",
                    "email": loadboard_lane.delivery_email,
                    "contact_phone": loadboard_lane.delivery_phone_number,
                    "notes": loadboard_lane.delivery_notes,
                }
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/spot-ftl-lane-loadboard/{id}")
def admin_get_individual_loadboard_ftl_lane(
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

        # Prevent division by zero
        distance = lane.distance or 1
        weight = (lane.minimum_weight_bracket or 1000) / 1000  # Convert kg to tons

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
                    "each_slot_size": lane.per_slot_size,
                    "total_slots": lane.total_slots,
                    "available_slots": lane.available_slots,
                    "rate_per_shipment": lane.rate_per_shipment,
                    "rate_per_km": lane.rate_per_km,
                    "rate_per_ton": lane.rate_per_ton,
                },
                "client_booking_rates": {
                    "contract_rate": client_booking_lane.contract_quote,
                    "per_slot_rate": client_booking_lane.contract_quote / client_booking_lane.shipments_per_interval,
                    "each_slot_size": lane.per_slot_size,
                    "total_slots": lane.total_slots,
                    "available_slots": lane.available_slots,
                    "rate_per_shipment": client_booking_lane.qoute_per_shipment,
                    "rate_per_km": client_booking_lane.qoute_per_shipment / distance,
                    "rate_per_ton": client_booking_lane.qoute_per_shipment / weight,
                },
                "platform_commission": {
                    "contract_commission": client_booking_lane.contract_quote - lane.contract_rate,
                    "commission_per_slot": (client_booking_lane.qoute_per_shipment - lane.rate_per_shipment) * lane.per_slot_size,
                    "each_slot_size": lane.per_slot_size,
                    "total_slots": lane.total_slots,
                    "available_slots": lane.available_slots,
                    "commission_per_shipment": client_booking_lane.qoute_per_shipment - lane.rate_per_shipment,
                    "commission_per_km": (client_booking_lane.qoute_per_shipment - lane.rate_per_shipment) / distance,
                    "commission_per_ton": (client_booking_lane.qoute_per_shipment - lane.rate_per_shipment) / weight,
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