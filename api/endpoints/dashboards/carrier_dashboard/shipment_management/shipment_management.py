from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.Exchange.auction import Exchange_FTL_Shipment_Bid, Exchange_POWER_Shipment_Bid, Exchange_FTL_Lane_Bid
from models.brokerage.assigned_lanes import Carrier_Lane
from models.brokerage.assigned_shipments import Carrier_Shipment
from models.vehicle import Vehicle, Trailer
from models.brokerage.finance import CarrierFinancialAccounts, Lane_Interim_Invoice, Load_Invoice
from models.brokerage.loadboards.exchange_loadboards import Exchange_Ftl_Load_Board, Exchange_Ftl_Lane_LoadBoard, Exchange_Power_Load_Board
from models.carrier import Carrier
from models.spot_bookings.ftl_shipment import Client_Shipment, Client_Shipment_Stop, Client_Shipment_Vehicle_Requirement
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
from services.brokerage.disputes import carrier_dispute_ftl_shipment
from utils.auth import get_current_user, verify_password
from utils.jwt_handler import create_access_token
from models.user import CarrierUser, Driver
from models.vehicle import ShipperTrailer, Trailer, Vehicle, Vehicle_Schedule
from schemas.auth import LoginRequest, LoginResponse
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Dispute_Create

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

#############################################################################################################
######################################Shipments Management###################################################
#############################################################################################################

@router.get("/carrier-shipments")
def get_all_carrier_shipments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")

    try:
        shipments = db.query(Carrier_Shipment).filter(
            Carrier_Shipment.carrier_id == company_id
        ).all()

        shipment_data = []

        for shipment in shipments:
            origin = db.query(Client_Shipment_Stop).filter(
                Client_Shipment_Stop.shipment_id == shipment.client_shipment_id,
                Client_Shipment_Stop.stop_type == "Origin"
            ).first()

            stops = db.query(Client_Shipment_Stop).filter(
                Client_Shipment_Stop.shipment_id == shipment.client_shipment_id,
                Client_Shipment_Stop.stop_type == "Intermediate"
            ).order_by(Client_Shipment_Stop.stop_sequence.asc()).all()

            destination = db.query(Client_Shipment_Stop).filter(
                Client_Shipment_Stop.shipment_id == shipment.client_shipment_id,
                Client_Shipment_Stop.stop_type == "Destination"
            ).first()

            vehicle = db.query(Vehicle).filter(
                Vehicle.id == shipment.vehicle_id
            ).first() if shipment.vehicle_id else None

            trailer = db.query(Trailer).filter(
                Trailer.id == vehicle.trailer_id
            ).first() if vehicle and vehicle.trailer_id else None

            driver = db.query(Driver).filter(
                Driver.id == vehicle.primary_driver_id
            ).first() if vehicle and vehicle.primary_driver_id else None

            shipment_data.append({
                "id": shipment.id,
                "shipment_reference": shipment.shipment_reference,
                "sub_shipment": {
                    "is_subshipment": shipment.is_subshipment,
                    "lane_id": shipment.carrier_lane_id
                },
                "status": shipment.status,
                "rate_and_basis": {
                    "rate": shipment.rate,
                    "rate_basis": shipment.pricing_basis
                },
                "origin": {
                    "city_province": origin.city_province if origin else None,
                    "facility_name": origin.facility_name if origin else None,
                    "pickup_date": shipment.pickup_date,
                    "pickup_start_time": origin.operating_start_time if origin else None
                },
                "transit": {
                    "distance": shipment.distance,
                    "no_of_stops": len(stops),
                    "via": [stop.city_province for stop in stops]
                },
                "destination": {
                    "city_province": destination.city_province if destination else None,
                    "facility_name": destination.facility_name if destination else None,
                    "eta_date": shipment.eta_date,
                    "eta_window": {
                        "start_time": destination.operating_start_time if destination else None,
                        "end_time": destination.operating_end_time if destination else None
                    }
                },
                "assigned_vehicle": {
                    "make_model": {
                        "make": vehicle.make if vehicle else None,
                        "model": vehicle.model if vehicle else None
                    },
                    "license_plate": vehicle.license_plate if vehicle else None,
                    "vehicle_type": vehicle.type if vehicle else None,
                    "equipment": vehicle.equipment_type if vehicle else None,
                    "trailer": {
                        "type": trailer.trailer_type if trailer else None,
                        "equipment": trailer.equipment_type if trailer else None,
                        "length": trailer.trailer_length if trailer else None
                    } if trailer else None
                },
                "assigned_driver": {
                    "id": driver.id if driver else None,
                    "first_name": driver.first_name if driver else None,
                    "last_name": driver.last_name if driver else None,
                    "phone_number": driver.phone_number if driver else None,
                    "prdp_status": "Valid" if driver else None
                },
                "cycle_and_trip_progress_status": shipment.trip_status
            })

        return shipment_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/carrier-shipment-summary/{id}")
