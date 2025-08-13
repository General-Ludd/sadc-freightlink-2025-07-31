from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session
from db.database import SessionLocal
from utils.auth import get_current_user, verify_password
from models.user import Director, User, Driver, CarrierDirector
from schemas.user import DirectorCreate, DirectorUpdate
from services.user_service import create_shipper_sub_user
from enums import UserStatus

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/company/create-sub-user", status_code=status.HTTP_201_CREATED)
def create_shipper_sub_user_endpoint(
    user_data: DirectorCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = create_shipper_sub_user(db, user_data, current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/all-company-users")
def get_shipper_and_broker_users(
    status: Optional[UserStatus] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        query = db.query(User).filter(User.company_id == company_id)

        if status:
            query = query.filter(User.status == status.value)

        users = query.all()

        return [{
            "name": f"{user.first_name} {user.last_name}",
            "id": user.id,
            "status": user.status,
            "director": user.is_director or None,
            "verification_status": user.is_verified,
            "nationality": user.nationality,
            "address": user.home_address,
            "phone_number": user.phone_number,
            "email": user.email,
            "company_id": user.company_id,
        } for user in users]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company-user/{id}")
def get_shipper_and_broker_user_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        user = db.query(Director).filter(Director.id == id,
                                        Director.company_id == company_id).first()

        return {
            "user_details": {
                "id": user.id,
                "company_id": user.company_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "id_number": user.id_number,
                "nationality": user.nationality,
                "home_address": user.home_address,
                "phone_number": user.phone_number,
                "email": user.email,
                "is_director": user.is_director,
                "is_verified": user.is_verified,
                "status": user.status
            },

            "documents": {
                "id_documents": user.id_document,
                "proof_of_address": user.proof_of_address
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update-company-user/{user_id}")
def update_company_user(
    user_id: int,
    user_data: DirectorUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    # Find the user to update
    user = db.query(Director).filter(
        Director.id == user_id,
        Director.company_id == company_id
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found or not in your company")

    updated_fields = user_data.dict(exclude_unset=True)

    for field, new_value in updated_fields.items():
        old_value = getattr(user, field)

        if old_value != new_value:
            # Update the field
            setattr(user, field, new_value)

            # Create an audit log record
            log = UserAuditLog(
                user_id=user.id,
                changed_by_user_id=current_user["user_id"],
                company_id=current_user["company_id"],
                company_type="Shipper or Brokerage Firm",
                field_name=field,
                old_value=str(old_value) if old_value is not None else None,
                new_value=str(new_value) if new_value is not None else None
            )
            db.add(log)

    db.commit()
    db.refresh(user)

    return {
        "message": f"User {user.first_name} {user.last_name} updated successfully",
        "updated_fields": updated_fields
    }
