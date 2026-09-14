from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid
from models.brokerage.assigned_lanes import Assigned_Ftl_Lanes
from models.brokerage.assigned_shipments import Assigned_Power_Shipments, Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import CarrierFinancialAccounts, Lane_Interim_Invoice, Load_Invoice
from models.brokerage.loadboard import Lane_Tender_Loadboard
from models.carrier import Carrier
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs
from models.spot_bookings.dedicated_lane_ftl_shipment import Lane_Stop, Lane_Vehicle_Config, Lane_Volume_Profile
from models.spot_bookings.power_shipment import POWER_SHIPMENT
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from schemas.brokerage.assigned_lanes import Dedicated_Ftl_Lane_Summary_Response
from schemas.brokerage.assigned_shipments import Assigned_Shipments_SummaryResponse, GetAssigned_Spot_Ftl_ShipmentRequest
from schemas.brokerage.finance import CarrierFinancialAccountResponse
from schemas.carrier import CarrierCompanyResponse
from schemas.user import CarrierUserResponse, DriverCreate, DriverResponse
from schemas.vehicle import Fleet_Trailer_Truck_response, TrailerCreate, TrailerResponse, Trailers_Summary_Response, Vehicle_Info, Vehicle_Schedule_Response, VehicleCreate, VehicleResponse, VehicleUpdate, Vehicles_Summary_Response
from services.carrier_service import fleet_create_driver
from services.carrier_dashboards import assign_trailer_to_vehicle
from services.vehicle_service import create_trailer, create_vehicle
from services.brokerage.disputes import carrier_dispute_ftl_lane
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import CarrierUser, Driver
from models.vehicle import ShipperTrailer, Trailer, Vehicle, Vehicle_Schedule
from schemas.auth import LoginRequest, LoginResponse
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import FTL_Lane_Dispute_Create

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#############################################################################################################
######################################Contact Lanes Management###############################################
#############################################################################################################
@router.get("/carrier-contracts")
def get_carrier_contracts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        lanes = (
            db.query(Carrier_Lane)
            .filter(Carrier_Lane.carrier_id == company_id)
            .all()
        )

        lane_data = []

        # =============================================================
        # SUMMARY VARIABLES
        # =============================================================

        active_contracts_count = 0
        active_trucks = 0
        active_guaranteed_volume = 0
        earned_revenue_to_date = 0

        active_volume_periods = []

        for lane in lanes:

            # =========================================================
            # CLIENT
            # =========================================================

            client = (
                db.query(Corporation)
                .filter(Corporation.id == lane.client_id)
                .first()
            )

            # =========================================================
            # ROUTE
            # =========================================================

            origin = (
                db.query(Lane_Stop)
                .filter(
                    Lane_Stop.lane_id == lane.id,
                    Lane_Stop.stop_type == "Origin"
                )
                .first()
            )

            stops = (
                db.query(Lane_Stop)
                .filter(
                    Lane_Stop.lane_id == lane.id,
                    Lane_Stop.stop_type == "Intermediate"
                )
                .all()
            )

            destination = (
                db.query(Lane_Stop)
                .filter(
                    Lane_Stop.lane_id == lane.id,
                    Lane_Stop.stop_type == "Destination"
                )
                .first()
            )

            # =========================================================
            # VOLUME ENTRIES
            # =========================================================

            volume_entries = (
                db.query(Lane_Volume_Profile)
                .filter(
                    Lane_Volume_Profile.lane_id == lane.client_lane_id
                )
                .order_by(
                    Lane_Volume_Profile.period_start_date.asc()
                )
                .all()
            )

            # The period label is common to the volume entries.
            interval_period = (
                volume_entries[0].period_label
                if volume_entries
                else None
            )

            # Only use entries that actually contain expected loads.
            expected_load_values = [
                entry.expected_loads
                for entry in volume_entries
                if entry.expected_loads is not None
            ]

            # Average expected loads for the interval.
            average_expected_loads = (
                sum(expected_load_values) / len(expected_load_values)
                if expected_load_values
                else 0
            )

            # =========================================================
            # EQUIPMENT
            # =========================================================

            equipment = (
                db.query(Lane_Vehicle_Config)
                .filter(
                    Lane_Vehicle_Config.lane_id == lane.client_lane_id,
                    Lane_Vehicle_Config.configuration_type == "Primary"
                )
                .first()
            )

            equipment_type = None

            if equipment:

                equipment_name = (
                    equipment.trailer_type
                    if equipment.trailer_type
                    else equipment.truck_type
                )

                if equipment_name:
                    equipment_type = equipment_name

                if equipment.equipment_type:
                    equipment_type = (
                        f"{equipment_type} "
                        f"{equipment.equipment_type}"
                    )

                if lane.minimum_weight_bracket_kg:
                    equipment_type = (
                        f"{equipment_type} "
                        f"({lane.minimum_weight_bracket_kg})"
                    )

            # =========================================================
            # LANE SHIPMENTS
            # =========================================================

            lane_shipments = (
                db.query(Carrier_Shipments)
                .filter(
                    Carrier_Shipments.lane_id == lane.id
                )
                .all()
            )

            # =========================================================
            # COMPLETED LOADS
            # =========================================================

            completed_loads = len(lane_shipments)

            number_of_volume_periods = len(volume_entries)

            total_committed_loads = (
                lane.slots_per_interval * number_of_volume_periods
                if lane.slots_per_interval
                else 0
            )

            loads_remaining = max(
                total_committed_loads - completed_loads,
                0
            )

            # =========================================================
            # EARNED REVENUE
            # =========================================================
            #
            # Each shipment already has its applicable rate.
            # Therefore:
            #
            # shipment 1 = R20,000
            # shipment 2 = R20,000
            # shipment 3 = R20,000
            #
            # earned revenue = R60,000
            #
            # If there are no shipments, this remains 0.
            # =========================================================

            lane_earned_revenue = sum(
                shipment.rate
                for shipment in lane_shipments
                if getattr(shipment, "rate", None) is not None
            )

            earned_revenue_to_date += lane_earned_revenue

            # =========================================================
            # PROJECTED CONTRACT VALUE
            # =========================================================

            average_shipment_weight_kg = (
                lane.average_shipment_weight_kg
                if lane.average_shipment_weight_kg is not None
                else 0
            )

            average_shipment_weight_tons = (
                average_shipment_weight_kg / 1000
            )

            if lane.rate is not None:

                if lane.pricing_basis == "Rate per Ton":

                    projected_total_contract_value = (
                        lane.rate
                        * average_shipment_weight_tons
                        * total_committed_loads
                    )

                else:

                    projected_total_contract_value = (
                        lane.rate
                        * total_committed_loads
                    )

            else:
                projected_total_contract_value = 0

            # =========================================================
            # PAYMENT DATE
            # =========================================================

            payment_date = None

            if (
                lane.payment_terms == "70%/30%"
                and volume_entries
            ):
                payment_date = volume_entries[0].period_start_date

            # =========================================================
            # VOLUME ENTRY DATA
            # =========================================================

            volume_entry_data = [
                {
                    "expected_loads": entry.expected_loads,
                    "period_start_date": entry.period_start_date,
                    "period_end_date": getattr(
                        entry,
                        "period_end_date",
                        None
                    ),
                }
                for entry in volume_entries
            ]

            # =========================================================
            # ACTIVE CONTRACT SUMMARY
            # =========================================================

            if lane.contract_status in ["Active", "In-Progress"]:

                active_contracts_count += 1

                active_trucks += (
                    lane.slots_per_interval
                    if lane.slots_per_interval
                    else 0
                )

                # Average expected volume for this contract's interval.
                active_guaranteed_volume += average_expected_loads

                if interval_period:
                    active_volume_periods.append(interval_period)

            # =========================================================
            # CONTRACT DATA
            # =========================================================

            lane_data.append({

                "id": lane.id,

                "category": lane.lane_category,

                "status": lane.contract_status,

                "contract_shipper_principal": {
                    "client": (
                        client.legal_business_name
                        if client
                        else None
                    ),
                    "status": (
                        client.is_verified
                        if client
                        else False
                    ),
                },

                "cargo_commodity": lane.commodity,

                "route": {

                    "origin": {
                        "city_province": (
                            origin.city_province
                            if origin
                            else None
                        ),
                        "facility_name": (
                            origin.facility_name
                            if origin
                            else None
                        ),
                    },

                    "stops": [
                        {
                            "city_province": stop.city_province,
                            "facility_name": stop.facility_name,
                        }
                        for stop in stops
                    ],

                    "destination": {
                        "city_province": (
                            destination.city_province
                            if destination
                            else None
                        ),
                        "facility_name": (
                            destination.facility_name
                            if destination
                            else None
                        ),
                    },
                },

                # =====================================================
                # VOLUME TYPE & COMMITMENT
                # =====================================================

                "volume_type_commitment": {

                    "volume_type": {

                        "period": interval_period,

                        "average_expected_loads": (
                            average_expected_loads
                        ),

                        "entries": volume_entry_data,
                    },

                    "commitment": (
                        lane.volume_commitment
                        if lane.volume_commitment
                        else None
                    ),
                },

                # =====================================================
                # COMMITTED SLOTS
                # =====================================================

                "committed_slots": {

                    "committed_slots_per_interval": (
                        lane.slots_per_interval
                    ),

                    "equipment_type": equipment_type,
                },

                # =====================================================
                # COMMITTED LOADS
                # =====================================================

                "committed_loads": {

                    "total_committed": (
                        total_committed_loads
                    ),

                    "per_interval": {

                        "loads": lane.slots_per_interval,

                        "interval_period": interval_period,
                    },
                },

                # =====================================================
                # CONTRACT TERM
                # =====================================================

                "contract_term": {

                    "term": lane.lane_length_category,

                    "period": {

                        "start_date": lane.contract_start_date,

                        "end_date": lane.contract_end_date,
                    },
                },

                # =====================================================
                # COMPLETED LOADS
                # =====================================================

                "completed_loads": {

                    "completed_shipments": completed_loads,

                    "total_lane_shipments": (
                        total_committed_loads
                    ),

                    "loads_remaining": loads_remaining,

                    "on_time_sla": 0.0,
                },

                # =====================================================
                # CONTRACT RATE DETAILS
                # =====================================================

                "contract_rate_details": {

                    "rate": lane.rate,

                    "pricing_basis": lane.pricing_basis,

                    "average_shipment_weight_kg": (
                        average_shipment_weight_kg
                    ),

                    "average_shipment_weight_tons": (
                        average_shipment_weight_tons
                    ),

                    "earned_to_date": lane_earned_revenue,

                    "projected_total_contract_value": (
                        projected_total_contract_value
                    ),

                    "payment_terms": lane.payment_terms,

                    "payment_date": payment_date,
                },
            })

        # =============================================================
        # SUMMARY PERIOD
        # =============================================================
        #
        # If all active contracts use the same period, return it.
        # If there are different periods, return "Mixed".
        # =============================================================

        unique_active_periods = set(active_volume_periods)

        if len(unique_active_periods) == 1:
            summary_period = active_volume_periods[0]
        elif len(unique_active_periods) > 1:
            summary_period = "Mixed"
        else:
            summary_period = None

        # =============================================================
        # FINAL RESPONSE
        # =============================================================

        return {
            "summary": {
                "active_contracts": active_contracts_count,
                "monthly_guaranteed_volume": {
                    "loads": active_guaranteed_volume,
                    "period": summary_period,
                },
                "total_contracts_value": sum(
                    contract["contract_rate_details"][
                        "projected_total_contract_value"
                    ]
                    for contract in lane_data
                    if contract["status"] in [
                        "Active",
                        "In-Progress"
                    ]
                ),
                "earned_revenue_to_date": (
                    earned_revenue_to_date
                ),
                "average_on_time_sla": 0.0,
            },
            "contracts": lane_data,

        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve carrier contracts: {str(e)}"
        )

