from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from io import BytesIO
from datetime import date, datetime

from sqlalchemy.orm import Session
from db.database import SessionLocal
from utils.auth import get_current_user

# ============================================================
# YOUR EXISTING MODELS
# ============================================================
from models.Exchange.dedicated_ftl_lane import Lane_Tender_RFQ, Lane_Tender_RFQ_Stop, Lane_Tender_RFQ_Vehicle_Config, Lane_Tender_RFQ_Volume_Profile, Lane_Tender_RFQ_Accessorial, Turnaround_Window_Demurrage_Protocals, Carrier_Certification_Driver_Standards, Escort_Policy, Sla_incident_Reporting
from models.shipper import Corporation


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# ============================================================
# SAFE SERIALIZATION HELPERS
# ============================================================

def _json_value(value):
    """
    Converts SQLAlchemy/Python values into JSON/PDF-friendly values.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    return value


def _getattr(obj, field, default=None):
    """
    Safe attribute getter.
    """
    if obj is None:
        return default

    return getattr(obj, field, default)


def _clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Removes internal None values only where appropriate.
    Keeps explicit False and 0 values.
    """
    cleaned = {}

    for key, value in data.items():
        if isinstance(value, dict):
            cleaned[key] = _clean_dict(value)

        elif isinstance(value, list):
            cleaned[key] = [
                _clean_dict(item) if isinstance(item, dict)
                else _json_value(item)
                for item in value
            ]

        else:
            cleaned[key] = _json_value(value)

    return cleaned


# ============================================================
# RELATED TENDER RESOLUTION
# ============================================================

def get_related_tenders(
    db: Session,
    tender_id: int
) -> List[Lane_Tender_RFQ]:

    requested_tender = (
        db.query(Lane_Tender_RFQ)
        .filter(Lane_Tender_RFQ.id == tender_id)
        .first()
    )

    if not requested_tender:
        raise HTTPException(
            status_code=404,
            detail="Tender not found"
        )

    # --------------------------------------------------------
    # Find the master/root tender
    # --------------------------------------------------------

    root_tender = requested_tender

    visited = set()

    while getattr(root_tender, "parent_tender_id", None):

        if root_tender.id in visited:
            break

        visited.add(root_tender.id)

        parent = (
            db.query(Lane_Tender_RFQ)
            .filter(
                Lane_Tender_RFQ.id == tender_id
            )
            .first()
        )

        if not parent:
            break

        root_tender = parent

    # --------------------------------------------------------
    # Recursively collect master + all children
    # --------------------------------------------------------

    collected = []
    visited_ids = set()

    def collect_children(tender):

        if not tender:
            return

        if tender.id in visited_ids:
            return

        visited_ids.add(tender.id)
        collected.append(tender)

        children = (
            db.query(Lane_Tender_RFQ)
            .filter(
                Lane_Tender_RFQ.parent_tender_id == tender.id
            )
            .order_by(Lane_Tender_RFQ.id.asc())
            .all()
        )

        for child in children:
            collect_children(child)

    collect_children(root_tender)

    return collected


# ============================================================
# DEMURRAGE PROTOCOL
# ============================================================

def serialize_demurrage_protocol(
    db: Session,
    tender_id: int,
    stop_id: int
) -> Optional[Dict[str, Any]]:

    protocol = (
        db.query(Turnaround_Window_Demurrage_Protocals)
        .filter(
            Turnaround_Window_Demurrage_Protocals.tender_id == tender_id,
            Turnaround_Window_Demurrage_Protocals.stop_id == stop_id
        )
        .first()
    )

    if not protocol:
        return None

    return {
        "demurrage_conditions": _getattr(
            protocol,
            "demurrage_conditions"
        ),

        "loading_offloading_turnaround_hours": _getattr(
            protocol,
            "loading_offloading_turnaround_hours"
        ),

        "free_demurrage_hours": _getattr(
            protocol,
            "free_demurrage_hours"
        ),

        "demurrage_rate_per_hour": _getattr(
            protocol,
            "demurrage_rate_per_hour"
        ),

        "maximum_demurrage_incursion_hours": _getattr(
            protocol,
            "maximum_demurrage_incursion_hours"
        ),
    }


