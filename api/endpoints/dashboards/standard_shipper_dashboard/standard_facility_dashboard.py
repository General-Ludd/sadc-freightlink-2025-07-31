from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.finance import FinancialAccounts
from models.shipper import Corporation
from schemas.brokerage.finance import Shipper_Financial_Account_Create
from schemas.shipper import CorporationBase, CorporationResponse
from schemas.user import DirectorCreate, DirectorResponse, ShipperUserResponse
from services.shipper_service import create_standard_shipper
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import Director, User, Driver, CarrierDirector
from models.vehicle import Vehicle
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/shippers/standard-registration", status_code=status.HTTP_201_CREATED)
def create_standard_shipper_endpoint(
    shipper_data: CorporationBase,
    director_data: DirectorCreate,
    financial_data: Shipper_Financial_Account_Create,
    db: Session = Depends(get_db)
):
    try:
        result = create_standard_shipper(db, shipper_data, director_data, financial_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/standard-shipper-sign-in", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    print("Login request received for:", request.email)
    
    # Check the `Carrier Director` table
    user = db.query(Director).filter(Director.email == request.email).first()
    if user:
        role = "director"
    else:
        print("User not found in any database.")
        raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(request.password, user.password_hash):
        print("Password verification failed for:", request.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    print(f"User authenticated successfully as {role}: {user.email}")

    # Create token with role-specific information
    token = create_access_token({"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "company_id": user.company_id})
    print("Generated JWT token:", token)

    return {"access_token": token, "token_type": "bearer"}

@router.get("/shipper/company-information/id")
def get_shipper_company_profile_information(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")
    try:
        company = db.query(Corporation).filter(
            Corporation.id == company_id
        )
        director = db.query(Director).filter(
            Director.company_id == company_id
        )
        financial_account = db.query(FinancialAccounts).filter(
            FinancialAccounts.id == company_id
        )
        return {
            "company_information": {
                "id": company.id,
                "type": company.type,
                "company_name": company.legal_business_name,
                "country_of_Incorporation": company.country_of_incorporation,
                "business_registration_number": company.business_registration_number,
                "company_address": company.company_address,
                "company_email": company.company_email,
                "company_phone_number": company.company_phone_number,
                "is_verified": company.is_verified,
                "company_registration_certificate": company.company_registration_certificate,
                "business_proof_of_address": company.business_proof_of_address,
                "tax_clearance_certificate": company.tax_clearance_certificate,
            },

            "director_information": {
                "id": director.id,
                "company_id": director.company_id,
                "first_name": director.first_name,
                "last_name": director.last_name,
                "id_number": director.id_number,
                "nationality": director.nationality,
                "home_address": director.home_address,
                "phone_number": director.phone_number,
                "email": director.email,
                "is_director": director.is_director,
                "is_verified": director.is_verified,
                "status": director.status,
                "id_document": director.id_document,
                "proof_off_address": director.proof_off_address,
                }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shipper/company/id", response_model=CorporationResponse) #UnTested
def get_current_users_shipper_company(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        shipper_company = db.query(Corporation).filter(
            Corporation.id == company_id,
        ).first()

        if not shipper_company:
            raise HTTPException(
                status_code=404,
                detail=f"Shipper company with (ID {id}) not found or user not authorized to access said account information"
            )
        
        return shipper_company
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/shipper/company/director/id", response_model=DirectorResponse) #UnTested
def get_current_users_shipper_company_director_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        shipper_director_account = db.query(Director).filter(
            Director.company_id == company_id,
            Director.is_verified == True
        ).first()

        if not shipper_director_account:
            raise HTTPException(
                status_code=404,
                detail=f"Shipper company director with (ID {id}) not found or user not authorized to access said account information"
            )
        
        return shipper_director_account
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shipper/company/financial-account/id", response_model=CorporationResponse) #UnTested
def get_current_users_shipper_company_financial_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        shipper_financial_account = db.query(FinancialAccounts).filter(
            FinancialAccounts.id == company_id,
        ).first()

        if not shipper_financial_account:
            raise HTTPException(
                status_code=404,
                detail=f"Shipper financial account with (ID {id}) not found or user not authorized to access said account information"
            )
        
        return shipper_financial_account
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

#################################To be re-eximaned##########################################################

@router.get("/shipper/user/{id}", response_model=ShipperUserResponse) #UnTested
def get_individual_shipper_user_account(
    id: int,
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
        user = db.query(Director).filter(
            Director.id == id,
            Director.company_id == company_id
        ).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {id} not found or not authorized"
            )

        return user

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shipper/current/user", response_model=ShipperUserResponse) #UnTested
def get_individual_shipper_current_user_account(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )


    try:
        user = db.query(Director).filter(
            Director.id == user_id,
        ).first()

        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {id} not found or not authorized"
            )

        return user

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))