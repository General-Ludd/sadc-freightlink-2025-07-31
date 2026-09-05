from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, Lane_Slot_Ledger, CarrierFinancialAccounts, FinancialAccounts, Interim_Invoice, Load_Invoice
from models.brokerage.loadboard import Ftl_Load_Board
from models.shipper import Corporation
from models.user import Director, Driver
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
                    "origin": origin.pickup_address if origin else None,
                    "facility_name": origin.facility_name if origin else None,
                    "pickup_date": origin.pickup_date if origin else None,
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
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        # Shipment
        shipment = db.query(Client_Shipment).filter(Client_Shipment.id == id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        # Carrier
        carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first() if shipment.carrier_id else None

        # Carrier user
        carrier_user = None
        if carrier:
            carrier_user_id = getattr(carrier, "user_id", None)
            if carrier_user_id:
                carrier_user = db.query(Director).filter(Director.id == carrier_user_id).first()

        # Vehicle
        vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first() if shipment.vehicle_id else None

        # Trailer linked to vehicle
        trailer = None
        if vehicle and getattr(vehicle, "trailer_id", None):
            trailer = db.query(Trailer).filter(Trailer.id == vehicle.trailer_id).first()

        # Driver
        driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first() if shipment.driver_id else None

        # Stops
        stops = (
            db.query(Client_Shipment_Stop)
            .filter(Client_Shipment_Stop.shipment_id == shipment.id)
            .order_by(Client_Shipment_Stop.stop_sequence.asc())
            .all()
        )

        # Vehicle requirements
        configs = (
            db.query(Client_Shipment_Vehicle_Requirement)
            .filter(Client_Shipment_Vehicle_Requirement.shipment_id == shipment.id)
            .all()
        )

        # ============================================================
        # RESPONSE
        # ============================================================

        return {
            "financials": {
                "rate": shipment.rate,
                "vat_inclusive": shipment.vat_included if shipment.vat_included is not None else "Not Applicable",
                "payment_terms": shipment.payment_terms,
                "rate_inclusive_of": {
                    "rate_includes_fuel": shipment.rate_includes_fuel,
                    "rate_includes_driver": shipment.rate_includes_driver,
                    "rate_includes_maintenance": shipment.rate_includes_maintenance,
                    "rate_includes_insurance": shipment.rate_includes_insurance,
                    "tolls": shipment.rate_includes_tolls,
                    "border_charges": shipment.rate_includes_border_charges,
                    "empty_return": shipment.rate_includes_empty_return,
                    "detention_time": shipment.rate_includes_waiting_time,
                    "loading_assistance_charges": shipment.rate_includes_loading_assistance,
                    "offloading_assistance_charges": shipment.rate_includes_offloading_assistance
                },
                "invoice_id": shipment.invoice_id,
                "invoice_due_date": shipment.invoice_due_date,
                "rate_basis": shipment.pricing_basis
            },

            "shipment_details": {
                "id": shipment.id,
                "is_subshipment": shipment.is_subshipment,
                "auction_id": shipment.auction_id,
                "lane_id": getattr(shipment, "client_lane_id", None),
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
                "pickup_date": shipment.pickup_date,
                "priority_level": shipment.priority_level,
                "cargo_details": {
                    "customer_reference_number": shipment.customer_reference_number,
                    "commodity": shipment.commodity,
                    "shipment_weight": shipment.shipment_weight,
                    "packaging": {
                        "packaging_type": shipment.packaging_type,
                        "packaging_quantity": shipment.packaging_quantity
                    },
                    "temperature": {
                        "temperature_control": shipment.temperature_control,
                        "target_temperature_spec": shipment.target_temperature_spec
                    },
                    "hazchem": {
                        "hazardous_materials": shipment.hazardous_materials,
                        "hazchem_classification": shipment.hazchem_classification
                    },
                    "under_customs_bond": shipment.under_bond,
                    "requires_rib": shipment.rib_requirements
                }
            },

            "pod_submission_rules": {
                "local_haul_shipments": shipment.pod_submission_local,
                "long_haul_shipments": shipment.pod_submission_long_haul,
                "cross_border_haul_shipments": shipment.pod_submission_cross_border
            },

            "insurance_requirements": {
                "git_requirement": shipment.minimum_git_cover_amount,
                "liability_requirement": shipment.minimum_liability_cover_amount,
                "cover_spectrum": {
                    "git_all_risk": shipment.git_all_risk_required,
                    "first_loss": shipment.git_first_loss_required,
                    "driver_fidelity": shipment.git_driver_fidelity_required
                }
            },

            "equipments": [
                {
                    "configuration_type": config.configuration_type,
                    "truck_type": config.truck_type,
                    "equipment_type": config.equipment_type,
                    "trailer_type": config.trailer_type,
                    "trailer_length": config.trailer_length,
                    "minimum_weight_bracket": shipment.minimum_weight_bracket_kg,
                    "fleet_compliance_requirements": {
                        "vehicle_tracking_required": shipment.vehicle_tracking_required,
                        "control_room_monitoring": shipment.all_time_hour_control_room,
                        "driver_mobile_phone": shipment.driver_mobile_phone,
                        "clean_compliant_equipment": shipment.clean_compliant_equipment
                    },
                    "accessorial_rigging_gear": {
                        "chep_pallet_management": shipment.pallet_management,
                        "tarpaulin_required": shipment.tarpaulin_compliance_required,
                        "corner_plates": shipment.corner_plates_required,
                        "chock_blocks": shipment.chock_blocks_required,
                        "ratchets_belts": shipment.ratchets_belts_required,
                        "other_equipment_requirements": shipment.other_equipment_requirements
                    }
                }
                for config in configs
            ],

            "facilities": [
                {
                    "stop_sequence": stop.stop_sequence,
                    "stop_type": stop.stop_type,
                    "facility_name": stop.facility_name,
                    "complete_address": stop.complete_address,
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
                    "notes": stop.notes
                }
                for stop in stops
            ],

            # ========================================================
            # ASSIGNED CARRIER
            # ========================================================

            "assigned_carrier": {
                "carrier_information": {
                    "id": carrier.id,
                    "is_verified": carrier.is_verified,
                    "status": carrier.status,
                    "company_name": carrier.legal_business_name,
                    "country_of_incorporation": carrier.country_of_incorporation,
                    "business_registration_number": carrier.business_registration_number,
                    "address": carrier.business_address,
                    "insurance": {
                        "goods_in_transit": {
                            "insurer": carrier.name_of_git_cover_insurance_company,
                            "policy_number": carrier.git_insurance_policy_number,
                            "cover_amount": carrier.git_cover_amount
                        },
                        "third_party_liability": {
                            "insurer": carrier.name_of_liability_cover_insurance_company,
                            "policy_number": carrier.liability_insurance_policy_number,
                            "cover_amount": carrier.liability_insurance_cover_amount
                        }
                    },
                    "contact_person": {
                        "first_name": carrier_user.first_name if carrier_user else None,
                        "last_name": carrier_user.last_name if carrier_user else None,
                        "role": carrier.user.role if carrier_user else None,
                        "email": carrier_user.email if carrier_user else None,
                        "phone_number": carrier_user.phone_number if carrier_user else None
                    },
                    "carrier_docs": {
                        "registration_certificate": carrier.business_registration_certificate,
                        "proof_of_address": carrier.proof_of_address,
                        "brnc_certificate": carrier.brnc_certificate,
                        "git_certificate": carrier.git_insurance_certificate,
                        "liability_certificate": carrier.liability_insurance_certificate
                    }
                }
            } if carrier else None,

            # ========================================================
            # ASSIGNED DRIVER
            # ========================================================

            "assigned_driver": {
                "id": driver.id,
                "is_verified": driver.is_verified,
                "status": driver.status,
                "nationality": driver.nationality,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "phone_number": driver.phone_number,
                "compliance": {
                    "id_number": driver.id_number,
                    "passport_number": driver.passport_number,
                    "license": {
                        "license_number": driver.license_number,
                        "license_expiry_date": driver.license_expiry_date
                    },
                    "prdp": {
                        "prdp_number": driver.prdp_number,
                        "prdp_expiry_date": driver.prdp_expiry_date
                    },
                    "docs": {
                        "id_document": driver.id_document,
                        "license_document": driver.license_document,
                        "prdp_document": driver.prdp_document,
                        "passport_document": driver.passport_document
                    }
                }
            } if driver else None,

            # ========================================================
            # ASSIGNED VEHICLE + TRAILER
            # ========================================================

            "assigned_vehicle": {
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
                            "registration_or_leasing_certificate": vehicle.vrc_or_leasing,
                            "vehicle_license_disk": vehicle.vehicle_license_disk,
                            "roadworthy_certificate": vehicle.vehicle_road_worthy_certificate,
                            "tracking_certificate": vehicle.vehicle_tracking_certificate
                        }
                    }
                },

                "trailer_information": {
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
                            "registration_or_leasing_certificate": trailer.vrc_leasing,
                            "license_disk": trailer.license_disk,
                            "road_worthy_certificate": trailer.road_worthy_certificate
                        }
                    }
                } if trailer else None
            } if vehicle else None
        }

    except HTTPException:
        raise
    except Exception as e:
        print("=" * 100)
        print("ERROR GETTING CLIENT SHIPMENT")
        print(f"SHIPMENT ID: {id}")
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
