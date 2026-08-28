from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, Lane_Slot_Ledger, CarrierFinancialAccounts, FinancialAccounts, Interim_Invoice, Load_Invoice
from models.brokerage.loadboard import Ftl_Load_Board
from models.shipper import Corporation
from models.user import Director
from models.carrier import Carrier
from models.spot_bookings.dedicated_lane_ftl_shipment import Client_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs, shipment_status_Update
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.user import Driver
from models.vehicle import ShipperTrailer, Vehicle
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