@router.get("/carrier/all-ftl-assigned-lanes", response_model=List[Dedicated_Ftl_Lane_Summary_Response])
def get_all_carrier_assigned_ftl_lanes_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")   

    try:
        shipments_summary = []

        # --- 1. Assigned Spot FTL Shipments ---
        lanes = db.query(Assigned_Ftl_Lanes).filter(
            Assigned_Ftl_Lanes.carrier_id == company_id,
        ).all()

        for lane in lanes:

            shipments_summary.append(Dedicated_Ftl_Lane_Summary_Response(
                id=lane.id,
                lane_id=lane.lane_id,
                type=lane.type,
                status=lane.status,
                contract_rate=lane.contract_rate,
                origin_city_province=lane.origin_city_province,
                destination_city_province=lane.destination_city_province,
                distance=lane.distance,
                recurrence_frequency=lane.recurrence_frequency,
                shipments_per_interval=lane.shipments_per_interval,
                start_date=lane.start_date,
                end_date=lane.end_date,
                total_shipments_completed=lane.total_shipment_completed
            ))

        return shipments_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/carrier/ftl-lane/{id}")
def carrier_get_ftl_lane_details(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        lane = db.query(Assigned_Ftl_Lanes).filter_by(lane_id=id).first()
        if not lane:
            raise HTTPException(status_code=404, detail="Contract lane not found")

        pickup_facility = db.query(ShipmentFacility).filter_by(id=lane.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=lane.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        lane_sub_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter_by(lane_id=lane.lane_id).all()
        lane_interim_invoices = db.query(Lane_Interim_Invoice).filter_by(contract_id=lane.lane_id).all()

        return {
            "contract_lane_details": {
                "id": lane.lane_id,
                "type": lane.type,
                "trip_type": lane.trip_type,
                "load_type": lane.load_type,
                "required_truck_type": lane.required_truck_type,
                "equipment_type": lane.equipment_type,
                "trailer_type": lane.trailer_type,
                "trailer_length": lane.trailer_length,
                "minimum_weight_bracket": lane.minimum_weight_bracket,
                "average_shipment_weight": lane.average_shipment_weight,
                "origin_address": lane.origin_address,
                "destination_address": lane.destination_address,
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "priority_level": lane.priority_level,
                "customer_reference_number": lane.customer_reference_number,
                "commodity": lane.commodity,
                "temperature_control": lane.temperature_control,
                "min_git_cover": lane.minimum_git_cover_amount,
                "min_liability_cover": lane.minimum_liability_cover_amount,
                "packaging_quantity": lane.packaging_quantity,
                "packaging_type": lane.packaging_type,
                "hazardous_material": lane.hazardous_materials,
                "pickup_number": lane.pickup_number,
                "delivery_number": lane.delivery_number,
                "distance": lane.distance,
                "estimated_transit_time": lane.estimated_transit_time,
                "pickup_notes": lane.pickup_notes,
                "delivery_notes": lane.delivery_notes,
                "route_preview_embed": lane.route_preview_embed,
            },

            "contract_details": {
                "recurrence_frequency": lane.recurrence_frequency,
                "recurrence_days": lane.recurrence_days,
                "shipments_per_interval": lane.shipments_per_interval,
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "total_shipments": lane.total_shipments,
                "contract_rate": lane.contract_rate,
                "per_shipment_rate": lane.rate_per_shipment,
                "payment_terms": lane.payment_terms,
                "lane_progress": lane.total_shipment_completed,
            },

            "payment_schedule": [{
                "due_date": lane_interim_invoice.due_date,
                "amount": lane_interim_invoice.due_amount,
                "status": lane_interim_invoice.status,
            } for lane_interim_invoice in lane_interim_invoices],

            "lane_sub_shipments": [{
                "shipment_id": lane_sub_shipment.shipment_id,
                "date": lane_sub_shipment.pickup_date,
                "route": f"{lane_sub_shipment.origin_city_province} to {lane_sub_shipment.destination_city_province}",
                "status": lane_sub_shipment.status,
                "vehicle": lane_sub_shipment.vehicle_id
            } for lane_sub_shipment in lane_sub_shipments],

            "pickup_facility": {
                "location": lane.origin_city_province if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "location": lane.destination_city_province if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/carrier/ftl-lane-dispute")
def carrier_dispute_ftl_lane(
    dispute_data: FTL_Lane_Dispute_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        carrier_dispute_ftl_lane(
            db,
            dispute_data,
            current_user=current_user,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
