from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.finance import CarrierFinancialAccounts
from models.carrier import Carrier, CarrierUserAccountLog
from schemas.brokerage.finance import CarrierFinancialAccountResponse
from schemas.carrier import CarrierCompanyResponse
from schemas.user import CarrierUserResponse, DriverCreate, DriverResponse, CarrierUserUpdate
from schemas.vehicle import TrailerCreate, TrailerResponse, VehicleCreate, VehicleResponse, VehicleUpdate
from services.carrier_service import fleet_create_driver
from services.carrier_dashboards import assign_trailer_to_vehicle
from services.vehicle_service import create_trailer, create_vehicle
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import CarrierUser, Driver, CarrierUserDocs
from models.vehicle import Trailer, Vehicle
from schemas.auth import LoginRequest, LoginResponse
import json

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


@router.get("/carrier/account-users")
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
                detail="No user accounts found for this carrier"
            )

        return {
            "users": [
                {
                    "id": user.id,
                    "status": user.status,
                    "verification_status": user.is_verified,
                    "role": user.role,
                    "name": f"{user.first_name} {user.last_name}",
                    "nationality": user.nationality,
                    "id_number": user.id_number,
                    "address": user.home_address if user.home_address else None,
                    "phone_number": user.phone_number,
                    "email": user.email
                }
                for user in users
            ]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@router.get("/carrier/account-user/{user_id}")
def get_carrier_user_with_documents(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        company_id = current_user.get("company_id")

        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="User does not belong to a company"
            )

        # Make sure the requested user belongs to the
        # currently authenticated carrier
        user = db.query(CarrierUser).filter(
            CarrierUser.id == user_id,
            CarrierUser.company_id == company_id
        ).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Carrier user not found"
            )

        # Fetch documents belonging to this user
        documents = db.query(CarrierUserDocs).filter(
            CarrierUserDocs.user_id == user.id
        ).all()

        return {
            "user": {
                "id": user.id,
                "status": user.status,
                "verification_status": user.is_verified,
                "role": user.role,
                "name": f"{user.first_name} {user.last_name}",
                "first_name": user.first_name,
                "last_name": user.last_name,
                "nationality": user.nationality,
                "id_number": user.id_number,
                "address": user.home_address if user.home_address else None,
                "phone_number": user.phone_number,
                "email": user.email,
            },

            "documents": [
                {
                    "id": document.id,
                    "document_type": document.document_type,
                    "document_url": document.document_url,
                    "expiry_date": document.expiry_date,
                    "verification_status": document.is_verified,
                    "status": document.status,
                    "created_at": document.created_at,
                    "updated_at": document.updated_at
                }
                for document in documents
            ]
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch carrier user: {str(e)}"
        )

@router.put("/carrier/update-account-user/{user_id}")
def update_carrier_user(
    db: Session = Depends(get_db),
    user_id = int,
    user_data = CarrierUserUpdate,
    current_user: dict = Depends(get_current_user)
):
    try:
        company_id = current_user.get("company_id")
        changed_by_user_id = current_user.get("user_id")

        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="User does not belong to a company"
            )

        user = db.query(CarrierUser).filter(
            CarrierUser.id == user_id,
            CarrierUser.company_id == company_id
        ).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Carrier user not found"
            )

        changes = []

        # ---------------------------------------------------------
        # ACCOUNT INFORMATION
        # ---------------------------------------------------------

        account_fields = [
            "first_name",
            "last_name",
            "nationality",
            "id_number",
            "home_address",
            "email",
            "phone_number"
        ]

        for field in account_fields:

            new_value = getattr(user_data, field)

            if new_value is None:
                continue

            old_value = getattr(user, field)

            if str(old_value) != str(new_value):

                setattr(user, field, new_value)

                changes.append({
                    "change_type": "Account Information Update",
                    "field_name": field,
                    "old_value": str(old_value) if old_value is not None else None,
                    "new_value": str(new_value)
                })

        # ---------------------------------------------------------
        # ID DOCUMENT
        # ---------------------------------------------------------

        if user_data.id_document:

            document_data = user_data.id_document

            old_document = db.query(CarrierUserDocs).filter(
                CarrierUserDocs.user_id == user.id,
                CarrierUserDocs.document_type == "Identity Document",
                CarrierUserDocs.is_active == True
            ).first()

            new_document = CarrierUserDocs(
                user_id=user.id,
                document_type=document_data.document_type or "Identity Document",
                document_url=document_data.document_url,
                expiry_date=document_data.expiry_date,
                is_active=True,
                is_verified=False,
                status="Un-verified"
            )

            # Deactivate old document
            if old_document:

                old_document.is_active = False

                changes.append({
                    "change_type": "Document Replacement",
                    "field_name": "Identity Document",
                    "old_value": old_document.document_url,
                    "new_value": document_data.document_url
                })

            else:

                changes.append({
                    "change_type": "Document Added",
                    "field_name": "Identity Document",
                    "old_value": None,
                    "new_value": document_data.document_url
                })

            db.add(new_document)

        # ---------------------------------------------------------
        # PROOF OF ADDRESS
        # ---------------------------------------------------------

        if user_data.proof_of_address:

            document_data = user_data.proof_of_address

            old_document = db.query(CarrierUserDocs).filter(
                CarrierUserDocs.user_id == user.id,
                CarrierUserDocs.document_type == "Proof of Address",
                CarrierUserDocs.is_active == True
            ).first()

            new_document = CarrierUserDocs(
                user_id=user.id,
                document_type=document_data.document_type or "Proof of Address",
                document_url=document_data.document_url,
                expiry_date=document_data.expiry_date,
                is_active=True,
                is_verified=False,
                status="Un-verified"
            )

            # Deactivate old document
            if old_document:

                old_document.is_active = False

                changes.append({
                    "change_type": "Document Replacement",
                    "field_name": "Proof of Address",
                    "old_value": old_document.document_url,
                    "new_value": document_data.document_url
                })

            else:

                changes.append({
                    "change_type": "Document Added",
                    "field_name": "Proof of Address",
                    "old_value": None,
                    "new_value": document_data.document_url
                })

            db.add(new_document)

        # ---------------------------------------------------------
        # AUDIT LOG
        # ---------------------------------------------------------

        for change in changes:

            audit_log = CarrierUserAccountLog(
                carrier_user_id=user.id,
                company_id=company_id,
                changed_by_user_id=changed_by_user_id,
                change_type=change["change_type"],
                field_name=change["field_name"],
                old_value=change["old_value"],
                new_value=change["new_value"]
            )

            db.add(audit_log)

        # ---------------------------------------------------------
        # SAVE
        # ---------------------------------------------------------

        db.commit()

        db.refresh(user)

        return {
            "message": "Carrier user account successfully updated.",
            "user_id": user.id,
            "changes_made": len(changes),
            "changes": changes
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to update carrier user: {str(e)}"
        )