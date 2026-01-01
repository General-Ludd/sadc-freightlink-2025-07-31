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
from schemas.nexus.customs import CountryBase, Customs_Duty_Authority_Base, CountryTradeAgreementBase, TariffScheduleBase
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
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
    CountryBase,
    Customs_Duty_Authority_Base
):
    try:
        result = admin_create_country(
            db,
            CountryBase,
            Customs_Duty_Authority_Base,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))