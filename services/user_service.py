from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from models.brokerage.finance import FinancialAccounts
from models.user import User, Director
from schemas.user import DirectorCreate, DirectorUpdate
from utils.auth import hash_password

def create_shipper_sub_user(db: Session, user_data: DirectorCreate, current_user=dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    user = Director(
        company_id=company_id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        id_number=user_data.id_number,
        nationality=user_data.nationality,
        home_address=user_data.home_address,
        phone_number=user_data.phone_number,
        email=user_data.email,
        password_hash=hash_password(user_data.password_hash),
        is_director=False,
        id_document=user_data.id_document,
        proof_of_address=user_data.proof_of_address,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {f"sub-user-{user.id} ({user.first_name}-{user.last_name}) successfully created, currently awaiting verification"}


