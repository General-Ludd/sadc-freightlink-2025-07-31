from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.finance import FinancialAccounts, Shipment_Invoice, Interim_Invoice, Invoices
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.shipper import Corporation, Client_Notification
from schemas.brokerage.finance import Shipper_Financial_Account_Create
from schemas.shipper import CorporationBase, CorporationResponse
from schemas.user import DirectorCreate, DirectorResponse, ShipperUserResponse
from services.shipper_service import create_standard_shipper
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import Director, User, Driver, CarrierDirector
from schemas.auth import LoginRequest, LoginResponse

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/shipper/company-name")
def get_shipper_company_name(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        shipper = db.query(Corporation).filter(Corporation.id == current_user.get("company_id")).first()
        return shipper.legal_business_name
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/shipper/current-user-name")
def get_current_user_name(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        user = db.query(Director).filter(Director.id == current_user.get("id")).first()
        return user.first_name
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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

@router.get("/shipper/company-information")
def get_shipper_company_profile_information(
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
            "verification": {
                "company_information": company.is_verified,
                "director_information": director.is_verified,
                "financial_information": financial_account.is_verified
            },
            
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
                "company_name": company.legal_business_name,
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
                "business_credit_score": financial_account.credit_score,
                "bank_name": financial_account.bank_name,
                "branch_code": financial_account.branch_code,
                "account_number": financial_account.account_number,
                "account_type": financial_account.account_type,
                "projected_monthly_bookings": financial_account.projected_monthly_bookings,
                "is_verified": financial_account.is_verified,
                "status": financial_account.status,
                "account_confirmation_letter": financial_account.account_confirmation_letter,
                "tax_clearance_certificate": financial_account.tax_clearance_certificate,
                "audited_financial_statements": financial_account.audited_financial_statement,
                "bank_statement": financial_account.bank_statement,
                "business_credit_score_report": financial_account.business_credit_score_report,
                "suretyship": financial_account.suretyship,

                "financial_metrics": {
                    "total_spent": financial_account.total_spent,
                    "average_spend": financial_account.average_spend,
                    "total_outstanding": financial_account.total_outstanding,
                    "total_paid": financial_account.total_paid,
                    "credit_balance": financial_account.credit_balance,
                    "spending_limit": financial_account.spending_limit,
                    "number_of_paid_invoices": financial_account.num_paid_invoices,
                    "number_of_outstanding_invoices": financial_account.num_outstanding_invoices,
                    "number_of_overdue_invoices": financial_account.num_overdue_invoices,
                    "number_of_ongoing_interim_invoices": financial_account.ongoing_interim_invoices,
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/shipper/financial-account")
def get_shipper_financial_profile_information(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")
    try:
        financial_account = db.query(FinancialAccounts).filter(FinancialAccounts.id == company_id).first()
        service_invoices = db.query(Shipment_Invoice).filter(Shipment_Invoice.financial_account_id == financial_account.id).all()
        interim_invoices = db.query(Interim_Invoice).filter(Interim_Invoice.financial_account_id == financial_account.id).all()
        lane_invoices = db.query(Invoices).filter(Invoices.financial_account_id == financial_account.id).all()
        ftl_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.shipper_company_id == company_id).all()
        power_shipments = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.shipper_company_id == company_id).all()

        return {
            "financial_account_information": {
                "id": financial_account.id,
                "payment_terms": financial_account.payment_terms,
                "years_in_business": financial_account.years_in_business,
                "nature_of_business": financial_account.nature_of_business,
                "annual_turnover": financial_account.annual_turnover,
                "annual_cashflow": financial_account.annual_cash_flow,
                "business_credit_score": financial_account.credit_score,
                "bank_name": financial_account.bank_name,
                "branch_code": financial_account.branch_code,
                "account_number": financial_account.account_number,
                "account_type": financial_account.account_type,
                "projected_monthly_bookings": financial_account.projected_monthly_bookings,
                "is_verified": financial_account.is_verified,
                "status": financial_account.status,
                "account_confirmation_letter": financial_account.account_confirmation_letter,
                "tax_clearance_certificate": financial_account.tax_clearance_certificate,
                "audited_financial_statements": financial_account.audited_financial_statement,
                "bank_statement": financial_account.bank_statement,
                "business_credit_score_report": financial_account.business_credit_score_report,
                "suretyship": financial_account.suretyship,

                "financial_metrics": {
                    "total_spent": financial_account.total_spent,
                    "average_spend": financial_account.average_spend,
                    "total_outstanding": financial_account.total_outstanding,
                    "total_paid": financial_account.total_paid,
                    "credit_balance": financial_account.credit_balance,
                    "projected_spending": financial_account.projected_balance,
                    "spending_limit": financial_account.spending_limit,
                    "number_of_paid_invoices": financial_account.num_paid_invoices,
                    "number_of_outstanding_invoices": financial_account.num_outstanding_invoices,
                    "number_of_overdue_invoices": financial_account.num_overdue_invoices,
                    "number_of_ongoing_interim_invoices": financial_account.ongoing_interim_invoices,
                }
            },
            
            "financial_spending": [{
                "amount": service_invoice.due_amount,
                "date": service_invoice.billing_date
            } for service_invoice in service_invoices],

            "invoices": {
                "service_invoices": [{
                    "id": service_invoice.id,
                    "description": service_invoice.description,
                    "billing_date": service_invoice.billing_date,
                    "status": service_invoice.status,
                    "due_date": service_invoice.due_date,
                    "due_amount": (service_invoice.due_amount - service_invoice.paid_amount if service_invoice.paid_amount else service_invoice.due_amount),
                } for service_invoice in service_invoices],

                "interim_invoices": [{
                    "id": interim_invoice.id,
                    "lane_id": interim_invoice.contract_id,
                    "lane_type": interim_invoice.contract_type,
                    "period": f"{interim_invoice.billing_date}-{interim_invoice.due_date}",
                    "description": interim_invoice.description,
                    "status": interim_invoice.status,
                    "due_date": interim_invoice.due_date,
                    "due_amount": (interim_invoice.due_amount - interim_invoice.paid_amount),
                    } for interim_invoice in interim_invoices],

                "lane_invoices": [{
                    "id": lane_invoice.id,
                    "billing_date": lane_invoice.billing_date,
                    "description": lane_invoice.description,
                    "status": lane_invoice.status,
                    "due_date": lane_invoice.due_date,
                    "due_amount": (lane_invoice.due_amount - lane_invoice.paid_amount),
                } for lane_invoice in lane_invoices],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/shipper/notifications")
def get_shipper_account_notifications(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    try:
        notifications = db.query(Client_Notification).filter(Client_Notification.company_id == company_id).all()

        return {
            "notifications": [{
                "id": notification.id,
                "subject": notification.type,
                "message": notification.message,
                "is_read": notification.is_read,
                "recieved_at": notification.created_at
            } for notification in notifications]
        }
    except Exception as e:
        return {"error": str(e)}