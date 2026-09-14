from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.brokerage.finance import CarrierFinancialAccounts
from models.carrier import Carrier, CarrierDocs, Carrier_Profile, Carrier_Notification
from models.user import CarrierDirector, CarrierUserDocs, CarrierUser
from models.user import Driver
from schemas.brokerage.finance import Carrier_FinancialAccount_Create
from schemas.user import DriverCreate
from schemas.user import CarrierDirectorCreate, CarrierUsers
from schemas.carrier import CarrierCreate, CreateFleetCarrier, CarrierProfile
from utils.auth import hash_password
import json


def create_fleet_carrier(
    db: Session,
    carrier_data: CarrierCreate,
    director_data: CarrierUsers,
    financial_data: Carrier_FinancialAccount_Create,
    carrier_profile_data: CarrierProfile
):
    try:

        # ============================================================
        # 1. CREATE FLEET CARRIER
        # ============================================================

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

            # Existing Carrier VARCHAR JSON fields
            business_registration_certificate=json.dumps(
                carrier_data.business_registration_certificate.model_dump(mode="json")
            ),

            proof_of_address=json.dumps(
                carrier_data.proof_of_address.model_dump(mode="json")
            ),

            brnc_certificate=(
                json.dumps(
                    carrier_data.brnc_certificate.model_dump(mode="json")
                )
                if carrier_data.brnc_certificate
                else None
            ),

            git_insurance_certificate=json.dumps(
                carrier_data.git_insurance_certificate.model_dump(mode="json")
            ),

            liability_insurance_certificate=json.dumps(
                carrier_data.liability_insurance_certificate.model_dump(mode="json")
            ),
        )

        db.add(company)

        # Get company.id without committing yet
        db.flush()


        # ============================================================
        # 2. CREATE CARRIER DOCUMENT RECORDS
        # ============================================================

        carrier_documents = [

            # Business Registration Certificate
            CarrierDocs(
                carrier_id=company.id,
                document_type=carrier_data.business_registration_certificate.document_type,
                document_url=carrier_data.business_registration_certificate.document_url,
                expiry_date=carrier_data.business_registration_certificate.expiry_date,
                is_verified=False,
                status="Un-verified"
            ),

            # Proof of Address
            CarrierDocs(
                carrier_id=company.id,
                document_type=carrier_data.proof_of_address.document_type,
                document_url=carrier_data.proof_of_address.document_url,
                expiry_date=carrier_data.proof_of_address.expiry_date,
                is_verified=False,
                status="Un-verified"
            ),

            # GIT Insurance Certificate
            CarrierDocs(
                carrier_id=company.id,
                document_type=carrier_data.git_insurance_certificate.document_type,
                document_url=carrier_data.git_insurance_certificate.document_url,
                expiry_date=carrier_data.git_insurance_certificate.expiry_date,
                is_verified=False,
                status="Un-verified"
            ),

            # Liability Insurance Certificate
            CarrierDocs(
                carrier_id=company.id,
                document_type=carrier_data.liability_insurance_certificate.document_type,
                document_url=carrier_data.liability_insurance_certificate.document_url,
                expiry_date=carrier_data.liability_insurance_certificate.expiry_date,
                is_verified=False,
                status="Un-verified"
            )
        ]


        # Optional BRNC Certificate
        if carrier_data.brnc_certificate:

            carrier_documents.append(
                CarrierDocs(
                    carrier_id=company.id,
                    document_type=carrier_data.brnc_certificate.document_type,
                    document_url=carrier_data.brnc_certificate.document_url,
                    expiry_date=carrier_data.brnc_certificate.expiry_date,
                    is_verified=False,
                    status="Un-verified"
                )
            )


        db.add_all(carrier_documents)


        # ============================================================
        # 3. CREATE DIRECTOR
        # ============================================================

        director = CarrierUser(
            role=director_data.role,
            first_name=director_data.first_name,
            last_name=director_data.last_name,
            nationality=director_data.nationality,
            id_number=director_data.id_number,
            home_address=director_data.home_address,
            email=director_data.email,
            phone_number=director_data.phone_number,

            # Existing CarrierUser VARCHAR JSON fields
            id_document=json.dumps(
                director_data.id_document.model_dump(mode="json")
            ),

            proof_of_address=(
                json.dumps(
                    director_data.proof_of_address.model_dump(mode="json")
                )
                if director_data.proof_of_address
                else None
            ),

            password_hash=hash_password(
                director_data.password_hash
            ),

            is_director=True,
            is_verified=False,

            company_id=company.id,
            company_name=company.legal_business_name,
            company_type=company.type,
        )

        db.add(director)
        db.flush()


        # ============================================================
        # 4. CREATE FINANCIAL ACCOUNT
        # ============================================================

        financial_account = CarrierFinancialAccounts(
            id=company.id,

            legal_business_name=carrier_data.legal_business_name,
            business_country_of_incorporation=carrier_data.country_of_incorporation,
            business_registration_number=carrier_data.business_registration_number,

            business_address=carrier_data.business_address,
            business_email=carrier_data.business_email,
            business_phone_number=carrier_data.business_phone_number,

            bank_name=financial_data.bank_name,
            bank_country=financial_data.bank_country,
            branch_code=financial_data.branch_code,
            account_type=financial_data.account_type,
            account_number=financial_data.account_number,

            # Existing VARCHAR JSON field
            account_confirmation_letter=json.dumps(
                financial_data.account_confirmation_letter.model_dump(mode="json")
            ),
        )

        db.add(financial_account)
        db.flush()


        # ============================================================
        # 5. CREATE CARRIER PROFILE
        # ============================================================

        carrier_profile = Carrier_Profile(
            carrier_id=company.id,

            primary_routes=carrier_profile_data.primary_routes,
            hazchem_certified=carrier_profile_data.hazchem_certified,
            rib_certification=carrier_profile_data.rib_certification,

            rigid_tautliners=carrier_profile_data.rigid_tautliners,
            triaxle_tautliners=carrier_profile_data.triaxle_tautliners,
            superlink_tautliners=carrier_profile_data.superlink_tautliners,

            rigid_flatbeds=carrier_profile_data.rigid_flatbeds,
            triaxle_flatbeds=carrier_profile_data.triaxle_flatbeds,
            superlink_flatbeds=carrier_profile_data.superlink_flatbeds,

            rigid_flatbeds_with_twistlocks=carrier_profile_data.rigid_flatbeds_with_twistlocks,
            triaxle_flatbeds_with_twistlocks=carrier_profile_data.triaxle_flatbeds_with_twistlocks,
            superlink_flatbeds_with_twistlocks=carrier_profile_data.superlink_flatbeds_with_twistlocks,

            rigid_dropsides=carrier_profile_data.rigid_dropsides,
            triaxle_dropside=carrier_profile_data.triaxle_dropside,
            superlink_dropside=carrier_profile_data.superlink_dropside,

            triaxle_skeletals=carrier_profile_data.triaxle_skeletals,
            superlink_skeletals=carrier_profile_data.superlink_skeletals,

            triaxle_pantechs=carrier_profile_data.triaxle_pantechs,

            triaxle_side_tippers=carrier_profile_data.triaxle_side_tippers,
            superlink_side_tippers=carrier_profile_data.superlink_side_tippers,

            rigid_end_tipper=carrier_profile_data.rigid_end_tipper,
            triaxle_end_tipper=carrier_profile_data.triaxle_end_tipper,

            low_beds=carrier_profile_data.low_beds,
        )

        db.add(carrier_profile)


        # ============================================================
        # 6. FINAL COMMIT
        # ============================================================

        db.commit()

        db.refresh(company)
        db.refresh(director)
        db.refresh(financial_account)
        db.refresh(carrier_profile)

        for document in carrier_documents:
            db.refresh(document)


        # ============================================================
        # 7. SUCCESS
        # ============================================================

        return {
            "message": "Fleet carrier account successfully registered",
            "company_id": company.id,
            "director_id": director.id,
            "carrier_document_ids": [
                document.id for document in carrier_documents
            ]
        }


    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to register fleet carrier: {str(e)}"
        )

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