# ============================================================
# STOP SERIALIZER
# ============================================================

def serialize_tender_stop(
    db: Session,
    tender,
    stop
) -> Dict[str, Any]:

    return {
        "stop_id": stop.id,

        "stop_sequence": _getattr(
            stop,
            "stop_sequence"
        ),

        "facility_name": _getattr(
            stop,
            "facility_name"
        ),

        "address": _getattr(
            stop,
            "address"
        ),

        "complete_address": _getattr(
            stop,
            "complete_address"
        ),

        "city_province": _getattr(
            stop,
            "city_province"
        ),

        "country": _getattr(
            stop,
            "country"
        ),

        "region": _getattr(
            stop,
            "region"
        ),

        "latitude": _getattr(
            stop,
            "latitude"
        ),

        "longitude": _getattr(
            stop,
            "longitude"
        ),

        "turnaround_window_demurrage_protocol":
            serialize_demurrage_protocol(
                db,
                tender.id,
                stop.id
            )
    }


# ============================================================
# VOLUME PROFILE
# ============================================================

def serialize_volume_profiles(
    tender
) -> List[Dict[str, Any]]:

    # --------------------------------------------------------
    # Prefer SQLAlchemy relationship if it exists.
    #
    # Expected relationship name:
    # tender.volume_profiles
    #
    # If your relationship has a different name, change here.
    # --------------------------------------------------------

    profiles = getattr(
        tender,
        "volume_profiles",
        None
    )

    if not profiles:
        return []

    return [
        {
            "volume_entry_method": _getattr(
                profile,
                "volume_entry_method"
            ),

            "period_sequence": _getattr(
                profile,
                "period_sequence"
            ),

            "period_label": _getattr(
                profile,
                "period_label"
            ),

            "period_start_date": _json_value(
                _getattr(
                    profile,
                    "period_start_date"
                )
            ),

            "period_end_date": _json_value(
                _getattr(
                    profile,
                    "period_end_date"
                )
            ),

            "day_of_week": _getattr(
                profile,
                "day_of_week"
            ),

            "expected_loads": _getattr(
                profile,
                "expected_loads",
                0
            ),
        }
        for profile in profiles
    ]


# ============================================================
# VEHICLE CONFIGURATIONS
# ============================================================

def serialize_vehicle_configurations(
    db: Session,
    tender
) -> List[Dict[str, Any]]:

    configurations = (
        db.query(Lane_Tender_RFQ_Vehicle_Config)
        .filter(
            Lane_Tender_RFQ_Vehicle_Config.tender_id
            == tender.id
        )
        .all()
    )

    return [
        {
            "configuration_type": _getattr(
                config,
                "configuration_type"
            ),

            "truck_type": _getattr(
                config,
                "truck_type"
            ),

            "equipment_type": _getattr(
                config,
                "equipment_type"
            ),

            "trailer_type": _getattr(
                config,
                "trailer_type"
            ),

            "trailer_length": _getattr(
                config,
                "trailer_length"
            ),
        }
        for config in configurations
    ]


# ============================================================
# DRIVER / CERTIFICATION REQUIREMENTS
# ============================================================

def serialize_certifications(
    db: Session,
    tender_id: int
) -> List[Dict[str, Any]]:

    certifications = (
        db.query(Carrier_Certification_Driver_Standards)
        .filter(
            Carrier_Certification_Driver_Standards.tender_id
            == tender_id
        )
        .all()
    )

    return [
        {
            "certification_name": _getattr(
                item,
                "certification_name"
            ),

            "driver_qualification_security_directives":
                _getattr(
                    item,
                    "driver_qualification_security_directives"
                ),

            "is_required": _getattr(
                item,
                "is_required",
                True
            )
        }
        for item in certifications
    ]


# ============================================================
# ESCORT POLICY
# ============================================================

