from sqlalchemy.orm import Session
from statistics import mean, pstdev
from utils.shipment_kpi_service import get_shipment_kpis
from models.shipment import FTL_SHIPMENT


def get_lane_kpis(db: Session, lane_id: int):
    shipments = db.query(FTL_SHIPMENT).filter(
        FTL_SHIPMENT.dedicated_lane_id == lane_id
    ).all()

    if not shipments:
        return None

    total = len(shipments)
    completed = len([s for s in shipments if s.shipment_status == "Completed"])

    # KPI storage arrays
    pickup_on_time_list = []
    delivery_delay_list = []
    pickup_delay_list = []
    pickup_dwell_list = []
    delivery_dwell_list = []
    transit_time_list = []
    tracking_update_list = []

    carrier_map = {}

    for s in shipments:
        kpi = get_shipment_kpis(db, s.id)
        if not kpi:
            continue

        k = kpi["kpis"]

        # Collect metrics if they exist
        if k["pickup_on_time"] is not None:
            pickup_on_time_list.append(1 if k["pickup_on_time"] else 0)

        if k["delivery_late_by_minutes"] is not None:
            delivery_delay_list.append(k["delivery_late_by_minutes"])

        if k["pickup_dwell_minutes"] is not None:
            pickup_dwell_list.append(k["pickup_dwell_minutes"])

        if k["delivery_dwell_minutes"] is not None:
            delivery_dwell_list.append(k["delivery_dwell_minutes"])

        if k["transit_duration_minutes"] is not None:
            transit_time_list.append(k["transit_duration_minutes"])

        tracking_update_list.append(k["total_status_updates"])

        # Carrier performance aggregation
        if s.carrier_id:
            if s.carrier_id not in carrier_map:
                carrier_map[s.carrier_id] = {"deliveries": 0, "on_time": 0}

            carrier_map[s.carrier_id]["deliveries"] += 1
            if k["delivery_late_by_minutes"] == 0:
                carrier_map[s.carrier_id]["on_time"] += 1

    # Build carrier performance result
    carrier_kpis = {
        f"carrier_{cid}": {
            "on_time_delivery": cdata["on_time"] / cdata["deliveries"]
        }
        for cid, cdata in carrier_map.items()
    }

    return {
        "lane_id": lane_id,
        "kpis": {
            "total_shipments": total,
            "completed_shipments": completed,
            "on_time_pickup_rate": mean(pickup_on_time_list) if pickup_on_time_list else None,
            "on_time_delivery_rate": sum(1 for d in delivery_delay_list if d == 0) / len(delivery_delay_list) if delivery_delay_list else None,
            "average_pickup_delay_minutes": mean(pickup_delay_list) if pickup_delay_list else None,
            "average_delivery_delay_minutes": mean(delivery_delay_list) if delivery_delay_list else None,
            "average_pickup_dwell_minutes": mean(pickup_dwell_list) if pickup_dwell_list else None,
            "average_delivery_dwell_minutes": mean(delivery_dwell_list) if delivery_dwell_list else None,
            "average_actual_transit_minutes": mean(transit_time_list) if transit_time_list else None,
            "transit_reliability_stddev": pstdev(transit_time_list) if len(transit_time_list) > 1 else 0,
            "average_tracking_updates": mean(tracking_update_list) if tracking_update_list else None,
            "tracking_compliance": sum(1 for t in tracking_update_list if t > 10) / total,  # threshold based
            "average_shipment_cycle_minutes": None,  # you can add if needed
            "carrier_performance": carrier_kpis
        }
    }
