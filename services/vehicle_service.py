from sqlalchemy.orm import Session
from models.carrier import Carrier, Carrier_Notification
from models.shipper import Corporation
from models.vehicle import Vehicle, VehicleDocs, Trailer, ShipperTrailer
from models.user import CarrierDirector
from schemas.vehicle import VehicleCreate, TrailerCreate, ShipperTrailerCreate, TrailerUpdate
from utils.auth import get_current_user
from fastapi import Depends, HTTPException
from utils.payload_capacity import calculate_payload_capacity  # Import the payload calculation function
import json


def get_vehicle_by_id(vehicle_id: int, db: Session) -> Vehicle:
    return db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()

def create_vehicle(
    db: Session,
    vehicle_data: VehicleCreate,
    current_user: dict
):
    try:
        # ============================================================
        # 1. VALIDATE COMPANY
        # ============================================================

        assert "company_id" in current_user, "Missing company_id in current_user"

        print(f"current_user: {current_user}")

        company_id = current_user.get("company_id")

        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="User does not belong to a company"
            )

        carrier = db.query(Carrier).filter(
            Carrier.id == company_id
        ).first()

        if not carrier:
            raise HTTPException(
                status_code=400,
                detail="Carrier not found."
            )


        # ============================================================
        # 2. CALCULATE PAYLOAD CAPACITY
        # ============================================================

        temp_truck = Vehicle(
            type=vehicle_data.type,
            tare_weight=vehicle_data.tare_weight,
            gvm_weight=vehicle_data.gvm_weight
        )

        payload_capacity = calculate_payload_capacity(temp_truck)


        # ============================================================
        # 3. CREATE VEHICLE
        # ============================================================

        truck = Vehicle(
            type=vehicle_data.type,
            make=vehicle_data.make,
            model=vehicle_data.model,
            year=vehicle_data.year,
            color=vehicle_data.color,
            axle_configuration=vehicle_data.axle_configuration,
            vin=vehicle_data.vin,
            license_plate=vehicle_data.license_plate,
            license_expiry_date=vehicle_data.license_expiry_date,

            tare_weight=vehicle_data.tare_weight,
            gvm_weight=vehicle_data.gvm_weight,

            # Tracker information
            tracker_providers_name=vehicle_data.tracker.tracker_providers_name,
            tracker_providers_country=vehicle_data.tracker.tracker_providers_country,
            tracker_id=vehicle_data.tracker.tracker_id,
            tracker_login_username=vehicle_data.tracker.tracker_login_username,
            tracker_login_password=vehicle_data.tracker.tracker_login_password,

            equipment_type=vehicle_data.equipment_type,

            owner_id=company_id,
            company_name=carrier.legal_business_name,
            company_type=carrier.type,

            # Vehicle documents are stored as JSON strings
            vrc_or_leasing=json.dumps(
                vehicle_data.reg_or_leasing_certificate.model_dump(mode="json")
            ),

            vehicle_license_disk=json.dumps(
                vehicle_data.license_disk.model_dump(mode="json")
            ),

            vehicle_road_worthy_certificate=(
                json.dumps(
                    vehicle_data.road_worthy_certificate.model_dump(mode="json")
                )
                if vehicle_data.road_worthy_certificate
                else None
            ),

            # Existing database column expects a String
            # We use the tracker information here.
            vehicle_tracking_certificate=json.dumps(
                vehicle_data.tracker.model_dump(mode="json")
            ),

            # Vehicle images are also VehicleDocsCreate objects
            front_angle_image=(
                json.dumps(
                    vehicle_data.front_angle_image.model_dump(mode="json")
                )
                if vehicle_data.front_angle_image
                else None
            ),

            rear_angle_image=(
                json.dumps(
                    vehicle_data.rear_angle_image.model_dump(mode="json")
                )
                if vehicle_data.rear_angle_image
                else None
            ),

            left_angle_image=(
                json.dumps(
                    vehicle_data.left_angle_image.model_dump(mode="json")
                )
                if vehicle_data.left_angle_image
                else None
            ),

            right_angle_image=(
                json.dumps(
                    vehicle_data.right_angle_image.model_dump(mode="json")
                )
                if vehicle_data.right_angle_image
                else None
            ),

            payload_capacity=payload_capacity,
        )

        db.add(truck)
        db.commit()
        db.refresh(truck)


        # ============================================================
        # 4. CREATE VEHICLE DOCUMENT RECORDS
        # ============================================================

        vehicle_documents = [
            VehicleDocs(
                vehicle_id=truck.id,
                document_type=vehicle_data.reg_or_leasing_certificate.document_type,
                document_url=vehicle_data.reg_or_leasing_certificate.document_url,
                expiry_date=vehicle_data.reg_or_leasing_certificate.expiry_date,
                is_verified=False,
                status="Un-verified"
            ),

            VehicleDocs(
                vehicle_id=truck.id,
                document_type=vehicle_data.license_disk.document_type,
                document_url=vehicle_data.license_disk.document_url,
                expiry_date=vehicle_data.license_disk.expiry_date,
                is_verified=False,
                status="Un-verified"
            )
        ]

        if vehicle_data.road_worthy_certificate:
            vehicle_documents.append(
                VehicleDocs(
                    vehicle_id=truck.id,
                    document_type=vehicle_data.road_worthy_certificate.document_type,
                    document_url=vehicle_data.road_worthy_certificate.document_url,
                    expiry_date=vehicle_data.road_worthy_certificate.expiry_date,
                    is_verified=False,
                    status="Un-verified"
                )
            )

        if vehicle_data.vehicle_permits:
            for permit in vehicle_data.vehicle_permits:
                vehicle_documents.append(
                    VehicleDocs(
                        vehicle_id=truck.id,
                        document_type=permit.document_type,
                        document_url=permit.document_url,
                        expiry_date=permit.expiry_date,
                        is_verified=False,
                        status="Un-verified"
                    )
                )

        db.add_all(vehicle_documents)


        # ============================================================
        # 5. CREATE VEHICLE TRACKER RECORD
        # ============================================================

        tracker = VehicleTracker(
            vehicle_id=truck.id,

            tracker_providers_name=vehicle_data.tracker.tracker_providers_name,
            tracker_providers_country=vehicle_data.tracker.tracker_providers_country,
            tracker_id=vehicle_data.tracker.tracker_id,
            tracker_login_username=vehicle_data.tracker.tracker_login_username,
            tracker_login_password=vehicle_data.tracker.tracker_login_password,

            # These are not supplied by the current schema.
            # They can be populated later when the tracker integration
            # is configured.
            tracker_api_username="",
            tracker_api_token="",

            is_verified=False,
            service_status="Available",
            status="Un-verified"
        )

        db.add(tracker)


        # ============================================================
        # 6. UPDATE CARRIER VEHICLE COUNT
        # ============================================================

        carrier.number_of_vehicles += 1

        db.add(carrier)


        # ============================================================
        # 7. CREATE NOTIFICATION
        # ============================================================

        notification = Carrier_Notification(
            company_id=company_id,
            type="vehicle registration successful",
            message=(
                f"New vehicle {truck.make} {truck.model} "
                f"({truck.license_plate}) has been added to your fleet "
                f"and is undergoing verification."
            ),
            is_read=False
        )

        db.add(notification)

        db.commit()

        db.refresh(truck)
        db.refresh(notification)


        # ============================================================
        # 8. RETURN VEHICLE
        # ============================================================

        return truck

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create vehicle: {str(e)}"
        )