def serialize_escort_policy(
    db: Session,
    tender_id: int
):

    policy = (
        db.query(Escort_Policy)
        .filter(
            Escort_Policy.tender_id == tender_id
        )
        .first()
    )

    if not policy:
        return None

    return {
        "armed_escort_required": _getattr(
            policy,
            "armed_escort_required",
            False
        ),

        "escort_expense_responsible_party":
            _getattr(
                policy,
                "escort_expense_responsible_party"
            )
    }


# ============================================================
# SLA / INCIDENT REPORTING
# ============================================================

def serialize_sla_reporting(
    db: Session,
    tender_id: int
):

    sla = (
        db.query(Sla_incident_Reporting)
        .filter(
            Sla_incident_Reporting.tender_id
            == tender_id
        )
        .first()
    )

    if not sla:
        return None

    return {
        "incident_reporting_sla":
            _getattr(
                sla,
                "incident_reporting_sla"
            ),

        "service_level_agreement":
            _getattr(
                sla,
                "service_level_agreement"
            )
    }


# ============================================================
# CLIENT / COMPANY INFORMATION
# ============================================================

def serialize_client(
    db: Session,
    tender
) -> Dict[str, Any]:

    client = (
        db.query(Corporation)
        .filter(
            Corporation.id == tender.client_id
        )
        .first()
    )

    if not client:
        return {
            "id": tender.client_id,
            "legal_business_name": None,
            "company_profile": {}
        }

    # --------------------------------------------------------
    # These are intentionally safe/common company fields.
    # Add your exact Corporation fields here if you have them.
    # --------------------------------------------------------

    company_profile = {
        "legal_business_name": _getattr(
            client,
            "legal_business_name"
        ),

        "trading_name": _getattr(
            client,
            "trading_name"
        ),

        "registration_number": _getattr(
            client,
            "registration_number"
        ),

        "vat_number": _getattr(
            client,
            "vat_number"
        ),

        "company_type": _getattr(
            client,
            "company_type"
        ),

        "industry": _getattr(
            client,
            "industry"
        ),

        "company_description": _getattr(
            client,
            "company_description"
        ),

        "company_profile": _getattr(
            client,
            "company_profile"
        ),

        "company_logo": _getattr(
            client,
            "company_logo"
        ),
    }

    return {
        "id": client.id,
        "legal_business_name":
            _getattr(
                client,
                "legal_business_name"
            ),
        "company_profile": company_profile
    }


# ============================================================
# SINGLE FULL TENDER SERIALIZER
# ============================================================

