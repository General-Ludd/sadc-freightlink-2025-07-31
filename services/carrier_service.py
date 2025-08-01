from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.brokerage.finance import CarrierFinancialAccounts
from models.carrier import Carrier
from models.user import CarrierDirector, CarrierUser
from models.user import Driver
from schemas.brokerage.finance import Carrier_FinancialAccount_Create
from schemas.user import DriverCreate
from schemas.user import CarrierDirectorCreate, CarrierUsers
from schemas.carrier import CarrierCreate, CreateFleetCarrier
from utils.auth import hash_password

def create_fleet_carrier(db: Session, carrier_data: CarrierCreate, director_data: CarrierUsers, financial_data: Carrier_FinancialAccount_Create):
    # Create Fleet Carrier
    company = Carrier(
        type="Fleet",
        legal_business_name=carrier_data.legal_business_name,
        country_of_incorporation=carrier_data.country_of_incorporation,
        business_registration_number=carrier_data.business_registration_number,
        git_insurance_policy_number=carrier_data.git_insurance_policy_number,
        git_cover_amount=carrier_data.git_cover_amount,
        name_of_git_cover_insurance_company=carrier_data.name_of_git_cover_insurance_company,
        liability_insurance_policy_number=carrier_data.liability_insurance_policy_number,
        liability_insurance_cover_amount=carrier_data.liability_insurance_cover_amount,
        name_of_liability_cover_insurance_company=carrier_data.name_of_liability_cover_insurance_company,
        business_address=carrier_data.business_address,
        business_email=carrier_data.business_email,
        business_phone_number=carrier_data.business_phone_number,
        business_registration_certificate=carrier_data.business_registration_certificate,
        proof_of_address=carrier_data.proof_of_address,
        brnc_certificate=carrier_data.brnc_certificate,
        git_insurance_certificate=carrier_data.git_insurance_certificate,
        liability_insurance_certificate=carrier_data.liability_insurance_certificate,
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    director = CarrierUser(
        role="Director",
        first_name=director_data.first_name,
        last_name=director_data.last_name,
        nationality=director_data.nationality,
        id_number=director_data.id_number,
        home_address=director_data.home_address,
        email=director_data.email,
        phone_number=director_data.phone_number,
        id_document=director_data.id_document,
        proof_of_address=director_data.proof_of_address,
        password_hash=hash_password(director_data.password_hash),
        is_director=True,
        is_verified=False,
        company_id=company.id,
        company_name=company.legal_business_name,
        company_type=company.type,
    )
    db.add(director)
    db.commit()
    db.refresh(director)

    financial_account = CarrierFinancialAccounts(
        id=company.id,
        legal_business_name=carrier_data.legal_business_name,
        business_country_of_incorporation=carrier_data.country_of_incorporation,
        business_registration_number=carrier_data.business_registration_number,
        business_address=carrier_data.business_address,
        business_email=carrier_data.business_email,
        business_phone_number=carrier_data.business_phone_number,
        directors_first_name=director_data.first_name,
        directors_last_name=director_data.last_name,
        directors_nationality=director_data.nationality,
        directors_id_number=director_data.id_number,
        directors_address=director_data.home_address,
        directors_phone_number=director_data.phone_number,
        directors_email_address=director_data.email,
        bank_name=financial_data.bank_name,
        branch_code=financial_data.branch_code,
        account_number=financial_data.account_number,
        account_confirmation_letter=financial_data.account_confirmation_letter,
    )
    db.add(financial_account)
    db.commit()
    db.refresh(financial_account)


    return {"company": company, "director": director}

def create_owner_operator(db: Session, carrier_data: CreateFleetCarrier, director_data: CarrierDirectorCreate, driver_data: DriverCreate):
    # Create Carrier Company
    company = Fleet(
        name=carrier_data.name,
        registration_number=carrier_data.registration_number,
        dot_number=carrier_data.dot_number,
        insurance_policy_number=carrier_data.insurance_policy_number,
        address=carrier_data.address,
        email=carrier_data.email,
        phone_number=carrier_data.phone_number,
        type="fleet",
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    director = CarrierDirector(
        first_name=director_data.first_name,
        last_name=director_data.last_name,
        id_number=director_data.id_number,
        address=director_data.address,
        email=director_data.email,
        phone_number=director_data.phone_number,
        password_hash=hash_password(director_data.password),
        is_admin=True,
        is_verified=False,
        company_id=company.id,
    )
    db.add(director)
    db.commit()
    db.refresh(director)

    driver = Driver(
        first_name=director_data.first_name,
        last_name=director_data.last_name,
        id_number=director_data.id_number,
        license_number=driver_data.license_number,
        prdp_number=driver_data.prdp_number,
        address=driver_data.address,
        email=director_data.email,
        phone_number=director_data.phone_number,
        password_hash=hash_password(driver_data.password),
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)

    return {"company": company, "director": director}

def create_driver(db: Session, driver_data: DriverCreate):
    # Create Driver
    driver = Driver(
        first_name=driver_data.first_name,
        last_name=driver_data.last_name,
        nationality=driver_data.nationality,
        id_number=driver_data.id_number,
        license_number=driver_data.license_number,
        prdp_number=driver_data.prdp_number,
        id_document=driver_data.id_document,
        license_document=driver_data.license_document,
        prdp_document=driver_data.prdp_document,
        proof_of_address=driver_data.proof_of_address,
        address=driver_data.address,
        email=driver_data.email,
        phone_number=driver_data.phone_number,
        password_hash=hash_password(driver_data.password_hash),
    )
    db.add(driver)
    db.commit()
    db.refresh(driver)

    return {"driver": driver}

def fleet_create_driver(db: Session, driver_data: DriverCreate, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )
    
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier Account not verified, or not active")

    # Create Driver
    driver = Driver(
        first_name=driver_data.first_name,
        last_name=driver_data.last_name,
        nationality=driver_data.nationality,
        id_number=driver_data.id_number,
        license_number=driver_data.license_number,
        license_expiry_date=driver_data.license_expiry_date,
        prdp_number=driver_data.prdp_number,
        prdp_expiry_date=driver_data.prdp_expiry_date,
        company_id=carrier.id,
        company_name=carrier.legal_business_name,
        company_type=carrier.type,
        id_document=driver_data.id_document,
        license_document=driver_data.license_document,
        prdp_document=driver_data.prdp_document,
        proof_of_address=driver_data.proof_of_address,
        address=driver_data.address,
        email=driver_data.email,
        phone_number=driver_data.phone_number,
        password_hash=hash_password(driver_data.password_hash),
    )

    carrier.number_of_drivers + 1
    db.add(driver)
    db.commit()
    db.refresh(driver)

    return {"driver": driver}