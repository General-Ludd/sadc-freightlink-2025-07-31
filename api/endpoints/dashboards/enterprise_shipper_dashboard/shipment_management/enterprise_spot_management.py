from typing import List
from collections import defaultdict
from decimal import Decimal
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, Lane_Slot_Ledger, CarrierFinancialAccounts, FinancialAccounts, Interim_Invoice, Load_Invoice
from models.brokerage.loadboard import Ftl_Load_Board
from models.shipper import Corporation
from models.user import Director, Driver, CarrierUser
from models.carrier import Carrier
from models.spot_bookings.ftl_shipment import Client_Shipment, Client_Shipment_Stop, Client_Shipment_Vehicle_Requirement
from models.spot_bookings.dedicated_lane_ftl_shipment import Client_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs, shipment_status_Update
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.user import Driver
from models.vehicle import ShipperTrailer, Vehicle, Trailer
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import Ftl_Lanes_Summary_Response, Individual_FTL_Lane_Response, individual_shipment_or_lane_request, FTL_Lane_Dispute_Create
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Response, FTL_Shipments_Summary_Response, FTL_Shipment_Dispute_Create
from schemas.spot_bookings.power_shipment import POWER_SHIPMENT_RESPONSE, Power_Shipments_Summary_Response
from utils.auth import get_current_user
from utils.shipment_kpi_service import get_shipment_kpis
from utils.lane_kpi_service import get_lane_kpis
from services.cancellations.spot_cancellations import cancel_spot_ftl_shipment
from services.brokerage.disputes import shipper_dispute_ftl_shipment, shipper_dispute_ftl_lane
from enums import ShipperShipmentStatus

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_client_contracts(
    tender_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        # ---------------------------------------------------------
        # CLIENT ID
        # ---------------------------------------------------------
        company_id = current_user.get("company_id")

        if not company_id:
            raise HTTPException(
                status_code=401,
                detail="Client company could not be identified."
            )

        # ---------------------------------------------------------
        # FETCH ALL CLIENT CONTRACTS FOR THIS TENDER
        # ---------------------------------------------------------
        client_lanes = (
            db.query(Client_Lane)
            .filter(
                Client_Lane.tender_id == tender_id,
                Client_Lane.client_id == company_id
            )
            .all()
        )

        if not client_lanes:
            raise HTTPException(
                status_code=404,
                detail="No contracts found for this tender."
            )

        # ---------------------------------------------------------
        # FETCH ALL CARRIER CONTRACTS FOR THIS TENDER
        # ---------------------------------------------------------
        carrier_lanes = (
            db.query(Carrier_Lane)
            .filter(
                Carrier_Lane.tender_id == tender_id
            )
            .all()
        )

        if not carrier_lanes:
            raise HTTPException(
                status_code=404,
                detail="No awarded carrier contracts found for this tender."
            )

        # ---------------------------------------------------------
        # FETCH CARRIERS
        # ---------------------------------------------------------
        carrier_ids = list({
            lane.carrier_id
            for lane in carrier_lanes
            if lane.carrier_id
        })

        carriers = (
            db.query(Carrier)
            .filter(
                Carrier.id.in_(carrier_ids)
            )
            .all()
        )

        carrier_map = {
            carrier.id: carrier
            for carrier in carriers
        }

        # ---------------------------------------------------------
        # CLIENT LANE IDS
        # ---------------------------------------------------------
        client_lane_ids = [
            lane.id
            for lane in client_lanes
        ]

        # ---------------------------------------------------------
        # FETCH SHIPMENTS FOR ALL CLIENT LANES
        # ---------------------------------------------------------
        shipments = (
            db.query(Client_Shipment)
            .filter(
                Client_Shipment.client_lane_id.in_(
                    client_lane_ids
                )
            )
            .all()
        )

        # ---------------------------------------------------------
        # CONTRACT STATUS
        #
        # Rules:
        #
        # 1. ALL Completed
        #       -> Completed
        #
        # 2. Active + Completed
        #       -> Partially Completed
        #
        # 3. Any Active with no Completed
        #       -> Active
        #
        # 4. Any Awarded
        #       -> Awarded
        #
        # 5. Expired / Suspended are disregarded when determining
        #    the overall status.
        #
        # 6. If all are Cancelled
        #       -> Cancelled
        # ---------------------------------------------------------

        statuses = [
            lane.contract_status
            for lane in client_lanes
            if lane.contract_status
        ]

        status_set = set(statuses)

        if statuses and all(
            status == "Completed"
            for status in statuses
        ):
            contract_status = "Completed"

        elif (
            "Active" in status_set
            and "Completed" in status_set
        ):
            contract_status = "Partially Completed"

        elif "Active" in status_set:
            contract_status = "Active"

        elif "Awarded" in status_set:
            contract_status = "Awarded"

        elif statuses and all(
            status == "Cancelled"
            for status in statuses
        ):
            contract_status = "Cancelled"

        else:
            # Expired / Suspended are disregarded.
            # Find any meaningful remaining status.
            meaningful_statuses = [
                status
                for status in statuses
                if status not in {
                    "Expired",
                    "Suspended"
                }
            ]

            if meaningful_statuses:
                contract_status = meaningful_statuses[0]

            else:
                # If everything is Expired/Suspended,
                # retain the first lane's actual status.
                contract_status = statuses[0] if statuses else None

        # ---------------------------------------------------------
        # EXECUTION STATUS
        #
        # No shipments:
        #       Planned
        #
        # At least one shipment:
        #       Executing
        #
        # Overall contract Completed:
        #       Completed
        # ---------------------------------------------------------

        if contract_status == "Completed":
            execution_status = "Completed"

        elif shipments:
            execution_status = "Executing"

        else:
            execution_status = "Planned"

        # ---------------------------------------------------------
        # CONTRACT TERM
        #
        # Return the overall date range represented by the contracts.
        # ---------------------------------------------------------

        start_dates = [
            lane.contract_start_date
            for lane in client_lanes
            if lane.contract_start_date
        ]

        end_dates = [
            lane.contract_end_date
            for lane in client_lanes
            if lane.contract_end_date
        ]

        contract_start_date = (
            min(start_dates)
            if start_dates
            else None
        )

        contract_end_date = (
            max(end_dates)
            if end_dates
            else None
        )

        # ---------------------------------------------------------
        # LONGEST CONTRACT DURATION
        #
        # Determine the longest individual Client_Lane contract.
        #
        # Examples:
        # 1 year  -> "Annually"
        # 2 years -> "2 years"
        # 3 months -> "3 months"
        # ---------------------------------------------------------

        def calculate_contract_duration(start_date, end_date):
            if not start_date or not end_date:
                return None

            # Exact whole years
            years = end_date.year - start_date.year

            try:
                anniversary = start_date.replace(
                    year=start_date.year + years
                )
            except ValueError:
                # Handles leap-day dates
                anniversary = start_date.replace(
                    month=2,
                    day=28,
                    year=start_date.year + years
                )

            if anniversary > end_date:
                years -= 1

                try:
                    anniversary = start_date.replace(
                        year=start_date.year + years
                    )
                except ValueError:
                    anniversary = start_date.replace(
                        month=2,
                        day=28,
                        year=start_date.year + years
                    )

            if years >= 1:
                remaining_days = (
                    end_date - anniversary
                ).days

                if remaining_days < 30:
                    if years == 1:
                        return "Annually"

                    return f"{years} years"

            # Whole months
            months = (
                (end_date.year - start_date.year) * 12
                + end_date.month
                - start_date.month
            )

            if end_date.day < start_date.day:
                months -= 1

            if months >= 1:
                if months == 1:
                    return "1 month"

                return f"{months} months"

            # Remaining days
            days = (
                end_date - start_date
            ).days

            if days == 1:
                return "1 day"

            return f"{days} days"

        longest_contract_duration = None
        longest_contract_days = -1
        longest_contract_lane = None

        for lane in client_lanes:

            if (
                not lane.contract_start_date
                or not lane.contract_end_date
            ):
                continue

            duration_days = (
                lane.contract_end_date
                - lane.contract_start_date
            ).days

            if duration_days > longest_contract_days:
                longest_contract_days = duration_days
                longest_contract_lane = lane

        if longest_contract_lane:
            longest_contract_duration = (
                calculate_contract_duration(
                    longest_contract_lane.contract_start_date,
                    longest_contract_lane.contract_end_date
                )
            )

        # ---------------------------------------------------------
        # TOTAL CONTRACTUAL SHIPMENTS
        # ---------------------------------------------------------

        total_shipments = sum(
            lane.total_slots or 0
            for lane in carrier_lanes
        )

        # ---------------------------------------------------------
        # COMPLETED SHIPMENTS
        # ---------------------------------------------------------

        completed_shipments = sum(
            1
            for shipment in shipments
            if (
                shipment.status
                and shipment.status.lower() == "completed"
            )
        )

        # ---------------------------------------------------------
        # REMAINING SHIPMENTS
        # ---------------------------------------------------------

        remaining_shipments = max(
            total_shipments - completed_shipments,
            0
        )

        # ---------------------------------------------------------
        # PROGRESS
        # ---------------------------------------------------------

        progress_percentage = (
            round(
                (
                    completed_shipments
                    / total_shipments
                ) * 100,
                2
            )
            if total_shipments > 0
            else 0
        )

        # ---------------------------------------------------------
        # SHIPMENTS PER INTERVAL
        # ---------------------------------------------------------

        shipments_per_interval = sum(
            lane.slots_per_interval or 0
            for lane in carrier_lanes
        )

        # ---------------------------------------------------------
        # INTERVAL PERIOD
        # ---------------------------------------------------------

        interval_periods = list({
            lane.volume_entry_method
            for lane in client_lanes
            if lane.volume_entry_method
        })

        if len(interval_periods) == 1:
            interval_period = interval_periods[0]

        else:
            interval_period = interval_periods

        # ---------------------------------------------------------
        # AVERAGE SHIPMENT RATE
        #
        # Weighted by total contractual shipments.
        # ---------------------------------------------------------

        total_rate_value = Decimal("0.00")

        for lane in carrier_lanes:

            rate = (
                lane.rate
                or Decimal("0.00")
            )

            slots = lane.total_slots or 0

            total_rate_value += (
                rate * slots
            )

        average_shipment_rate = (
            (
                total_rate_value
                / Decimal(str(total_shipments))
            ).quantize(
                Decimal("0.01")
            )
            if total_shipments > 0
            else Decimal("0.00")
        )

        # ---------------------------------------------------------
        # TOTAL COMBINED CONTRACT VALUE
        #
        # Retaining the current calculation for now.
        # ---------------------------------------------------------

        total_combined_contract_value = Decimal("0.00")

        for lane in carrier_lanes:

            contract_rate = (
                lane.contract_rate
                or Decimal("0.00")
            )

            total_slots = lane.total_slots or 0

            total_combined_contract_value += (
                contract_rate * total_slots
            )

        # ---------------------------------------------------------
        # PAYMENT TERMS
        # ---------------------------------------------------------

        payment_terms = (
            client_lanes[0].payment_terms
        )

        # ---------------------------------------------------------
        # PAYMENT BASIS
        #
        # TEMPORARY DUMMY DATA
        # ---------------------------------------------------------

        payment_basis = "From Statement"

        # ---------------------------------------------------------
        # TITLE
        # ---------------------------------------------------------

        title = client_lanes[0].lane_title

        # ---------------------------------------------------------
        # FUEL
        #
        # TEMPORARY DUMMY DATA
        # ---------------------------------------------------------

        fuel = {
            "base_diesel_price": 29.45,
            "unit": "L",
            "review_period": "Monthly"
        }

        # ---------------------------------------------------------
        # TARGET OTIF
        #
        # TEMPORARY DUMMY DATA
        # ---------------------------------------------------------

        target_otif_percentage = 97.0
        otif_period = "30-day rolling"

        # ---------------------------------------------------------
        # AWARDED CARRIERS
        # ---------------------------------------------------------

        awarded_carriers = []

        for carrier_lane in carrier_lanes:

            carrier = carrier_map.get(
                carrier_lane.carrier_id
            )

            # ---------------------------------------------
            # SHIPMENTS FOR THIS CARRIER CONTRACT
            # ---------------------------------------------
            carrier_shipments = [
                shipment
                for shipment in shipments
                if (
                    shipment.carrier_lane_id
                    == carrier_lane.id
                )
            ]

            # ---------------------------------------------
            # FALLBACK
            #
            # If carrier_lane_id has not yet been populated
            # on older shipments, use client_lane_id.
            # ---------------------------------------------
            if not carrier_shipments:

                carrier_shipments = [
                    shipment
                    for shipment in shipments
                    if (
                        shipment.client_lane_id
                        == carrier_lane.client_lane_id
                    )
                ]

            carrier_completed_shipments = sum(
                1
                for shipment in carrier_shipments
                if (
                    shipment.status
                    and shipment.status.lower()
                    == "completed"
                )
            )

            # ---------------------------------------------
            # TEMPORARY OTIF DUMMY DATA
            # ---------------------------------------------
            carrier_otif = 97.0

            awarded_carriers.append({
                "name": (
                    carrier.legal_business_name
                    if carrier
                    else None
                ),
                "otif_percentage": (
                    carrier_otif
                ),
                "committed_slots_per_interval": (
                    carrier_lane.slots_per_interval
                ),
                "rate": carrier_lane.rate,
            })

        # ---------------------------------------------------------
        # FINAL RESPONSE
        # ---------------------------------------------------------

        return {
            "tender_id": tender_id,
            "execution_status": execution_status,
            "status": contract_status,
            "title": title,
            "term": {
                "start_date": contract_start_date,
                "end_date": contract_end_date,
            },
            "shipments_per_interval": {
                "no_of_shipments": shipments_per_interval,
                "interval_period": interval_period,
            },
            "no_of_awarded_carriers": len(awarded_carriers),
            "no_of_master_lanes": len(awarded_carriers),
            "progress": {
                "total_shipments": total_shipments,
                "completed_shipments": completed_shipments,
                "remaining_shipments_balance": remaining_shipments,
                "progress_percentage": progress_percentage,
            },
            "total_value": {
                "total_combined_contract_value": total_combined_contract_value,
                "term": longest_contract_duration,
            },
            "cef_diesel_base": {
                "fuel": fuel,
            },
            "target_otif": {
                "target_otif_percentage": (
                    target_otif_percentage
                ),
                "otif_period": (
                    otif_period
                )
            },
            "payment_terms": {
                "payment_terms": payment_terms,
                "payment_basis": payment_basis,
            },
            "carriers": awarded_carriers,
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to fetch client contracts: {str(e)}"
            )
        )