def get_carrier_shipment_summary(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    shipment = db.query(Carrier_Shipment).filter(
        Carrier_Shipment.id == id
    ).first()

    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    origin = db.query(Client_Shipment_Stop).filter(
        Client_Shipment_Stop.shipment_id == shipment.client_shipment_id,
        Client_Shipment_Stop.stop_type == "Origin"
    ).first()

    stops = db.query(Client_Shipment_Stop).filter(
        Client_Shipment_Stop.shipment_id == shipment.client_shipment_id,
        Client_Shipment_Stop.stop_type == "Intermediate"
    ).order_by(Client_Shipment_Stop.stop_sequence.asc()).all()

    destination = db.query(Client_Shipment_Stop).filter(
        Client_Shipment_Stop.shipment_id == shipment.client_shipment_id,
        Client_Shipment_Stop.stop_type == "Destination"
    ).first()

    return {
        "id": shipment.id,
        "reference": shipment.shipment_reference,
        "tracking_description": getattr(shipment, "live_location", None),
        "corridor_information": {
            "origin": {
                "city_province": origin.city_province if origin else None,
                "country": origin.country if origin else None,
                "pickup_date": shipment.pickup_date,
                "start_time": origin.operating_start_time if origin else None
            },
            "trip_information": {
                "no_of_stops": len(stops),
                "distance": shipment.distance,
                "stops_information": [
                    {
                        "city_province": stop.city_province,
                        "notes": stop.notes
                    }
                    for stop in stops
                ],
                "trip_status": shipment.trip_status
            },
            "destination": {
                "city_province": destination.city_province if destination else None,
                "country": destination.country if destination else None,
                "eta_date": shipment.eta_date,
                "window": {
                    "start_time": destination.operating_start_time if destination else None,
                    "end_time": destination.operating_end_time if destination else None
                }
            }
        }
    }

@router.get("/carrier-shipment/{id}")
def carrier_get_carrier_shipment_details(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        shipment = db.query(Carrier_Shipment).filter_by(id=id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        origin = db.query(Client_Shipment_Stop).filter(Client_Shipment_Stop.shipment_id == shipment.client_shipment_id, Client_Shipment_Stop.stop_type == "Origin").first()
        stops = db.query(Client_Shipment_Stop).filter(Client_Shipment_Stop.shipment_id == shipment.client_shipment_id, Client_Shipment_Stop.stop_type == "Intermediate").first()
        destination = db.query(Client_Shipment_Stop).filter(Client_Shipment_Stop.shipment_id == shipment.client_shipment_id, Client_Shipment_Stop.stop_type == "Destination").first()
        equipments = db.query(Client_Shipment_Vehicle_Requirement.shipment_id == shipment.client_shipment_id).all()

        # Vehicle & Driver
        vehicle = db.query(Vehicle).filter_by(id=shipment.vehicle_id).first() if shipment.vehicle_id else None
        driver = db.query(Driver).filter_by(id=shipment.driver_id).first() if shipment.driver_id else None

        # Docs & Invoice
        documents = db.query(FTL_Shipment_Docs).filter_by(shipment_id=shipment.shipment_id).first()
        invoice = db.query(Load_Invoice).filter_by(id=shipment.invoice_id).first() if shipment.invoice_id else None

        return {
            "shipment_details": {
                "id": shipment.shipment_id,
                "is_subshipment": shipment.is_subshipment,
                "lane_id": shipment.lane_id if shipment.carrier_lane_id else None,
                "customer_reference_number": shipment.customer_reference_number,
                "type": shipment.type,
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
                "priority_level": shipment.priority_level,
                "pickup_date": shipment.pickup_date,
                "trip_route_information": {
                    "origin": origin.complete_address,
                    "stops": [{
                        "address": stop.complete_address,
                    } for stop in stops],
                    "destination": destination.complete_address,
                    "distance": shipment.distance,
                    "estimated_transit_time": shipment.estimated_transit_time,
                },
                "cargo_information": {
                    "commodity": shipment.commodity,
                    "weight": shipment.shipment_weight,
                    "packaging": {
                        "packaging_type": shipment.packaging_type,
                        "packaging_quanity": shipment.packaging_quanity,
                    },
                    "temp": {
                        "temperature_control": shipment.temperature_control,
                        "target_temperature_spec": shipment.target_temperature_spec,
                    },
                    "hazchem": {
                        "hazardous_materials": shipment.hazardous_materials,
                        "hazchem_classification": shipment.hazchem_classification,
                    },
                    "transit_compliance": {
                        "under_bond": shipment.under_bond,
                        "rib_required": shipment.rib_requirements,
                    },
                },
                "insurance_requirements": {
                    "git_requirement": shipment.minimum_git_cover_amount,
                    "third_party_liability_requirement": shipment.minimum_liability_cover_amount,
                    "encompassed_requirements": {
                        "all_risk_required": shipment.git_all_risk_required,
                        "first_loss_required": shipment.git_first_loss_required,
                        "driver_fidelity": shipment.git_driver_fidelity_required,
                    },
                },
                "truck_equipments": {
                    "accepted_configurations": [{
                        "configuration_type": e.configuration_type,
                        "truck_type": e.truck_type,
                        "equipment_type": e.equipment_type,
                        "trailer_type": e.trailer_type if e.trailer_type else None,
                        "trailer_legnth": e.trailer_legnth if e.trailer_length else None,
                        "minimum_weight_bracket": shipment.minimum_weight_bracket_kg,
                    } for e in equipments],
                    "complaince_requirements": {
                        "vehicle_tracking_required": shipment.vehicle_tracking_required,
                        "all_time_hour_control_room": shipment.all_time_hour_control_room,
                        "driver_mobile_phone": shipment.driver_mobile_phone,
                        "tarpaulin_compliance_required": shipment.tarpaulin_compliance_required,
                        "corner_plates_required": shipment.corner_plates_required,
                        "chock_blocks_required": shipment.chock_blocks_required,
                        "ratchets_belts_required": shipment.ratchets_belts_required,
                        "clean_compliant_equipment": shipment.clean_compliant_equipment,
                        "chep_pallet_management": shipment.pallet_management,
                        "other_equipment_requirements": shipment.other_equipment_requirements,
                    }
                },
                "financials": {
                    "rate": shipment.rate,
                    "vat_inclusive": shipment.vat_included,
                    "rate_basis": shipment.pricing_basis,
                    "payment_terms": shipment.payment_terms,
                    "payment_date": shipment.invoice_due_date if shipment.invoice_due_date else None,
                    "invoice_status": shipment.invoice_status if shipment.invoice_status else None,
                    "invoice_id": shipment.invoice_id if shipment.invoice_id else None,
                    "rate_inclusive": {
                        "rate_includes_tolls": shipment.rate_includes_tolls,
                        "rate_includes_border_charges": shipment.rate_includes_border_charges,
                        "rate_includes_waiting_time": shipment.rate_includes_waiting_time,
                        "rate_includes_loading_assistance": shipment.rate_includes_loading_assistance,
                        "rate_includes_offloading_assistance": shipment.rate_includes_offloading_assistance,
                        "rate_includes_fuel": shipment.rate_includes_fuel,
                        "rate_includes_driver": shipment.rate_includes_driver,
                        "rate_includes_maintenance": shipment.rate_includes_maintenance,
                        "rate_includes_insurance": shipment.rate_includes_insurance,
                    },
                },
            },
            "assignments": {
                "assigned_driver": {
                    "id": driver.id,
                    "first_name": driver.first_name,
                    "last_name": driver.last_name,
                    "nationality": driver.nationality,
                    "phone_number": driver.phone_number,
                    "identification": {
                        "id_number": driver.id_number,
                        "id_document": driver.id_document,
                    },
                    "license": {
                        "license_number": driver.license_number,
                        "license_expiry_date": driver.license_expiry_date,
                        "license_document": driver.license_document,
                    },
                    "prdp": {
                        "prdp_number": driver.prdp_number,
                        "prdp_expiry_date": driver.prdp_expiry_date,
                        "prdp_document": driver.prdp_document,
                    },
                    "passport": {
                        "passport_number": driver.passport_number,
                        "passport_document": driver.passport_document,
                    },
                },
                "assigned_vehicle": {
                    "id": vehicle.id,
                    "service_status": vehicle.service_status,
                    "is_verified": vehicle.is_verified,
                    "status": vehicle.status,
                    "make": vehicle.make,
                    "model": vehicle.model,
                    "year": vehicle.year,
                    "color": vehicle.color,
                    "tare_weight": vehicle.tare_weight,
                    "gvm_weight": vehicle.gvm_weight,
                    "payload_capacity": vehicle.payload_capacity,
                    "axle_config": vehicle.axle_configuration,
                    "equipment_type": vehicle.equipment_type if vehicle.equipment_type else None,
                    "compliance_docs": {
                        "registration_or_leasing_certificate": vehicle.vrc_or_leasing,
                        "license_disk": vehicle.vehicle_license_disk,
                        "roadworthy_certificate": vehicle.vehicle_road_worthy_certificate if vehicle.road_worthy_certificate else None,
                        "tracker_certificate": vehicle.vehicle_tracking_certificate,
                    },
                    "images": {
                        "front": vehicle.front_angle_image if vehicle.front_angle_image else None,
                        "rear": vehicle.rear_angle_image if vehicle.rear_angle_image else None,
                        "left_angle_image": vehicle.left_angle_image if vehicle.left_angle_image else None,
                        "right_angle_image": vehicle.right_angle_image if vehicle.right_angle_image else None,
                    },
                },
                "assigned_trailer": {
                    "id": trailer.id,
                    "is_verified": trailer.is_verified,
                    "status": trailer.status,
                    "make": trailer.make,
                    "model": trailer.model,
                    "year": trailer.year,
                    "color": trailer.color,
                    "tare_weight": trailer.tare_weight,
                    "gvm_weight": trailer.gvm_weight,
                    "payload_capacity": trailer.payload_capacity,
                    "equipment_type": trailer.equipment_type,
                    "trailer_type": trailer.trailer_type,
                    "trailer_length": trailer.trailer_length,
                    "license_plate": trailer.license_plate,
                    "license_expiry_date": trailer.license_expiry_date,
                    "compliance_docs": {
                        "registration_or_leasing_certification": trailer.vrc_leasing,
                        "license_disk": trailer.license_disk,
                        "road_worthy_certificate": trailer.road_worthy_certificate if trailer.road_worthy_certificate else None,
                    },
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/ftl-shipment/{id}")
def carrier_get_ftl_shipment_details(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        shipment = db.query(Assigned_Spot_Ftl_Shipments).filter_by(shipment_id=id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        # Facilities
        pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first() if shipment.pickup_facility_id else None
        delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first() if shipment.delivery_facility_id else None

        # Contacts
        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility and pickup_facility.contact_person else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility and delivery_facility.contact_person else None

        # Vehicle & Driver
        vehicle = db.query(Vehicle).filter_by(id=shipment.vehicle_id).first() if shipment.vehicle_id else None
        driver = db.query(Driver).filter_by(id=shipment.driver_id).first() if shipment.driver_id else None

        # Docs & Invoice
        documents = db.query(FTL_Shipment_Docs).filter_by(shipment_id=shipment.shipment_id).first()
        invoice = db.query(Load_Invoice).filter_by(id=shipment.invoice_id).first() if shipment.invoice_id else None

        return {
            "id": shipment.shipment_id,
            "is_subshipment": shipment.is_subshipment,
            "lane_id": shipment.lane_id,
            "type": shipment.type,
            "trip_type": shipment.trip_type,
            "load_type": shipment.load_type,
            "required_truck_type": shipment.required_truck_type,
            "equipment_type": shipment.equipment_type,
            "trailer_type": shipment.trailer_type,
            "trailer_length": shipment.trailer_length,
            "minimum_weight_bracket": shipment.minimum_weight_bracket,
            "shipment_weight": shipment.shipment_weight,
            "origin_address": shipment.origin_address_completed,
            "destination_address": shipment.destination_address_completed,
            "distance": shipment.distance,
            "estimated_transit_time": shipment.estimated_transit_time,
            "pickup_date": shipment.pickup_date,
            "priority_level": shipment.priority_level,
            "customer_reference_number": shipment.customer_reference_number,
            "commodity": shipment.commodity,
            "temperature_control": shipment.temperature_control,
            "minimum_git_cover_amount": shipment.minimum_git_cover_amount,
            "minimum_liability_cover_amount": shipment.minimum_liability_cover_amount,
            "packaging_quantity": shipment.packaging_quantity,
            "packaging_type": shipment.packaging_type,
            "hazardous_material": shipment.hazardous_materials,
            "pickup_number": shipment.pickup_number,
            "delivery_number": shipment.delivery_number,
            "pickup_notes": shipment.pickup_notes,
            "delivery_notes": shipment.delivery_notes,
            "payment_terms": shipment.payment_terms,

            "shipment_financials": {
                "rate": shipment.shipment_rate,
                "distance": shipment.distance,
                "rate_per_km": shipment.rate_per_km,
                "rate_per_ton": shipment.rate_per_ton,
                "payment_terms": shipment.payment_terms,
                "payment_date": shipment.invoice_due_date,
                "invoice_status": shipment.invoice_status,
                "invoice_id": shipment.invoice_id,
            },

            "documents": {
                "id": documents.id if documents else None,
                "commercial_invoice": documents.commercial_invoice if documents else None,
                "packaging_list": documents.packaging_list if documents else None,
                "customs_declaration_form": documents.customs_declaration_form if documents else None,
                "import_or_export_permits": documents.import_or_export_permits if documents else None,
                "certificate_of_origin": documents.certificate_of_origin if documents else None,
                "da5501orsad500": documents.da5501orsad500 if documents else None,
                "pod": shipment.pod_document,
            } if documents else None,

            "pickup_facility": {
                "location": shipment.origin_city_province,
                "address": pickup_facility.address if pickup_facility else None,
                "date": shipment.pickup_date,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}" if pickup_facility else None,
                "contact_name": f"{pickup_contact.first_name} {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "location": shipment.destination_city_province,
                "address": delivery_facility.address if delivery_facility else None,
                "date": shipment.eta_date,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}" if delivery_facility else None,
                "eta": shipment.eta_window,
                "contact_name": f"{delivery_contact.first_name} {delivery_contact.last_name}" if delivery_contact else None,
                "email": delivery_contact.email if delivery_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            "assigned_vehicle": {
                "id": vehicle.id,
                "verification_status": vehicle.is_verified,
                "status": vehicle.status,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "color": vehicle.color,
                "vin": vehicle.vin,
                "license_plate": vehicle.license_plate,
                "license_expiry_date": vehicle.license_expiry_date,
                "type": vehicle.type,
                "axle_configuration": vehicle.axle_configuration,
                "equipment_type": vehicle.equipment_type,
                "trailer_type": vehicle.trailer_type,
                "trailer_length": vehicle.trailer_length,
                "tare_weight": vehicle.tare_weight,
                "gvm_weight": vehicle.gvm_weight,
                "payload_capacity": vehicle.payload_capacity
            } if vehicle else None,

            "driver_information": {
                "id": driver.id,
                "availability_status": driver.service_status,
                "verification_status": driver.is_verified,
                "status": driver.status,
                "first_name": driver.first_name,
                "last_name": driver.last_name,
                "nationality": driver.nationality,
                "id_number": driver.id_number,
                "license_number": driver.license_number,
                "license_expiry_date": driver.license_expiry_date,
                "prdp_number": driver.prdp_number,
                "prdp_expiry_date": driver.prdp_expiry_date,
                "phone": driver.phone_number,
                "email": driver.email,
                "address": driver.address,
                "distance_driven": driver.total_distance_driven,
                "shipments_complete": driver.total_shipments_completed,
            } if driver else None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/carrier/ftl-shipment-dispute")
def carrier_dispute_ftl_shipment(
    dispute_data: FTL_Shipment_Dispute_Create,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    try:
        carrier_dispute_ftl_shipment(
            db,
            dispute_data,
            current_user=current_user,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/carrier/all-power-assigned-shipments", response_model=List[Assigned_Shipments_SummaryResponse])
def get_all_carrier_assigned_power_shipments_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    company_id = current_user.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="User does not belong to a company")   

    try:
        shipments_summary = []

        # --- 1. Assigned Spot FTL Shipments ---
        ftl_shipments = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.carrier_id == company_id,
            Assigned_Power_Shipments.status.notin_(["Assigned", "In-Progress", "Completed", "Delayed", "Cancelled"])
        ).all()

        for shipment in ftl_shipments:
            vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
            driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()
            facility = db.query(ShipmentFacility).filter(ShipmentFacility.id == shipment.pickup_facility_id).first()

            shipments_summary.append(Assigned_Shipments_SummaryResponse(
                id=shipment.id,
                type="FTL",
                status=shipment.status,
                shipment_rate=shipment.shipment_rate,
                is_subshipment=shipment.is_subshipment,
                lane_id=shipment.lane_id,
                origin_city_province=shipment.origin_city_province,
                pickup_date=shipment.pickup_date,
                pickup_start_time=facility.start_time,
                destination_city_province=shipment.destination_city_province,
                eta_date=shipment.eta_date,
                eta_window=shipment.eta_window,
                distance=shipment.distance,
                vehicle_id=vehicle.id if vehicle else None,
                vehicle_make=vehicle.make if vehicle else None,
                vehicle_model=vehicle.model if vehicle else None,
                driver_id=driver.id if driver else None,
                driver_first_name=driver.first_name if driver else None,
                driver_last_name=driver.last_name if driver else None,
                driver_phone_number=driver.phone_number if driver else None,
            ))

        return shipments_summary

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/carrier/power-shipment/id")
def carrier_get_power_shipment_details(
    shipment_data: GetAssigned_Spot_Ftl_ShipmentRequest,
    db: Session = Depends(get_db)
):
    try:
        shipment = db.query(Assigned_Power_Shipments).filter_by(shipment_id=shipment_data.id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        trailer = db.query(ShipperTrailer).filter_by(id=shipment.trailer_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        vehicle = db.query(Vehicle).filter_by(id=shipment.vehicle_id).first() if shipment.vehicle_id else None
        driver = db.query(Driver).filter_by(id=shipment.driver_id).first() if shipment.driver_id else None
        documents = db.query(FTL_Shipment_Docs).filter_by(shipment_id=shipment.shipment_id).all()
        invoice = db.query(Load_Invoice).filter_by(id=shipment.invoice_id).first()

        return {
            "id": shipment.shipment_id,
            "is_subshipment": shipment.is_subshipment,
            "lane_id": shipment.lane_id,
            "type": shipment.type,
            "trip_type": shipment.trip_type,
            "load_type": shipment.load_type,
            "required_truck_type": shipment.required_truck_type,
            "axle_configuration": shipment.axle_configuration,
            "minimum_weight_bracket": shipment.minimum_weight_bracket,
            "shipment_weight": shipment.shipment_weight,
            "origin_address": shipment.origin_address_completed,
            "destination_address": shipment.destination_address_completed,
            "pickup_date": shipment.pickup_date,
            "priority_level": shipment.priority_level,
            "customer_reference_number": shipment.customer_reference_number,
            "commodity": shipment.commodity,
            "temperature_control": shipment.temperature_control,
            "min_git_cover": shipment.minimum_git_cover_amount,
            "min_liability_cover": shipment.minimum_liability_cover_amount,
            "packaging_quantity": shipment.packaging_quantity,
            "packaging_type": shipment.packaging_type,
            "hazardous_material": shipment.hazardous_materials,
            "pickup_number": shipment.pickup_number,
            "delivery_number": shipment.delivery_number,
            "distance": shipment.distance,
            "estimated_transit_time": shipment.estimated_transit_time,
            "is_trailer_loaded": shipment.is_trailer_loaded,
            "pickup_notes": shipment.pickup_notes,
            "delivery_notes": shipment.delivery_notes,
            "payment_terms": shipment.payment_terms,

            "trailer": {
                "id": trailer.id,
                "is_verified": trailer.is_verified,
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.year,
                "color": trailer.color,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "vin": trailer.vin,
                "license_plate": trailer.license_plate,
                "tare_weight": trailer.tare_weight,
                "gvm_weight": trailer.gvm_weight,
                "payload_capacity": trailer.payload_capacity,
            },

            "pickup_facility": {
                "location": shipment.origin_city_province if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "date": shipment.pickup_date,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "location": shipment.destination_city_province if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "date": shipment.eta_date,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "eta": shipment.eta_window,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            "vehicle": {
                "id": vehicle.id,
                "make": vehicle.make,
                "model": vehicle.model,
                "year": vehicle.year,
                "license_plate": vehicle.license_plate,
                "color": vehicle.color,
                "vin": vehicle.vin,
                "axle_config": vehicle.axle_configuration,
                "license_expiry": vehicle.license_expiry_date,
                "vehicle_type": vehicle.type,
                "payload_capacity": vehicle.payload_capacity,
            } if vehicle else None,

            "driver": {
                "id": driver.id,
                "full_name": f"{driver.first_name} {driver.last_name}",
                "phone": driver.phone_number,
                "email": driver.email,
                "license_number": driver.license_number,
                "license_expiry": driver.license_expiry_date,
                "address": driver.address,
            } if driver else None,

            "documents": [{
                "id": doc.id,
                "commercial_invoice": doc.commercial_invoice,
                "packaging_list": doc.packaging_list,
                "customs_declaration_form": doc.customs_declaration_form,
                "import_or_export_permits": doc.import_or_export_permits,
                "certificate_of_origin": doc.certificate_of_origin,
                "da5501orsad500": doc.da5501orsad500,
                "pod": shipment.pod_document,
            } for doc in documents],

            "invoice": {
                "id": invoice.id,
                "status": invoice.status,
                "issued": invoice.billing_date,
                "due_date": invoice.due_date,
                "subtotal": invoice.base_amount,
                "total": invoice.due_amount,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/carrier/assigned-shipments-available-for-vehicle")
def get_assigned_shipments_available_for_vehicle_assignment(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if "company_id" not in current_user:
        raise HTTPException(status_code=400, detail="Missing company_id in current_user")
    company_id = current_user["company_id"]

    try:
        # 🚛 Assigned FTL shipments with no vehicle assigned
        ftl_shipments = db.query(Assigned_Spot_Ftl_Shipments).filter(
            Assigned_Spot_Ftl_Shipments.carrier_id == company_id,
            Assigned_Spot_Ftl_Shipments.status == "Assigned",
            Assigned_Spot_Ftl_Shipments.vehicle_id.is_(None)   # 🚨 No vehicle assigned
        ).all()

        # ⚡ Assigned Power shipments with no vehicle assigned
        power_shipments = db.query(Assigned_Power_Shipments).filter(
            Assigned_Power_Shipments.carrier_id == company_id,
            Assigned_Power_Shipments.status == "Assigned",
            Assigned_Power_Shipments.vehicle_id.is_(None)  # 🚨 No vehicle assigned
        ).all()

        # 📦 Format FTL
        ftl_results = [{
            "id": shipment.shipment_id,
            "type": "FTL",
            "origin": shipment.origin_city_province,
            "destination": shipment.destination_city_province,
            "pickup_date": shipment.pickup_date,
            "distance": shipment.distance,
            "required_truck_type": shipment.required_truck_type,
            "required_axle_configuration": None,
            "equipment_type": shipment.equipment_type,
            "trailer_type": shipment.trailer_type,
            "trailer_length": shipment.trailer_length
        } for shipment in ftl_shipments]

        # ⚡ Format Power
        power_results = [{
            "id": shipment.shipment_id,
            "type": "POWER",
            "origin": shipment.origin_city_province,
            "destination": shipment.destination_city_province,
            "pickup_date": shipment.pickup_date,
            "distance": shipment.distance,
            "required_truck_type": shipment.required_truck_type,
            "required_axle_configuration": shipment.axle_configuration,
            "equipment_type": None,
            "trailer_type": None,
            "trailer_length": None
        } for shipment in power_shipments]

        return {
            "assigned_shipments": ftl_results + power_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

