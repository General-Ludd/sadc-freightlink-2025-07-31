from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from models.brokerage.finance import FinancialAccounts
from models.user import User, Director, Corporation_Profile
from models.shipper import Corporation, Consignor
from schemas.shipper import CorporationBase, ShipperCreate, ConsignorCreate, FacilityCreation
from schemas.user import UserCreate, DirectorCreate
from schemas.shipper import FacilityCreate, CorporationProfile
from schemas.brokerage.finance import Shipper_Financial_Account_Create, Enterprise_Financial_Account_Create
from utils.auth import hash_password
from utils.notifications import create_notification

def create_facility_shipper(
    db: Session,
    shipper_data: FacilityCreation,
    manager_data: DirectorCreate,
    current_user: dict     # ✅ FIX: Pass current_user into the function
):
    # --- VALIDATE CURRENT USER ---
    if "company_id" not in current_user:
        raise HTTPException(status_code=400, detail="Missing company_id in current_user")

    company_id = current_user.get("company_id")
    user_id = current_user.get("id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    # --- FETCH PARENT COMPANY + ADMIN DIRECTOR ---
    parent_company = db.query(Corporation).filter(
        Corporation.id == company_id
    ).first()

    parent_director = db.query(Director).filter(
        Director.company_id == parent_company.id,
        Director.is_admin == True
    ).first()

    parent_financial_account = db.query(FinancialAccounts).filter(
        FinancialAccounts.id == parent_company.id
    ).first()

    # --- CREATE FACILITY COMPANY ---
    company = Corporation(
        parent_company_id=parent_company.id,
        type="Facility",
        legal_business_name=shipper_data.facility_name,
        country_of_incorporation=shipper_data.country,
        business_registration_number=parent_company.business_registration_number,
        business_address=shipper_data.facility_address,
        business_email=shipper_data.facility_email,
        business_phone_number=shipper_data.facility_phone_number,
        business_registration_certificate=parent_company.business_registration_certificate,
        business_proof_of_address=shipper_data.facility_proof_of_address,
        tax_clearance_certificate=parent_company.tax_clearance_certificate if parent_company.tax_clearance_certificate else None,
        is_verified=True,
        status="Active",
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    # --- CREATE FACILITY MANAGER ---
    manager = Director(
        first_name=manager_data.first_name,
        last_name=manager_data.last_name,
        id_number=manager_data.id_number,
        nationality=manager_data.nationality,
        home_address=manager_data.home_address,
        phone_number=manager_data.phone_number,
        email=manager_data.email,
        password_hash=hash_password(manager_data.password),
        id_document=manager_data.id_document,
        is_director=False,
        is_verified=True,
        status="Active",
        company_id=company.id,
    )
    db.add(manager)
    db.commit()
    db.refresh(manager)

    # --- CREATE FACILITY FINANCIAL ACCOUNT ---
    account = FinancialAccounts(
        id=company.id,   # same as facility id
        payment_terms=parent_financial_account.payment_terms,
        company_name=f"{shipper_data.facility_name} facility of ({parent_company.legal_business_name})",
        business_country_of_incorporation=shipper_data.country,
        business_registration_number=parent_company.business_registration_number,
        business_address=shipper_data.facility_address,

        # Parent director information (not the facility manager)
        directors_first_name=parent_director.first_name,
        directors_last_name=parent_director.last_name,
        directors_nationality=parent_director.nationality,
        directors_id_number=parent_director.id_number,
        directors_home_address=parent_director.home_address,
        directors_phone_number=parent_director.phone_number,
        directors_email_address=parent_director.email,
        years_in_business=parent_financial_account.years_in_business,
        nature_of_business=parent_financial_account.nature_of_business,
        projected_monthly_bookings=parent_financial_account.projected_monthly_bookings,
        spending_limit=parent_financial_account.spending_limit,
        is_verified=True,
        status="Active",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return {
        "facility": company,
        "facility_manager": manager,
        "financial_account": account
    }

def create_enterprise_shipper(db: Session, shipper_data: CorporationBase, director_data: DirectorCreate, financial_data: Enterprise_Financial_Account_Create):
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
        role=director_data.role,
        first_name=director_data.first_name,
        last_name=director_data.last_name,
        id_number=director_data.id_number,
        nationality=director_data.nationality,
        home_address=director_data.home_address,
        phone_number=director_data.phone_number,
        email=director_data.email,
        password_hash=hash_password(director_data.password),
        id_document=director_data.id_document,
        is_director=False,
        is_verified=False,
        company_id=company.id,
    )
    db.add(director)
    db.commit()
    db.refresh(director)

    account = FinancialAccounts(
        id=company.id,
        payment_terms=financial_data.payment_terms,
        years_in_business=financial_data.years_in_business,
        nature_of_business=financial_data.nature_of_business,
        projected_monthly_bookings=(financial_data.projected_daily_bookings * 30),
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
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return {"company": company, "director": director}


def create_standard_shipper(db: Session, shipper_data: CorporationBase, director_data: DirectorCreate, client_profile: CorporationProfile, financial_data: Shipper_Financial_Account_Create):
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
        role=director_data.role,
        first_name=director_data.first_name,
        last_name=director_data.last_name,
        id_number=director_data.id_number,
        nationality=director_data.nationality,
        home_address=director_data.home_address,
        phone_number=director_data.phone_number,
        email=director_data.email,
        password_hash=hash_password(director_data.password_hash),
        id_document=director_data.id_document,
        is_director=False,
        is_verified=False,
        company_id=company.id,
    )
    db.add(director)
    db.commit()
    db.refresh(director)

    client_profile = Corporation_Profile(
        commodities=client_profile_data.commodities
        commodity_description=client_profile_data.commodity_description,
        maximum_git_insurance_required=client_profile_data.maximum_git_insurance_required,
        number_of_transport_providers_currently_used=client_profile_data.number_of_transport_providers_currently_used,
        primary_routes=client_profile_data.primary_routes,
        tautliners=client_profile_data.tautliners,
        flatbeds=client_profile_data.flatbeds,
        flatbeds_with_twistlocks=client_profile_data.flatbeds_with_twistlocks,
        dropsides=client_profile_data.dropsides,
        skeletals=client_profile_data.skeletals,
        pantechs=client_profile_data.pantechs,
        bottom_dumpers=client_profile_data.bottom_dumpers,
        side_tippers=client_profile_data.side_tippers,
        low_beds=client_profile_data.low_beds,
        timber_trailers=client_profile_data.timber_trailers,
        sugar_cane_trailers=client_profile_data.sugar_cane_trailers,
    )
    db.add(client_profile)
    db.commit()
    db.refresh(client_profile)

    account = FinancialAccounts(
        id=company.id,
        payment_terms=financial_data.payment_terms,
        company_name=shipper_data.legal_business_name,
        business_country_of_incorporation=shipper_data.country_of_incorporation,
        business_registration_number=shipper_data.business_registration_number,
        business_address=shipper_data.business_address,
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
        role=director_data.role,
        first_name=director_data.first_name,
        last_name=director_data.last_name,
        id_number=director_data.id_number,
        nationality=director_data.nationality,
        home_address=director_data.home_address,
        phone_number=director_data.phone_number,
        email=director_data.email,
        password_hash=hash_password(director_data.password_hash),
        id_document=director_data.id_document,
        is_director=False,
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

        # ✅ Create notification for the new brokerage firm
        create_notification(
            db=db,
            company_id=company.id,
            notif_type="registration",
            message=f"Brokerage firm '{company.legal_business_name}' has been successfully registered. Your company account is currently undergoing verification."
        )

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
    
    return {"message": "Consignor successfully created", "id": consignor.id}
