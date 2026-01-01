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
from models.nexus.customs_territories import Country, Customs_Duty_Authority, CountryTradeAgreement, BorderPost, BorderClearanceProfile, TariffSchedule, TradeDefenseMeasure, CountrySpecialFee, TransitBondFee, CustomsProcedure, ExciseTaxRate, AntiDumpingMeasure, CurrencyExchangeRate
from schemas.nexus.customs import CountryBase, Customs_Duty_Authority_Base, CountryTradeAgreementBase, TariffScheduleBase, CountrySpecialFeeBase, TransitBondFeeBase, TradeDefenseMeasureBase
from schemas.administration import CreateAdministrationUser, AdminPermissionsSchema
from schemas.auth import LoginRequest, LoginResponse
from services.vehicle_service import create_shipper_trailer
from services.user_service import create_admin_super_user
from services.nexus.admin_func import admin_create_country
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

@router.post("/admin-create-country")
def admin_create_customs_country(
    country_data: CountryBase,  # Changed to CountryCreate to include all fields
    authority_data: Customs_Duty_Authority_Base,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        result = admin_create_country(
            db=db,
            country_data=country_data,
            authority_data=authority_data,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# 2. Endpoint for creating customs authority for an existing country
@router.post("/create-country-{country_id}/customs-authority")
def create_country_customs_authority(
    country_id: int,
    authority_data: Customs_Duty_Authority_Base,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        result = create_customs_authority(
            country_id=country_id,
            db=db,
            authority_data=authority_data,
        )
        return {"message": "Customs authority created successfully", "authority_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 3. Endpoint for creating trade agreements for a country
@router.post("/create-country-{country_id}/trade-agreement")
def create_country_trade_agreement(
    country_id: int,
    agreement_data: CountryTradeAgreementBase,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        result = create_trade_agreement(
            country_id=country_id,
            db=db,
            agreement_data=agreement_data,
        )
        return {"message": "Trade agreement created successfully", "agreement_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 4. Endpoint for creating tariff schedules for a country
@router.post("/create-country-{country_id}/tariff-schedules")
def create_country_tariff_schedule(
    country_id: int,
    tariff_data: TariffScheduleBase,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        result = create_tariff_schedule(
            country_id=country_id,
            db=db,
            tariff_data=tariff_data,
        )
        return {"message": "Tariff schedule created successfully", "tariff_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 5. Endpoint for creating trade defense measures for a country
@router.post("/create-country-{country_id}/trade-defense-measures")
def create_country_trade_defense_measure(
    country_id: int,
    measure_data: TradeDefenseMeasureBase,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        result = create_trade_defense_measure(
            country_id=country_id,
            db=db,
            measure_data=measure_data,
        )
        return {"message": "Trade defense measure created successfully", "measure_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 6. Endpoint for creating special fees for a country
@router.post("/create-country-{country_id}/special-fees")
def create_country_special_fee(
    country_id: int,
    fee_data: CountrySpecialFeeBase,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        result = create_special_fee(
            country_id=country_id,
            db=db,
            fee_data=fee_data,
        )
        return {"message": "Special fee created successfully", "fee_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# 7. Endpoint for creating transit bonds for a country
@router.post("/create-country-{country_id}/transit-bond")
def create_country_transit_bond(
    country_id: int,
    bond_data: TransitBondFeeBase,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        result = create_transit_bond(
            country_id=country_id,
            db=db,
            bond_data=bond_data,
        )
        return {"message": "Transit bond created successfully", "bond_id": result.id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