def get_tender_contracts(
    tender_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        # =========================================================
        # 1. CLIENT VALIDATION
        # =========================================================

        company_id = current_user.get("company_id")

        if not company_id:
            raise HTTPException(
                status_code=401,
                detail="Client company could not be identified.",
            )

        # =========================================================
        # 2. HELPER FUNCTIONS
        # =========================================================

        def value(obj, field, default=None):
            return getattr(obj, field, default) if obj else default

        def decimal_value(number):
            if number is None:
                return Decimal("0.00")
            return Decimal(str(number))

        def json_number(number):
            if number is None:
                return None
            if isinstance(number, Decimal):
                return float(number)
            return number

        def json_date(value_):
            if value_ is None:
                return None
            if isinstance(value_, (date, datetime)):
                return value_.isoformat()
            return value_

        def unique_values(items):
            result = []
            seen = set()

            for item in items:
                if item is None:
                    continue

                marker = str(item)

                if marker not in seen:
                    seen.add(marker)
                    result.append(item)

            return result

        def lane_route(lane):
            origin = value(lane, "origin_city_province")
            destination = value(lane, "destination_city_province")

            return {
                "origin": origin,
                "destination": destination,
                "route": (
                    f"{origin} → {destination}"
                    if origin and destination
                    else None
                ),
            }

        def serialize_document(document):
            return {
                "id": document.id,
                "name": document.name,
                "document_url": document.doc_url,
                "created_at": json_date(
                    value(document, "created_at")
                ),
                "updated_at": json_date(
                    value(document, "updated_at")
                ),
            }

        def serialize_stop(stop):
            return {
                "stop_id": stop.id,
                "facility_name": stop.facility_name,
                "sequence": stop.stop_sequence,
                "stop_type": stop.stop_type,
                "address": stop.address,
                "complete_address": stop.complete_address,
                "city_province": stop.city_province,
                "country": stop.country,
                "region": stop.region,
                "reference_number": stop.reference_number,
                "scheduling_type": stop.scheduling_type,
                "operating_start_time": (
                    stop.operating_start_time.isoformat()
                    if stop.operating_start_time
                    else None
                ),
                "operating_end_time": (
                    stop.operating_end_time.isoformat()
                    if stop.operating_end_time
                    else None
                ),
                "operating_days": {
                    "monday": stop.open_monday,
                    "tuesday": stop.open_tuesday,
                    "wednesday": stop.open_wednesday,
                    "thursday": stop.open_thursday,
                    "friday": stop.open_friday,
                    "saturday": stop.open_saturday,
                    "sunday": stop.open_sunday,
                },
                "contact": {
                    "first_name": stop.contact_first_name,
                    "last_name": stop.contact_last_name,
                    "phone": stop.contact_phone_number,
                    "email": stop.contact_email,
                },
                "arrival_time": json_date(stop.arrival_time),
                "departure_time": json_date(stop.departure_time),
                "notes": stop.notes,
                "coordinates": {
                    "latitude": stop.latitude,
                    "longitude": stop.longitude,
                },
            }

        # =========================================================
        # 3. FETCH THE REQUESTED TENDER'S CLIENT LANES
        # =========================================================

        requested_lanes = (
            db.query(Client_Lane)
            .filter(
                Client_Lane.tender_id == tender_id,
                Client_Lane.client_id == company_id,
            )
            .order_by(
                Client_Lane.bundle_trip_sequence.asc(),
                Client_Lane.id.asc(),
            )
            .all()
        )

        if not requested_lanes:
            raise HTTPException(
                status_code=404,
                detail="No contracts found for this tender.",
            )

        # =========================================================
        # 4. RESOLVE BUNDLE MEMBERSHIP
        #
        # Lane_Bundle.master_tender_id references Client_Lane.id.
        # Client_Lane.bundlee_id is also used to identify siblings.
        #
        # We retain the requested tender when it has no bundle.
        # =========================================================

        requested_lane_ids = [
            lane.id for lane in requested_lanes
        ]

        requested_bundle_ids = unique_values([
            lane.bundlee_id
            for lane in requested_lanes
        ])

        requested_bundle_refs = unique_values([
            lane.bundle_reference
            for lane in requested_lanes
        ])

        bundle_query = db.query(Lane_Bundle).filter(
            Lane_Bundle.client_id == company_id
        )

        bundle_conditions = []

        if requested_bundle_ids:
            bundle_conditions.append(
                Lane_Bundle.id.in_(requested_bundle_ids)
            )

        bundle_conditions.append(
            Lane_Bundle.master_tender_id.in_(requested_lane_ids)
        )

        if requested_bundle_refs:
            bundle_conditions.append(
                Lane_Bundle.bundle_reference.in_(
                    requested_bundle_refs
                )
            )

        from sqlalchemy import or_

        bundles = (
            bundle_query
            .filter(or_(*bundle_conditions))
            .all()
        )

        bundle_by_id = {
            bundle.id: bundle
            for bundle in bundles
        }

        bundle_by_reference = {
            bundle.bundle_reference: bundle
            for bundle in bundles
            if bundle.bundle_reference
        }

        bundle_ids = unique_values([
            bundle.id for bundle in bundles
        ])

        bundle_refs = unique_values([
            bundle.bundle_reference
            for bundle in bundles
        ])

        # Retrieve every sibling lane belonging to a resolved bundle.
        sibling_query = db.query(Client_Lane).filter(
            Client_Lane.client_id == company_id
        )

        sibling_conditions = []

        if bundle_ids:
            sibling_conditions.append(
                Client_Lane.bundlee_id.in_(bundle_ids)
            )

        if bundle_refs:
            sibling_conditions.append(
                Client_Lane.bundle_reference.in_(bundle_refs)
            )

        if sibling_conditions:
            sibling_lanes = (
                sibling_query
                .filter(or_(*sibling_conditions))
                .all()
            )
        else:
            sibling_lanes = []

        all_lanes_by_id = {
            lane.id: lane
            for lane in requested_lanes + sibling_lanes
        }

        # Include the bundle's master lane if it is not already present.
        master_lane_ids = unique_values([
            bundle.master_tender_id
            for bundle in bundles
        ])

        missing_master_ids = [
            lane_id
            for lane_id in master_lane_ids
            if lane_id not in all_lanes_by_id
        ]

        if missing_master_ids:
            master_lanes = (
                db.query(Client_Lane)
                .filter(
                    Client_Lane.client_id == company_id,
                    Client_Lane.id.in_(missing_master_ids),
                )
                .all()
            )

            for lane in master_lanes:
                all_lanes_by_id[lane.id] = lane

        all_lanes = list(all_lanes_by_id.values())

        # Only show sibling lanes in the same resolved bundle.
        # For an unbundled tender, keep the requested tender's lanes.
        if bundles:
            bundle_lane_ids = set(all_lanes_by_id.keys())
            all_lanes = [
                lane
                for lane in all_lanes
                if lane.id in bundle_lane_ids
            ]
        else:
            all_lanes = requested_lanes

        all_lane_ids = [lane.id for lane in all_lanes]

        # =========================================================
        # 5. FETCH RELATED DATA IN BATCHES
        # =========================================================

        client_lane_id_set = set(all_lane_ids)

        carrier_lanes = (
            db.query(Carrier_Lane)
            .filter(
                Carrier_Lane.client_lane_id.in_(all_lane_ids)
            )
            .order_by(Carrier_Lane.id.asc())
            .all()
        ) if all_lane_ids else []

        carrier_ids = unique_values([
            lane.carrier_id for lane in carrier_lanes
        ])

        carriers = (
            db.query(Carrier)
            .filter(Carrier.id.in_(carrier_ids))
            .all()
        ) if carrier_ids else []

        carrier_map = {
            carrier.id: carrier
            for carrier in carriers
        }

        volume_profiles = (
            db.query(Lane_Volume_Profile)
            .filter(
                Lane_Volume_Profile.lane_id.in_(all_lane_ids)
            )
            .order_by(
                Lane_Volume_Profile.period_sequence.asc()
            )
            .all()
        ) if all_lane_ids else []

        profiles_by_lane = defaultdict(list)

        for profile in volume_profiles:
            profiles_by_lane[profile.lane_id].append(profile)

        stops = (
            db.query(Lane_Stop)
            .filter(Lane_Stop.lane_id.in_(all_lane_ids))
            .order_by(
                Lane_Stop.lane_id.asc(),
                Lane_Stop.stop_sequence.asc(),
            )
            .all()
        ) if all_lane_ids else []

        stops_by_lane = defaultdict(list)

        for stop in stops:
            stops_by_lane[stop.lane_id].append(stop)

        vehicle_configs = (
            db.query(Lane_Vehicle_Config)
            .filter(
                Lane_Vehicle_Config.lane_id.in_(all_lane_ids),
                Lane_Vehicle_Config.is_active.is_(True),
            )
            .all()
        ) if all_lane_ids else []

        vehicles_by_lane = defaultdict(list)

        for config in vehicle_configs:
            vehicles_by_lane[config.lane_id].append(config)

        accessorials = (
            db.query(Lane_Accessorial)
            .filter(
                Lane_Accessorial.lane_id.in_(all_lane_ids)
            )
            .all()
        ) if all_lane_ids else []

        accessorials_by_lane = defaultdict(list)

        for item in accessorials:
            accessorials_by_lane[item.lane_id].append(item)

        turnaround_records = (
            db.query(Lane_Turnaround_Window_Demurrage_Protocals)
            .filter(
                Lane_Turnaround_Window_Demurrage_Protocals.lane_id.in_(
                    all_lane_ids
                )
            )
            .all()
        ) if all_lane_ids else []

        turnaround_by_lane = defaultdict(list)

        for item in turnaround_records:
            turnaround_by_lane[item.lane_id].append(item)

        escort_records = (
            db.query(Lane_Escort_Policy)
            .filter(
                Lane_Escort_Policy.lane_id.in_(all_lane_ids)
            )
            .all()
        ) if all_lane_ids else []

        escort_by_lane = defaultdict(list)

        for item in escort_records:
            escort_by_lane[item.lane_id].append(item)

        certification_records = (
            db.query(Lane_Carrier_Certification_Driver_Standards)
            .filter(
                Lane_Carrier_Certification_Driver_Standards.lane_id.in_(
                    all_lane_ids
                )
            )
            .all()
        ) if all_lane_ids else []

        certifications_by_lane = defaultdict(list)

        for item in certification_records:
            certifications_by_lane[item.lane_id].append(item)

        documents = (
            db.query(Lane_Documents)
            .filter(Lane_Documents.lane_id.in_(all_lane_ids))
            .all()
        ) if all_lane_ids else []

        documents_by_lane = defaultdict(list)

        for document in documents:
            documents_by_lane[document.lane_id].append(document)

        shipments = (
            db.query(Client_Shipment)
            .filter(
                Client_Shipment.client_id == company_id,
                Client_Shipment.client_lane_id.in_(all_lane_ids),
            )
            .all()
        ) if all_lane_ids else []

        shipments_by_lane = defaultdict(list)

        for shipment in shipments:
            shipments_by_lane[shipment.client_lane_id].append(
                shipment
            )

        # Service standards belong to tenders, so query every tender
        # represented by the selected bundle.
        all_tender_ids = unique_values([
            lane.tender_id for lane in all_lanes
        ])

        service_standards = (
            db.query(Lane_Service_Standard)
            .filter(
                Lane_Service_Standard.tender_id.in_(all_tender_ids)
            )
            .all()
        ) if all_tender_ids else []

        standards_by_tender = defaultdict(list)

        for standard in service_standards:
            standards_by_tender[standard.tender_id].append(
                standard
            )

        tender_records = (
            db.query(Lane_Tender_RFQ)
            .filter(
                Lane_Tender_RFQ.id.in_(all_tender_ids),
                Lane_Tender_RFQ.client_id == company_id,
            )
            .all()
        ) if all_tender_ids else []

        tenders_by_id = {
            tender.id: tender
            for tender in tender_records
        }

        # =========================================================
        # 6. GROUP CARRIER AWARDS BY CLIENT LANE
        # =========================================================

        awards_by_client_lane = defaultdict(list)

        for award in carrier_lanes:
            awards_by_client_lane[award.client_lane_id].append(
                award
            )

        # =========================================================
        # 7. BUILD INDIVIDUAL LANE INFORMATION
        # =========================================================

        lane_payloads = {}

        for lane in all_lanes:
            lane_profiles = profiles_by_lane[lane.id]
            lane_stops = stops_by_lane[lane.id]
            lane_shipments = shipments_by_lane[lane.id]
            lane_awards = awards_by_client_lane[lane.id]

            # A client lane may have several profile rows.
            # Keep profile rows individually visible to preserve their
            # period semantics; calculate the profile total as requested.
            expected_loads = sum(
                max(profile.expected_loads or 0, 0)
                for profile in lane_profiles
            )

            interval_methods = unique_values([
                profile.volume_entry_method
                for profile in lane_profiles
            ])

            period_labels = unique_values([
                profile.period_label
                for profile in lane_profiles
            ])

            completed_lane_shipments = sum(
                1
                for shipment in lane_shipments
                if (
                    (shipment.status or "").strip().lower()
                    == "completed"
                )
            )

            lane_weight_kg = (
                (lane.average_shipment_weight_kg or 0)
                * expected_loads
            )

            # A logical corridor can have multiple client lanes
            # because carriers were awarded separate allocations.
            # Use carrier allocations for actual contracted volume.
            awarded_total_loads = sum(
                max(award.total_slots or 0, 0)
                for award in lane_awards
            )

            corridor_loads = (
                awarded_total_loads
                if lane_awards
                else expected_loads
            )

            # -----------------------------------------------------
            # ROUTE AND BUNDLE ROLE
            # -----------------------------------------------------

            route = lane_route(lane)

            matching_bundle = (
                bundle_by_id.get(lane.bundlee_id)
                or bundle_by_reference.get(lane.bundle_reference)
            )

            bundle_reference = (
                value(matching_bundle, "bundle_reference")
                or lane.bundle_reference
            )

            # -----------------------------------------------------
            # FACILITIES
            # -----------------------------------------------------

            facilities = [
                serialize_stop(stop)
                for stop in lane_stops
            ]

            # -----------------------------------------------------
            # VEHICLES
            # -----------------------------------------------------

            equipment = [
                {
                    "configuration_type": item.configuration_type,
                    "truck_type": item.truck_type,
                    "equipment_type": item.equipment_type,
                    "trailer_type": item.trailer_type,
                    "trailer_length": item.trailer_length,
                }
                for item in vehicles_by_lane[lane.id]
            ]

            # -----------------------------------------------------
            # TURNAROUND / DEMURRAGE
            # -----------------------------------------------------

            turnaround = []

            for item in turnaround_by_lane[lane.id]:
                matching_stop = next(
                    (
                        stop for stop in lane_stops
                        if stop.id == item.stop_id
                    ),
                    None,
                )

                turnaround.append({
                    "stop_id": item.stop_id,
                    "facility_name": (
                        matching_stop.facility_name
                        if matching_stop
                        else None
                    ),
                    "loading_offloading_turnaround_hours": (
                        item.loading_offloading_turnaround_hours
                    ),
                    "free_demurrage_hours": (
                        item.free_demurrage_hours
                    ),
                    "demurrage_rate_per_hour": (
                        item.demurrage_rate_per_hour
                    ),
                    "maximum_demurrage_incursion_hours": (
                        item.maximum_demurrage_incursion_hours
                    ),
                    "demurrage_conditions": (
                        item.demurrage_conditions
                    ),
                })

            # -----------------------------------------------------
            # ACCESSORIALS
            # -----------------------------------------------------

            lane_accessorials = [
                {
                    "charge_type": item.charge_type,
                    "treatment": item.treatment,
                    "threshold_value": json_number(
                        item.threshold_value
                    ),
                    "threshold_unit": item.threshold_unit,
                    "notes": item.notes,
                }
                for item in accessorials_by_lane[lane.id]
            ]

            # -----------------------------------------------------
            # ESCORT POLICIES
            # -----------------------------------------------------

            escort_policy = [
                {
                    "armed_escort_required": (
                        item.armed_escort_required
                    ),
                    "escort_expense_responsible_party": (
                        item.escort_expense_responsible_party
                    ),
                }
                for item in escort_by_lane[lane.id]
            ]

            # -----------------------------------------------------
            # CERTIFICATION / DRIVER STANDARDS
            # -----------------------------------------------------

            certifications = [
                {
                    "certification_name": (
                        item.certification_name
                    ),
                    "driver_qualification_security_directives": (
                        item.driver_qualification_security_directives
                    ),
                    "is_required": item.is_required,
                }
                for item in certifications_by_lane[lane.id]
            ]

            # -----------------------------------------------------
            # SERVICE STANDARDS
            #
            # Actual performance remains null until actual
            # performance metrics have been identified.
            # -----------------------------------------------------

            lane_standards = []

            for standard in standards_by_tender.get(
                lane.tender_id, []
            ):
                lane_standards.append({
                    "standard_type": standard.standard_type,
                    "target_value": standard.target_value,
                    "unit": standard.unit,
                    "is_mandatory": standard.is_mandatory,
                    "actual_value": None,
                    "performance_status": "Awaiting performance data",
                })

            # -----------------------------------------------------
            # FULL LANE SPECIFICATIONS
            # -----------------------------------------------------

            full_lane_information = {
                "administrative_and_lane_parameters": {
                    "lane_id": lane.id,
                    "tender_id": lane.tender_id,
                    "lane_reference": lane.lane_reference,
                    "title": lane.lane_title,
                    "scope": lane.scope_description,
                    "business_unit": lane.business_unit,
                    "cost_centre_project_code": (
                        lane.cost_centre_project_code
                    ),
                    "lane_commitment_type": (
                        lane.lane_commitment_type
                    ),
                    "length_category": lane.lane_length_category,
                    "category": lane.lane_category,
                    "contract_status": lane.contract_status,
                    "start_date": json_date(
                        lane.contract_start_date
                    ),
                    "end_date": json_date(
                        lane.contract_end_date
                    ),
                    "load_type": lane.load_type,
                    "distance_km": lane.actual_distance_km,
                    "priority_level": lane.priority_level,
                    "customer_reference": lane.customer_reference,
                },

                "freight_and_cargo_specifications": {
                    "commodity": lane.commodity,
                    "average_shipment_weight_kg": (
                        lane.average_shipment_weight_kg
                    ),
                    "average_shipment_weight_tonnes": round(
                        (lane.average_shipment_weight_kg or 0) / 1000,
                        3,
                    ),
                    "minimum_weight_bracket_kg": (
                        lane.minimum_weight_bracket_kg
                    ),
                    "packaging_type": lane.packaging_type,
                    "packaging_quantity": lane.packaging_quantity,
                    "temperature_control": lane.temperature_control,
                    "target_temperature_spec": (
                        lane.target_temperature_spec
                    ),
                },

                "regulatory_customs_and_bonded_transit": {
                    "hazardous_materials": lane.hazardous_materials,
                    "hazchem_classification": (
                        lane.hazchem_classification
                    ),
                    "under_bond": lane.under_bond,
                    "rib_requirements": lane.rib_requirements,
                    "border_customs_responsibility": (
                        lane.border_customs_responsibility
                    ),
                },

                "volume_commitments_and_pricing": {
                    "volume_entry_method": lane.volume_entry_method,
                    "volume_commitment": lane.volume_commitment,
                    "pricing_basis": lane.pricing_basis,
                    "incumbent_transport_rate_per_shipment": (
                        json_number(
                            lane.incumbent_transport_rate_per_shipment
                        )
                    ),
                    "incumbent_contract_rate": json_number(
                        lane.incumbent_contract_rate
                    ),
                    "procurement_target_rate": json_number(
                        lane.procurement_target_rate
                    ),
                    "procurement_target_contract_rate": json_number(
                        lane.procurement_target_contract_rate
                    ),
                    "awarded_rate_per_shipment": json_number(
                        lane.awarded_rate_per_shipment
                    ),
                    "awarded_contract_rate": json_number(
                        lane.awarded_contract_rate
                    ),
                    "awarded_rate_per_shipment_savings": (
                        json_number(
                            lane.awarded_rate_per_shipment_savings
                        )
                    ),
                    "awarded_savings_contract_value": json_number(
                        lane.awarded_savings_contract_value
                    ),
                    "vat_included": lane.vat_included,
                    "rate_validity": lane.rate_validity,
                    "profiles": [
                        {
                            "period_sequence": p.period_sequence,
                            "period_label": p.period_label,
                            "period_start_date": json_date(
                                p.period_start_date
                            ),
                            "period_end_date": json_date(
                                p.period_end_date
                            ),
                            "day_of_week": p.day_of_week,
                            "expected_loads": p.expected_loads,
                            "volume_entry_method": (
                                p.volume_entry_method
                            ),
                        }
                        for p in lane_profiles
                    ],
                    "profile_expected_loads_total": expected_loads,
                    "profile_interval_methods": interval_methods,
                    "profile_period_labels": period_labels,
                },

                "fuel_treatment": {
                    "fuel_treatment_type": (
                        lane.fuel_treatment_type
                    ),
                    "base_diesel_price": json_number(
                        lane.base_diesel_price
                    ),
                    "fuel_review_period": lane.fuel_review_period,
                    "fuel_component_percentage": json_number(
                        lane.fuel_component_percentage
                    ),
                },

                "operational_inclusions": {
                    "rate_includes_fuel": lane.rate_includes_fuel,
                    "rate_includes_driver": lane.rate_includes_driver,
                    "rate_includes_maintenance": (
                        lane.rate_includes_maintenance
                    ),
                    "rate_includes_insurance": (
                        lane.rate_includes_insurance
                    ),
                    "rate_includes_tolls": lane.rate_includes_tolls,
                    "rate_includes_border_charges": (
                        lane.rate_includes_border_charges
                    ),
                    "rate_includes_empty_return": (
                        lane.rate_includes_empty_return
                    ),
                    "rate_includes_waiting_time": (
                        lane.rate_includes_waiting_time
                    ),
                    "rate_includes_loading_assistance": (
                        lane.rate_includes_loading_assistance
                    ),
                    "rate_includes_offloading_assistance": (
                        lane.rate_includes_offloading_assistance
                    ),
                },

                "payment_and_invoicing": {
                    "payment_terms": lane.payment_terms,
                    "invoice_submission_frequency": (
                        lane.invoice_submission_frequency
                    ),
                    "invoice_submission_deadline": (
                        lane.invoice_submission_deadline
                    ),
                },

                "insurance_and_risk": {
                    "minimum_git_cover_amount": json_number(
                        lane.minimum_git_cover_amount
                    ),
                    "minimum_liability_cover_amount": json_number(
                        lane.minimum_liability_cover_amount
                    ),
                    "git_all_risk_required": (
                        lane.git_all_risk_required
                    ),
                    "git_first_loss_required": (
                        lane.git_first_loss_required
                    ),
                    "git_driver_fidelity_required": (
                        lane.git_driver_fidelity_required
                    ),
                    "delivery_documentation_sla": (
                        lane.delivery_documentation_sla
                    ),
                    "claims_risk_policy": lane.claims_risk_policy,
                    "claims_risk_requirements": (
                        lane.claims_risk_requirements
                    ),
                },

                "operations": {
                    "vehicle_tracking_required": (
                        lane.vehicle_tracking_required
                    ),
                    "all_time_hour_control_room": (
                        lane.all_time_hour_control_room
                    ),
                    "driver_mobile_phone": (
                        lane.driver_mobile_phone
                    ),
                    "clean_compliant_equipment": (
                        lane.clean_compliant_equipment
                    ),
                    "pallet_management": lane.pallet_management,
                    "pod_submission_local": lane.pod_submission_local,
                    "pod_submission_long_haul": (
                        lane.pod_submission_long_haul
                    ),
                    "pod_submission_cross_border": (
                        lane.pod_submission_cross_border
                    ),
                    "subcontracting_policy": (
                        lane.subcontracting_policy
                    ),
                    "turnaround_and_demurrage": turnaround,
                    "escort_policy": escort_policy,
                    "accessorials": lane_accessorials,
                    "driver_certification_standards": certifications,
                    "target_service_standards": lane_standards,
                },

                "vehicle_requirements": equipment,

                "facilities_and_stops": facilities,
            }

            # -----------------------------------------------------
            # SHORT LANE SUMMARY
            # -----------------------------------------------------

            distinct_awarded_carriers = unique_values([
                award.carrier_id for award in lane_awards
            ])

            lane_payloads[lane.id] = {
                "lane_id": lane.id,
                "tender_id": lane.tender_id,
                "bundle_reference": bundle_reference,
                "bundle_role": lane.bundle_role,
                "bundle_trip_sequence": lane.bundle_trip_sequence,

                "lane_summary": {
                    "origin": route["origin"],
                    "destination": route["destination"],
                    "route": route["route"],
                    "is_return_leg": (
                        (lane.bundle_role or "").strip().lower()
                        == "return"
                    ),
                    "distance_km": lane.actual_distance_km,
                    "priority_level": lane.priority_level,
                    "awarded_carrier_count": len(
                        distinct_awarded_carriers
                    ),
                    "commitment_type": lane.lane_commitment_type,
                    "lane_reference": lane.lane_reference,
                    "title": lane.lane_title,
                    "target_rate_per_trip": json_number(
                        lane.procurement_target_rate
                    ),
                    "expected_loads": expected_loads,
                    "awarded_loads": corridor_loads,
                },

                "full_lane_information": full_lane_information,

                "awarded_carriers": [],
            }

            # -----------------------------------------------------
            # CARRIER AWARDS FOR THIS LANE
            # -----------------------------------------------------

            for award in lane_awards:
                carrier = carrier_map.get(award.carrier_id)

                award_shipments = lane_shipments

                # Each award's shipments are identified by its unique
                # client_lane_id. Never count another award's trips.
                award_completed_shipments = sum(
                    1
                    for shipment in award_shipments
                    if (
                        shipment.carrier_lane_id == award.id
                        and (shipment.status or "").strip().lower()
                        == "completed"
                    )
                )

                # Legacy fallback: shipments with no carrier_lane_id
                # may still be associated through client_lane_id.
                if award_completed_shipments == 0:
                    award_completed_shipments = sum(
                        1
                        for shipment in award_shipments
                        if (
                            shipment.carrier_lane_id is None
                            and (
                                shipment.status or ""
                            ).strip().lower() == "completed"
                        )
                    )

                award_total_shipments = max(
                    award.total_slots or 0,
                    0,
                )

                completion_percentage = (
                    round(
                        award_completed_shipments
                        / award_total_shipments * 100,
                        2,
                    )
                    if award_total_shipments > 0
                    else None
                )

                carrier_documents = [
                    serialize_document(document)
                    for document in documents_by_lane[lane.id]
                ]

                lane_payloads[lane.id]["awarded_carriers"].append({
                    "carrier_lane_id": award.id,
                    "allocation_id": award.lane_reference
                    or f"AC-{award.id:06d}",

                    # No MSA/contract identifier exists in the supplied
                    # Carrier_Lane model, so we do not fabricate one.
                    "contract_id": None,

                    "status": award.contract_status,
                    "carrier_id": award.carrier_id,
                    "carrier_name": (
                        carrier.legal_business_name
                        if carrier
                        else None
                    ),

                    "term": {
                        "start_date": json_date(
                            award.contract_start_date
                        ),
                        "end_date": json_date(
                            award.contract_end_date
                        ),
                    },

                    "committed_slots": award.slots_per_interval,
                    "interval_label": award.volume_entry_method,
                    "volume_commitment": award.volume_commitment,
                    "estimated_total_shipments": award_total_shipments,
                    "completed_shipments": (
                        award_completed_shipments
                    ),
                    "completion_percentage": completion_percentage,

                    "rate": json_number(award.rate),
                    "contract_rate": json_number(
                        award.contract_rate
                    ),
                    "rate_basis": award.pricing_basis,
                    "award_rate_type": award.award_rate_type,
                    "vat_included": award.vat_included,

                    "documents": carrier_documents,
                })

        # =========================================================
        # 8. GROUP CORRIDORS BY TENDER ID
        #
        # Several client lane IDs with the same tender_id represent
        # one corridor and multiple awarded carrier allocations.
        # =========================================================

        lanes_by_tender = defaultdict(list)

        for lane in all_lanes:
            lanes_by_tender[lane.tender_id].append(lane)

        corridor_groups = []

        for corridor_tender_id, corridor_lanes in lanes_by_tender.items():
            # Choose the first lane as the source of corridor metadata.
            # The lane rows should represent the same logical corridor.
            representative = corridor_lanes[0]

            tender = tenders_by_id.get(corridor_tender_id)

            # Consolidate carrier awards from all client lanes
            # belonging to this tender.
            corridor_awards = []
            seen_award_ids = set()

            for lane in corridor_lanes:
                payload = lane_payloads[lane.id]

                for award in payload["awarded_carriers"]:
                    if award["carrier_lane_id"] not in seen_award_ids:
                        seen_award_ids.add(
                            award["carrier_lane_id"]
                        )
                        corridor_awards.append(award)

            # Logical corridor details are returned once.
            # Carrier allocations from duplicate client lanes are merged.
            corridor_distance = (
                representative.actual_distance_km or 0
            )

            corridor_loads = sum(
                award["estimated_total_shipments"]
                for award in corridor_awards
            )

            corridor_completed = sum(
                award["completed_shipments"]
                for award in corridor_awards
            )

            corridor_weight_kg = (
                (representative.average_shipment_weight_kg or 0)
                * corridor_loads
            )

            corridor_lane_ids = [
                lane.id for lane in corridor_lanes
            ]

            # Combine facility stops from all award lane records,
            # deduplicating facilities by their stop reference/name.
            corridor_facilities = []
            seen_facilities = set()

            for lane_id in corridor_lane_ids:
                for stop in stops_by_lane[lane_id]:
                    facility_key = (
                        stop.reference_number
                        or (
                            stop.facility_name,
                            stop.address,
                            stop.stop_type,
                        )
                    )

                    if facility_key not in seen_facilities:
                        seen_facilities.add(facility_key)
                        corridor_facilities.append(
                            serialize_stop(stop)
                        )

            distinct_carriers = unique_values([
                award["carrier_id"]
                for award in corridor_awards
            ])

            # A corridor is Active if at least one underlying lane
            # is Active.
            corridor_statuses = [
                lane.contract_status
                for lane in corridor_lanes
                if lane.contract_status
            ]

            corridor_status = (
                "Active"
                if "Active" in corridor_statuses
                else (
                    "Completed"
                    if corridor_statuses
                    and all(
                        status == "Completed"
                        for status in corridor_statuses
                    )
                    else (
                        "Awarded"
                        if "Awarded" in corridor_statuses
                        else (
                            corridor_statuses[0]
                            if corridor_statuses
                            else None
                        )
                    )
                )
            )

            corridor_groups.append({
                "group_type": "corridor",
                "tender_id": corridor_tender_id,
                "tender_reference": f"TND-{corridor_tender_id}",
                "title": representative.lane_title,
                "tender_title": (
                    tender.tender_title
                    if tender
                    else representative.lane_title
                ),
                "tender_category": (
                    tender.tender_category
                    if tender
                    else representative.lane_category
                ),
                "status": corridor_status,

                "lane_summary": {
                    "origin": representative.origin_city_province,
                    "destination": (
                        representative.destination_city_province
                    ),
                    "route": lane_route(representative)["route"],
                    "distance_km": corridor_distance,
                    "awarded_carrier_count": len(distinct_carriers),
                    "expected_loads": corridor_loads,
                    "completed_shipments": corridor_completed,
                    "combined_tonnage": round(
                        corridor_weight_kg / 1000,
                        3,
                    ),
                },

                # The representative's lane fields contain the
                # specifications for this corridor.
                "full_lane_information": lane_payloads[
                    representative.id
                ]["full_lane_information"],

                "facilities_and_stops": corridor_facilities,
                "awarded_carriers": corridor_awards,
            })

        # =========================================================
        # 9. GROUP CORRIDORS INTO BUNDLES
        # =========================================================

        corridors_by_tender = {
            corridor["tender_id"]: corridor
            for corridor in corridor_groups
        }

        bundle_groups = defaultdict(list)
        unbundled_corridors = []

        for corridor in corridor_groups:
            corridor_lanes = lanes_by_tender[
                corridor["tender_id"]
            ]

            representative = corridor_lanes[0]

            bundle = (
                bundle_by_id.get(representative.bundlee_id)
                or bundle_by_reference.get(
                    representative.bundle_reference
                )
            )

            if bundle:
                bundle_groups[bundle.id].append(corridor)
            else:
                unbundled_corridors.append(corridor)

        contract_groups = []

        for bundle_id, bundle_corridors in bundle_groups.items():
            bundle = bundle_by_id[bundle_id]

            # Sequence comes from the lane records, not from the
            # carrier allocation order.
            bundle_corridors.sort(
                key=lambda corridor: (
                    min(
                        (
                            lane.bundle_trip_sequence
                            if lane.bundle_trip_sequence is not None
                            else 999999
                        )
                        for lane in lanes_by_tender[
                            corridor["tender_id"]
                        ]
                    ),
                    corridor["tender_id"],
                )
            )

            contract_groups.append({
                "group_type": "bundle",
                "bundle_id": bundle.id,
                "bundle_reference": bundle.bundle_reference,
                "bundle_type": bundle.bundle_type,
                "award_scope": bundle.award_scope,
                "stage_count": bundle.stage_count,
                "status": bundle.status,
                "total_corridors": len(bundle_corridors),
                "legs": bundle_corridors,
            })

        for corridor in unbundled_corridors:
            contract_groups.append({
                "group_type": "single_corridor",
                "bundle_reference": None,
                "total_corridors": 1,
                "legs": [corridor],
            })

        # Ensure the requested tender is represented first where possible.
        contract_groups.sort(
            key=lambda group: (
                0
                if any(
                    leg["tender_id"] == tender_id
                    for leg in group["legs"]
                )
                else 1,
                group.get("bundle_reference") or "",
            )
        )

        # =========================================================
        # 10. CONTRACT-WIDE SUMMARY
        # =========================================================

        all_statuses = [
            lane.contract_status
            for lane in all_lanes
            if lane.contract_status
        ]

        if all_statuses and all(
            status == "Completed"
            for status in all_statuses
        ):
            contract_status = "Completed"
        elif "Active" in all_statuses:
            contract_status = "Active"
        elif "Awarded" in all_statuses:
            contract_status = "Awarded"
        elif all_statuses and all(
            status == "Cancelled"
            for status in all_statuses
        ):
            contract_status = "Cancelled"
        else:
            contract_status = (
                all_statuses[0] if all_statuses else None
            )

        start_dates = [
            lane.contract_start_date
            for lane in all_lanes
            if lane.contract_start_date
        ]

        end_dates = [
            lane.contract_end_date
            for lane in all_lanes
            if lane.contract_end_date
        ]

        contract_start_date = (
            min(start_dates) if start_dates else None
        )

        contract_end_date = (
            max(end_dates) if end_dates else None
        )

        distinct_tender_ids = unique_values([
            lane.tender_id for lane in all_lanes
        ])

        distinct_carrier_ids = unique_values([
            award.carrier_id for award in carrier_lanes
        ])

        total_combined_distance = sum(
            corridor["lane_summary"]["distance_km"] or 0
            for corridor in corridor_groups
        )

        total_completed_shipments = sum(
            corridor["lane_summary"]["completed_shipments"]
            for corridor in corridor_groups
        )

        total_estimated_shipments = sum(
            corridor["lane_summary"]["expected_loads"]
            for corridor in corridor_groups
        )

        total_combined_tonnage = sum(
            corridor["lane_summary"]["combined_tonnage"]
            for corridor in corridor_groups
        )

        # Strategic facilities are deduplicated across all corridors.
        strategic_facilities = []
        seen_strategic_facilities = set()

        for corridor in corridor_groups:
            for facility in corridor["facilities_and_stops"]:
                key = (
                    facility.get("reference_number")
                    or (
                        facility.get("facility_name"),
                        facility.get("address"),
                    )
                )

                if key not in seen_strategic_facilities:
                    seen_strategic_facilities.add(key)
                    strategic_facilities.append(facility)

        # =========================================================
        # 11. CONSOLIDATED CARRIER ALLOCATION LEDGER
        # =========================================================

        allocation_ledger = []

        total_committed_slots = 0
        total_awarded_shipments = 0
        total_ledger_completed = 0

        for corridor in corridor_groups:
            for award in corridor["awarded_carriers"]:
                total_committed_slots += (
                    award["committed_slots"] or 0
                )

                total_awarded_shipments += (
                    award["estimated_total_shipments"] or 0
                )

                total_ledger_completed += (
                    award["completed_shipments"] or 0
                )

                allocation_ledger.append({
                    "allocation_id": award["allocation_id"],
                    "carrier_lane_id": award["carrier_lane_id"],
                    "contract_id": award["contract_id"],
                    "tender_id": corridor["tender_id"],
                    "awarded_corridor": (
                        corridor["lane_summary"]["route"]
                    ),
                    "lane_reference": (
                        corridor["full_lane_information"]
                        ["administrative_and_lane_parameters"]
                        ["lane_reference"]
                    ),
                    "status": award["status"],
                    "carrier_id": award["carrier_id"],
                    "carrier_name": award["carrier_name"],
                    "term": award["term"],
                    "committed_slots": award["committed_slots"],
                    "interval_label": award["interval_label"],
                    "estimated_total_shipments": (
                        award["estimated_total_shipments"]
                    ),
                    "rate": award["rate"],
                    "contract_rate": award["contract_rate"],
                    "rate_basis": award["rate_basis"],
                    "completed_shipments": (
                        award["completed_shipments"]
                    ),
                    "completion_percentage": (
                        award["completion_percentage"]
                    ),
                    "documents": award["documents"],
                })

        # =========================================================
        # 12. CLIENT COMPANY NAME
        #
        # No client/company model was supplied. Use a name already
        # present in the authenticated user context if available.
        # =========================================================

        client_company_name = (
            current_user.get("company_name")
            or current_user.get("business_name")
            or current_user.get("legal_business_name")
        )

        # =========================================================
        # 13. FINAL RESPONSE
        # =========================================================

        return {
            "contract_overview": {
                "client_id": company_id,
                "client_company_name": client_company_name,
                "requested_tender_id": tender_id,
                "tender_ids": distinct_tender_ids,
                "status": contract_status,

                "total_corridors": len(corridor_groups),
                "combined_distance_km": total_combined_distance,
                "total_loads": total_estimated_shipments,
                "combined_tonnage": round(
                    total_combined_tonnage,
                    3,
                ),

                "term": {
                    "start_date": json_date(
                        contract_start_date
                    ),
                    "end_date": json_date(
                        contract_end_date
                    ),
                },

                "strategic_facilities": strategic_facilities,
            },

            "contract_agreement": {
                "title": (
                    contract_groups[0]["legs"][0]["tender_title"]
                    if contract_groups
                    and contract_groups[0].get("legs")
                    else None
                ),
                "status": contract_status,
                "length_category": unique_values([
                    lane.lane_length_category
                    for lane in all_lanes
                ]),
                "categories": unique_values([
                    lane.lane_category
                    for lane in all_lanes
                ]),
                "term": {
                    "start_date": json_date(
                        contract_start_date
                    ),
                    "end_date": json_date(
                        contract_end_date
                    ),
                },
                "total_loads": total_estimated_shipments,
                "combined_tonnage": round(
                    total_combined_tonnage,
                    3,
                ),
                "load_types": unique_values([
                    lane.load_type for lane in all_lanes
                ]),
                "payment_terms": unique_values([
                    lane.payment_terms for lane in all_lanes
                ]),
                "commodities": unique_values([
                    lane.commodity for lane in all_lanes
                ]),
            },

            "contract_scope_and_executive_statement": {
                "scope_of_work": unique_values([
                    lane.scope_description
                    for lane in all_lanes
                    if lane.scope_description
                ]),
                "origin_hubs": unique_values([
                    lane.origin_city_province
                    for lane in all_lanes
                ]),
                "destination_regions": unique_values([
                    lane.destination_region
                    or lane.destination_city_province
                    for lane in all_lanes
                ]),
                "required_equipment_configurations": unique_values([
                    config.equipment_type
                    for config in vehicle_configs
                ]),
            },

            "contract_groups": contract_groups,

            "contract_allocation_ledger": {
                "total_allocations": len(allocation_ledger),
                "total_committed_slots": total_committed_slots,
                "total_estimated_shipments": total_awarded_shipments,
                "completed_shipments": total_ledger_completed,
                "allocations": allocation_ledger,
            },

            "execution_summary": {
                "completed_shipments": total_completed_shipments,
                "remaining_shipments": max(
                    total_estimated_shipments
                    - total_completed_shipments,
                    0,
                ),
                "progress_percentage": (
                    round(
                        total_completed_shipments
                        / total_estimated_shipments * 100,
                        2,
                    )
                    if total_estimated_shipments > 0
                    else 0
                ),
            },

            "metadata": {
                "requested_tender_id": tender_id,
                "returned_client_lane_ids": all_lane_ids,
                "returned_tender_count": len(distinct_tender_ids),
                "returned_corridor_count": len(corridor_groups),
                "returned_bundle_count": len(bundle_groups),
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch client contracts: {str(e)}",
        )


@router.get("/client-shipments")
def get_client_shipments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        shipments = db.query(Client_Shipment).filter(Client_Shipment.client_id == company_id).all()

        if not shipments:
            return []

        shipment_data = []

        for shipment in shipments:

            carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first() if shipment.vehicle_id else None
            origin = db.query(Client_Shipment_Stop).filter(Client_Shipment_Stop.shipment_id == shipment.id, Client_Shipment_Stop.stop_type == "Origin").first()
            stops = db.query(Client_Shipment_Stop).filter(Client_Shipment_Stop.shipment_id == shipment.id).all()
            destination = db.query(Client_Shipment_Stop).filter(Client_Shipment_Stop.shipment_id == shipment.id, Client_Shipment_Stop.stop_type == "Destination").first()
            config = db.query(Client_Shipment_Vehicle_Requirement).filter(Client_Shipment_Vehicle_Requirement.shipment_id == shipment.id, Client_Shipment_Vehicle_Requirement.configuration_type == "Primary").first()

            shipment_data.append({
                "id": shipment.id,
                "auction_id": shipment.auction_id,
                "sub_shipment": {
                    "is_subshipment": shipment.is_subshipment,
                    "lane_id": shipment.client_lane_id,
                },
                "status": shipment.status,
                "hazchem_information": {
                    "hazardous_materials": shipment.hazardous_materials,
                    "hazchem_classification": shipment.hazchem_classification,
                },
                "tracking_status": shipment.tracking_status,
                "pickup_location": {
                    "origin": origin.address if origin else None,
                    "facility_name": origin.facility_name if origin else None,
                    "pickup_date": shipment.pickup_date if origin else None,
                    "window": {
                        "start_time": origin.operating_start_time if origin else None,
                        "end_time": origin.operating_end_time if origin else None,
                    },
                },
                "corridor_transit": {
                    "distance": shipment.distance,
                    "trip_type": shipment.trip_type,
                    "no_of_stops": len(stops),
                    "equipment_truck": {
                        "truck_type": config.truck_type if config and config.truck_type == "Rigid" else config.trailer_type if config else None,
                        "equipment_type": config.equipment_type if config else None,
                        "payload_capacity": shipment.minimum_weight_bracket_kg,
                    },
                    "cargo": {
                        "commodity": shipment.commodity,
                        "packaging_type": shipment.packaging_type,
                        "packaging_quantity": shipment.packaging_quantity,
                    },
                    "shipment_weight": shipment.shipment_weight,
                },
                "carrier": {
                    "company": carrier.legal_business_name if carrier else None,
                    "vehicle": vehicle.license_plate if vehicle else None,
                },
                "delivery_destination": {
                    "destination": destination.address if destination else None,
                    "facility_name": destination.facility_name if destination else None,
                    "eta_date": shipment.eta_date,
                    "window": {
                        "start_time": destination.operating_start_time if destination else None,
                        "end_time": destination.operating_end_time if destination else None,
                    },
                    "agreed_shipment_rate": {
                        "rate_basis": shipment.pricing_basis,
                        "rate": shipment.rate,
                        "rate_includes": {
                            "vat_inclusive": shipment.vat_included,
                            "fuel": shipment.rate_includes_fuel,
                            "driver": shipment.rate_includes_driver,
                            "tolls": shipment.rate_includes_tolls,
                            "insurance": {
                                "rate_includes_insurance": shipment.rate_includes_insurance,
                                "insurance_requirement": shipment.minimum_git_cover_amount,
                            },
                            "loading_assistance": shipment.rate_includes_loading_assistance,
                        },
                    },
                },
            })

        auction_groups = {}
        lane_groups = {}
        response = []

        for shipment in shipment_data:

            if shipment["auction_id"]:
                auction_groups.setdefault(shipment["auction_id"], []).append(shipment)

            elif shipment["sub_shipment"]["lane_id"] and shipment["pickup_location"]["pickup_date"]:
                group_key = (
                    shipment["sub_shipment"]["lane_id"],
                    shipment["pickup_location"]["pickup_date"]
                )
                lane_groups.setdefault(group_key, []).append(shipment)

            else:
                response.append(shipment)

        for auction_id, grouped_shipments in auction_groups.items():

            if len(grouped_shipments) == 1:
                response.append(grouped_shipments[0])
                continue

            first = grouped_shipments[0]

            response.append({
                "group_id": f"GRP-AUC-{auction_id}",
                "group_type": "auction",
                "auction_id": auction_id,
                "shipment_count": len(grouped_shipments),
                "status": first["status"],
                "tracking_status": first["tracking_status"],
                "pickup_location": first["pickup_location"],
                "corridor_transit": {
                    "distance": first["corridor_transit"]["distance"],
                    "trip_type": first["corridor_transit"]["trip_type"],
                    "no_of_stops": first["corridor_transit"]["no_of_stops"],
                    "equipment_truck": first["corridor_transit"]["equipment_truck"],
                    "cargo": first["corridor_transit"]["cargo"],
                    "shipment_weight": sum(
                        shipment["corridor_transit"]["shipment_weight"] or 0
                        for shipment in grouped_shipments
                    ),
                },
                "carrier": {
                    "company": ", ".join(
                        sorted(set(
                            shipment["carrier"]["company"]
                            for shipment in grouped_shipments
                            if shipment["carrier"]["company"]
                        ))
                    ) or None,
                    "vehicles": [
                        shipment["carrier"]["vehicle"]
                        for shipment in grouped_shipments
                        if shipment["carrier"]["vehicle"]
                    ],
                },
                "delivery_destination": {
                    "destination": first["delivery_destination"]["destination"],
                    "facility_name": first["delivery_destination"]["facility_name"],
                    "eta_date": first["delivery_destination"]["eta_date"],
                    "window": first["delivery_destination"]["window"],
                    "agreed_shipment_rate": {
                        "rate_basis": "Consolidated Group Rate",
                        "rate": sum(
                            shipment["delivery_destination"]["agreed_shipment_rate"]["rate"] or 0
                            for shipment in grouped_shipments
                        ),
                        "rate_includes": first["delivery_destination"]["agreed_shipment_rate"]["rate_includes"],
                    },
                },
                "shipments": grouped_shipments,
            })

        for group_key, grouped_shipments in lane_groups.items():

            if len(grouped_shipments) == 1:
                response.append(grouped_shipments[0])
                continue

            lane_id, pickup_date = group_key
            first = grouped_shipments[0]

            response.append({
                "group_id": f"GRP-LANE-{lane_id}-{pickup_date}",
                "group_type": "lane",
                "client_lane_id": lane_id,
                "shipment_count": len(grouped_shipments),
                "status": first["status"],
                "tracking_status": first["tracking_status"],
                "pickup_location": first["pickup_location"],
                "corridor_transit": {
                    "distance": first["corridor_transit"]["distance"],
                    "trip_type": first["corridor_transit"]["trip_type"],
                    "no_of_stops": first["corridor_transit"]["no_of_stops"],
                    "equipment_truck": first["corridor_transit"]["equipment_truck"],
                    "cargo": first["corridor_transit"]["cargo"],
                    "shipment_weight": sum(
                        shipment["corridor_transit"]["shipment_weight"] or 0
                        for shipment in grouped_shipments
                    ),
                },
                "carrier": {
                    "company": ", ".join(
                        sorted(set(
                            shipment["carrier"]["company"]
                            for shipment in grouped_shipments
                            if shipment["carrier"]["company"]
                        ))
                    ) or None,
                    "vehicles": [
                        shipment["carrier"]["vehicle"]
                        for shipment in grouped_shipments
                        if shipment["carrier"]["vehicle"]
                    ],
                },
                "delivery_destination": {
                    "destination": first["delivery_destination"]["destination"],
                    "facility_name": first["delivery_destination"]["facility_name"],
                    "eta_date": first["delivery_destination"]["eta_date"],
                    "window": first["delivery_destination"]["window"],
                    "agreed_shipment_rate": {
                        "rate_basis": "Consolidated Group Rate",
                        "rate": sum(
                            shipment["delivery_destination"]["agreed_shipment_rate"]["rate"] or 0
                            for shipment in grouped_shipments
                        ),
                        "rate_includes": first["delivery_destination"]["agreed_shipment_rate"]["rate_includes"],
                    },
                },
                "shipments": grouped_shipments,
            })

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/client-shipments/{id}")
def get_client_shipment(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    from decimal import Decimal

    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:

        # -----------------------------------------------------
        # BOOKING USER
        # -----------------------------------------------------

        booking_user = None

        if auction.client_user_id is not None:
            booking_user = (
                db.query(Director)
                .filter(
                    Director.id == auction.client_user_id,
                    Director.company_id == auction.client_id
                )
                .first()
            )

        booking_user_information = (
            {
                "id": booking_user.id,
                "first_name": booking_user.first_name,
                "last_name": booking_user.last_name,
                "full_name": (
                    f"{booking_user.first_name} {booking_user.last_name}"
                ),
                "role": booking_user.role,
                "email": booking_user.email,
                "phone_number": booking_user.phone_number,
            }
            if booking_user
            else None
        )


        # ============================================================
        # HELPERS
        # ============================================================

        def safe_value(value):
            """
            Keep numeric financial values accurate and let FastAPI
            serialize dates, times, Decimal values and other supported
            database values.
            """
            return value

        def get_latest_execution_metrics(shipment_id):
            return (
                db.query(Shipment_Execution_Metrics)
                .filter(
                    Shipment_Execution_Metrics.shipment_id == shipment_id
                )
                .order_by(
                    Shipment_Execution_Metrics.updated_at.desc(),
                    Shipment_Execution_Metrics.id.desc()
                )
                .first()
            )


        # ============================================================
        # DOCUMENT HELPERS
        # ============================================================

        def normalize_document_type(value):
            """
            Normalize document labels so that common naming variations
            match, e.g. 'Road Worthy Certificate' and 'roadworthy_certificate'.
            """
            return "".join(
                character.lower()
                for character in str(value or "")
                if character.isalnum()
            )

        def serialize_document(document):
            """
            Serialize a document record from its dedicated document table.
            """
            if document is None:
                return None

            return {
                "id": document.id,
                "document_type": document.document_type,
                "document_url": document.document_url,
                "expiry_date": document.expiry_date,
                "is_verified": document.is_verified,
                "status": document.status,
                "created_at": document.created_at,
                "updated_at": document.updated_at
            }

        def get_entity_documents(
            model,
            entity_id_column,
            entity_id,
            active_only=False
        ):
            """
            Fetch document records for a carrier, driver, vehicle or trailer.

            Document URLs and expiry dates are read from the document
            tables, not from the main entity tables.

            Missing documents are allowed and do not raise an error.
            """
            query = db.query(model).filter(
                entity_id_column == entity_id
            )

            # CarrierDocs explicitly has an is_active field.
            if active_only and hasattr(model, "is_active"):
                query = query.filter(model.is_active.is_(True))

            documents = (
                query.order_by(
                    model.created_at.desc(),
                    model.id.desc()
                ).all()
            )

            serialized_documents = [
                serialize_document(document)
                for document in documents
            ]

            return serialized_documents

        def find_document(documents, *accepted_types):
            """
            Find a document by any accepted document-type label.
            Returns None when no matching document exists.

            Matching is case-insensitive and ignores spaces,
            underscores, hyphens and other punctuation.
            """
            accepted = {
                normalize_document_type(value)
                for value in accepted_types
            }

            for document in documents:
                if normalize_document_type(
                    document.get("document_type")
                ) in accepted:
                    return document

            return None

        # ============================================================
        # ASSIGNED CARRIER
        # ============================================================

        def get_assigned_carrier(shipment):
            if not shipment.carrier_id:
                return None

            carrier = (
                db.query(Carrier)
                .filter(Carrier.id == shipment.carrier_id)
                .first()
            )

            if not carrier:
                return None

            carrier_user = (
                db.query(CarrierUser)
                .filter(CarrierUser.company_id == carrier.id)
                .first()
            )

            carrier_documents = get_entity_documents(
                model=CarrierDocs,
                entity_id_column=CarrierDocs.carrier_id,
                entity_id=carrier.id,
                active_only=True
            )

            # Named document lookups. Missing documents return None.
            registration_certificate = find_document(
                carrier_documents,
                "Business Registration Certificate",
                "Registration Certificate",
                "Business Registration",
                "BR Certificate",
                "BR"
            )

            proof_of_address = find_document(
                carrier_documents,
                "Proof of Address",
                "Address Confirmation",
                "Address Verification"
            )

            brnc_certificate = find_document(
                carrier_documents,
                "BRNC",
                "BRNC Certificate",
                "Business Registration Number Certificate"
            )

            git_certificate = find_document(
                carrier_documents,
                "GIT",
                "GIT Certificate",
                "Goods In Transit",
                "Goods In Transit Insurance",
                "Goods In Transit Certificate",
                "GIT Insurance Certificate"
            )

            liability_certificate = find_document(
                carrier_documents,
                "Liability",
                "Liability Certificate",
                "Third Party Liability",
                "Third Party Liability Certificate",
                "Liability Insurance Certificate"
            )

            return {
                "carrier_information": {
                    "id": carrier.id,
                    "is_verified": carrier.is_verified,
                    "status": carrier.status,
                    "company_name": carrier.legal_business_name,
                    "country_of_incorporation": (
                        carrier.country_of_incorporation
                    ),
                    "business_registration_number": (
                        carrier.business_registration_number
                    ),
                    "address": carrier.business_address,

                    "insurance": {
                        "goods_in_transit": {
                            "insurer": (
                                carrier.name_of_git_cover_insurance_company
                            ),
                            "policy_number": (
                                carrier.git_insurance_policy_number
                            ),
                            "cover_amount": carrier.git_cover_amount,
                            "certificate": git_certificate
                        },
                        "third_party_liability": {
                            "insurer": (
                                carrier.name_of_liability_cover_insurance_company
                            ),
                            "policy_number": (
                                carrier.liability_insurance_policy_number
                            ),
                            "cover_amount": (
                                carrier.liability_insurance_cover_amount
                            ),
                            "certificate": liability_certificate
                        }
                    },

                    "contact_person": {
                        "first_name": (
                            carrier_user.first_name if carrier_user else None
                        ),
                        "last_name": (
                            carrier_user.last_name if carrier_user else None
                        ),
                        "role": (
                            carrier_user.role if carrier_user else None
                        ),
                        "email": (
                            carrier_user.email if carrier_user else None
                        ),
                        "phone_number": (
                            carrier_user.phone_number if carrier_user else None
                        )
                    },

                    "carrier_docs": {
                        "registration_certificate": (
                            registration_certificate
                        ),
                        "proof_of_address": proof_of_address,

                        # BRNC is optional.
                        "brnc_certificate": brnc_certificate,

                        "git_certificate": git_certificate,
                        "liability_certificate": liability_certificate,

                        # Includes all active carrier document records.
                        "all_documents": carrier_documents
                    }
                }
            }

        # ============================================================
        # ASSIGNED DRIVER
        # ============================================================

        def get_assigned_driver(shipment):
            if not shipment.driver_id:
                return None

            driver = (
                db.query(Driver)
                .filter(Driver.id == shipment.driver_id)
                .first()
            )

            if not driver:
                return None

            driver_documents = get_entity_documents(
                model=DriverDocs,
                entity_id_column=DriverDocs.driver_id,
                entity_id=driver.id
            )

            id_document = find_document(
                driver_documents,
                "ID",
                "ID Document",
                "Identity Document",
                "Identity Card",
                "National ID",
                "South African ID"
            )

            license_document = find_document(
                driver_documents,
                "Driver License",
                "Drivers License",
                "Driving License",
                "Driving Licence",
                "License",
                "Licence"
            )

            # Support both the common PRDP spelling and the schema's PRPD
            # spelling so document labels can be matched consistently.
            prdp_document = find_document(
                driver_documents,
                "PRDP",
                "PRPD",
                "Professional Driving Permit",
                "Professional Driving Permit Document",
                "Professional Drivers Permit"
            )

            passport_document = find_document(
                driver_documents,
                "Passport",
                "Passport Document"
            )

            return {
                "id": driver.id,
                "is_verified": driver.is_verified,
                "status": driver.status,
                "nationality": driver.nationality,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "phone_number": driver.phone_number,

                "compliance": {
                    "id_number": driver.id_number,
                    "passport_number": (
                        driver.passport_number
                        if driver.passport_number else None
                    ),

                    "license": {
                        "license_number": driver.license_number,
                        "license_expiry_date": driver.license_expiry_date,
                        "document": license_document
                    },

                    "prdp": {
                        "prdp_number": (
                            getattr(driver, "prdp_number", None)
                            or getattr(driver, "prpd_number", None)
                        ),
                        "prdp_expiry_date": (
                            getattr(driver, "prdp_expiry_date", None)
                            or getattr(driver, "prpd_expiry_date", None)
                        ),

                        # Optional document.
                        "document": prdp_document
                    },

                    # Optional passport document.
                    "passport": {
                        "passport_number": (
                            driver.passport_number
                            if driver.passport_number else None
                        ),
                        "document": passport_document
                    },

                    "docs": {
                        "id_document": id_document,
                        "license_document": license_document,
                        "prdp_document": prdp_document,
                        "passport_document": passport_document,

                        "all_documents": driver_documents
                    }
                }
            }

        # ============================================================
        # ASSIGNED VEHICLE AND TRAILER
        # ============================================================

        def get_assigned_vehicle(shipment):
            if not shipment.vehicle_id:
                return None

            vehicle = (
                db.query(Vehicle)
                .filter(Vehicle.id == shipment.vehicle_id)
                .first()
            )

            if not vehicle:
                return None

            # --------------------------------------------------------
            # VEHICLE DOCUMENTS
            # --------------------------------------------------------

            vehicle_documents = get_entity_documents(
                model=VehicleDocs,
                entity_id_column=VehicleDocs.vehicle_id,
                entity_id=vehicle.id
            )

            vehicle_registration_document = find_document(
                vehicle_documents,
                "VRC",
                "Vehicle Registration Certificate",
                "Registration Certificate",
                "Registration or Leasing Certificate",
                "Vehicle Registration or Leasing"
            )

            vehicle_license_document = find_document(
                vehicle_documents,
                "Vehicle License Disk",
                "Vehicle Licence Disk",
                "License Disk",
                "Licence Disk"
            )

            vehicle_roadworthy_document = find_document(
                vehicle_documents,
                "Roadworthy",
                "Road Worthy",
                "Roadworthy Certificate",
                "Road Worthy Certificate",
                "Vehicle Roadworthy Certificate"
            )

            vehicle_tracking_document = find_document(
                vehicle_documents,
                "Tracking Certificate",
                "Vehicle Tracking Certificate",
                "Vehicle Tracking"
            )

            # --------------------------------------------------------
            # TRAILER AND TRAILER DOCUMENTS
            # --------------------------------------------------------

            trailer = None
            trailer_id = getattr(vehicle, "trailer_id", None)

            if trailer_id:
                trailer = (
                    db.query(Trailer)
                    .filter(Trailer.id == trailer_id)
                    .first()
                )

            trailer_information = None

            if trailer:
                trailer_documents = get_entity_documents(
                    model=Trailer_Docs,
                    entity_id_column=Trailer_Docs.trailer_id,
                    entity_id=trailer.id
                )

                trailer_registration_document = find_document(
                    trailer_documents,
                    "VRC",
                    "Trailer Registration Certificate",
                    "Registration Certificate",
                    "Registration or Leasing Certificate",
                    "VRC Leasing",
                    "Leasing Certificate"
                )

                trailer_license_document = find_document(
                    trailer_documents,
                    "Trailer License Disk",
                    "Trailer Licence Disk",
                    "License Disk",
                    "Licence Disk"
                )

                trailer_roadworthy_document = find_document(
                    trailer_documents,
                    "Roadworthy",
                    "Road Worthy",
                    "Roadworthy Certificate",
                    "Road Worthy Certificate",
                    "Trailer Roadworthy Certificate"
                )

                trailer_information = {
                    "id": trailer.id,
                    "is_verified": trailer.is_verified,
                    "status": trailer.status,
                    "make": trailer.make,
                    "model": trailer.model,
                    "year": trailer.year,
                    "color": trailer.color,

                    "equipment_payload_specs": {
                        "equipment_type": trailer.equipment_type,
                        "trailer_type": trailer.trailer_type,
                        "trailer_length": trailer.trailer_length,

                        "payload_specs": {
                            "tare_weight": trailer.tare_weight,
                            "gvm_weight": trailer.gvm_weight,
                            "payload_capacity": trailer.payload_capacity
                        }
                    },

                    "compliance": {
                        "vin": trailer.vin,
                        "license_plate": trailer.license_plate,
                        "license_expiry_date": trailer.license_expiry_date,

                        "docs": {
                            "registration_or_leasing_certificate": (
                                trailer_registration_document
                            ),
                            "license_disk": trailer_license_document,

                            # Optional document.
                            "road_worthy_certificate": (
                                trailer_roadworthy_document
                            ),

                            "all_documents": trailer_documents
                        }
                    }
                }

            # --------------------------------------------------------
            # VEHICLE RESPONSE
            # --------------------------------------------------------

            return {
                "truck_information": {
                    "id": vehicle.id,
                    "is_verified": vehicle.is_verified,
                    "status": vehicle.status,
                    "type": vehicle.type,
                    "make": vehicle.make,
                    "model": vehicle.model,
                    "year": vehicle.year,
                    "color": vehicle.color,
                    "axle_configuration": vehicle.axle_configuration,
                    "equipment_type": vehicle.equipment_type,

                    "payload_specs": {
                        "tare_weight": vehicle.tare_weight,
                        "gvm_weight": vehicle.gvm_weight,
                        "payload_capacity": vehicle.payload_capacity
                    },

                    "compliance": {
                        "vin": vehicle.vin,
                        "license_plate": vehicle.license_plate,
                        "license_expiry_date": vehicle.license_expiry_date,

                        "docs": {
                            "registration_or_leasing_certificate": (
                                vehicle_registration_document
                            ),
                            "vehicle_license_disk": (
                                vehicle_license_document
                            ),

                            # Optional document.
                            "roadworthy_certificate": (
                                vehicle_roadworthy_document
                            ),

                            "tracking_certificate": (
                                vehicle_tracking_document
                            ),

                            "all_documents": vehicle_documents
                        }
                    }
                },

                "trailer_information": trailer_information
            }

        def get_shipment_details(shipment):
            """
            Builds the full response for one shipment.

            Every bundle leg uses this same function so that each leg
            retains its own requirements, carrier, route and metrics.
            """

            # --------------------------------------------------------
            # ROUTE STOPS
            # --------------------------------------------------------

            stops = (
                db.query(Client_Shipment_Stop)
                .filter(
                    Client_Shipment_Stop.shipment_id == shipment.id
                )
                .order_by(
                    Client_Shipment_Stop.stop_sequence.asc(),
                    Client_Shipment_Stop.id.asc()
                )
                .all()
            )

            facilities = []

            for stop in stops:
                demurrage = (
                    db.query(
                        Shipment_Turnaround_Window_Demurrage_Protocals
                    )
                    .filter(
                        Shipment_Turnaround_Window_Demurrage_Protocals
                        .shipment_id == shipment.id,
                        Shipment_Turnaround_Window_Demurrage_Protocals
                        .stop_id == stop.id
                    )
                    .first()
                )

                facilities.append({
                    "stop_sequence": stop.stop_sequence,
                    "stop_type": stop.stop_type,
                    "facility_name": stop.facility_name,
                    "address": stop.address,
                    "complete_address": stop.complete_address,
                    "city_province": stop.city_province,
                    "country": stop.country,
                    "region": stop.region,
                    "latitude": stop.latitude,
                    "longitude": stop.longitude,

                    "scheduling_type": stop.scheduling_type,

                    "operations_availability": {
                        "open_monday": stop.open_monday,
                        "open_tuesday": stop.open_tuesday,
                        "open_wednesday": stop.open_wednesday,
                        "open_thursday": stop.open_thursday,
                        "open_friday": stop.open_friday,
                        "open_saturday": stop.open_saturday,
                        "open_sunday": stop.open_sunday,

                        "operating_times": {
                            "start_time": stop.operating_start_time,
                            "end_time": stop.operating_end_time
                        }
                    },

                    "contact_person": {
                        "first_name": stop.contact_first_name,
                        "last_name": stop.contact_last_name,
                        "phone_number": stop.contact_phone_number,
                        "email": stop.contact_email
                    },

                    "reference_number": stop.reference_number,
                    "arrival_time": stop.arrival_time,
                    "departure_time": stop.departure_time,
                    "notes": stop.notes,

                    "turnaround_window_and_demurrage": (
                        {
                            "condition": demurrage.demurrage_conditions,
                            "turn_around_time": (
                                demurrage.loading_offloading_turnaround_hours
                            ),
                            "free_demurrage_hours": (
                                demurrage.free_demurrage_hours
                            ),
                            "rate_per_hour": (
                                demurrage.demurrage_rate_per_hour
                            ),
                            "maximum_demurrage_incursion_hours": (
                                demurrage.maximum_demurrage_incursion_hours
                            )
                        }
                        if demurrage else None
                    )
                })

            # --------------------------------------------------------
            # VEHICLE REQUIREMENTS
            # --------------------------------------------------------

            configs = (
                db.query(Client_Shipment_Vehicle_Requirement)
                .filter(
                    Client_Shipment_Vehicle_Requirement.shipment_id
                    == shipment.id
                )
                .order_by(
                    Client_Shipment_Vehicle_Requirement.id.asc()
                )
                .all()
            )

            accessorials = (
                db.query(Shipment_Accessorial)
                .filter(Shipment_Accessorial.shipment_id == shipment.id)
                .order_by(Shipment_Accessorial.id.asc())
                .all()
            )

            accessorial_details = [
                {
                    "type": item.charge_type,
                    "treatment": item.treatment,
                    "threshold_value": item.threshold_value,
                    "threshold_unit": item.threshold_unit,
                    "notes": item.notes
                }
                for item in accessorials
            ]

            equipment_requirements = [
                {
                    "configuration_type": config.configuration_type,
                    "truck_type": config.truck_type,
                    "equipment_type": config.equipment_type,
                    "trailer_type": config.trailer_type,
                    "trailer_length": config.trailer_length,
                    "is_required": config.is_required,
                    "minimum_weight_bracket": (
                        shipment.minimum_weight_bracket_kg
                    ),

                    "fleet_compliance_requirements": {
                        "vehicle_tracking_required": (
                            shipment.vehicle_tracking_required
                        ),
                        "control_room_monitoring": (
                            shipment.all_time_hour_control_room
                        ),
                        "driver_mobile_phone": shipment.driver_mobile_phone,
                        "clean_compliant_equipment": (
                            shipment.clean_compliant_equipment
                        )
                    },

                    "accessorial_rigging_gear": {
                        "chep_pallet_management": shipment.pallet_management,
                        "tarpaulin_required": (
                            shipment.tarpaulin_compliance_required
                        ),
                        "corner_plates": shipment.corner_plates_required,
                        "chock_blocks": shipment.chock_blocks_required,
                        "ratchets_belts": shipment.ratchets_belts_required,
                        "accessorials": accessorial_details,
                        "other_equipment_requirements": (
                            shipment.other_equipment_requirements
                        )
                    }
                }
                for config in configs
            ]

            # --------------------------------------------------------
            # DOCUMENTS
            # --------------------------------------------------------

            documents = (
                db.query(Shipment_Documents)
                .filter(
                    Shipment_Documents.shipment_id == shipment.id
                )
                .order_by(Shipment_Documents.id.asc())
                .all()
            )

            document_details = [
                {
                    "id": doc.id,
                    "name": doc.name,
                    "url": doc.doc_url,
                    "uploaded_at": doc.created_at,
                }
                for doc in documents
            ]

            # --------------------------------------------------------
            # CERTIFICATIONS / DRIVER STANDARDS
            # --------------------------------------------------------

            certifications = (
                db.query(
                    Shipment_Carrier_Certification_Driver_Standards
                )
                .filter(
                    Shipment_Carrier_Certification_Driver_Standards
                    .shipment_id == shipment.id
                )
                .order_by(
                    Shipment_Carrier_Certification_Driver_Standards.id.asc()
                )
                .all()
            )

            certification_details = [
                {
                    "id": cert.id,
                    "name": cert.certification_name,
                    "is_required": cert.is_required,
                    "directive": (
                        cert.driver_qualification_security_directives
                    )
                }
                for cert in certifications
            ]

            # --------------------------------------------------------
            # ESCORT POLICY
            # --------------------------------------------------------

            escort_policy = (
                db.query(Shipment_Escort_Policy)
                .filter(
                    Shipment_Escort_Policy.shipment_id == shipment.id
                )
                .first()
            )

            escort_details = (
                {
                    "armed_escort_required": (
                        escort_policy.armed_escort_required
                    ),
                    "escort_expense_responsible_party": (
                        escort_policy.escort_expense_responsible_party
                    )
                }
                if escort_policy else None
            )

            # --------------------------------------------------------
            # SERVICE STANDARDS
            # --------------------------------------------------------

            slas = (
                db.query(Shipment_Service_Standard)
                .filter(
                    Shipment_Service_Standard.shipment_id == shipment.id
                )
                .order_by(Shipment_Service_Standard.id.asc())
                .all()
            )

            sla_details = [
                {
                    "id": sla.id,
                    "standard_type": sla.standard_type,
                    "target_value": sla.target_value,
                    "unit": sla.unit,
                    # The schema does not define a direct link between
                    # each service standard and an actual measurement.
                    # Actual execution measurements are returned below.
                }
                for sla in slas
            ]

            # --------------------------------------------------------
            # EXECUTION METRICS
            # --------------------------------------------------------

            metrics = get_latest_execution_metrics(shipment.id)

            if metrics:
                performance = {
                    "trip_time": {
                        "start_time": metrics.actual_pickup_at,
                        "completion_time": metrics.completed_at
                    },

                    "pickup_otif": {
                        "planned_pickup_at": metrics.planned_pickup_at,
                        "actual_pickup_at": metrics.actual_pickup_at,
                        "pickup_delay_minutes": metrics.pickup_delay_minutes,
                        "dwell_or_detention_time": (
                            metrics.origin_dwell_minutes
                        )
                    },

                    "stops": {
                        "planned_stop_count": metrics.planned_stop_count,
                        "actual_stop_count": metrics.actual_stop_count,
                        "dwell_time": metrics.intermediate_dwell_minutes
                    },

                    "delivery": {
                        "planned_delivery_at": metrics.planned_delivery_at,
                        "actual_delivery_at": metrics.actual_delivery_at,
                        "dwell_or_detention_time": (
                            metrics.destination_dwell_minutes
                        ),
                        "delivery_delay_minutes": (
                            metrics.delivery_delay_minutes
                        )
                    },

                    "route_distance": {
                        "planned_distance": metrics.planned_distance,
                        "actual_distance": metrics.actual_distance,
                        "route_variance_km": metrics.route_variance_km
                    },

                    "transit_time": {
                        "planned_transit_in_minutes": (
                            metrics.planned_transit_minutes
                        ),
                        "actual_transit_minutes": (
                            metrics.actual_transit_minutes
                        ),
                        "transit_variance_minutes": (
                            metrics.transit_variance_minutes
                        )
                    },

                    "summary": {
                        "stops_summary": {
                            "planned_stop_count": metrics.planned_stop_count,
                            "actual_stop_count": metrics.actual_stop_count,

                            "pickup_dwell_time_minutes": (
                                metrics.origin_dwell_minutes
                            ),
                            "stops_dwell_time_minutes": (
                                metrics.intermediate_dwell_minutes
                            ),
                            "delivery_dwell_time_minutes": (
                                metrics.destination_dwell_minutes
                            ),

                            "total_dwell_time": {
                                "total_stop_dwell_minutes": (
                                    metrics.total_stop_dwell_minutes
                                ),
                                "longest_stop_dwell_minutes": (
                                    metrics.longest_stop_dwell_minutes
                                )
                            }
                        },

                        "delays": {
                            "pickup_delay_minutes": (
                                metrics.pickup_delay_minutes
                            ),
                            "delivery_delay_minutes": (
                                metrics.delivery_delay_minutes
                            ),
                            "total_delay_minutes": (
                                metrics.total_delay_minutes
                            )
                        }
                    },

                    "tracking_compliance_percent": (
                        metrics.tracking_compliance_percent
                    ),
                    "execution_status": metrics.status,
                    "completed_at": metrics.completed_at
                }
            else:
                # A shipment can exist before tracking/execution metrics
                # have been created. Do not fail the entire response.
                performance = {
                    "trip_time": {
                        "start_time": None,
                        "completion_time": None
                    },
                    "pickup_otif": {
                        "planned_pickup_at": None,
                        "actual_pickup_at": None,
                        "pickup_delay_minutes": None,
                        "dwell_or_detention_time": None
                    },
                    "stops": {
                        "planned_stop_count": None,
                        "actual_stop_count": None,
                        "dwell_time": None
                    },
                    "delivery": {
                        "planned_delivery_at": None,
                        "actual_delivery_at": None,
                        "dwell_or_detention_time": None,
                        "delivery_delay_minutes": None
                    },
                    "route_distance": {
                        "planned_distance": None,
                        "actual_distance": None,
                        "route_variance_km": None
                    },
                    "transit_time": {
                        "planned_transit_in_minutes": None,
                        "actual_transit_minutes": None,
                        "transit_variance_minutes": None
                    },
                    "summary": {
                        "stops_summary": {
                            "planned_stop_count": None,
                            "actual_stop_count": None,
                            "pickup_dwell_time_minutes": None,
                            "stops_dwell_time_minutes": None,
                            "delivery_dwell_time_minutes": None,
                            "total_dwell_time": {
                                "total_stop_dwell_minutes": None,
                                "longest_stop_dwell_minutes": None
                            }
                        },
                        "delays": {
                            "pickup_delay_minutes": None,
                            "delivery_delay_minutes": None,
                            "total_delay_minutes": None
                        }
                    },
                    "tracking_compliance_percent": None,
                    "execution_status": None,
                    "completed_at": None
                }

            # --------------------------------------------------------
            # COMPLETE SHIPMENT OBJECT
            # --------------------------------------------------------

            return {
                "shipment_summary": {
                    "id": shipment.id,
                    "shipment_reference": shipment.shipment_reference,
                    "booking_reference": shipment.booking_reference,

                    "booked_by": booking_user_information,
            
                    "customer_reference_number": (
                        shipment.customer_reference_number
                    ),
                    "status": shipment.status,
                    "trip_status": shipment.trip_status,
                    "tracking_status": shipment.tracking_status,
                    "booking_source": shipment.booking_source,
                    "is_subshipment": shipment.is_subshipment,
                    "auction_id": shipment.auction_id,
                    "client_lane_id": shipment.client_lane_id,
                    "carrier_lane_id": shipment.carrier_lane_id,
                    "bundle_reference": shipment.bundle_reference,
                    "bundle_role": shipment.bundle_role,
                    "bundle_trip_sequence": shipment.bundle_trip_sequence,
                    "pickup_date": shipment.pickup_date,
                    "eta_date": shipment.eta_date,
                    "eta_window": shipment.eta_window,
                    "distance": shipment.distance,
                    "estimated_transit_time": (
                        shipment.estimated_transit_time
                    ),
                    "number_of_stops": len(stops),
                    "execution_status": (
                        metrics.status if metrics else None
                    )
                },

                "financials": {
                    "rate": shipment.rate,
                    "rate_basis": shipment.pricing_basis,
                    "payment_terms": shipment.payment_terms,
                    "vat_inclusive": (
                        shipment.vat_included
                        if shipment.vat_included is not None
                        else "Not Applicable"
                    ),
                    "invoice_id": shipment.invoice_id,
                    "invoice_due_date": shipment.invoice_due_date,
                    "invoice_status": shipment.invoice_status,

                    "rate_inclusive_of": {
                        "rate_includes_fuel": shipment.rate_includes_fuel,
                        "rate_includes_driver": shipment.rate_includes_driver,
                        "rate_includes_maintenance": (
                            shipment.rate_includes_maintenance
                        ),
                        "rate_includes_insurance": (
                            shipment.rate_includes_insurance
                        ),
                        "tolls": shipment.rate_includes_tolls,
                        "border_charges": (
                            shipment.rate_includes_border_charges
                        ),
                        "empty_return": (
                            shipment.rate_includes_empty_return
                        ),
                        "detention_time": (
                            shipment.rate_includes_waiting_time
                        ),
                        "loading_assistance_charges": (
                            shipment.rate_includes_loading_assistance
                        ),
                        "offloading_assistance_charges": (
                            shipment.rate_includes_offloading_assistance
                        )
                    }
                },

                "shipment_details": {
                    "id": shipment.id,
                    "shipment_reference": shipment.shipment_reference,
                    "booking_reference": shipment.booking_reference,
                    "is_subshipment": shipment.is_subshipment,
                    "auction_id": shipment.auction_id,
                    "lane_id": shipment.client_lane_id,
                    "trip_type": shipment.trip_type,
                    "load_type": shipment.load_type,
                    "pickup_date": shipment.pickup_date,
                    "priority_level": shipment.priority_level,
                    "status": shipment.status,
                    "trip_status": shipment.trip_status,
                    "tracking_status": shipment.tracking_status,
                    "booking_source": shipment.booking_source,
                    "bundle_reference": shipment.bundle_reference,
                    "bundle_role": shipment.bundle_role,
                    "bundle_trip_sequence": (
                        shipment.bundle_trip_sequence
                    ),
                    "bundle_type": shipment.bundle_type,

                    "cargo_details": {
                        "customer_reference_number": (
                            shipment.customer_reference_number
                        ),
                        "commodity": shipment.commodity,
                        "shipment_weight": shipment.shipment_weight,

                        "packaging": {
                            "packaging_type": shipment.packaging_type,
                            "packaging_quantity": (
                                shipment.packaging_quantity
                            )
                        },

                        "temperature": {
                            "temperature_control": (
                                shipment.temperature_control
                            ),
                            "target_temperature_spec": (
                                shipment.target_temperature_spec
                            )
                        },

                        "hazchem": {
                            "hazardous_materials": (
                                shipment.hazardous_materials
                            ),
                            "hazchem_classification": (
                                shipment.hazchem_classification
                            )
                        },

                        "under_customs_bond": shipment.under_bond,
                        "requires_rib": shipment.rib_requirements
                    },

                    "route": {
                        "distance": shipment.distance,
                        "estimated_transit_time": (
                            shipment.estimated_transit_time
                        ),
                        "eta_date": shipment.eta_date,
                        "eta_window": shipment.eta_window,
                        "route_preview_embed": (
                            shipment.route_preview_embed
                        ),
                        "polyline": shipment.polyline
                    }
                },

                "documents": document_details,

                "pod_submission_rules": {
                    "local_haul_shipments": shipment.pod_submission_local,
                    "long_haul_shipments": (
                        shipment.pod_submission_long_haul
                    ),
                    "cross_border_haul_shipments": (
                        shipment.pod_submission_cross_border
                    ),
                    "pod_document": shipment.pod_document
                },

                "insurance_requirements": {
                    "git_requirement": shipment.minimum_git_cover_amount,
                    "liability_requirement": (
                        shipment.minimum_liability_cover_amount
                    ),

                    "cover_spectrum": {
                        "git_all_risk": shipment.git_all_risk_required,
                        "first_loss": shipment.git_first_loss_required,
                        "driver_fidelity": (
                            shipment.git_driver_fidelity_required
                        )
                    },

                    "permits_and_certifications": certification_details
                },

                "equipments": equipment_requirements,

                "target_sla": sla_details,

                "facilities": facilities,

                "escort_policy": escort_details,

                "assigned_carrier": get_assigned_carrier(shipment),

                "assigned_driver": get_assigned_driver(shipment),

                "assigned_vehicle": get_assigned_vehicle(shipment),

                "performance": performance
            }

        # ============================================================
        # 1. FETCH THE REQUESTED SHIPMENT WITH CLIENT ISOLATION
        # ============================================================

        shipment = (
            db.query(Client_Shipment)
            .filter(
                Client_Shipment.id == id,
                Client_Shipment.client_id == company_id
            )
            .first()
        )

        if not shipment:
            raise HTTPException(
                status_code=404,
                detail="Shipment not found"
            )

        # ============================================================
        # 2. DETERMINE WHETHER THIS IS A SINGLE SHIPMENT OR A BUNDLE
        # ============================================================

        bundle = None
        bundle_shipments = []

        if shipment.bundlee_id is not None:
            # Check the bundle record belongs to the same client.
            bundle = (
                db.query(Client_Shipment_Bundle)
                .filter(
                    Client_Shipment_Bundle.id == shipment.bundlee_id,
                    Client_Shipment_Bundle.client_id == company_id
                )
                .first()
            )

            # Fetch only shipments from this bundle and this client.
            # Sorting ensures the legs are returned in trip sequence.
            bundle_shipments = (
                db.query(Client_Shipment)
                .filter(
                    Client_Shipment.bundlee_id == shipment.bundlee_id,
                    Client_Shipment.client_id == company_id
                )
                .order_by(
                    Client_Shipment.bundle_trip_sequence.asc(),
                    Client_Shipment.id.asc()
                )
                .all()
            )

            # Defensive fallback: never omit the requested shipment.
            if not any(item.id == shipment.id for item in bundle_shipments):
                bundle_shipments.append(shipment)
                bundle_shipments.sort(
                    key=lambda item: (
                        item.bundle_trip_sequence is None,
                        item.bundle_trip_sequence
                        if item.bundle_trip_sequence is not None
                        else item.id,
                        item.id
                    )
                )

        else:
            # A standalone shipment is represented as a one-item list.
            bundle_shipments = [shipment]

        # ============================================================
        # 3. BUILD INDIVIDUAL SHIPMENT DETAILS
        # ============================================================

        shipment_details = [
            get_shipment_details(item)
            for item in bundle_shipments
        ]

        is_bundle = shipment.bundlee_id is not None
        shipment_count = len(bundle_shipments)

        # ============================================================
        # 4. BUILD SHIPMENT STATUS COUNTS
        # ============================================================

        def normalize_status(value):
            return str(value or "").strip().lower().replace("_", " ").replace("-", " ")

        completed_statuses = {
            "completed", "delivered", "complete", "closed"
        }
        in_transit_statuses = {
            "in transit", "in progress", "on route", "on the road"
        }
        delayed_statuses = {
            "delayed", "late", "exception", "at risk"
        }
        pending_statuses = {
            "pending", "booked", "scheduled", "awaiting pickup",
            "awaiting collection", "assigned"
        }

        completed_count = 0
        in_transit_count = 0
        delayed_count = 0
        pending_count = 0
        status_counts = {}
        operational_exceptions = []

        for item in bundle_shipments:
            status = normalize_status(item.status)
            trip_status = normalize_status(item.trip_status)
            tracking_status = normalize_status(item.tracking_status)

            display_status = item.status or "Unknown"
            status_counts[display_status] = (
                status_counts.get(display_status, 0) + 1
            )

            # Count each shipment only once. Prefer its primary status,
            # using trip_status as a fallback when primary status is absent.
            effective_status = status or trip_status

            if effective_status in completed_statuses:
                completed_count += 1
            elif effective_status in in_transit_statuses:
                in_transit_count += 1
            elif effective_status in delayed_statuses:
                delayed_count += 1
            elif effective_status in pending_statuses or not effective_status:
                pending_count += 1

            # Surface explicit delay/exception indicators.
            if (
                status in delayed_statuses
                or trip_status in delayed_statuses
                or tracking_status in delayed_statuses
            ):
                operational_exceptions.append({
                    "shipment_id": item.id,
                    "shipment_reference": item.shipment_reference,
                    "exception_type": "Shipment status indicates a delay or exception",
                    "status": item.status,
                    "trip_status": item.trip_status,
                    "tracking_status": item.tracking_status
                })

        # ============================================================
        # 5. CALCULATE RATE TOTAL AND ROUTE SEQUENCE
        # ============================================================

        total_shipment_rates = sum(
            (
                item.rate
                if isinstance(item.rate, Decimal)
                else Decimal(str(item.rate or 0))
            )
            for item in bundle_shipments
        )

        route_sequence = []
        total_distance = Decimal("0")
        known_distance_count = 0

        for item in bundle_shipments:
            stops = (
                db.query(Client_Shipment_Stop)
                .filter(
                    Client_Shipment_Stop.shipment_id == item.id
                )
                .order_by(
                    Client_Shipment_Stop.stop_sequence.asc(),
                    Client_Shipment_Stop.id.asc()
                )
                .all()
            )

            first_stop = stops[0] if stops else None
            last_stop = stops[-1] if stops else None

            route_sequence.append({
                "shipment_id": item.id,
                "shipment_reference": item.shipment_reference,
                "sequence": item.bundle_trip_sequence,
                "role": item.bundle_role,
                "status": item.status,
                "origin": (
                    {
                        "facility_name": first_stop.facility_name,
                        "address": (
                            first_stop.complete_address
                            or first_stop.address
                        ),
                        "city_province": first_stop.city_province,
                        "country": first_stop.country
                    }
                    if first_stop else None
                ),
                "destination": (
                    {
                        "facility_name": last_stop.facility_name,
                        "address": (
                            last_stop.complete_address
                            or last_stop.address
                        ),
                        "city_province": last_stop.city_province,
                        "country": last_stop.country
                    }
                    if last_stop else None
                )
            })

            if item.distance is not None:
                total_distance += Decimal(str(item.distance))
                known_distance_count += 1

        # Only call the distance total complete when every shipment has
        # a recorded distance. This avoids presenting a partial sum as total.
        combined_distance = (
            total_distance if known_distance_count == shipment_count else None
        )

        completion_percentage = (
            round((completed_count / shipment_count) * 100, 2)
            if shipment_count else 0
        )

        # ============================================================
        # 6. AGGREGATE EXECUTION PERFORMANCE
        # ============================================================

        metrics_by_shipment = {
            item.id: get_latest_execution_metrics(item.id)
            for item in bundle_shipments
        }

        def sum_metric(metric_name):
            values = [
                getattr(metric, metric_name, None)
                for metric in metrics_by_shipment.values()
                if metric is not None
                and getattr(metric, metric_name, None) is not None
            ]

            # Do not present a partial sum as a complete bundle total.
            if len(values) != shipment_count:
                return None

            return sum(values)

        pickup_delays = [
            metric.pickup_delay_minutes
            for metric in metrics_by_shipment.values()
            if metric is not None and metric.pickup_delay_minutes is not None
        ]

        delivery_delays = [
            metric.delivery_delay_minutes
            for metric in metrics_by_shipment.values()
            if metric is not None and metric.delivery_delay_minutes is not None
        ]

        tracking_values = [
            metric.tracking_compliance_percent
            for metric in metrics_by_shipment.values()
            if metric is not None
            and metric.tracking_compliance_percent is not None
        ]

        # Average only available tracking measurements; expose the count
        # so consumers can see how many legs contributed to the average.
        average_tracking_compliance = (
            round(sum(tracking_values) / len(tracking_values), 2)
            if tracking_values else None
        )

        performance_overview = {
            "pickup_delay_minutes_total": sum_metric(
                "pickup_delay_minutes"
            ),
            "delivery_delay_minutes_total": sum_metric(
                "delivery_delay_minutes"
            ),
            "total_delay_minutes": sum_metric("total_delay_minutes"),
            "planned_transit_minutes_total": sum_metric(
                "planned_transit_minutes"
            ),
            "actual_transit_minutes_total": sum_metric(
                "actual_transit_minutes"
            ),
            "tracking_compliance_average_percent": (
                average_tracking_compliance
            ),
            "tracking_compliance_legs_with_data": len(tracking_values),
            "legs_with_execution_metrics": sum(
                1 for metric in metrics_by_shipment.values()
                if metric is not None
            ),
            "legs_with_pickup_delay_data": len(pickup_delays),
            "legs_with_delivery_delay_data": len(delivery_delays)
        }

        # Add execution-derived delay exceptions without duplicating
        # an exception already identified from shipment statuses.
        for item in bundle_shipments:
            metric = metrics_by_shipment.get(item.id)
            if metric is None:
                continue

            if (
                metric.pickup_delay_minutes is not None
                and metric.pickup_delay_minutes > 0
            ):
                operational_exceptions.append({
                    "shipment_id": item.id,
                    "shipment_reference": item.shipment_reference,
                    "exception_type": "Pickup delay",
                    "delay_minutes": metric.pickup_delay_minutes
                })

            if (
                metric.delivery_delay_minutes is not None
                and metric.delivery_delay_minutes > 0
            ):
                operational_exceptions.append({
                    "shipment_id": item.id,
                    "shipment_reference": item.shipment_reference,
                    "exception_type": "Delivery delay",
                    "delay_minutes": metric.delivery_delay_minutes
                })

        # ============================================================
        # 7. DETERMINE OVERALL STATUS
        # ============================================================

        if shipment_count and completed_count == shipment_count:
            overall_status = "Completed"
        elif delayed_count:
            overall_status = "Delayed / Exception"
        elif in_transit_count:
            overall_status = "In Progress"
        elif pending_count == shipment_count:
            overall_status = "Pending"
        else:
            overall_status = "Partially Completed"

        # ============================================================
        # 8. BUILD THE OVERVIEW
        # ============================================================

        if is_bundle:
            overview = {
                "overview_type": "bundle",
                "bundle_id": (
                    bundle.id if bundle else shipment.bundlee_id
                ),
                "bundle_reference": (
                    bundle.bundle_reference
                    if bundle else shipment.bundle_reference
                ),
                "bundle_type": (
                    bundle.bundle_type
                    if bundle else shipment.bundle_type
                ),
                "bundle_status": (
                    bundle.status if bundle else None
                ),
                "overall_status": overall_status,

                "total_shipments": shipment_count,
                "planned_stages": (
                    bundle.stage_count if bundle else shipment_count
                ),
                "completed_shipments": completed_count,
                "in_transit_shipments": in_transit_count,
                "pending_shipments": pending_count,
                "delayed_shipments": delayed_count,
                "completion_percentage": completion_percentage,

                "route_sequence": route_sequence,

                "distance": {
                    "combined_distance": combined_distance,
                    "unit": "km",
                    "legs_with_distance_data": known_distance_count
                },

                "financials": {
                    "total_shipment_rates": total_shipment_rates,
                    "currency": None,
                    "calculation_note": (
                        "Sum of stored shipment rates; not necessarily "
                        "an invoice total when pricing bases differ."
                    )
                },

                "performance": performance_overview,
                "operational_exceptions": operational_exceptions,

                "data_completeness": {
                    "all_legs_have_distance": (
                        known_distance_count == shipment_count
                    ),
                    "legs_with_execution_metrics": (
                        performance_overview[
                            "legs_with_execution_metrics"
                        ]
                    )
                }
            }

        else:
            # Standalone shipments use their own shipment summary as
            # the overview placeholder. No artificial bundle is created.
            single = shipment_details[0]
            shipment_summary = single["shipment_summary"]
            performance = single["performance"]

            overview = {
                "overview_type": "single_shipment",
                **shipment_summary,
                "origin": (
                    route_sequence[0]["origin"] if route_sequence else None
                ),
                "destination": (
                    route_sequence[0]["destination"] if route_sequence else None
                ),
                "completion_percentage": (
                    100 if normalize_status(shipment.status)
                    in completed_statuses else 0
                ),
                "performance": performance,
                "operational_exceptions": operational_exceptions
            }

        # ============================================================
        # 9. RETURN A CONSISTENT RESPONSE
        # ============================================================

        bundle_metadata = None

        if is_bundle:
            bundle_metadata = {
                "id": bundle.id if bundle else shipment.bundlee_id,
                "bundle_reference": (
                    bundle.bundle_reference
                    if bundle else shipment.bundle_reference
                ),
                "bundle_type": (
                    bundle.bundle_type
                    if bundle else shipment.bundle_type
                ),
                "stage_count": (
                    bundle.stage_count if bundle else shipment_count
                ),
                "status": bundle.status if bundle else None,
                "created_at": bundle.created_at if bundle else None,
                "updated_at": bundle.updated_at if bundle else None
            }

        return {
            "group_type": "bundle" if is_bundle else "single_shipment",
            "overview": overview,
            "bundle": bundle_metadata,
            "shipments": shipment_details
        }

    except HTTPException:
        raise

    except Exception as e:
        print("=" * 100)
        print("ERROR GETTING CLIENT SHIPMENT")
        print(f"SHIPMENT ID: {id}")
        print(f"COMPANY ID: {company_id}")
        print(f"ERROR TYPE: {type(e).__name__}")
        print(f"ERROR: {str(e)}")
        print("=" * 100)

        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve shipment: {str(e)}"
        )

@router.get("/contract-lanes")
def get_client_contract_lanes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # ============================================================
    # 1. GET CURRENT USER COMPANY
    # ============================================================

    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:

        # ========================================================
        # 2. GET ALL CONTRACT LANES BELONGING TO THE CLIENT
        # ========================================================

        lanes = (
            db.query(Client_Lane)
            .filter(Client_Lane.client_id == company_id)
            .all()
        )

        if not lanes:
            return []

        response = []

        # ========================================================
        # 3. BUILD EACH CONTRACT LANE
        # ========================================================

        for lane in lanes:

            # ----------------------------------------------------
            # ORIGIN
            # ----------------------------------------------------

            origin = (
                db.query(Lane_Stop)
                .filter(
                    Lane_Stop.lane_id == lane.id,
                    Lane_Stop.stop_type == "Origin"
                )
                .first()
            )

            # ----------------------------------------------------
            # DESTINATION
            # ----------------------------------------------------

            destination = (
                db.query(Lane_Stop)
                .filter(
                    Lane_Stop.lane_id == lane.id,
                    Lane_Stop.stop_type == "Destination"
                )
                .first()
            )

            # ----------------------------------------------------
            # PRIMARY EQUIPMENT
            # ----------------------------------------------------

            equipment = (
                db.query(Lane_Vehicle_Config)
                .filter(
                    Lane_Vehicle_Config.lane_id == lane.id,
                    Lane_Vehicle_Config.configuration_type == "Primary"
                )
                .first()
            )

            # ----------------------------------------------------
            # PRIMARY CARRIER
            # ----------------------------------------------------

            carrier = None

            if lane.carrier_id:
                carrier = (
                    db.query(Carrier)
                    .filter(Carrier.id == lane.carrier_id)
                    .first()
                )

            # ----------------------------------------------------
            # EQUIPMENT DISPLAY NAME
            # ----------------------------------------------------

            equipment_name = None

            if equipment:

                if equipment.truck_type == "Rigid":
                    vehicle_name = equipment.truck_type
                else:
                    vehicle_name = equipment.trailer_type

                if vehicle_name and equipment.equipment_type:
                    equipment_name = (
                        f"{vehicle_name} {equipment.equipment_type}"
                    )
                elif vehicle_name:
                    equipment_name = vehicle_name
                elif equipment.equipment_type:
                    equipment_name = equipment.equipment_type

            # ----------------------------------------------------
            # MONTHLY VOLUME
            # ----------------------------------------------------
#
            # This prevents a long contract from displaying the
            # entire contract volume. Instead, it displays a
            # representative monthly volume.
            # ----------------------------------------------------

            volume_profiles = (
                db.query(Lane_Volume_Profile)
                .filter(
                    Lane_Volume_Profile.lane_id == lane.id
                )
                .order_by(
                    Lane_Volume_Profile.period_sequence.asc()
                )
                .all()
            )

            monthly_volume = None
            volume_entry_method = None

            if volume_profiles:

                # ------------------------------------------------
                # Get the volume entry method
                # ------------------------------------------------

                volume_entry_method = (
                    volume_profiles[0].volume_entry_method
                )

                # ------------------------------------------------
                # Get only profiles that actually contain volume
                # ------------------------------------------------

                valid_profiles = [
                    profile
                    for profile in volume_profiles
                    if profile.expected_loads is not None
                ]

                if valid_profiles:

                    # ------------------------------------------------
                    # Normalize the method for comparison
                    # ------------------------------------------------

                    method = str(
                        volume_entry_method
                    ).strip().lower()

                    # ------------------------------------------------
                    # Calculate average expected loads per profile
                    # ------------------------------------------------

                    average_expected_loads = (
                        sum(
                            profile.expected_loads
                            for profile in valid_profiles
                        )
                        / len(valid_profiles)
                    )

                    # ------------------------------------------------
                    # DAILY
                    # ------------------------------------------------
                    #
                    # Example:
                    #
                    # 28 daily entries
                    # Average = 5 loads/day
                    #
                    # Monthly volume = 5 × 28
                    #
                    # = 140 loads/month
                    # ------------------------------------------------

                    if method in [
                        "daily",
                        "day"
                    ]:

                        monthly_volume = round(
                            average_expected_loads * 28
                        )

                    # ------------------------------------------------
                    # WEEKLY
                    # ------------------------------------------------
                    #
                    # Example:
                    #
                    # 52 weekly entries
                    # Average = 10 loads/week
                    #
                    # Monthly volume = 10 × 4
                    #
                    # = 40 loads/month
                    # ------------------------------------------------

                    elif method in [
                        "weekly",
                        "week"
                    ]:

                        monthly_volume = round(
                            average_expected_loads * 4
                        )

                    # ------------------------------------------------
                    # MONTHLY
                    # ------------------------------------------------
                    #
                    # Example:
                    #
                    # 12 monthly entries
                    # Average = 145 loads/month
                    #
                    # Monthly volume = 145
                    # ------------------------------------------------

                    elif method in [
                        "monthly",
                        "month"
                    ]:

                        monthly_volume = round(
                            average_expected_loads
                        )

                    # ------------------------------------------------
                    # UNKNOWN METHOD
                    # ------------------------------------------------
                    #
                    # If another volume method exists, don't make
                    # assumptions. Return the average profile volume.
                    # ------------------------------------------------

                    else:

                        monthly_volume = round(
                            average_expected_loads
                        )
            # ----------------------------------------------------
            # RATE PER KM
            # ----------------------------------------------------

            rate_per_km = None

            if (
                lane.awarded_rate_per_shipment is not None
                and lane.distance
                and lane.distance > 0
            ):
                rate_per_km = round(
                    lane.awarded_rate_per_shipment / lane.distance,
                    2
                )

            # ----------------------------------------------------
            # BUILD RESPONSE OBJECT
            # ----------------------------------------------------

            response.append({

                "lane_code": lane.id,

                "origin": {
                    "origin": origin.city_province,
                    "facility": origin.facility_name,
                },

                "destination": {
                    "destination": destination.city_province,
                    "facility": destination.facility_name, 
                },

                "distance": lane.distance,

                "equipment": equipment_name,

                "monthly_volume": monthly_volume,

                "contracted_rate": lane.awarded_rate_per_shipment if lane.awarded_rate_per_shipment else None,

                "spot_benchmark": lane.procurement_target_rate,

                "rate_per_km": rate_per_km,

                "primary_carrier": (
                    carrier.legal_business_name
                    if carrier
                    else None
                ),

                "status": lane.contract_status
            })

        # ========================================================
        # 4. RETURN CONTRACT LANES
        # ========================================================

        return response

    except HTTPException:
        raise

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve contract lanes: {str(e)}"
        )



@router.get("/carrier-lane/{id}")
def get_client_contract_lane(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Return the complete awarded contract lane for a carrier.

    The carrier can only view a lane where:
        Client_Lane.id == id
        AND
        Client_Lane.carrier_id == logged-in carrier company_id
    """

    # ============================================================
    # 1. GET CURRENT CARRIER
    # ============================================================

    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company."
        )

    carrier = (
        db.query(Carrier)
        .filter(Carrier.id == company_id)
        .first()
    )

    if not carrier:
        raise HTTPException(
            status_code=404,
            detail="Carrier account not found."
        )

    # ============================================================
    # 2. GET SPECIFIC CONTRACT LANE
    # ============================================================

    lane = (
        db.query(Client_Lane)
        .filter(
            Client_Lane.id == id,
            Client_Lane.carrier_id == company_id
        )
        .first()
    )

    if not lane:
        raise HTTPException(
            status_code=404,
            detail="Contract lane not found or this lane has not been awarded to your carrier."
        )

    # ============================================================
    # 3. GET SHIPPER
    # ============================================================

    shipper = (
        db.query(Corporation)
        .filter(Corporation.id == lane.client_id)
        .first()
    )

    if not shipper:
        raise HTTPException(
            status_code=404,
            detail="Shipper associated with this contract lane was not found."
        )

    # ============================================================
    # 4. GET ALL LANE STOPS
    # ============================================================

    stops = (
        db.query(Lane_Stop)
        .filter(Lane_Stop.lane_id == lane.id)
        .order_by(Lane_Stop.stop_sequence.asc())
        .all()
    )

    # ============================================================
    # 5. SEPARATE ORIGIN / DESTINATION
    # ============================================================

    origin = next(
        (
            stop
            for stop in stops
            if stop.stop_type.lower() == "origin"
        ),
        None
    )

    destination = next(
        (
            stop
            for stop in stops
            if stop.stop_type.lower() == "destination"
        ),
        None
    )

    intermediate_stops = [
        stop
        for stop in stops
        if stop.stop_type.lower() not in ["origin", "destination"]
    ]

    # ============================================================
    # 6. VALIDATE ROUTE
    # ============================================================

    if not origin:
        raise HTTPException(
            status_code=500,
            detail="Contract lane does not contain an origin stop."
        )

    if not destination:
        raise HTTPException(
            status_code=500,
            detail="Contract lane does not contain a destination stop."
        )

    # ============================================================
    # 7. GET ALL EQUIPMENT CONFIGURATIONS
    # ============================================================

    equipments = (
        db.query(Lane_Vehicle_Config)
        .filter(
            Lane_Vehicle_Config.lane_id == lane.id
        )
        .all()
    )

    # ============================================================
    # 8. GET VOLUME PROFILE
    # ============================================================
    #
    # IMPORTANT:
    # Change Lane_Volume_Profile below if your actual model
    # has a different name.
    #
    # ============================================================

    volume_profiles = (
        db.query(Lane_Volume_Profile)
        .filter(
            Lane_Volume_Profile.lane_id == lane.id
        )
        .order_by(
            Lane_Volume_Profile.period_sequence.asc()
        )
        .all()
    )

    # ============================================================
    # 9. BUILD EQUIPMENT RESPONSE
    # ============================================================

    equipment_response = []

    for equipment in equipments:

        # For Rigid trucks:
        #     Rigid-Box
        #
        # For tractor/trailer combinations:
        #     Superlink-Tautliner
        #
        if equipment.truck_type == "Rigid":
            equipment_name = (
                f"{equipment.truck_type}-"
                f"{equipment.equipment_type}"
            )
        else:
            equipment_name = (
                f"{equipment.trailer_type}-"
                f"{equipment.equipment_type}"
            )

        equipment_response.append({
            "configuration_type": equipment.configuration_type,
            "name": equipment_name,
            "truck_type": equipment.truck_type,
            "equipment_type": equipment.equipment_type,
            "trailer_type": equipment.trailer_type,
            "trailer_length": equipment.trailer_length,
            "is_active": equipment.is_active,
        })

    # ============================================================
    # 10. BUILD VOLUME RESPONSE
    # ============================================================

    volume_response = []

    for volume in volume_profiles:

        volume_response.append({
            "volume_entry_method": volume.volume_entry_method,
            "period_sequence": volume.period_sequence,
            "period_label": volume.period_label,
            "period_start_date": volume.period_start_date,
            "period_end_date": volume.period_end_date,
            "day_of_week": volume.day_of_week,
            "expected_loads": volume.expected_loads,
        })

    # ============================================================
    # 11. CALCULATE RATE METRICS SAFELY
    # ============================================================

    awarded_rate = lane.awarded_rate_per_shipment

    rate_per_km = None

    if (
        awarded_rate is not None
        and lane.distance is not None
        and lane.distance > 0
    ):
        rate_per_km = round(
            float(awarded_rate) / float(lane.distance),
            2
        )

    rate_per_ton = None

    if (
        awarded_rate is not None
        and lane.average_shipment_weight is not None
        and lane.average_shipment_weight > 0
    ):
        weight_tons = (
            float(lane.average_shipment_weight) / 1000
        )

        rate_per_ton = round(
            float(awarded_rate) / weight_tons,
            2
        )

    # ============================================================
    # 12. BUILD INTERMEDIATE STOP RESPONSE
    # ============================================================

    intermediate_stop_response = []

    for stop in intermediate_stops:

        intermediate_stop_response.append({
            "stop_sequence": stop.stop_sequence,
            "stop_type": stop.stop_type,
            "city_province": stop.city_province,
            "facility_name": stop.facility_name,
            "address": getattr(
                stop,
                "address",
                None
            ),
            "complete_address": getattr(
                stop,
                "complete_address",
                None
            ),
            "country": getattr(
                stop,
                "country",
                None
            ),
            "region": getattr(
                stop,
                "region",
                None
            ),
        })

    # ============================================================
    # 13. BUILD FINAL RESPONSE
    # ============================================================

    return {

        # ========================================================
        # CONTRACT HEADER
        # ========================================================

        "contract": {

            "contract_lane_id": lane.id,

            "contract_reference": getattr(
                lane,
                "lane_reference",
                None
            ),

            "title": (
                f"{shipper.legal_business_name} "
                f"→ "
                f"{carrier.legal_business_name}"
            ),

            "shipper": {
                "id": shipper.id,
                "legal_business_name": shipper.legal_business_name,
            },

            "carrier": {
                "id": carrier.id,
                "legal_business_name": carrier.legal_business_name,
            },

            "status": lane.status,

            "contract_period": {
                "start_date": lane.contract_start_date,
                "end_date": lane.contract_end_date,
            },
        },

        # ========================================================
        # CONTRACT LANE INFORMATION
        # ========================================================

        "contract_lane_information": {

            "parent_lane_id": (
                lane.parent_lane_id
                if lane.parent_lane_id
                else None
            ),

            "lane_title": lane.lane_title,

            "lane_length_category": (
                lane.lane_length_category
            ),

            "scope_description": lane.scope_description,

            "business_unit": lane.business_unit,

            "cost_centre_project": (
                lane.cost_centre_project
            ),

            "lane_reference": lane.lane_reference,

            "scope_of_contract": {

                "service": {

                    "category": lane.lane_category,

                    "commodity": lane.commodity,

                    "equipment": equipment_response,

                    "operating_regions": {

                        "origin": {
                            "city_province": origin.city_province,
                            "facility_name": origin.facility_name,
                            "address": getattr(
                                origin,
                                "address",
                                None
                            ),
                        },

                        "stops": intermediate_stop_response,

                        "destination": {
                            "city_province": destination.city_province,
                            "facility_name": destination.facility_name,
                            "address": getattr(
                                destination,
                                "address",
                                None
                            ),
                        },
                    },
                },
            },
        },

        # ========================================================
        # LANE COMMERCIAL SUMMARY
        # ========================================================

        "lane": {

            "origin": origin.city_province,

            "destination": destination.city_province,

            "distance_km": lane.distance,

            "equipment": equipment_response,

            "expected_volume": volume_response,

            "awarded_rate_per_shipment": awarded_rate,

            "rate_per_km": rate_per_km,

            "rate_per_ton": rate_per_ton,
        },

        # ========================================================
        # PRICING & RATE SCHEDULE
        # ========================================================

        "pricing_and_rate_schedule": {

            "payment_terms": {

                "payment_terms": lane.payment_terms,

                "invoice_submission_frequency": (
                    lane.invoice_submission_frequency
                ),

                "invoice_submission_deadline": (
                    lane.invoice_submission_deadline
                ),

                "method": (
                    "Administered by/through "
                    "SADC FREIGHTLINK PTY LTD"
                ),
            },

            "rate_basis": lane.pricing_basis,

            "base_transport_rate": (
                lane.awarded_rate_per_shipment
            ),

            "rate_per_km": rate_per_km,

            "rate_per_ton": rate_per_ton,

            "pricing_basis": {

                "vat_inclusive": lane.vat_included,

                "fuel_surcharge": (
                    lane.rate_includes_fuel
                ),

                "border_charges": (
                    lane.rate_includes_border_charges
                ),

                "toll_charges": lane.toll_charges,

                "waiting_or_detention_time": (
                    lane.rate_includes_waiting_time
                ),

                "empty_return": (
                    lane.rate_includes_empty_return
                ),

                "loading_assistance_charges": (
                    lane.rate_includes_loading_assistance
                ),

                "offloading_assistance_charges": (
                    lane.rate_includes_offloading_assistance
                ),
            },

            "fuel_escalation": {

                "base_diesel_price": (
                    lane.base_diesel_price
                ),

                "treatment_type": (
                    lane.fuel_treatment_type
                ),

                "review_period": (
                    lane.fuel_review_period
                ),

                "adjustment_threshold": (
                    lane.fuel_component_percentage
                ),
            },
        },

        # ========================================================
        # SERVICE LEVEL REQUIREMENTS
        # ========================================================

        "service_levels_requirement": {

            "on_time_pickup_target": ">95%",

            "on_time_delivery_target": "95%",

            "pod_submission": {

                "short_haul": (
                    lane.pod_submission_local
                ),

                "long_haul": (
                    lane.pod_submission_long_haul
                ),

                "cross_border": (
                    lane.pod_submission_cross_border
                ),
            },
        },

        # ========================================================
        # CARRIER OBLIGATIONS
        # ========================================================

        "carrier_obligations": {

            "1": "Maintain valid operating documentation.",

            "2": (
                f"Maintain required insurance of "
                f"{lane.minimum_git_cover_amount} "
                f"GIT cover."
            ),

            "3": (
                f"Maintain required insurance of "
                f"{lane.minimum_liability_cover_amount} "
                f"Third Party Liability Cover."
            ),

            "4": (
                "Provide compliant vehicles specified "
                "by the contract requirements."
            ),

            "5": (
                "Maintain vehicle roadworthiness."
            ),

            "6": (
                "Provide licensed and documented drivers."
            ),

            "7": (
                "Provide vehicle tracking telematics access."
            ),

            "8": (
                "Comply with loading and unloading site rules."
            ),

            "9": (
                "Comply with safety requirements."
            ),

            "10": (
                "Maintain confidentiality."
            ),

            "11": (
                f"Notify {shipper.legal_business_name} "
                "and SADC FREIGHTLINK of incidents."
            ),

            "vehicle_driver_requirements": {

                "vehicle": {

                    "1": (
                        "Vehicles must be within the "
                        "specified required vehicle configurations."
                    ),

                    "2": (
                        f"Vehicle payload capacity must meet "
                        f"the specified minimum payload capacity "
                        f"of {lane.minimum_weight_bracket_kg} kg."
                    ),

                    "3": (
                        "Vehicles must have tracking telematics "
                        "and telematics access must be provided "
                        "through SADC FREIGHTLINK for the duration "
                        "of the contract."
                    ),

                    "4": (
                        "Vehicles must be roadworthy and the "
                        "roadworthiness certificate must be "
                        "made available."
                    ),
                },

                "driver": {

                    "1": (
                        "Valid driver's licence, PRDP and "
                        "required documentation for non-RSA citizens."
                    ),

                    "2": (
                        "Required PPE must be worn/provided."
                    ),
                },
            },
        },
    }
