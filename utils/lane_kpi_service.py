from sqlalchemy.orm import Session
from statistics import mean, pstdev
from utils.shipment_kpi_service import get_shipment_kpis
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT

TRACKING_THRESHOLD = 10


def calculate_reliability_score(on_time_rate, tracking_rate, avg_delay):
    """
    Reliability score (0–100)
    Weighted composite:
    - 50% On-time delivery
    - 30% Tracking compliance
    - 20% Delay penalty
    """
    delay_score = max(0, 100 - avg_delay) if avg_delay else 100

    score = (
        (on_time_rate * 0.5) +
        (tracking_rate * 0.3) +
        ((delay_score / 100) * 0.2)
    ) * 100

    return round(score, 1)


def get_lane_kpis(db: Session, lane_id: int):

    shipments = db.query(FTL_SHIPMENT).filter(
        FTL_SHIPMENT.dedicated_lane_id == lane_id
    ).all()

    if not shipments:
        return None

    total = len(shipments)
    completed = len([s for s in shipments if s.shipment_status == "Completed"])

    # ------------------------
    # LANE KPI COLLECTION
    # ------------------------
    pickup_on_time_list = []
    pickup_delay_list = []
    delivery_on_time_list = []
    delivery_delay_list = []
    pickup_dwell_list = []
    delivery_dwell_list = []
    transit_time_list = []
    cycle_time_list = []
    tracking_update_list = []

    # ------------------------
    # CARRIER KPI MAP
    # ------------------------
    carrier_map = {}

    for s in shipments:

        kpi = get_shipment_kpis(db, s.id)
        if not kpi:
            continue

        k = kpi["kpis"]

        # ------------------------
        # LANE KPIs
        # ------------------------
        if k.get("pickup_on_time") is not None:
            pickup_on_time_list.append(1 if k["pickup_on_time"] else 0)

        if k.get("pickup_delay_minutes") is not None:
            pickup_delay_list.append(k["pickup_delay_minutes"])

        if k.get("delivery_on_time") is not None:
            delivery_on_time_list.append(1 if k["delivery_on_time"] else 0)

        if k.get("delivery_late_by_minutes") is not None:
            delivery_delay_list.append(k["delivery_late_by_minutes"])

        if k.get("pickup_dwell_minutes") is not None:
            pickup_dwell_list.append(k["pickup_dwell_minutes"])

        if k.get("delivery_dwell_minutes") is not None:
            delivery_dwell_list.append(k["delivery_dwell_minutes"])

        if k.get("transit_duration_minutes") is not None:
            transit_time_list.append(k["transit_duration_minutes"])

        if k.get("total_shipment_duration_minutes") is not None:
            cycle_time_list.append(k["total_shipment_duration_minutes"])

        tracking_update_list.append(k.get("total_status_updates", 0))

        # ------------------------
        # CARRIER PERFORMANCE
        # ------------------------
        if not s.carrier_id:
            continue

        if s.carrier_id not in carrier_map:
            carrier = db.query(Carrier).filter(Carrier.id == s.carrier_id).first()

            carrier_map[s.carrier_id] = {
                "carrier_id": s.carrier_id,
                "carrier_name": carrier.legal_business_name if carrier else "Unknown Carrier",
                "total_shipments": 0,
                "on_time_deliveries": 0,
                "delivery_delays": [],
                "tracking_hits": 0,
                "tracking_total": 0,
            }

        c = carrier_map[s.carrier_id]
        c["total_shipments"] += 1

        if k.get("delivery_on_time"):
            c["on_time_deliveries"] += 1
        elif k.get("delivery_late_by_minutes") is not None:
            c["delivery_delays"].append(k["delivery_late_by_minutes"])

        if k.get("total_status_updates") is not None:
            c["tracking_total"] += 1
            if k["total_status_updates"] >= TRACKING_THRESHOLD:
                c["tracking_hits"] += 1

    # ------------------------
    # BUILD CARRIER KPI OUTPUT
    # ------------------------
    carrier_kpis = []

    for c in carrier_map.values():
        on_time_rate = (
            c["on_time_deliveries"] / c["total_shipments"]
            if c["total_shipments"] else 0
        )

        avg_delay = mean(c["delivery_delays"]) if c["delivery_delays"] else 0

        tracking_rate = (
            c["tracking_hits"] / c["tracking_total"]
            if c["tracking_total"] else 0
        )

        reliability_score = calculate_reliability_score(
            on_time_rate,
            tracking_rate,
            avg_delay
        )

        carrier_kpis.append({
            "carrier_id": c["carrier_id"],
            "carrier_name": c["carrier_name"],
            "total_shipments": c["total_shipments"],
            "on_time_delivery_rate": round(on_time_rate * 100, 1),
            "average_delay_minutes": round(avg_delay, 1),
            "tracking_compliance_rate": round(tracking_rate * 100, 1),
            "reliability_score": reliability_score
        })

    # ------------------------
    # FINAL RESPONSE
    # ------------------------
    return {
        "lane_id": lane_id,
        "kpis": {
            "total_shipments": total,
            "completed_shipments": completed,
            "on_time_pickup_rate": mean(pickup_on_time_list) if pickup_on_time_list else None,
            "on_time_delivery_rate": mean(delivery_on_time_list) if delivery_on_time_list else None,
            "average_pickup_delay_minutes": mean(pickup_delay_list) if pickup_delay_list else None,
            "average_delivery_delay_minutes": mean(delivery_delay_list) if delivery_delay_list else None,
            "average_pickup_dwell_minutes": mean(pickup_dwell_list) if pickup_dwell_list else None,
            "average_delivery_dwell_minutes": mean(delivery_dwell_list) if delivery_dwell_list else None,
            "average_actual_transit_minutes": mean(transit_time_list) if transit_time_list else None,
            "transit_reliability_stddev": pstdev(transit_time_list) if len(transit_time_list) > 1 else 0,
            "average_tracking_updates": mean(tracking_update_list) if tracking_update_list else None,
            "tracking_compliance": sum(1 for t in tracking_update_list if t >= TRACKING_THRESHOLD) / total,
            "average_shipment_cycle_minutes": mean(cycle_time_list) if cycle_time_list else None,
            "carrier_performance": carrier_kpis
        }
    }