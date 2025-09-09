from typing import List
from fastapi import APIRouter, Depends, HTTPException
from requests import Session
from db.database import SessionLocal
from models.shipper import Corporation, Consignor
from models.carrier import Carrier
from models.user import CarrierUser
from models.vehicle import Vehicle, Trailer
from models.brokerage.finance import FinancialAccounts, Shipment_Invoice, Interim_Invoice, Invoices, CarrierFinancialAccounts, Load_Invoice, Lane_Interim_Invoice, Lane_Invoice
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments, Assigned_Power_Shipments
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
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

@router.get("/company/carrier/{id}")
def admin_get_carrier_company_information(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        company = db.query(Carrier).filter(Carrier.id == id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        financial_account = db.query(CarrierFinancialAccounts).filter(CarrierFinancialAccounts.id == company.id).first()
        users = db.query(CarrierUser).filter(CarrierUser.company_id == company.id).all()
        vehicles = db.query(Vehicle).filter(Vehicle.owner_id == company.id).all()
        trailers = db.query(Trailer).filter(Trailer.owner_id == company.id).all()
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(Assigned_Spot_Ftl_Shipments.carrier_id == company.id).all()
        power_shipments = db.query(Assigned_Power_Shipments).filter(Assigned_Power_Shipments.carrier_id == company.id).all()
        ftl_lanes = db.query(Assigned_Ftl_Lanes).filter(Assigned_Ftl_Lanes.carrier_id == company.id).all()

        return {
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
            "users": [{
                "name": f"{user.first_name}-{user.last_name}",
                "id": user.id,
                "company_id": user.company_id,
                "role": user.role,
                "nationality": user.nationality,
                "id_number": user.id_number,
                "is_director": user.is_director,
                "is_verified": user.is_verified,
                "status": user.status,
            } for user in user],
            "vehicles": [{
                "make_year": f"{vehicle.make}-{vehicle.year}",
                "id": vehicle.id,
                "color": vehicle.color,
                "type": vehicle.type,
                "axle_configuration": vehicle.axle_configuration,
                "equipment_type": vehicle.equipment_type,
                "payload_capacity": vehicle.payload_capacity,
                "trailer_type": vehicle.trailer_type,
                "trailer_length": vehicle.trailer_length,
                "company_id": vehicle.owner_id,
                "is_verified": vehicle.is_verified,
                "status": vehicle.status,
            } for vehicle in vehicles],
            "trailers": [{
                "make_model": f"{trailer.make}-{trailer.model}",
                "id": trailer.id,
                "company": trailer.owner_id,
                "year": trailer.year,
                "color": trailer.color,
                "license_plate": trailer.license_plate,
                "payload_capacity": trailer.payload_capacity,
                "vehicle_id": trailer.truck_id if trailer.truck_id else "N/A",
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "length": trailer.trailer_length,
                "is_verified": trailer.is_verified,
                "status": trailer.status,
            } for trailer in trailers],
            "shipments": {
                "ftl_shipments": [{
                    "id": ftl_shipment.shipment_id,
                    "status": ftl_shipment.status,
                    "origin": ftl_shipment.origin_city_province,
                    "destination": ftl_shipment.destination_city_province,
                    "distance": ftl_shipment.distance,
                    "required_truck_type": ftl_shipment.required_truck_type,
                    "equipment_type": ftl_shipment.equipment_type,
                    "trailer_type": ftl_shipment.trailer_type,
                    "trailer_length": ftl_shipment.trailer_length,
                    "weight_bracket": ftl_shipment.minimum_weight_bracket,
                    "shipment_weight": ftl_shipment.shipment_weight,
                    "hazardous_materials": ftl_shipment.hazardous_materials,
                    "rate": ftl_shipment.shipment_rate,
                } for ftl_shipment in ftl_shipments],
                "power_shipments": [{
                    "id": power_shipment.shipment_id,
                    "status": power_shipment.status,
                    "origin": power_shipment.origin_city_province,
                    "destination": power_shipment.destination_city_province,
                    "distance": power_shipment.distance,
                    "required_truck_type": power_shipment.required_truck_type,
                    "axle_configuration": power_shipment.axle_configuration,
                    "weight_bracket": power_shipment.minimum_weight_bracket,
                    "shipment_weight": power_shipment.shipment_weight,
                    "rate": power_shipment.shipment_rate
                } for power_shipment in power_shipments],
            },
            "Lanes": {
                "ftl_lanes": [{
                    "id": lane.lane_id,
                    "status": lane.status,
                    "origin": lane.origin_city_province,
                    "destination": lane.destination_city_province,
                    "distance": lane.distance,
                    "required_truck_type": lane.required_truck_type,
                    "equipment_type": lane.equipment_type,
                    "trailer_type": lane.trailer_type,
                    "start_date": lane.start_date,
                    "end_date": lane.end_date,
                    "recurrence": lane.recurrence_frequency,
                    "days": lane.recurrence_days,
                    "shipments_per_interval": lane.shipments_per_interval,
                    "total_shipments": lane.total_shipments,
                    "per_shipment_rate": lane.rate_per_shipment,
                    "contract_rate": lane.contract_rate
                } for ftl_lane in ftl_lanes],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))