def serialize_full_tender(
    db: Session,
    tender
) -> Dict[str, Any]:

    # --------------------------------------------------------
    # CLIENT
    # --------------------------------------------------------

    client = serialize_client(
        db,
        tender
    )

    # --------------------------------------------------------
    # STOPS
    # --------------------------------------------------------

    route_points = (
        db.query(Lane_Tender_RFQ_Stop)
        .filter(
            Lane_Tender_RFQ_Stop.tender_id == tender.id
        )
        .order_by(
            Lane_Tender_RFQ_Stop.stop_sequence.asc()
        )
        .all()
    )

    serialized_stops = [
        serialize_tender_stop(
            db,
            tender,
            stop
        )
        for stop in route_points
    ]

    origin = (
        serialized_stops[0]
        if serialized_stops
        else None
    )

    destination = (
        serialized_stops[-1]
        if serialized_stops
        else None
    )

    intermediate_stops = (
        serialized_stops[1:-1]
        if len(serialized_stops) > 2
        else []
    )

    # --------------------------------------------------------
    # VEHICLE CONFIGURATION
    # --------------------------------------------------------

    equipment = serialize_vehicle_configurations(
        db,
        tender
    )

    # --------------------------------------------------------
    # CONFIDENTIAL COMMERCIAL DATA IS DELIBERATELY OMITTED
    #
    # DO NOT RETURN:
    #
    # incumbent_transport_rate_per_shipment
    # incumbent_contract_rate
    # procurement_target_rate
    #
    # These remain procurement/admin-only.
    # --------------------------------------------------------

    return _clean_dict({

        # ====================================================
        # IDENTITY
        # ====================================================

        "id": tender.id,

        "parent_tender_id":
            _getattr(
                tender,
                "parent_id"
            ),

        "is_parent":
            _getattr(
                tender,
                "parent_id"
            ) is None,

        "tender_reference":
            _getattr(
                tender,
                "tender_reference",
                f"TDR-{tender.id}"
            ),

        "tender_title":
            _getattr(
                tender,
                "tender_title"
            ),

        "scope_description":
            _getattr(
                tender,
                "scope_description"
            ),

        # ====================================================
        # CLIENT
        # ====================================================

        "client": client,

        # ====================================================
        # STATUS / TIMELINE
        # ====================================================

        "status":
            _getattr(
                tender,
                "status"
            ),

        "published_at":
            _getattr(
                tender,
                "published_at"
            ),

        "priority_level":
            _getattr(
                tender,
                "priority_level"
            ),

        "tender_closing_date":
            _getattr(
                tender,
                "tender_closing_date"
            ),

        "questions_deadline":
            _getattr(
                tender,
                "questions_deadline"
            ),

        "contract": {
            "start_date":
                _getattr(
                    tender,
                    "contract_start_date"
                ),

            "end_date":
                _getattr(
                    tender,
                    "contract_end_date"
                ),

            "length_category":
                _getattr(
                    tender,
                    "tender_length_category"
                ),
        },

        # ====================================================
        # BUSINESS / PROCUREMENT
        # ====================================================

        "procurement": {
            "business_unit":
                _getattr(
                    tender,
                    "business_unit"
                ),

            "cost_centre_project_code":
                _getattr(
                    tender,
                    "cost_centre_project_code"
                ),

            "customer_reference":
                _getattr(
                    tender,
                    "customer_reference"
                ),

            "tender_category":
                _getattr(
                    tender,
                    "tender_category"
                ),
        },

        # ====================================================
        # ROUTING
        # ====================================================

        "routing": {
            "origin": origin,

            "intermediate_stops":
                intermediate_stops,

            "destination":
                destination,

            "total_stops":
                len(serialized_stops),

            "estimated_distance_km":
                _getattr(
                    tender,
                    "estimated_distance_km"
                ),

            "actual_distance_km":
                _getattr(
                    tender,
                    "actual_distance_km"
                ),

            "trip_type":
                _getattr(
                    tender,
                    "trip_type"
                ),

            "border_customs_responsibility":
                _getattr(
                    tender,
                    "border_customs_responsibility"
                ),

            "polyline":
                _getattr(
                    tender,
                    "polyline"
                ),
        },

        # ====================================================
        # CARGO
        # ====================================================

        "cargo": {
            "load_type":
                _getattr(
                    tender,
                    "load_type"
                ),

            "commodity":
                _getattr(
                    tender,
                    "commodity"
                ),

            "average_shipment_weight_kg":
                _getattr(
                    tender,
                    "average_shipment_weight_kg"
                ),

            "minimum_weight_bracket_kg":
                _getattr(
                    tender,
                    "minimum_weight_bracket_kg"
                ),

            "packaging_type":
                _getattr(
                    tender,
                    "packaging_type"
                ),

            "packaging_quantity":
                _getattr(
                    tender,
                    "packaging_quantity"
                ),

            "temperature_control":
                _getattr(
                    tender,
                    "temperature_control"
                ),

            "target_temperature_spec":
                _getattr(
                    tender,
                    "target_temperature_spec"
                ),

            "hazardous_materials":
                _getattr(
                    tender,
                    "hazardous_materials"
                ),

            "hazchem_classification":
                _getattr(
                    tender,
                    "hazchem_classification"
                ),

            "under_bond":
                _getattr(
                    tender,
                    "under_bond"
                ),

            "rib_requirements":
                _getattr(
                    tender,
                    "rib_requirements"
                ),
        },

        # ====================================================
        # VOLUME
        # ====================================================

        "volume": {
            "entry_method":
                _getattr(
                    tender,
                    "volume_entry_method"
                ),

            "commitment":
                _getattr(
                    tender,
                    "volume_commitment"
                ),

            "profiles":
                serialize_volume_profiles(
                    tender
                )
        },

        # ====================================================
        # EQUIPMENT
        # ====================================================

        "equipment": {
            "configurations":
                equipment,

            "vehicle_tracking_required":
                _getattr(
                    tender,
                    "vehicle_tracking_required"
                ),

            "clean_compliant_equipment":
                _getattr(
                    tender,
                    "clean_compliant_equipment"
                ),
        },

        # ====================================================
        # DRIVER / CARRIER REQUIREMENTS
        # ====================================================

        "carrier_requirements": {

            "certifications":
                serialize_certifications(
                    db,
                    tender.id
                ),

            "subcontracting_policy":
                _getattr(
                    tender,
                    "subcontracting_policy"
                ),

            "driver_mobile_phone":
                _getattr(
                    tender,
                    "driver_mobile_phone"
                ),

            "all_time_hour_control_room":
                _getattr(
                    tender,
                    "all_time_hour_control_room"
                ),
        },

        # ====================================================
        # ESCORT
        # ====================================================

        "escort_policy":
            serialize_escort_policy(
                db,
                tender.id
            ),

        # ====================================================
        # OPERATIONS
        # ====================================================

        "operational_requirements": {

            "pallet_management":
                _getattr(
                    tender,
                    "pallet_management"
                ),

            "tarpaulin_compliance_required":
                _getattr(
                    tender,
                    "tarpaulin_compliance_required"
                ),

            "corner_plates_required":
                _getattr(
                    tender,
                    "corner_plates_required"
                ),

            "chock_blocks_required":
                _getattr(
                    tender,
                    "chock_blocks_required"
                ),

            "ratchets_belts_required":
                _getattr(
                    tender,
                    "ratchets_belts_required"
                ),

            "other_equipment_requirements":
                _getattr(
                    tender,
                    "other_equipment_requirements"
                ),
        },

        # ====================================================
        # DOCUMENTATION / POD
        # ====================================================

        "documentation": {

            "pod_submission_local":
                _getattr(
                    tender,
                    "pod_submission_local"
                ),

            "pod_submission_long_haul":
                _getattr(
                    tender,
                    "pod_submission_long_haul"
                ),

            "pod_submission_cross_border":
                _getattr(
                    tender,
                    "pod_submission_cross_border"
                ),

            "delivery_documentation_sla":
                _getattr(
                    tender,
                    "delivery_documentation_sla"
                ),
        },

        # ====================================================
        # SLA
        # ====================================================

        "sla_reporting":
            serialize_sla_reporting(
                db,
                tender.id
            ),

        # ====================================================
        # RISK / INSURANCE
        # ====================================================

        "risk_and_insurance": {

            "minimum_git_cover_amount":
                _getattr(
                    tender,
                    "minimum_git_cover_amount"
                ),

            "minimum_liability_cover_amount":
                _getattr(
                    tender,
                    "minimum_liability_cover_amount"
                ),

            "git_all_risk_required":
                _getattr(
                    tender,
                    "git_all_risk_required"
                ),

            "git_first_loss_required":
                _getattr(
                    tender,
                    "git_first_loss_required"
                ),

            "git_driver_fidelity_required":
                _getattr(
                    tender,
                    "git_driver_fidelity_required"
                ),

            "claims_risk_policy":
                _getattr(
                    tender,
                    "claims_risk_policy"
                ),

            "claims_risk_requirements":
                _getattr(
                    tender,
                    "claims_risk_requirements"
                ),
        },

        # ====================================================
        # COMMERCIAL TERMS
        #
        # IMPORTANT:
        # Confidential benchmark rates are NOT returned.
        # ====================================================

        "commercial_terms": {

            "pricing_basis":
                _getattr(
                    tender,
                    "pricing_basis"
                ),

            "rate_direction":
                _getattr(
                    tender,
                    "rate_direction"
                ),

            "rate_includes": {

                "fuel":
                    _getattr(
                        tender,
                        "rate_includes_fuel"
                    ),

                "driver":
                    _getattr(
                        tender,
                        "rate_includes_driver"
                    ),

                "maintenance":
                    _getattr(
                        tender,
                        "rate_includes_maintenance"
                    ),

                "insurance":
                    _getattr(
                        tender,
                        "rate_includes_insurance"
                    ),

                "tolls":
                    _getattr(
                        tender,
                        "rate_includes_tolls"
                    ),

                "border_charges":
                    _getattr(
                        tender,
                        "rate_includes_border_charges"
                    ),

                "empty_return":
                    _getattr(
                        tender,
                        "rate_includes_empty_return"
                    ),

                "waiting_time":
                    _getattr(
                        tender,
                        "rate_includes_waiting_time"
                    ),

                "loading_assistance":
                    _getattr(
                        tender,
                        "rate_includes_loading_assistance"
                    ),

                "offloading_assistance":
                    _getattr(
                        tender,
                        "rate_includes_offloading_assistance"
                    ),
            },

            "fuel": {

                "treatment_type":
                    _getattr(
                        tender,
                        "fuel_treatment_type"
                    ),

                "review_period":
                    _getattr(
                        tender,
                        "fuel_review_period"
                    ),

                "vat_included":
                    _getattr(
                        tender,
                        "vat_included"
                    ),
            },

            "rate_validity":
                _getattr(
                    tender,
                    "rate_validity"
                ),
        },

        # ====================================================
        # EVALUATION
        # ====================================================

        "evaluation_criteria": {

            "price":
                _getattr(
                    tender,
                    "evaluation_price_enabled"
                ),

            "capacity":
                _getattr(
                    tender,
                    "evaluation_capacity_enabled"
                ),

            "service":
                _getattr(
                    tender,
                    "evaluation_service_enabled"
                ),

            "compliance":
                _getattr(
                    tender,
                    "evaluation_compliance_enabled"
                ),

            "flexibility":
                _getattr(
                    tender,
                    "evaluation_flexibility_enabled"
                ),
        },

        # ====================================================
        # ACCESSORIALS
        #
        # Uses SQLAlchemy relationship if configured.
        # ====================================================

        "accessorials": [
            {
                "charge_type":
                    _getattr(
                        item,
                        "charge_type"
                    ),

                "treatment":
                    _getattr(
                        item,
                        "treatment"
                    ),

                "threshold_value":
                    _getattr(
                        item,
                        "threshold_value"
                    ),

                "threshold_unit":
                    _getattr(
                        item,
                        "threshold_unit"
                    ),

                "notes":
                    _getattr(
                        item,
                        "notes"
                    ),
            }
            for item in (
                getattr(
                    tender,
                    "accessorials",
                    []
                ) or []
            )
        ],
    })


