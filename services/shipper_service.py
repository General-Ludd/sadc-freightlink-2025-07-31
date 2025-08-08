from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from models.brokerage.finance import FinancialAccounts
from models.user import User, Director
from models.shipper import Corporation, Consignor
from schemas.shipper import CorporationBase, ShipperCreate, ConsignorCreate
from schemas.user import UserCreate, DirectorCreate
from schemas.shipper import FacilityCreate
from schemas.brokerage.finance import Shipper_Financial_Account_Create
from utils.auth import hash_password

def create_enterprise_shipper(db: Session, shipper_data: CorporationBase, director_data: DirectorCreate, financial_data: Shipper_Financial_Account_Create):
    #Create Enterprise Shipper
    company = Corporation(
        type="ENTERPRISE",
        legal_business_name=shipper_data.legal_business_name,
        country_of_incorporation=shipper_data.country_of_incorporation,
        business_registration_number=shipper_data.business_registration_number,
        business_address=shipper_data.business_address,
        business_email=shipper_data.business_email,
        business_phone_number=shipper_data.business_phone_number,
        business_registration_certificate=shipper_data.business_registration_certificate,
        business_proof_of_address=shipper_data.business_proof_of_address,
        tax_clearance_certificate=shipper_data.tax_clearence_certificate
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    director = Director(
        first_name=director_data.first_name,
        last_name=director_data.last_name,
        id_number=director_data.id_number,
        nationality=director_data.nationality,
        home_address=director_data.home_address,
        phone_number=director_data.phone_number,
        email=director_data.email,
        password_hash=hash_password(director_data.password),
        id_document=director_data.id_document,
        is_admin=True,
        is_verified=False,
        company_id=company.id,
    )
    db.add(director)
    db.commit()
    db.refresh(director)

    account = FinancialAccounts(
        id=company.id,
        payment_terms=financial_data.payment_terms,
        company_name=shipper_data.legal_business_name,
        business_country_of_incorporation=shipper_data.country_of_incorporation,
        business_registration_number=shipper_data.business_registration_number,
        business_address=shipper_data.business_address,
        directors_first_name=director_data.first_name,
        directors_last_name=director_data.last_name,
        directors_nationality=director_data.nationality,
        directors_id_number=director_data.id_number,
        directors_home_address=director_data.home_address,
        directors_phone_number=director_data.phone_number,
        directors_email_address=director_data.email,
        years_in_business=financial_data.years_in_business,
        nature_of_business=financial_data.nature_of_business,
        annual_turnover=financial_data.annual_turnover,
        annual_cash_flow=financial_data.annual_cash_flow,
        credit_score=financial_data.credit_score,
        bank_name=financial_data.bank_name,
        branch_code=financial_data.branch_code,
        account_number=financial_data.account_number,
        account_type=financial_data.account_type,
        projected_monthly_bookings=financial_data.projected_monthly_bookings,
        tax_clearance_certificate=financial_data.tax_clearance_certificate,
        audited_financial_statement=financial_data.audited_financial_statement,
        bank_statement=financial_data.bank_statement,
        business_credit_score_report=financial_data.business_credit_score_report,
        account_confirmation_letter=financial_data.account_confirmation_letter,
        suretyship=financial_data.suretyship,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return {"company": company, "director": director}


def create_standard_shipper(db: Session, shipper_data: CorporationBase, director_data: DirectorCreate, financial_data: Shipper_Financial_Account_Create):
    #Create Enterprise Shipper
    company = Corporation(
        type="Standard",
        legal_business_name=shipper_data.legal_business_name,
        country_of_incorporation=shipper_data.country_of_incorporation,
        business_registration_number=shipper_data.business_registration_number,
        business_address=shipper_data.business_address,
        business_email=shipper_data.business_email,
        business_phone_number=shipper_data.business_phone_number,
        business_registration_certificate=shipper_data.business_registration_certificate,
        business_proof_of_address=shipper_data.business_proof_of_address,
        tax_clearance_certificate=shipper_data.tax_clearence_certificate
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    director = Director(
        first_name=director_data.first_name,
        last_name=director_data.last_name,
        id_number=director_data.id_number,
        nationality=director_data.nationality,
        home_address=director_data.home_address,
        phone_number=director_data.phone_number,
        email=director_data.email,
        password_hash=hash_password(director_data.password),
        id_document=director_data.id_document,
        is_verified=False,
        company_id=company.id,
    )
    db.add(director)
    db.commit()
    db.refresh(director)

    account = FinancialAccounts(
        id=company.id,
        payment_terms=financial_data.payment_terms,
        company_name=shipper_data.legal_business_name,
        business_country_of_incorporation=shipper_data.country_of_incorporation,
        business_registration_number=shipper_data.business_registration_number,
        business_address=shipper_data.business_address,
        directors_first_name=director_data.first_name,
        directors_last_name=director_data.last_name,
        directors_nationality=director_data.nationality,
        directors_id_number=director_data.id_number,
        directors_home_address=director_data.home_address,
        directors_phone_number=director_data.phone_number,
        directors_email_address=director_data.email,
        years_in_business=financial_data.years_in_business,
        nature_of_business=financial_data.nature_of_business,
        annual_turnover=financial_data.annual_turnover,
        annual_cash_flow=financial_data.annual_cash_flow,
        credit_score=financial_data.credit_score,
        bank_name=financial_data.bank_name,
        branch_code=financial_data.branch_code,
        account_number=financial_data.account_number,
        account_type=financial_data.account_type,
        projected_monthly_bookings=financial_data.projected_monthly_bookings,
        tax_clearance_certificate=financial_data.tax_clearance_certificate,
        audited_financial_statement=financial_data.audited_financial_statement,
        bank_statement=financial_data.bank_statement,
        business_credit_score_report=financial_data.business_credit_score_report,
        account_confirmation_letter=financial_data.account_confirmation_letter,
        suretyship=financial_data.suretyship,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return {"company": company, "director": director}

def create_brokerage_firm(db: Session, shipper_data: CorporationBase, director_data: DirectorCreate, financial_data: Shipper_Financial_Account_Create):
    #Create Brokerage Firm/Shipper
    company = Corporation(
        type="Brokerage Firm",
        legal_business_name=shipper_data.legal_business_name,
        country_of_incorporation=shipper_data.country_of_incorporation,
        business_registration_number=shipper_data.business_registration_number,
        business_address=shipper_data.business_address,
        business_email=shipper_data.business_email,
        business_phone_number=shipper_data.business_phone_number,
        business_registration_certificate=shipper_data.business_registration_certificate,
        business_proof_of_address=shipper_data.business_proof_of_address,
        tax_clearance_certificate=shipper_data.tax_clearence_certificate
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    director = Director(
        first_name=director_data.first_name,
        last_name=director_data.last_name,
        id_number=director_data.id_number,
        nationality=director_data.nationality,
        home_address=director_data.home_address,
        phone_number=director_data.phone_number,
        email=director_data.email,
        password_hash=hash_password(director_data.password),
        id_document=director_data.id_document,
        is_verified=False,
        company_id=company.id,
    )
    db.add(director)
    db.commit()
    db.refresh(director)

    account = FinancialAccounts(
        id=company.id,
        payment_terms=financial_data.payment_terms,
        company_name=shipper_data.legal_business_name,
        business_country_of_incorporation=shipper_data.country_of_incorporation,
        business_registration_number=shipper_data.business_registration_number,
        business_address=shipper_data.business_address,
        directors_first_name=director_data.first_name,
        directors_last_name=director_data.last_name,
        directors_nationality=director_data.nationality,
        directors_id_number=director_data.id_number,
        directors_home_address=director_data.home_address,
        directors_phone_number=director_data.phone_number,
        directors_email_address=director_data.email,
        years_in_business=financial_data.years_in_business,
        nature_of_business=financial_data.nature_of_business,
        annual_turnover=financial_data.annual_turnover,
        annual_cash_flow=financial_data.annual_cash_flow,
        credit_score=financial_data.credit_score,
        bank_name=financial_data.bank_name,
        branch_code=financial_data.branch_code,
        account_number=financial_data.account_number,
        account_type=financial_data.account_type,
        projected_monthly_bookings=financial_data.projected_monthly_bookings,
        tax_clearance_certificate=financial_data.tax_clearance_certificate,
        audited_financial_statement=financial_data.audited_financial_statement,
        bank_statement=financial_data.bank_statement,
        business_credit_score_report=financial_data.business_credit_score_report,
        account_confirmation_letter=financial_data.account_confirmation_letter,
        suretyship=financial_data.suretyship,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return {"company": company, "director": director}

def create_facility_shipper(db: Session, facility_data: FacilityCreate, director_data: UserCreate):
    try:
        # Check if the facility type is subsidiary
        if facility_data.facility_type == "subsidiary_facility":
            # Create an entry in the companies table
            company = Company(
                name=facility_data.name,
                registration_number=facility_data.registration_number,
                address=facility_data.address,
                email=facility_data.email,
                phone_number=facility_data.phone_number,
                type="facility",
                parent_company_id=facility_data.parent_company_id,
                facility_type=facility_data.facility_type,
                is_verified=facility_data.is_verified,
            )
            db.add(company)
            db.commit()
            db.refresh(company)
        elif facility_data.facility_type == "outpost_facility":
            company = None  # No entry is made in the companies table
        else:
            raise ValueError("Invalid facility type provided.")

        # Create an entry in the facilities table
        facility = Facility(
            id=company.id if company else None,  # Use company ID for subsidiaries
            facility_code=facility_data.facility_code,
            name=facility_data.name,
            registration_number=facility_data.registration_number,
            address=facility_data.address,
            email=facility_data.email,
            phone_number=facility_data.phone_number,
            type="facility",
            parent_company_id=facility_data.parent_company_id,
            facility_type=facility_data.facility_type,
            is_verified=facility_data.is_verified,
        )
        db.add(facility)
        db.commit()
        db.refresh(facility)

        # Create the director/admin user for the facility
        director = User(
            first_name=director_data.first_name,
            last_name=director_data.last_name,
            id_number=director_data.id_number,
            address=director_data.address,
            email=director_data.email,
            phone_number=director_data.phone_number,
            password_hash=hash_password(director_data.password),
            is_admin=True,
            is_verified=False,
            company_id=company.id if company else None,  # Link to the company if it's a subsidiary
        )
        db.add(director)
        db.commit()
        db.refresh(director)

        return {"facility": facility, "director": director}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

def create_brokerage_firm_consignor_client(
    consignor_data: ConsignorCreate,
    db: Session,
    current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    consignor = Consignor(
        brokerage_firm_id=company_id,
        status=consignor_data.status,
        priority_level=consignor_data.priority_level,
        company_name=consignor_data.company_name,
        client_type=consignor_data.client_type,
        business_sector=consignor_data.business_sector,
        company_website=consignor_data.company_website,
        business_address=consignor_data.business_address,
        contact_person_name=consignor_data.contact_person_name,
        position=consignor_data.position,
        phone_number=consignor_data.phone_number,
        email=consignor_data.email,
        preferred_contact_method=consignor_data.preferred_contact_method,
        client_notes=consignor_data.client_notes,
    )
    db.add(consignor)
    db.commit()
    db.refresh(consignor)

    return {"Consignor successfully created"}