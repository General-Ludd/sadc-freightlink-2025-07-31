from sqlalchemy.orm import Session
from models.vehicle import Vehicle, Trailer

def calculate_payload_capacity(truck: Vehicle, trailer: Trailer = None) -> int:
    """
    Calculate the payload capacity for a truck, optionally with a trailer attached.
    """
    try:
        truck_gvm = int(truck.gvm_weight)  # Ensure numeric conversion
        truck_tare = int(truck.tare_weight)
    except ValueError:
        raise ValueError("Invalid data type: gvm_weight and tare_weight must be numbers.")

    truck_payload_capacity = truck_gvm - truck_tare

    if trailer:
        try:
            trailer_gvm = int(trailer.gvm_weight)
            trailer_tare = int(trailer.tare_weight)
        except ValueError:
            raise ValueError("Invalid data type: Trailer gvm_weight and tare_weight must be numbers.")
        
        trailer_payload_capacity = trailer_gvm - trailer_tare

        combined_gvm_weight = truck_gvm
        combined_tare_weight = truck_tare + trailer_tare
        combined_payload_capacity = combined_gvm_weight - combined_tare_weight

        MPCM = 56000  # Max permissible weight in kg
        if combined_gvm_weight > MPCM:
            raise ValueError("Combined Gross Vehicle Mass exceeds the legal limit.")

        payload_capacity = min(truck_payload_capacity, trailer_payload_capacity, combined_payload_capacity)
    else:
        payload_capacity = truck_payload_capacity

    if payload_capacity < 0:
        raise ValueError("Calculated payload capacity is negative. Check vehicle weights.")

    return int(payload_capacity)  # Ensure integer return value