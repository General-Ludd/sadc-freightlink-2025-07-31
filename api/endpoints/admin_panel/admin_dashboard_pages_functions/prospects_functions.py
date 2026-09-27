from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from db.database import SessionLocal
from utils.administration_auth import verify_admin_password, get_current_admin
from schemas.administration_schemas.prospects import ProspectCreate, ProspectBranchCreate, ProspectBranchUpdate, ProspectContactCreate, ProspectContactUpdate, ContactInteractionCreate, ContactInteractionUpdate, FreightProfileCreate, FreightProfileUpdate
from models.administration_models.prospects import Prospect, Branches, Prospect_Contact, Contact_Interaction, Freight_Profile
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/create-prospects")
def create_prospect(
    data: ProspectCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        # ==========================================================
        # CREATE PROSPECT
        # ==========================================================

        prospect = Prospect(
            company_name=data.company_name,
            industry=data.industry,
            website=data.website,
            country=data.country,
            status=data.status,
            current_stage=data.current_stage,
            notes=data.notes,
        )

        db.add(prospect)
        db.flush()


        # ==========================================================
        # CREATE BRANCHES
        # ==========================================================

        created_branches = []

        if data.branches:

            for branch_data in data.branches:

                branch = Branches(
                    company_id=prospect.id,
                    branch_name=branch_data.branch_name,
                    city=branch_data.city,
                    province=branch_data.province,
                    country=branch_data.country,
                    division=branch_data.division,
                    description=branch_data.description,
                )

                db.add(branch)
                db.flush()

                created_branches.append(branch)


        # ==========================================================
        # CREATE CONTACTS
        # ==========================================================

        created_contacts = []

        if data.contacts:

            for contact_data in data.contacts:

                # Validate branch if supplied
                if contact_data.branch_id:

                    branch_exists = (
                        db.query(Branches)
                        .filter(
                            Branches.id == contact_data.branch_id,
                            Branches.company_id == prospect.id,
                        )
                        .first()
                    )

                    if not branch_exists:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Branch {contact_data.branch_id} does not belong to this prospect"
                        )

                contact = Prospect_Contact(
                    company_id=prospect.id,
                    branch_id=contact_data.branch_id,
                    location=contact_data.location,
                    first_name=contact_data.first_name,
                    last_name=contact_data.last_name,
                    job_title=contact_data.job_title,
                    department=contact_data.department,
                    phone=contact_data.phone,
                    mobile=contact_data.mobile,
                    email=contact_data.email,
                    linkedin_url=contact_data.linkedin_url,
                    contact_status=contact_data.contact_status,
                    notes=contact_data.notes,
                )

                db.add(contact)
                db.flush()

                created_contacts.append(contact)


        # ==========================================================
        # CREATE FREIGHT PROFILE
        # ==========================================================

        created_freight_profile = None

        if data.freight_profile:

            freight_data = data.freight_profile

            freight_profile = Freight_Profile(
                company_id=prospect.id,
                commodity=freight_data.commodity,
                estimated_volumes=freight_data.estimated_volumes,
                interval=freight_data.interval,
                core_routes=freight_data.core_routes,
                current_carrier_model=freight_data.current_carrier_model,
                equipment=freight_data.equipment,
                pain_point=freight_data.pain_point,
                frequency=freight_data.frequency,
                procurement_model=freight_data.procurement_model,
            )

            db.add(freight_profile)
            db.flush()

            created_freight_profile = freight_profile
        # ==========================================================
        # COMMIT EVERYTHING
        # ==========================================================

        db.commit()
        db.refresh(prospect)


        # ==========================================================
        # RESPONSE
        # ==========================================================

        return {
            "message": "Prospect created successfully",

            "prospect": {
                "id": prospect.id,
                "company_name": prospect.company_name,
                "industry": prospect.industry,
                "website": prospect.website,
                "country": prospect.country,
                "status": prospect.status,
                "current_stage": prospect.current_stage,
                "notes": prospect.notes,
                "created_at": prospect.created_at,
                "updated_at": prospect.updated_at,
            },

            "created": {
                "branches": len(created_branches),
                "contacts": len(created_contacts),
                "freight_profile": created_freight_profile is not None,
                "interactions": len(created_interactions),
            },
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create prospect: {str(e)}"
        )
