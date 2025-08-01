from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.finance import CarrierFinancialAccounts
from models.carrier import Carrier
from schemas.brokerage.finance import CarrierFinancialAccountResponse
from schemas.carrier import CarrierCompanyResponse
from schemas.user import CarrierUserResponse, DriverCreate, DriverResponse
from schemas.vehicle import TrailerCreate, TrailerResponse, VehicleCreate, VehicleResponse, VehicleUpdate
from services.carrier_service import fleet_create_driver
from services.carrier_dashboards import assign_primary_driver, assign_trailer_to_vehicle
from services.vehicle_service import create_trailer, create_vehicle
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import CarrierUser, Driver
from models.vehicle import Trailer, Vehicle
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

################################################Carrier Account##############################################
#####POST#####GET####UPDATE#####DEACTIVATE/DELETE####
@router.get("/carrier/company/id", response_model=CarrierCompanyResponse) #UnTested
def get_carrier_company_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )


    try:
        company = db.query(Carrier).filter(
            Carrier.id == company_id
        ).first()

        if not company:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {id} not found or not authorized"
            )

        return company

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

##############################################Financial Account##############################################
#####POST#####GET####UPDATE#####DEACTIVATE/DELETE####
@router.get("/carrier/financial-account/id", response_model=CarrierFinancialAccountResponse) #UnTested
def get_carrier_financial_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )


    try:
        financial_account = db.query(CarrierFinancialAccounts).filter(
            CarrierFinancialAccounts.id == company_id,
        ).first()

        if not financial_account:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {id} not found or not authorized"
            )

        return financial_account

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

################################################Carrier User Accounts##############################################
#####POST#####GET####UPDATE#####DEACTIVATE/DELETE####

@router.get("/carrier/user/director", response_model=CarrierUserResponse)  # Fixed route
def get_carrier_director_user_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        user = db.query(CarrierUser).filter(
            CarrierUser.company_id == company_id,
            CarrierUser.is_director == True  # Fixed True
        ).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Director user not found or not authorized"  # Fixed message
            )

        return user

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/carrier/account-users", response_model=List[CarrierUserResponse]) #UnTested
def get_carrier_sub_user_accounts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )


    try:
        users = db.query(CarrierUser).filter(
            CarrierUser.company_id == company_id
        ).all()

        if not users:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {id} not found or not authorized"
            )

        return users

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))