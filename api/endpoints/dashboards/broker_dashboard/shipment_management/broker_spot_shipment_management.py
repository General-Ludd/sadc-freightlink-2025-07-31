from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import SessionLocal
from models.brokerage.assigned_shipments import Assigned_Spot_Ftl_Shipments
from models.brokerage.finance import BrokerageLedger, CarrierFinancialAccounts, FinancialAccounts, Interim_Invoice, Load_Invoice, Brokers_Brokerage_Transactions
from models.brokerage.loadboard import Ftl_Load_Board
from models.carrier import Carrier
from models.spot_bookings.dedicated_lane_ftl_shipment import FTL_Lane
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT, FTL_Shipment_Docs
from models.spot_bookings.power_shipment import POWER_SHIPMENT, POWER_Shipment_Docs
from models.Exchange.ftl_shipment import FTL_SHIPMENT_EXCHANGE
from models.Exchange.power_shipment import POWER_SHIPMENT_EXCHANGE
from models.Exchange.dedicated_ftl_lane import FTL_Lane_Exchange
from models.spot_bookings.shipment_facility import ContactPerson, ShipmentFacility
from models.user import Driver
from models.vehicle import ShipperTrailer, Vehicle
from models.shipper import Consignor
from schemas.spot_bookings.dedicated_lanes_ftl_shipment import Ftl_Lanes_Summary_Response, Individual_FTL_Lane_Response, individual_shipment_or_lane_request
from schemas.spot_bookings.ftl_shipment import FTL_Shipment_Response, FTL_Shipments_Summary_Response
from schemas.spot_bookings.power_shipment import POWER_SHIPMENT_RESPONSE, Power_Shipments_Summary_Response
from utils.auth import get_current_user
from services.cancellations.spot_cancellations import cancel_spot_ftl_shipment


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/broker-access")
def broker_access_get_dashboard_home_data(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    # =========================
    # 1. GET SHIPMENTS
    # =========================
    ftl_shipments = db.query(FTL_SHIPMENT).filter(
        FTL_SHIPMENT.shipper_company_id == company_id
    ).all()
    ftl_shipment_ids = [shipment.id for shipment in ftl_shipments]

    power_shipments = db.query(POWER_SHIPMENT).filter(
        POWER_SHIPMENT.shipper_company_id == company_id
    ).all()
    power_shipment_ids = [shipment.id for shipment in power_shipments]

    # Brokerage transactions
    ftl_brokerage_transactions = []
    power_brokerage_transactions = []

    # Brokerage transactions
    if ftl_shipment_ids:
        ftl_brokerage_transactions = db.query(Brokers_Brokerage_Transactions).filter(
            Brokers_Brokerage_Transactions.shipment_id.in_(ftl_shipment_ids),
            Brokers_Brokerage_Transactions.type == "FTL"
        ).all()

    if power_shipment_ids:
        power_brokerage_transactions = db.query(Brokers_Brokerage_Transactions).filter(
            Brokers_Brokerage_Transactions.shipment_id.in_(power_shipment_ids),
            Brokers_Brokerage_Transactions.type == "POWER"
        ).all()

    ftl_brokerage_map = {bt.shipment_id: bt.per_shipment_consignor_billable for bt in ftl_brokerage_transactions}
    power_brokerage_map = {bt.shipment_id: bt.per_shipment_consignor_billable for bt in power_brokerage_transactions}

    loads = ftl_shipments + power_shipments

    def format_load(load):
        brokerage_map = ftl_brokerage_map if load.type == "FTL" else power_brokerage_map
        return {
            "id": load.id,
            "consignor_ref": load.consignor_id,
            "type": load.type,
            "status": {
                "load_status": load.shipment_status,
                "last_updated": load.updated_at,
            },
            "pickup": {
                "origin": load.origin_city_province,
                "appointment": f"{load.pickup_date}, {load.pickup_appointment}"
            },
            "dropoff": {
                "destination": load.destination_city_province,
                "eta_window": f"{load.eta_date}-{load.eta_window}"
            },
            "details": {
                "truck_type": getattr(load, "required_truck_type", None),
                "axle_configuration": getattr(load, "axle_configuration", None),
                "equipment_type": getattr(load, "equipment_type", None),
                "trailer_type": getattr(load, "trailer_type", None),
                "trailer_length": getattr(load, "trailer_length", None),
                "commodity": getattr(load, "commodity", None),
            },
            "distance": {
                "trip_distance": load.distance,
                "transit_time": load.estimated_transit_time,
            },
            "price": {
                "rate": load.quote,
                "consignor_billable": brokerage_map.get(load.id, None),
                "priority_level": load.priority_level
            }
        }

    grouped_loads = {
        "all_loads": [format_load(load) for load in loads],
        "booked": [format_load(load) for load in loads if load.shipment_status == "Booked"],
        "assigned": [format_load(load) for load in loads if load.shipment_status == "Assigned"],
        "in_progress": [format_load(load) for load in loads if load.shipment_status == "In-progress"],
        "completed": [format_load(load) for load in loads if load.shipment_status == "Completed"],
        "cancelled": [format_load(load) for load in loads if load.shipment_status == "Cancelled"],
    }

    # =========================
    # 2. GET LANES
    # =========================
    lanes = db.query(FTL_Lane).filter(FTL_Lane.shipper_company_id == company_id).all()

    def format_lane(lane):
        return {
            "id": lane.id,
            "type": "FTL",
            "status": lane.status,  # e.g., Active
            "per_shipment_rate": lane.qoute_per_shipment,
            "origin": lane.origin_city_province,
            "destination": lane.destination_city_province,
            "distance": lane.distance,
            "frequency": lane.recurrence_frequency,  # e.g., "3 times weekly"
            "completed_shipments": lane.progress,
            "total_shipments": lane.total_shipments,
        }

    formatted_lanes = [format_lane(lane) for lane in lanes]

    # =========================
    # 3. GET EXCHANGES
    # =========================
    ftl_exchanges = db.query(FTL_SHIPMENT_EXCHANGE).filter(
        FTL_SHIPMENT_EXCHANGE.shipper_company_id == company_id
    ).all()

    power_exchanges = db.query(POWER_SHIPMENT_EXCHANGE).filter(
        POWER_SHIPMENT_EXCHANGE.shipper_company_id == company_id
    ).all()

    shipment_exchanges = ftl_exchanges + power_exchanges

    lane_exchanges = db.query(FTL_Lane_Exchange).filter(
        FTL_Lane_Exchange.shipper_company_id == company_id
    ).all()

    def format_shipment_exchange(exchange):
        return {
            "id": exchange.id,
            "type": exchange.type,
            "status": exchange.auction_status,  # e.g., Open
            "origin": exchange.origin_city_province,
            "pickup_date": exchange.pickup_date,
            "destination": exchange.destination_city_province,
            "your_offer_rate": exchange.offer_price,
            "leading_bid": exchange.leading_bid_amount if exchange.leading_bid_amount else None,
            "bids_submitted": exchange.number_of_bids_submitted,
        }

    def format_lane_exchange(exchange):
        return {
            "id": exchange.id,
            "type": "FTL Lane",
            "status": exchange.auction_status,  # e.g., Open
            "bids": exchange.number_of_bids_submitted,
            "origin": exchange.origin_city_province,
            "destination": exchange.destination_city_province,
            "per_shipment_offer": exchange.per_shipment_offer_rate,
            "contract_offer": exchange.contract_offer_rate,
            "leading_bid_per_shipment": exchange.leading_per_shipment_bid_amount,
            "leading_bid_contract_total": exchange.leading_contract_bid_amount
        }

    formatted_shipment_exchanges = [format_shipment_exchange(ex) for ex in shipment_exchanges]
    formatted_lane_exchanges = [format_lane_exchange(ex) for ex in lane_exchanges]

    # =========================
    # FINAL RESPONSE
    # =========================
    return {
        "shipments": grouped_loads,
        "lanes": formatted_lanes,
        "exchanges": {
            "shipment_exchanges": formatted_shipment_exchanges,
            "lane_exchanges": formatted_lane_exchanges
        }
    }

@router.get("/broker-access/ftl-shipment/{id}")
def broker_access_get_individual_ftl_shipment(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        shipment = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        documents = db.query(FTL_Shipment_Docs).filter(FTL_Shipment_Docs.shipment_id == shipment.id).first()

        consignor = db.query(Consignor).filter(Consignor.id == shipment.consignor_id).first()
        broker_transaction = db.query(Brokers_Brokerage_Transactions).filter(
            Brokers_Brokerage_Transactions.shipment_id == shipment.id,
            Brokers_Brokerage_Transactions.type == shipment.type
        ).first()

        carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
        vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
        driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        return {
            "shipment_details": {
                "id": shipment.id,
                "invoice_id": shipment.invoice_id,
                "status": shipment.shipment_status,
                "trip_status": shipment.trip_status,
                "is_sub_shipment": shipment.is_subshipment,
                "lane_id": shipment.dedicated_lane_id,
                "shipment_type": shipment.type,
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
                "required_truck_type": shipment.required_truck_type,
                "required_equipment_type": shipment.equipment_type,
                "required_trailer_type": shipment.trailer_type,
                "required_trailer_length": shipment.trailer_length,
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "origin_address": shipment.complete_origin_address,
                "destination_address": shipment.complete_destination_address,
                "pickup_date": shipment.pickup_date,
                "priority_level": shipment.priority_level,
                "customer_referece_number": shipment.customer_reference_number,
                "shipment_weight": shipment.shipment_weight,
                "commodity": shipment.commodity,
                "temperature_control": shipment.temperature_control,
                "hazardous_materials": shipment.hazardous_materials,
                "minimum_git_cover_amount": shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": shipment.minimum_liability_cover_amount,
                "packaging_quantity": shipment.packaging_quantity,
                "packaging_type": shipment.packaging_type,
                "pickup_number": shipment.pickup_number,
                "delivery_number": shipment.delivery_number,
                "pickup_notes": shipment.pickup_notes,
                "delivery_notes": shipment.delivery_notes,
                "distance": shipment.distance,
                "estimated_transit_time": shipment.estimated_transit_time,
                "route_preview_embed": shipment.route_preview_embed,
            },

            "shipment_documents": {
                "commercial_invoice": documents.commercial_invoice if documents and documents.commercial_invoice else "N/A",
                "packaging_list": documents.packaging_list if documents and documents.packaging_list else "N/A",
                "customs_declaration_form": documents.customs_declaration_form if documents and documents.customs_declaration_form else "N/A",
                "import_or_export_permits": documents.import_or_export_permits if documents and documents.import_or_export_permits else "N/A",
                "certificate_of_origin": documents.certificate_of_origin if documents and documents.certificate_of_origin else "N/A",
                "da5501orsad500": documents.da5501orsad500 if documents and documents.da5501orsad500 else "N/A",
                "pod_document": shipment.pod_document if shipment.pod_document else "N/A",
            },

            "consignor_information": {
                "id": consignor.id if consignor else "N/A",
                "client_type": consignor.client_type if consignor else "N/A",
                "business_sector": consignor.business_sector if consignor else "N/A",
                "company_name": consignor.company_name if consignor else "N/A",
                "contact_person": consignor.contact_person_name if consignor else "N/A",
                "phone_number": consignor.phone_number if consignor else "N/A",
                "email": consignor.email if consignor else "N/A",
                "client_billable": broker_transaction.per_shipment_consignor_billable if broker_transaction else "N/A",
                "broker_profit": (
                    broker_transaction.per_shipment_consignor_billable - shipment.quote
                ) if broker_transaction else "N/A"
            },

            "carrier_information": {
                "id": carrier.id if carrier else "N/A",
                "carrier_name": f"SADC FREIGHTLINK Carrier-{carrier.id}" if carrier else "N/A",
                "carrier_git_cover": carrier.git_cover_amount if carrier else "N/A",
                "carrier_liability_cover_amount": carrier.liability_insurance_cover_amount if carrier else "N/A",

                "assigned_vehicle": {
                    "id": vehicle.id if vehicle else "N/A",
                    "make": vehicle.make if vehicle else "N/A",
                    "model": vehicle.model if vehicle else "N/A",
                    "year": vehicle.year if vehicle else "N/A",
                    "license_plate": vehicle.license_plate if vehicle else "N/A",
                    "vin": vehicle.vin if vehicle else "N/A",
                    "vehicle_type": vehicle.type if vehicle else "N/A",
                    "equipment_type": vehicle.equipment_type if vehicle else "N/A",
                    "trailer_type": vehicle.trailer_type if vehicle else "N/A",
                    "trailer_length": vehicle.trailer_length if vehicle else "N/A",
                    "tare_weight": vehicle.tare_weight if vehicle else "N/A",
                    "gvm_weight": vehicle.gvm_weight if vehicle else "N/A",
                    "payload_capacity": vehicle.payload_capacity if vehicle else "N/A",
                } if vehicle else None,

                "assigned_driver": {
                    "id": driver.id if driver else "N/A",
                    "first_name": driver.first_name if driver else "N/A",
                    "last_name": driver.last_name if driver else "N/A",
                    "license_number": driver.license_number if driver else "N/A",
                    "email": driver.email if driver else "N/A",
                    "phone_number": driver.phone_number if driver else "N/A",
                } if driver else None,

                "financial": {
                    "rate": shipment.quote,
                    "rate_per_kilometer": (shipment.quote / shipment.distance) if shipment.distance else None,
                    "rate_per_ton": (shipment.quote / shipment.minimum_weight_bracket) if shipment.minimum_weight_bracket else None,
                    "distance": shipment.distance,
                    "payment_terms": shipment.payment_terms,
                    "invoice_due_date": shipment.invoice_due_date,
                },

                "pickup_facility": {
                    "facility_name": pickup_facility.name if pickup_facility else None,
                    "address": pickup_facility.address if pickup_facility else None,
                    "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}" if pickup_facility else None,
                    "scheduling_type": pickup_facility.scheduling_type if pickup_facility else None,
                    "contact_name": f"{pickup_contact.first_name} {pickup_contact.last_name}" if pickup_contact else None,
                    "email": pickup_contact.email if pickup_contact else None,
                    "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                    "notes": pickup_facility.facility_notes if pickup_facility else None,
                } if pickup_facility else None,

                "delivery_facility": {
                    "facility_name": delivery_facility.name if delivery_facility else None,
                    "address": delivery_facility.address if delivery_facility else None,
                    "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}" if delivery_facility else None,
                    "scheduling_type": delivery_facility.scheduling_type if delivery_facility else None,
                    "contact_name": f"{delivery_contact.first_name} {delivery_contact.last_name}" if delivery_contact else None,
                    "email": delivery_contact.email if delivery_contact else None,
                    "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                    "notes": delivery_facility.facility_notes if delivery_facility else None,
                } if delivery_facility else None,
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/broker-access/power-shipment/{id}")
def broker_access_get_individual_power_shipment(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        shipment = db.query(POWER_SHIPMENT).filter(POWER_SHIPMENT.id == id).first()
        documents = db.query(FTL_Shipment_Docs).filter(FTL_Shipment_Docs.shipment_id == shipment.id).first()
        consignor = db.query(Consignor).filter(Consignor.id == shipment.consignor_id).first()
        broker_transaction = db.query(Brokers_Brokerage_Transactions).filter(Brokers_Brokerage_Transactions.shipment_id == shipment.id,
                                                                            Brokers_Brokerage_Transactions.type == shipment.type).first()
        trailer = db.query(ShipperTrailer).filter(ShipperTrailer.id == shipment.trailer_id).first()

        carrier = db.query(Carrier).filter(Carrier.id == shipment.carrier_id).first()
        vehicle = db.query(Vehicle).filter(Vehicle.id == shipment.vehicle_id).first()
        driver = db.query(Driver).filter(Driver.id == shipment.driver_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=shipment.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=shipment.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        return {
            "shipment_details": {
                "id": shipment.id,
                "invoice_id": shipment.invoice_id,
                "status": shipment.shipment_status,
                "trip_status": shipment.trip_status,
                "is_sub_shipment": shipment.is_subshipment,
                "lane_id": shipment.dedicated_lane_id,
                "shipment_type": shipment.type,
                "trip_type": shipment.trip_type,
                "load_type": shipment.load_type,
                "required_truck_type": shipment.required_truck_type,
                "axle_configuration": shipment.axle_configuration,
                "minimum_weight_bracket": shipment.minimum_weight_bracket,
                "origin_address": shipment.complete_origin_address,
                "destination_address": shipment.complete_destination_address,
                "pickup_date": shipment.pickup_date,
                "priority_level": shipment.priority_level,
                "customer_referece_number": shipment.customer_reference_number,
                "shipment_weight": shipment.shipment_weight,
                "commodity": shipment.commodity,
                "temperature_control": shipment.temperature_control,
                "hazardous_materials": shipment.hazardous_materials,
                "minimum_git_cover_amount": shipment.minimum_git_cover_amount,
                "minimum_liability_cover_amount": shipment.minimum_liability_cover_amount,
                "packaging_quantity": shipment.packaging_quantity,
                "packaging_type": shipment.packaging_type,
                "pickup_number": shipment.pickup_number,
                "delivery_number": shipment.delivery_number,
                "pickup_notes": shipment.pickup_notes,
                "delivery_notes": shipment.delivery_notes,
                "distance": shipment.distance,
                "estimated_transit_time": shipment.estimated_transit_time,
                "route_preview_embed": shipment.route_preview_embed,
            },

            "shipment_documents": {
                "commercial_invoice": documents.commercial_invoice if documents and documents.commercial_invoice else "N/A",
                "packaging_list": documents.packaging_list if documents and documents.packaging_list else "N/A",
                "customs_declaration_form": documents.customs_declaration_form if documents and documents.customs_declaration_form else "N/A",
                "import_or_export_permits": documents.import_or_export_permits if documents and documents.import_or_export_permits else "N/A",
                "certificate_of_origin": documents.certificate_of_origin if documents and documents.certificate_of_origin else "N/A",
                "da5501orsad500": documents.da5501orsad500 if documents and documents.da5501orsad500 else "N/A",
                "pod_document": shipment.pod_document if shipment.pod_document else "N/A",
            },

            "consignor_information": {
                "id": consignor.id,
                "client_type": consignor.client_type,
                "business_sector": consignor.business_sector,
                "company_name": consignor.company_name,
                "contact_person": consignor.contact_person_name,
                "phone_number": consignor.phone_number,
                "email": consignor.email,
                "client_billable": broker_transaction.consignor_billable if broker_transaction else "N/A",
                "broker_profit": (broker.transaction.consignor_billable - shipment.quote)
            },

            "shipper_trailer_information": {
                "id": trailer.id,
                "make": trailer.make,
                "model": trailer.model,
                "year": trailer.model,
                "color": trailer.color,
                "license_plate": trailer.license_plate,
                "equipment_type": trailer.equipment_type,
                "trailer_type": trailer.trailer_type,
                "trailer_length": trailer.trailer_length,
                "tare_weight": trailer.tare_weight,
                "gvm_weight": trailer.gvm_weight,
                "payload_capacity": trailer.payload_capacity,
            },

            "carrier_information": {
                "id": carrier.id if carrier else "N/A",
                "carrier_name": f"SADC FREIGHTLINK Carrier-{carrier.id}" if carrier else "N/A",
                "carrier_git_cover": carrier.git_cover_amount if carrier else "N/A",
                "carrier_liability_cover_amount": carrier.liability_insurance_cover_amount if carrier else "N/A",
    
                "assigned_vehicle": {
                    "id": vehicle.id if vehicle else "N/A",
                    "make": vehicle.make if vehicle else "N/A",
                    "model": vehicle.model if vehicle else "N/A",
                    "year": vehicle.color if vehicle else "N/A",
                    "license_plate": vehicle.license_plate if vehicle else "N/A",
                    "vin": vehicle.vin if vehicle else "N/A",
                    "vehicle_type": vehicle.type if vehicle else "N/A",
                    "axle_configuration": vehicle.axle_configuration,
                    "tare_weight": vehicle.tare_weight if vehicle else "N/A",
                    "gvm_weight": vehicle.gvm_weight if vehicle else "N/A",
                    "payload_capacity": vehicle.payload_capacity if vehicle else "N/A",
                },

                "assigned_driver": {
                    "id": driver.id if driver else "N/A",
                    "first_name": driver.first_name if driver else "N/A",
                    "last_name": driver.last_name if driver else "N/A",
                    "license_number": driver.license_number if driver else "N/A",
                    "email": driver.email if driver else "N/A",
                    "phone_number": driver.phone_number if driver else "N/A",
                },

                "financial": {
                    "price": shipment.quote,
                    "rate_per_kilometer": (shipment.quote/shipment.distance),
                    "distance": shipment.distance,
                    "payment_terms": shipment.payment_terms,
                    "invoice_due_date": shipment.invoice_due_date,
                },

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "scheduling_type": pickup_facility.scheduling_type,
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.name if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "scheduling_type": delivery_facility.scheduling_type,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

        }
    }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


router.get("/broker-access/ftl-contract-lane/{id}")
def broker_access_get_individual_ftl_contract_lane(
    id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    assert "company_id" in current_user, "Missing company_id in current_user"
    company_id = current_user.get("company_id")

    if not company_id:
        raise HTTPException(
            status_code=400,
            detail="User does not belong to a company"
        )

    try:
        lane = db.query(FTL_Lane).filter(FTL_Lane.id == id).first()
        invoices = db.query(Interim_Invoice).filter(Interim_Invoice.contract_id == lane.id,
                                               Interim_Invoice.contract_type == lane.type).all()
        sub_shipments = db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.dedicated_lane_id == lane.id).all()

        carrier = db.query(Carrier).filter(Carrier.id == lane.carrier_id).first()

        pickup_facility = db.query(ShipmentFacility).filter_by(id=lane.pickup_facility_id).first()
        delivery_facility = db.query(ShipmentFacility).filter_by(id=lane.delivery_facility_id).first()

        pickup_contact = db.query(ContactPerson).filter_by(id=pickup_facility.contact_person).first() if pickup_facility else None
        delivery_contact = db.query(ContactPerson).filter_by(id=delivery_facility.contact_person).first() if delivery_facility else None

        return {
            "shipment_details": {
                "id": lane.id,
                "status": lane.status,
                "type": lane.type,
                "trip_type": lane.trip_type,
                "load_type": lane.load_type,
                "required_truck_type": lane.required_truck_type,
                "equipment_type": lane.equipment_type,
                "trailer_type": lane.trailer_type,
                "trailer_length": lane.trailer_length,
                "minimum_weight_bracket": lane.minimum_weight_bracket,
                "priority_level": lane.priority_level,
                "average_shipment_weight": lane.average_shipment_weight,
                "commodity": lane.commodity,
                "temperature_control": lane.temperature_control,
                "hazardous_materials": lane.hazardous_materials,
                "minimum_git_cover_amount": lane.minimum_git_cover_amount,
                "minimum_liability_cover_amount": lane.minimum_liability_cover_amount,
                "customer_referece_number": lane.customer_reference_number,
                "packaging_type": lane.packaging_type,
                "packaging_quantity": lane.packaging_quantity,
                "pickup_number": lane.pickup_number,
                "delivery_number": lane.delivery_number,
                "distance": lane.distance,
                "estimated_transit_time": lane.estimated_transit_time,
                "origin_address": lane.complete_origin_address,
                "destination_address": lane.complete_destination_address,
                "pickup_notes": lane.pickup_notes,
                "delivery_notes": lane.delivery_notes,
                "start_date": lane.start_date,
                "end_date": lane.end_date,
                "route_preview_embed": lane.route_preview_embed,
            },

            "contract_information": {
                "recurrence_frequency": lane.recurrence_frequency,
                "recurrence_days": lane.recurrence_days,
                "skip_weekends": lane.skip_weekends,
                "shipments_per_interval": lane.shipments_per_interval,
                "total_shipments": lane.total_shipments,
                "per_shipment_rate": lane.qoute_per_shipment,
                "contract_rate": lane.contract_quote,
                "payment_terms": lane.payment_terms,
            },

            "payment_schedule": [{
                "invoice_id": invoice.id,
                "issue_date": invoice.billing_date,
                "due_date": invoice.due_date,
                "status": invoice.status,
                "amount": invoice.due_amount,
            } for invoice in invoices],

            "shipment_schedule": [{
                "id": sub_shipment.id,
                "origin": sub_shipment.origin_city_province,
                "destination": sub_shipment.destination_city_province,
                "pickup_date": sub_shipment.pickup_date,
                "status": sub_shipment.shipment_status,
                "rate": sub_shipment.quote,
                "invoice_status": sub_shipment.invoice_status,
            } for sub_shipment in sub_shipments],

            "pickup_facility": {
                "facility_name": pickup_facility.name if pickup_facility else None,
                "address": pickup_facility.address if pickup_facility else None,
                "time_window": f"{pickup_facility.start_time} - {pickup_facility.end_time}",
                "scheduling_type": pickup_facility.scheduling_type,
                "contact_name": f"{pickup_contact.first_name} - {pickup_contact.last_name}" if pickup_contact else None,
                "email": pickup_contact.email if pickup_contact else None,
                "contact_phone": pickup_contact.phone_number if pickup_contact else None,
                "notes": pickup_facility.facility_notes if pickup_facility else None,
            } if pickup_facility else None,

            "delivery_facility": {
                "facility_name": delivery_facility.address.name if delivery_facility else None,
                "address": delivery_facility.address if delivery_facility else None,
                "time_window": f"{delivery_facility.start_time} - {delivery_facility.end_time}",
                "scheduling_type": delivery_facility.scheduling_type,
                "contact_name": f"{delivery_contact.first_name} - {delivery_contact.last_name}" if pickup_contact else None,
                "email": delivery_contact.email if pickup_contact else None,
                "contact_phone": delivery_contact.phone_number if delivery_contact else None,
                "notes": delivery_facility.facility_notes if delivery_facility else None,
            } if delivery_facility else None,

            "carrier_information": {
                "id": carrier.id if carrier else "N/A",
                "carrier_name": f"SADC FREIGHTLINK Carrier-{carrier.id}" if carrier else "N/A",
                "carrier_git_cover": carrier.git_cover_amount if carrier else "N/A",
                "carrier_liability_cover_amount": carrier.liability_insurance_cover_amount if carrier else "N/A",
            }

            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))