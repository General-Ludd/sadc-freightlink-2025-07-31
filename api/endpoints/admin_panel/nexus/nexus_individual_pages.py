from typing import List
from datetime import date
from sqlalchemy import func, case
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from sqlalchemy.orm import aliased
from sqlalchemy import or_, and_
from db.database import SessionLocal
from models.administration import Platform_Super_Admins, Platform_Super_and_Support_Admins_Permissions
from models.nexus.customs_territories import Country, CountryTradeAgreement, BorderPost, BorderClearanceProfile, TariffSchedule, TradeDefenseMeasure, CountrySpecialFee, TransitBondFee, CustomsProcedure, ExciseTaxRate, Customs_Duty_Authority
from schemas.administration import CreateAdministrationUser, AdminPermissionsSchema
from schemas.auth import LoginRequest, LoginResponse
from services.vehicle_service import create_shipper_trailer
from services.user_service import create_admin_super_user
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

@router.get("/countries/{id}")
def admin_get_individual_country(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # Get country first, return 404 if not found
        country = db.query(Country).filter(Country.id == id).first()
        if not country:
            raise HTTPException(status_code=404, detail="Country not found")
        
        # Fetch related data - handle None cases
        customs_procedures = db.query(CustomsProcedure).filter(CustomsProcedure.country_id == id).all()
        customs_authority = db.query(Customs_Duty_Authority).filter(Customs_Duty_Authority.country_id == id).first()
        trade_agreements = db.query(CountryTradeAgreement).filter(CountryTradeAgreement.country_id == id).all()
        tariff_schedules = db.query(TariffSchedule).filter(TariffSchedule.country_id == id).all()
        defense_measures = db.query(TradeDefenseMeasure).filter(TradeDefenseMeasure.country_id == id).all()
        special_fees = db.query(CountrySpecialFee).filter(CountrySpecialFee.country_id == id).all()
        transit_bond_fees = db.query(TransitBondFee).filter(TransitBondFee.country_id == id).all()

        # Build response with null handling
        response = {
            "country": {
                "id": country.id,
                "iso_code": country.iso_code,
                "currency_code": country.currency_code,
                "standard_vat_rate": country.standard_vat_rate,
                "requires_ctn": country.requires_ctn,
                "is_active": country.is_active,
                "is_sacu_member": country.is_sacu_member,
                "is_sadc_member": country.is_sadc_member,
                "is_comesa_member": country.is_comesa_member,  # Fixed typo: memeber -> member
            },
            "customs_authority": None,
            "customs_procedures": [],
            "trade_agreements": [],
            "tariff_schedule": [],  # Fixed typo: tarrif -> tariff
            "trade_defense_measures": [],  # Fixed typo: defence -> defense (to match variable name)
            "transit_bond": [],
            "special_fees": [],
        }

        # Handle customs_authority if exists
        if customs_authority:
            response["customs_authority"] = {
                "agency_name": customs_authority.agency_name,
                "agency_code": customs_authority.agency_code,
                "bank_name": customs_authority.bank_name,
                "branch_code": customs_authority.branch_code,
                "bank_account_number": customs_authority.bank_account_number,
                "account_type": customs_authority.account_type,
                "website": customs_authority.website,
                "email": customs_authority.email,
                "phone_number": customs_authority.phone_number
            }

        # Handle customs_procedures
        for procedure in customs_procedures:
            response["customs_procedures"].append({
                "id": procedure.id,
                "procedure_type": procedure.procedure_type,
                "required_documents": procedure.required_documents,
                "standard_processing_days": procedure.standard_processing_days,
                "is_electronic_filling_mandatory": procedure.is_electronic_filing_mandatory,
                "authority": procedure.authority_name,
                "authority_website": procedure.authority_website,
                "process_description": procedure.process_description,
            })

        # Handle trade_agreements
        for agreement in trade_agreements:
            response["trade_agreements"].append({
                "id": agreement.id,
                "is_active": agreement.is_active,
                "code": agreement.agreement_code,
                "name": agreement.agreement_name,
                "effective_date": agreement.effective_date.isoformat() if agreement.effective_date else None,
                "notes": agreement.notes,
            })

        # Handle tariff_schedules
        for schedule in tariff_schedules:
            response["tariff_schedule"].append({
                "hs_code": schedule.hs_code,
                "hs_description": schedule.hs_description,
                "mfn_rate": schedule.mfn_rate,
                "preferential_rate": schedule.preferential_rate,
                "agreement_source": schedule.agreement_source,
                "uom": schedule.uom,
                "excise_duty_rate": schedule.excise_duty_rate,
                "start_date": schedule.start_date.isoformat() if schedule.start_date else None,
                "end_date": schedule.end_date.isoformat() if schedule.end_date else None,
            })

        # Handle defense_measures
        for measure in defense_measures:
            response["trade_defense_measures"].append({
                "id": measure.id,
                "measure_type": measure.measure_type,
                "hs_code": measure.hs_code,
                "exporting_country_iso": measure.exporting_country_iso,
                "duty_rate": measure.duty_rate,
                "effective_date": measure.effective_date.isoformat() if measure.effective_date else None,
                "expiry_date": measure.expiry_date.isoformat() if measure.expiry_date else None,
                "legal_reference": measure.legal_reference,
                "description": measure.description
            })

        # Handle transit_bond_fees
        for fee in transit_bond_fees:
            response["transit_bond"].append({
                "id": fee.id,
                "is_active": fee.is_active,
                "country_id": fee.country_id,
                "amount_zar": fee.amount_zar,
                "validity_days": fee.validity_days,
                "effective_date": fee.effective_date.isoformat() if fee.effective_date else None,
                "description": fee.description,
            })

        # Handle special_fees
        for fee in special_fees:
            response["special_fees"].append({
                "id": fee.id,
                "code": fee.fee_code,
                "name": fee.fee_name,
                "amount": fee.amount,
                "percentage_rate": fee.percentage_rate,
                "threshold_amount_zar": fee.threshold_amount_zar,
                "description": fee.description,
                "payable_to": fee.payable_to,
                "is_mandatory": fee.is_mandatory,
            })

        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/countries-left/{id}")
def admin_geta_individual_country(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        country = db.query(Country).filter(Country.id == id).first()
        customs_procedures = db.query(CustomsProcedure).filter(CustomsProcedure.country_id == id).all()
        customs_authority = db.query(Customs_Duty_Authority).filter(Customs_Duty_Authority.country_id == country.id).first()
        trade_agreements = db.query(CountryTradeAgreement).filter(CountryTradeAgreement.country_id == country.id).all()
        tarrif_schedules = db.query(TariffSchedule).filter(TariffSchedule.country_id == country.id).all()
        defense_measures = db.query(TradeDefenseMeasure).filter(TradeDefenseMeasure.country_id == country.id).all()
        special_fees = db.query(CountrySpecialFee).filter(CountrySpecialFee.country_id == country.id).all()
        transit_bond_fees = db.query(TransitBondFee).filter(TransitBondFee.country_id == country.id).all()


        return {
            "country": {
                "id": country.id,
                "iso_code": country.iso_code,
                "currency_code": country.currency_code,
                "standard_vat_rate": country.standard_vat_rate,
                "requires_ctn": country.requires_ctn,
                "is_active": country.is_active,
                "is_sacu_member": country.is_sacu_member,
                "is_sadc_member": country.is_sadc_member,
                "is_comesa_memeber": country.is_comesa_member,
            },
            "customs_authority": {
                "agency_name": customs_authority.agency_name,
                "agency_code": customs_authority.agency_code,
                "bank_name": customs_authority.bank_name if customs_authority.bank_name else None,
                "branch_code": customs_authority.branch_code if customs_authority.branch_code else None,
                "bank_account_number": customs_authority.bank_account_number if customs_authority.bank_account_number else None,
                "account_type": customs_authority.account_type if customs_authority.account_type else None,
                "website": customs_authority.website if customs_authority.website else None,
                "email": customs_authority.email if customs_authority.email else None,
                "phone_number": customs_authority.phone_number if customs_authority.phone_number else None
            },
            "customs_procedures": [{
                "id": customs_procedure.id,
                "procedure_type": customs_procedure.procedure_type,
                "required_documents": customs_procedure.required_documents,
                "standard_processing_days": customs_procedure.standard_processing_days,
                "is_electronic_filling_mandatory": customs_procedure.is_electronic_filing_mandatory,
                "authority": customs_procedure.authority_name,
                "authority_website": customs_procedure.authority_website,
                "process_description": customs_procedure.process_description,
            } for customs_procedure in customs_procedures],
            "trade_agreements": [{
                "id": trade_agreement.id,
                "is_active": trade_agreement.is_active,
                "code": trade_agreement.agreement_code,
                "name": trade_agreement.agreement_name,
                "effective_date": trade_agreement.effective_date,
                "notes": trade_agreement.notes,
            } for trade_agreement in trade_agreements],
            "tarrif_schedule": [{
                "hs_code": tarrif_schedule.hs_code,
                "hs_description": tarrif_schedule.hs_description,
                "mfn_rate": tarrif_schedule.mfn_rate,
                "preferential_rate": tarrif_schedule.preferential_rate,
                "agreement_source": tarrif_schedule.agreement_source,
                "uom": tarrif_schedule.uom,
                "excise_duty_rate": tarrif_schedule.excise_duty_rate,
                "start_date": tarrif_schedule.start_date,
                "end_date": tarrif_schedule.end_date,
            } for tarrif_schedule in tarrif_schedules],
            "trade_defence_measures": [{
                "id": defense_measure.id,
                "measure_type": defense_measure.measure_type,
                "hs_code": defense_measure.hs_code,
                "exporting_country_iso": defense_measure.exporting_country_iso,
                "duty_rate": defense_measure.duty_rate,
                "effective_date": defense_measure.effective_date,
                "expiry_date": defense_measure.expiry_date,
                "legal_reference": defense_measure.legal_reference,
                "description": defense_measure.description
            }for defense_measure in trade_defence_measures],
            "transit_bond":  [{
                "id": transit_bond_fee.id,
                "is_active": transit_bond_fee.is_active,
                "country_id": transit_bond_fee.country_id,
                "amount_zar": transit_bond_fee.amount_zar,
                "validity_days": transit_bond_fee.validity_days,
                "effective_date": transit_bond_fee.effective_date,
                "description": transit_bond_fee.description,
            } for transit_bond_fee in transit_bond_fees],
            "special_fees": [{
                "id": special_fee.id,
                "code": special_fee.fee_code,
                "name": special_fee.fee_name,
                "amount": special_fee.amount,
                "percentage_rate": special_fee.percentage_rate,
                "threshold_amount_zar": special_fee.threshold_amount_zar,
                "description": special_fee.description,
                "payable_to": special_fee.payable_to,
                "is_mandatory": special_fee.is_mandatory,
            }for special_fee in special_fees],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))