# ============================================================
# UNIFIED CORPORATE SUMMARY
# ============================================================

def build_unified_tender_summary(
    tenders: List[Dict[str, Any]]
) -> Dict[str, Any]:

    if not tenders:
        return {}

    # --------------------------------------------------------
    # Unique helper
    # --------------------------------------------------------

    def unique(values):
        result = []

        for value in values:
            if value is None:
                continue

            if isinstance(value, str) and not value.strip():
                continue

            if value not in result:
                result.append(value)

        return result

    # --------------------------------------------------------
    # Client
    # --------------------------------------------------------

    client = tenders[0].get("client", {})

    # --------------------------------------------------------
    # Titles
    # --------------------------------------------------------

    titles = unique([
        tender.get("tender_title")
        for tender in tenders
    ])

    categories = unique([
        tender.get("procurement", {}).get(
            "tender_category"
        )
        for tender in tenders
    ])

    lengths = unique([
        tender.get("contract", {}).get(
            "length_category"
        )
        for tender in tenders
    ])

    # --------------------------------------------------------
    # Contract period
    # --------------------------------------------------------

    start_dates = [
        tender.get("contract", {}).get("start_date")
        for tender in tenders
        if tender.get("contract", {}).get("start_date")
    ]

    end_dates = [
        tender.get("contract", {}).get("end_date")
        for tender in tenders
        if tender.get("contract", {}).get("end_date")
    ]

    contract_period = {
        "start_date": min(start_dates)
        if start_dates else None,

        "end_date": max(end_dates)
        if end_dates else None,
    }

    # --------------------------------------------------------
    # Commodities
    # --------------------------------------------------------

    commodities = unique([
        tender.get("cargo", {}).get("commodity")
        for tender in tenders
    ])

    load_types = unique([
        tender.get("cargo", {}).get("load_type")
        for tender in tenders
    ])

    # --------------------------------------------------------
    # Equipment
    # --------------------------------------------------------

    equipment = []

    for tender in tenders:

        configurations = (
            tender.get(
                "equipment",
                {}
            ).get(
                "configurations",
                []
            )
        )

        for config in configurations:

            normalized = (
                f"{config.get('equipment_type') or ''} "
                f"{config.get('trailer_type') or ''} "
                f"{config.get('trailer_length') or ''}"
            ).strip()

            if normalized and normalized not in equipment:
                equipment.append(normalized)

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    total_expected_loads = 0

    for tender in tenders:

        profiles = (
            tender.get(
                "volume",
                {}
            ).get(
                "profiles",
                []
            )
        )

        for profile in profiles:

            expected = profile.get(
                "expected_loads"
            )

            if isinstance(expected, (int, float)):
                total_expected_loads += expected

    # --------------------------------------------------------
    # Route summary
    # --------------------------------------------------------

    corridors = []

    for tender in tenders:

        routing = tender.get(
            "routing",
            {}
        )

        origin = routing.get(
            "origin"
        )

        destination = routing.get(
            "destination"
        )

        if origin and destination:

            origin_name = (
                origin.get("facility_name")
                or origin.get("city_province")
                or origin.get("country")
            )

            destination_name = (
                destination.get("facility_name")
                or destination.get("city_province")
                or destination.get("country")
            )

            corridor = (
                f"{origin_name} → {destination_name}"
            )

            if corridor not in corridors:
                corridors.append(corridor)

    # --------------------------------------------------------
    # Corporate description
    # --------------------------------------------------------

    client_name = (
        client.get("legal_business_name")
        or "the Client"
    )

    if total_expected_loads:
        volume_statement = (
            f"Approximately {total_expected_loads:,.0f} "
            f"transportation movements"
        )
    else:
        volume_statement = (
            "Transportation volumes as specified "
            "within the individual tender schedules"
        )

    corporate_summary = (
        f"SADC FREIGHTLINK, as the appointed freight "
        f"procurement and transportation partner acting "
        f"on behalf of {client_name}, is conducting this "
        f"Request for Quotation for the procurement of "
        f"transportation services across the specified "
        f"contract lanes. The procurement comprises "
        f"{len(tenders)} related tender "
        f"{'lane' if len(tenders) == 1 else 'lanes'}, "
        f"covering {volume_statement}. "
        f"Participating transport operators are invited "
        f"to submit commercially competitive and "
        f"operationally compliant quotations through "
        f"the SADC FREIGHTLINK platform."
    )

    return {
        "tender_count": len(tenders),

        "client": client,

        "titles": titles,

        "tender_categories": categories,

        "tender_length_categories": lengths,

        "contract_period": contract_period,

        "commodities": commodities,

        "load_types": load_types,

        "corridors": corridors,

        "primary_equipment": equipment,

        "total_combined_expected_loads":
            total_expected_loads,

        "volume_statement":
            volume_statement,

        "corporate_summary":
            corporate_summary,
    }


# ============================================================
# FULL TENDER INFORMATION ENDPOINT
# ============================================================

@router.get(
    "/tender-loadboard/{tender_id}/full-information"
)
def get_full_tender_information(
    tender_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):

    # --------------------------------------------------------
    # Get master + children
    # --------------------------------------------------------

    related_tenders = get_related_tenders(
        db,
        tender_id
    )

    # --------------------------------------------------------
    # Serialize each tender
    # --------------------------------------------------------

    serialized_tenders = [
        serialize_full_tender(
            db,
            tender
        )
        for tender in related_tenders
    ]

    # --------------------------------------------------------
    # Unified corporate summary
    # --------------------------------------------------------

    summary = build_unified_tender_summary(
        serialized_tenders
    )

    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return {
        "success": True,

        "requested_tender_id":
            tender_id,

        "tender_summary":
            summary,

        "tenders":
            serialized_tenders
    }