######################################################################################
######################################Branch Managements##############################
######################################################################################
@router.post("/prospects/{prospect_id}/branches")
def create_prospect_branch(
    prospect_id: int,
    data: ProspectBranchCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        prospect = (
            db.query(Prospect)
            .filter(Prospect.id == prospect_id)
            .first()
        )

        if not prospect:
            raise HTTPException(
                status_code=404,
                detail="Prospect not found"
            )

        branch = Branches(
            company_id=prospect.id,
            branch_name=data.branch_name,
            city=data.city,
            province=data.province,
            country=data.country,
            division=data.division,
            description=data.description,
        )

        db.add(branch)
        db.commit()
        db.refresh(branch)

        return {
            "message": "Prospect branch created successfully",
            "branch": {
                "id": branch.id,
                "company_id": branch.company_id,
                "branch_name": branch.branch_name,
                "city": branch.city,
                "province": branch.province,
                "country": branch.country,
                "division": branch.division,
                "description": branch.description,
                "created_at": branch.created_at,
                "updated_at": branch.updated_at,
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create prospect branch: {str(e)}"
        )

@router.patch("/prospect-branches/{branch_id}")
def update_prospect_branch(
    branch_id: int,
    data: ProspectBranchUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        branch = (
            db.query(Branches)
            .filter(Branches.id == branch_id)
            .first()
        )

        if not branch:
            raise HTTPException(
                status_code=404,
                detail="Prospect branch not found"
            )

        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(branch, field, value)

        db.commit()
        db.refresh(branch)

        return {
            "message": "Prospect branch updated successfully",
            "branch": {
                "id": branch.id,
                "company_id": branch.company_id,
                "branch_name": branch.branch_name,
                "city": branch.city,
                "province": branch.province,
                "country": branch.country,
                "division": branch.division,
                "description": branch.description,
                "created_at": branch.created_at,
                "updated_at": branch.updated_at,
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update prospect branch: {str(e)}"
        )


######################################################################################
####################################Contact Managements##############################
######################################################################################
@router.post("/prospects/{prospect_id}/contacts")
def create_prospect_contact(
    prospect_id: int,
    data: ProspectContactCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        prospect = (
            db.query(Prospect)
            .filter(Prospect.id == prospect_id)
            .first()
        )

        if not prospect:
            raise HTTPException(
                status_code=404,
                detail="Prospect not found"
            )

        if data.branch_id:

            branch = (
                db.query(Branches)
                .filter(
                    Branches.id == data.branch_id,
                    Branches.company_id == prospect.id,
                )
                .first()
            )

            if not branch:
                raise HTTPException(
                    status_code=400,
                    detail="Branch does not belong to this prospect"
                )

        contact = Prospect_Contact(
            company_id=prospect.id,
            branch_id=data.branch_id,
            location=data.location,
            first_name=data.first_name,
            last_name=data.last_name,
            job_title=data.job_title,
            department=data.department,
            phone=data.phone,
            mobile=data.mobile,
            email=data.email,
            linkedin_url=data.linkedin_url,
            contact_status=data.contact_status,
            notes=data.notes,
        )

        db.add(contact)
        db.commit()
        db.refresh(contact)

        return {
            "message": "Prospect contact created successfully",
            "contact": {
                "id": contact.id,
                "company_id": contact.company_id,
                "branch_id": contact.branch_id,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "job_title": contact.job_title,
                "department": contact.department,
                "phone": contact.phone,
                "mobile": contact.mobile,
                "email": contact.email,
                "linkedin_url": contact.linkedin_url,
                "contact_status": contact.contact_status,
                "notes": contact.notes,
                "created_at": contact.created_at,
                "updated_at": contact.updated_at,
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create prospect contact: {str(e)}"
        )


@router.patch("/prospect-contacts/{contact_id}")
def update_prospect_contact(
    contact_id: int,
    data: ProspectContactUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        contact = (
            db.query(Prospect_Contact)
            .filter(Prospect_Contact.id == contact_id)
            .first()
        )

        if not contact:
            raise HTTPException(
                status_code=404,
                detail="Prospect contact not found"
            )

        updates = data.model_dump(exclude_unset=True)

        # If branch_id is being changed, verify it belongs
        # to the same prospect.
        if "branch_id" in updates and updates["branch_id"] is not None:

            branch = (
                db.query(Branches)
                .filter(
                    Branches.id == updates["branch_id"],
                    Branches.company_id == contact.company_id,
                )
                .first()
            )

            if not branch:
                raise HTTPException(
                    status_code=400,
                    detail="Branch does not belong to this prospect"
                )

        for field, value in updates.items():
            setattr(contact, field, value)

        db.commit()
        db.refresh(contact)

        return {
            "message": "Prospect contact updated successfully",
            "contact": {
                "id": contact.id,
                "company_id": contact.company_id,
                "branch_id": contact.branch_id,
                "first_name": contact.first_name,
                "last_name": contact.last_name,
                "job_title": contact.job_title,
                "department": contact.department,
                "phone": contact.phone,
                "mobile": contact.mobile,
                "email": contact.email,
                "linkedin_url": contact.linkedin_url,
                "contact_status": contact.contact_status,
                "notes": contact.notes,
                "created_at": contact.created_at,
                "updated_at": contact.updated_at,
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update prospect contact: {str(e)}"
        )


######################################################################################
#################################Interaction Managements##############################
######################################################################################
@router.post("/prospect-contacts/{contact_id}/interactions")
def create_contact_interaction(
    contact_id: int,
    data: ContactInteractionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        contact = (
            db.query(Prospect_Contact)
            .filter(Prospect_Contact.id == contact_id)
            .first()
        )

        if not contact:
            raise HTTPException(
                status_code=404,
                detail="Prospect contact not found"
            )

        interaction = Contact_Interaction(
            company_id=contact.company_id,
            contact_id=contact.id,
            interaction_type=data.interaction_type,
            interaction_direction=data.interaction_direction,
            subject=data.subject,
            notes=data.notes,
            outcome=data.outcome,
            interaction_date=data.interaction_date or get_sast_time(),
            next_action=data.next_action,
            next_follow_up_at=data.next_follow_up_at,
            created_by=current_user.get("id"),
        )

        db.add(interaction)
        db.commit()
        db.refresh(interaction)

        return {
            "message": "Contact interaction created successfully",
            "interaction": {
                "id": interaction.id,
                "company_id": interaction.company_id,
                "contact_id": interaction.contact_id,
                "interaction_type": interaction.interaction_type,
                "interaction_direction": interaction.interaction_direction,
                "subject": interaction.subject,
                "notes": interaction.notes,
                "outcome": interaction.outcome,
                "interaction_date": interaction.interaction_date,
                "next_action": interaction.next_action,
                "next_follow_up_at": interaction.next_follow_up_at,
                "created_by": interaction.created_by,
                "created_at": interaction.created_at,
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create contact interaction: {str(e)}"
        )


@router.patch("/prospect-interactions/{interaction_id}")
def update_contact_interaction(
    interaction_id: int,
    data: ContactInteractionUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        interaction = (
            db.query(Contact_Interaction)
            .filter(Contact_Interaction.id == interaction_id)
            .first()
        )

        if not interaction:
            raise HTTPException(
                status_code=404,
                detail="Contact interaction not found"
            )

        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(interaction, field, value)

        db.commit()
        db.refresh(interaction)

        return {
            "message": "Contact interaction updated successfully",
            "interaction": {
                "id": interaction.id,
                "company_id": interaction.company_id,
                "contact_id": interaction.contact_id,
                "interaction_type": interaction.interaction_type,
                "interaction_direction": interaction.interaction_direction,
                "subject": interaction.subject,
                "notes": interaction.notes,
                "outcome": interaction.outcome,
                "interaction_date": interaction.interaction_date,
                "next_action": interaction.next_action,
                "next_follow_up_at": interaction.next_follow_up_at,
                "created_by": interaction.created_by,
                "created_at": interaction.created_at,
                "updated_at": interaction.updated_at,
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update contact interaction: {str(e)}"
        )


######################################################################################
#############################Freight Profile Managements##############################
######################################################################################
@router.post("/prospects/{prospect_id}/freight-profile")
def create_freight_profile(
    prospect_id: int,
    data: FreightProfileCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        prospect = (
            db.query(Prospect)
            .filter(Prospect.id == prospect_id)
            .first()
        )

        if not prospect:
            raise HTTPException(
                status_code=404,
                detail="Prospect not found"
            )

        existing = (
            db.query(Freight_Profile)
            .filter(Freight_Profile.company_id == prospect.id)
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Freight profile already exists for this prospect"
            )

        freight_profile = Freight_Profile(
            company_id=prospect.id,
            commodity=data.commodity,
            estimated_volumes=data.estimated_volumes,
            interval=data.interval,
            core_routes=data.core_routes,
            current_carrier_model=data.current_carrier_model,
            equipment=data.equipment,
            pain_point=data.pain_point,
            frequency=data.frequency,
            procurement_model=data.procurement_model,
        )

        db.add(freight_profile)
        db.commit()
        db.refresh(freight_profile)

        return {
            "message": "Freight profile created successfully",
            "freight_profile": {
                "id": freight_profile.id,
                "company_id": freight_profile.company_id,
                "commodity": freight_profile.commodity,
                "estimated_volumes": freight_profile.estimated_volumes,
                "interval": freight_profile.interval,
                "core_routes": freight_profile.core_routes,
                "current_carrier_model": freight_profile.current_carrier_model,
                "equipment": freight_profile.equipment,
                "pain_point": freight_profile.pain_point,
                "frequency": freight_profile.frequency,
                "procurement_model": freight_profile.procurement_model,
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create freight profile: {str(e)}"
        )

@router.patch("/freight-profiles/{freight_profile_id}")
def update_freight_profile(
    freight_profile_id: int,
    data: FreightProfileUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:

        freight_profile = (
            db.query(Freight_Profile)
            .filter(Freight_Profile.id == freight_profile_id)
            .first()
        )

        if not freight_profile:
            raise HTTPException(
                status_code=404,
                detail="Freight profile not found"
            )

        updates = data.model_dump(exclude_unset=True)

        for field, value in updates.items():
            setattr(freight_profile, field, value)

        db.commit()
        db.refresh(freight_profile)

        return {
            "message": "Freight profile updated successfully",
            "freight_profile": {
                "id": freight_profile.id,
                "company_id": freight_profile.company_id,
                "commodity": freight_profile.commodity,
                "estimated_volumes": freight_profile.estimated_volumes,
                "interval": freight_profile.interval,
                "core_routes": freight_profile.core_routes,
                "current_carrier_model": freight_profile.current_carrier_model,
                "equipment": freight_profile.equipment,
                "pain_point": freight_profile.pain_point,
                "frequency": freight_profile.frequency,
                "procurement_model": freight_profile.procurement_model,
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update freight profile: {str(e)}"
        )