def create_trailer(
    db: Session,
    trailer_data: TrailerCreate,
    current_user: dict
):
    try:
        # ============================================================
        # 1. VALIDATE COMPANY
        # ============================================================

        assert "company_id" in current_user, "Missing company_id in current_user"

        print(f"current_user: {current_user}")

        company_id = current_user.get("company_id")

        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="User does not belong to a company"
            )

        carrier = db.query(Carrier).filter(
            Carrier.id == company_id
        ).first()

        if not carrier:
            raise HTTPException(
                status_code=400,
                detail="Carrier not found."
            )


        # ============================================================
        # 2. CALCULATE PAYLOAD CAPACITY
        # ============================================================

        temp_truck = Trailer(
            trailer_type=trailer_data.trailer_type,
            tare_weight=trailer_data.tare_weight,
            gvm_weight=trailer_data.gvm_weight
        )

        payload_capacity = calculate_payload_capacity(temp_truck)


        # ============================================================
        # 3. CREATE TRAILER
        # ============================================================

        trailer = Trailer(
            make=trailer_data.make,
            model=trailer_data.model,
            year=trailer_data.year,
            color=trailer_data.color,

            equipment_type=trailer_data.equipment_type,
            trailer_type=trailer_data.trailer_type,
            trailer_length=trailer_data.trailer_length,

            vin=trailer_data.vin,
            license_plate=trailer_data.license_plate,
            license_expiry_date=trailer_data.license_expiry_date,

            tare_weight=trailer_data.tare_weight,
            gvm_weight=trailer_data.gvm_weight,
            payload_capacity=payload_capacity,

            owner_id=company_id,
            company_name=carrier.legal_business_name,
            company_type=carrier.type,

            # ========================================================
            # Documents stored as JSON strings
            # ========================================================

            vrc_leasing=json.dumps(
                trailer_data.vrc_leasing.model_dump(mode="json")
            ),

            license_disk=json.dumps(
                trailer_data.license_disk.model_dump(mode="json")
            ),

            road_worthy_certificate=(
                json.dumps(
                    trailer_data.road_worthy_certificate.model_dump(mode="json")
                )
                if trailer_data.road_worthy_certificate
                else None
            ),

            # ========================================================
            # Images stored as JSON strings
            # ========================================================

            front_angle_image=(
                json.dumps(
                    trailer_data.front_angle_image.model_dump(mode="json")
                )
                if trailer_data.front_angle_image
                else None
            ),

            rear_angle_image=(
                json.dumps(
                    trailer_data.rear_angle_image.model_dump(mode="json")
                )
                if trailer_data.rear_angle_image
                else None
            ),

            left_angle_image=(
                json.dumps(
                    trailer_data.left_angle_image.model_dump(mode="json")
                )
                if trailer_data.left_angle_image
                else None
            ),

            right_angle_image=(
                json.dumps(
                    trailer_data.right_angle_image.model_dump(mode="json")
                )
                if trailer_data.right_angle_image
                else None
            ),
        )

        db.add(trailer)
        db.commit()
        db.refresh(trailer)


        # ============================================================
        # 4. CREATE TRAILER DOCUMENT RECORDS
        # ============================================================

        trailer_documents = [
            Trailer_Docs(
                trailer_id=trailer.id,
                document_type=trailer_data.vrc_leasing.document_type,
                document_url=trailer_data.vrc_leasing.document_url,
                expiry_date=trailer_data.vrc_leasing.expiry_date,
                is_verified=False,
                status="Un-verified"
            ),

            Trailer_Docs(
                trailer_id=trailer.id,
                document_type=trailer_data.license_disk.document_type,
                document_url=trailer_data.license_disk.document_url,
                expiry_date=trailer_data.license_disk.expiry_date,
                is_verified=False,
                status="Un-verified"
            )
        ]


        if trailer_data.road_worthy_certificate:
            trailer_documents.append(
                Trailer_Docs(
                    trailer_id=trailer.id,
                    document_type=trailer_data.road_worthy_certificate.document_type,
                    document_url=trailer_data.road_worthy_certificate.document_url,
                    expiry_date=trailer_data.road_worthy_certificate.expiry_date,
                    is_verified=False,
                    status="Un-verified"
                )
            )


        db.add_all(trailer_documents)


        # ============================================================
        # 5. UPDATE CARRIER TRAILER COUNT
        # ============================================================

        carrier.number_of_trailers += 1

        db.add(carrier)


        # ============================================================
        # 6. CREATE NOTIFICATION
        # ============================================================

        notification = Carrier_Notification(
            company_id=company_id,
            type="Trailer registration successful",
            message=(
                f"New trailer {trailer.make} {trailer.model} "
                f"({trailer.license_plate}) has been added to your fleet "
                f"and is undergoing verification."
            ),
            is_read=False
        )

        db.add(notification)


        # ============================================================
        # 7. FINAL COMMIT
        # ============================================================

        db.commit()

        db.refresh(trailer)
        db.refresh(notification)


        # ============================================================
        # 8. RETURN
        # ============================================================

        return trailer


    except HTTPException:
        db.rollback()
        raise


    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to create trailer: {str(e)}"
        )