def fleet_create_driver(
    db: Session,
    driver_data: DriverCreate,
    current_user: dict
):
    try:
        # 1. Validate current user's company
        assert "company_id" in current_user, "Missing company_id in current_user"

        print(f"current_user: {current_user}")

        company_id = current_user.get("company_id")

        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="User does not belong to a company"
            )

        # 2. Validate carrier
        carrier = db.query(Carrier).filter(
            Carrier.id == company_id
        ).first()

        if not carrier:
            raise HTTPException(
                status_code=404,
                detail="Carrier not found"
            )

        if not carrier.is_verified or carrier.status != "Active":
            raise HTTPException(
                status_code=400,
                detail="Carrier Account not verified, or not active"
            )

        # 3. Create Driver
        driver = Driver(
            first_name=driver_data.first_name,
            last_name=driver_data.last_name,
            nationality=driver_data.nationality,
            id_number=driver_data.id_number,

            license_number=driver_data.license_number,
            license_expiry_date=driver_data.license.expiry_date,

            prdp_number=driver_data.prdp_number,
            prdp_expiry_date=(
                driver_data.prdp_document.expiry_date
                if driver_data.prdp_document
                else None
            ),

            passport_number=driver_data.passport_number,

            company_id=carrier.id,
            company_name=carrier.legal_business_name,
            company_type=carrier.type,

            id_document=json.dumps(
                driver_data.id_document.model_dump(mode="json")
            ),

            license_document=json.dumps(
                driver_data.license.model_dump(mode="json")
            ),

            prdp_document=(
                json.dumps(
                    driver_data.prdp_document.model_dump(mode="json")
                )
                if driver_data.prdp_document
                else None
            ),

            passport_document=(
                json.dumps(
                    driver_data.passport_document.model_dump(mode="json")
                )
                if driver_data.passport_document
                else None
            ),

            proof_of_address=(
                json.dumps(
                    driver_data.proof_of_address.model_dump(mode="json")
                )
                if driver_data.proof_of_address
                else None
            ),

            address=driver_data.address,
            email=driver_data.email,
            phone_number=driver_data.phone_number,

            password_hash=hash_password(
                driver_data.password_hash
            )
        )

        db.add(driver)
        db.flush()

        # 4. Create Driver document records
        driver_documents = [
            DriverDocs(
                driver_id=driver.id,
                document_type=driver_data.id_document.document_type,
                document_url=driver_data.id_document.document_url,
                expiry_date=driver_data.id_document.expiry_date,
                is_verified=False,
                status="Un-verified"
            ),

            DriverDocs(
                driver_id=driver.id,
                document_type=driver_data.license.document_type,
                document_url=driver_data.license.document_url,
                expiry_date=driver_data.license.expiry_date,
                is_verified=False,
                status="Un-verified"
            )
        ]

        # PRDP
        if driver_data.prdp_document:
            driver_documents.append(
                DriverDocs(
                    driver_id=driver.id,
                    document_type=driver_data.prdp_document.document_type,
                    document_url=driver_data.prdp_document.document_url,
                    expiry_date=driver_data.prdp_document.expiry_date,
                    is_verified=False,
                    status="Un-verified"
                )
            )

        # Passport
        if driver_data.passport_document:
            driver_documents.append(
                DriverDocs(
                    driver_id=driver.id,
                    document_type=driver_data.passport_document.document_type,
                    document_url=driver_data.passport_document.document_url,
                    expiry_date=driver_data.passport_document.expiry_date,
                    is_verified=False,
                    status="Un-verified"
                )
            )

        # Proof of address
        if driver_data.proof_of_address:
            driver_documents.append(
                DriverDocs(
                    driver_id=driver.id,
                    document_type=driver_data.proof_of_address.document_type,
                    document_url=driver_data.proof_of_address.document_url,
                    expiry_date=driver_data.proof_of_address.expiry_date,
                    is_verified=False,
                    status="Un-verified"
                )
            )

        # Certifications & permits
        if driver_data.certifications_permits:
            for document in driver_data.certifications_permits:
                driver_documents.append(
                    DriverDocs(
                        driver_id=driver.id,
                        document_type=document.document_type,
                        document_url=document.document_url,
                        expiry_date=document.expiry_date,
                        is_verified=False,
                        status="Un-verified"
                    )
                )

        db.add_all(driver_documents)

        # 5. Update carrier driver count
        carrier.number_of_drivers = (
            (carrier.number_of_drivers or 0) + 1
        )

        db.add(carrier)

        # 6. Create carrier notification
        notification = Carrier_Notification(
            company_id=company_id,
            type="Driver registration successful",
            message=(
                f"New driver {driver.first_name} "
                f"{driver.last_name} has been added to your fleet "
                f"and is undergoing verification."
            ),
            is_read=False
        )

        db.add(notification)

        # 7. Final commit
        db.commit()

        db.refresh(driver)
        db.refresh(notification)

        return {
            "message": "Driver successfully registered and is undergoing verification.",
            "driver": driver
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create driver: {str(e)}"
        )