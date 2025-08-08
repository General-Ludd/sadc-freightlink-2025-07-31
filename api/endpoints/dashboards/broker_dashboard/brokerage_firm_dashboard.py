from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.finance import FinancialAccounts
from models.shipper import Corporation
from schemas.brokerage.finance import Shipper_Financial_Account_Create
from schemas.shipper import CorporationBase, CorporationResponse
from schemas.user import DirectorCreate, DirectorResponse, ShipperUserResponse
from services.shipper_service import create_brokerage_firm
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

@router.post("/broker-access/registration", status_code=status.HTTP_201_CREATED)
def create_brokerage_firm_endpoint(
    shipper_data: CorporationBase,
    director_data: DirectorCreate,
    financial_data: Shipper_Financial_Account_Create,
    db: Session = Depends(get_db)
):
    try:
        result = create_brokerage_firm(db, shipper_data, director_data, financial_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/broker-access/-sign-in", response_model=LoginResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    print("Login request received for:", request.email)
    
    # Check the `Carrier Director` table
    user = db.query(Director).filter(Director.email == request.email).first()
    company = db.query(Corporation).filter(Corporation.id == user.company_id,
                                            Corporation.type == "Brokerage Firm").first()
    if user:
        role = "director"
    else:
        print("User not found in any brokerage firms database.")
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

@router.get("/broker-access/company-information/id")
def get_brokerage_company_profile_information(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")
    try:
        company = db.query(Corporation).filter(
            Corporation.id == company_id
        ).first()
        director = db.query(Director).filter(
            Director.company_id == company_id
        ).first()
        financial_account = db.query(FinancialAccounts).filter(
            FinancialAccounts.id == company_id
        ).first()
        return {
            "company_information": {
                "id": company.id,
                "type": company.type,
                "company_name": company.legal_business_name,
                "country_of_Incorporation": company.country_of_incorporation,
                "business_registration_number": company.business_registration_number,
                "company_address": company.business_address,
                "company_email": company.business_email,
                "company_phone_number": company.business_phone_number,
                "is_verified": company.is_verified,
                "company_registration_certificate": company.business_registration_certificate,
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
                "proof_off_address": director.proof_of_address,
                },

            "financial_account_information": {
                "id": financial_account.id,
                "payment_terms": financial_account.payment_terms,
                "company_name": financial_account.legal_business_name,
                "country_of_incorporation": financial_account.business_country_of_incorporation,
                "company_registration_number": financial_account.business_registration_number,
                "company_address": financial_account.business_address,
                "company_email": financial_account.business_email,
                "company_phone_number": financial_account.business_phone_number,
                "directors_first_name": financial_account.directors_first_name,
                "directors_last_name": financial_account.directors_last_name,
                "directors_nationality": financial_account.directors_nationality,
                "directors_id_number": financial_account.directors_id_number,
                "directors_home_address": financial_account.directors_home_address,
                "directors_phone_number": financial_account.directors_phone_number,
                "directors_email_address": financial_account.directors_email_address,
                "years_in_business": financial_account.years_in_business,
                "nature_of_business": financial_account.nature_of_business,
                "annual_turnover": financial_account.annual_turnover,
                "annual_cashflow": financial_account.annual_cash_flow,
                "business_credit_score": financial_account.business_credit_score,
                "bank_name": financial_account.bank_name,
                "branch_code": financial_account.branch_code,
                "account_number": financial_account.account_number,
                "account_type": financial_account.account_type,
                "projected_monthly_bookings": financial_account.projected_monthly_bookings,
                "is_verified": financial_account.is_verified,
                "status": financial_account.status,
                "account_confirmation_letter": financial_account.account_confirmation_letter,
                "tax_clearance_certificate": financial_account.tax_clearance_certificate,
                "audited_financial_statement": financial_account.audited_financial_statement,
                "bank_statement": financial_account.bank_statement,
                "business_credit_score_report": financial_account.business_credit_score_report,
                "suretyship": financial_account.suretyship,

                "financial_metrics": {
                    "total_spent": financial_account.total_spent,
                    "average_spend": financial_account.average_spend,
                    "total_outstanding": financial_account.total_outstanding,
                    "total_paid": financial_account.total_paid,
                    "spending_limit": financial_account.spending_limit,
                    "number_of_paid_invoices": financial_account.num_of_paid_invoices,
                    "number_of_outstanding_invoices": financial_account.num_of_paid_invoices,
                    "number_of_overdue_invoices": financial_account.num_overdue_invoices,
                    "number_of_ongoing_interim_invoices": financial_account.number_of_ongoing_interim_invoices,
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


######################################Client Mana