def create_shipper_trailer(db: Session, trailer_data: ShipperTrailerCreate, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")
    # Extract the company_id from the current user
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    company = db.query(Corporation).filter(Corporation.id == company_id).first()
    if not company or not company.is_verified or company.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    # Create a temporary Vehicle object for payload calculation
    temp_truck = ShipperTrailer(
        trailer_type=trailer_data.trailer_type,
        tare_weight=trailer_data.tare_weight,
        gvm_weight=trailer_data.gvm_weight
    )

    # Calculate the payload capacity for the truck
    payload_capacity = calculate_payload_capacity(temp_truck)

    # Create the Trailer
    trailer = ShipperTrailer(
        make=trailer_data.make,
        model=trailer_data.model,
        year=trailer_data.year,
        color=trailer_data.color,
        equipment_type=trailer_data.equipment_type,
        trailer_type=trailer_data.trailer_type,
        trailer_length=trailer_data.trailer_length,
        vin=trailer_data.vin,
        license_plate=trailer_data.license_plate,
        license_expiry_date=trailer_data.license_expiry_date,
        tare_weight=trailer_data.tare_weight,
        gvm_weight=trailer_data.gvm_weight,
        owner_id=company_id,
        company_name=company.legal_business_name,
        company_type=company.type,
        vrc_leasing=trailer_data.vrc_leasing,
        license_disk=trailer_data.license_disk,
        road_worthy_certificate=trailer_data.road_worthy_certificate,
        front_angle_image=trailer_data.front_angle_image,
        rear_angle_image=trailer_data.rear_angle_image,
        left_angle_image=trailer_data.left_angle_image,
        right_angle_image=trailer_data.right_angle_image,
        payload_capacity=payload_capacity,  # Assign calculated payload capacity
    )
    db.add(trailer)
    db.commit()
    db.refresh(trailer)
    return trailer

def update_shipper_trailer(db: Session, trailer_id: int, trailer_data: TrailerUpdate, current_user: dict):
    assert "company_id" in current_user, "Missing company_id in current_user"
    print(f"current_user: {current_user}")

    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    # Check if carrier exists and is valid
    carrier = db.query(Carrier).filter(Carrier.id == company_id).first()
    if not carrier or not carrier.is_verified or carrier.status != "Active":
        raise HTTPException(status_code=400, detail="Carrier not found, not verified, or not active")

    # Get the existing trailer (your filter was missing a comma between conditions)
    trailer = db.query(ShipperTrailer).filter(
        ShipperTrailer.id == trailer_id,
        ShipperTrailer.company_id == company_id
    ).first()

    if not trailer:
        raise HTTPException(status_code=404, detail="Trailer not found")

    # ✅ Update fields dynamically if provided
    update_fields = [
        "vin", "license_plate", "license_expiry_date", "vrc_leasing",
        "vehicle_license_disk", "road_worthy_certificate",
        "front_angle_image", "rear_angle_image", "left_angle_image", "right_angle_image"
    ]

    for field in update_fields:
        value = getattr(trailer_data, field)
        if value is not None:
            setattr(trailer, field, value)

    # When updating, always reset verification status
    trailer.is_verified = False
    trailer.status = "Suspended"

    db.commit()
    db.refresh(trailer)

    return {
        "message": f"Trailer-{trailer.id} updated successfully, please wait while it undergoes partial verification"
    }


