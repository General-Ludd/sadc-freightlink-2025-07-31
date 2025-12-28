# route_analysis_service.py
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
import polyline
from geopy.distance import geodesic

# Your existing models
from models.spot_bookings.ftl_shipment import FTL_SHIPMENT
from models.nexus.customs import ShipmentCustomsEvent, RouteWaypoint
from database import SessionLocal

logger = logging.getLogger(__name__)

@dataclass
class GeoPoint:
    """Represents a geographic point with metadata"""
    latitude: Decimal
    longitude: Decimal
    country_code: Optional[str] = None
    location_name: Optional[str] = None
    waypoint_type: Optional[str] = None  # 'BORDER_CROSSING', 'PORT', 'CITY'
    sequence: int = 0

@dataclass
class DetectedBorder:
    """Represents a detected border crossing between two countries"""
    point: GeoPoint
    border_name: str
    from_country: str
    to_country: str
    border_type: str = 'ROAD'  # ROAD, PORT, AIRPORT

class RouteAnalyzer:
    """Main service class for route analysis"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
    def analyze_shipment_route(self, shipment_id: int, shipper_handles_entry: bool = False) -> List[ShipmentCustomsEvent]:
        """
        Main pipeline: Analyze a shipment's route and generate customs events.
        
        Args:
            shipment_id: ID of the FTL_SHIPMENT record
            shipper_handles_entry: True if shipper handles initial port of entry clearance
            
        Returns:
            List of generated ShipmentCustomsEvent objects (not yet saved to DB)
        """
        try:
            # 1. Get shipment and decode polyline
            shipment = self.db.query(FTL_SHIPMENT).filter(FTL_SHIPMENT.id == shipment_id).first()
            if not shipment:
                raise ValueError(f"Shipment {shipment_id} not found")
            
            # 2. Decode polyline to coordinate list
            coordinates = self._decode_polyline(shipment.polyline)
            
            # 3. Enrich coordinates with geographic data
            geo_points = self._enrich_coordinates(coordinates)
            
            # 4. Detect border crossings and ports
            border_points = self._detect_border_crossings(geo_points)
            
            # 5. Save waypoints to database
            waypoints = self._save_route_waypoints(shipment_id, geo_points)
            
            # 6. Generate customs events chain
            customs_events = self._generate_customs_events(
                shipment_id, border_points, shipment, shipper_handles_entry
            )
            
            logger.info(f"Generated {len(customs_events)} customs events for shipment {shipment_id}")
            return customs_events
            
        except Exception as e:
            logger.error(f"Route analysis failed for shipment {shipment_id}: {str(e)}")
            raise
    
    def _decode_polyline(self, polyline_str: str) -> List[Tuple[float, float]]:
        """Decode Google Maps polyline to list of coordinates"""
        if not polyline_str:
            raise ValueError("Polyline is empty")
        
        # polyline.decode() returns list of (lat, lng) tuples
        coordinates = polyline.decode(polyline_str)
        logger.debug(f"Decoded {len(coordinates)} coordinates from polyline")
        return coordinates
    
    def _enrich_coordinates(self, coordinates: List[Tuple[float, float]]) -> List[GeoPoint]:
        """
        Enrich raw coordinates with geographic data.
        This is where you'd integrate with a Geocoding API.
        
        For now, returns basic GeoPoint objects. In production, you would:
        1. Call Google Maps Reverse Geocoding API
        2. Identify country borders, ports, cities
        3. Cache results to avoid excessive API calls
        """
        geo_points = []
        
        for idx, (lat, lng) in enumerate(coordinates):
            point = GeoPoint(
                latitude=Decimal(str(lat)),
                longitude=Decimal(str(lng)),
                sequence=idx
            )
            
            # TODO: Replace with actual geocoding API call
            # For prototype, we'll simulate detection at specific indices
            if idx == 0:
                point.location_name = "Origin"
                point.waypoint_type = "ORIGIN"
            elif idx == len(coordinates) - 1:
                point.location_name = "Destination"
                point.waypoint_type = "DESTINATION"
            elif idx % 50 == 0:  # Simulate border detection
                point.waypoint_type = "BORDER_CROSSING"
                point.location_name = "Simulated Border"
            
            geo_points.append(point)
        
        return geo_points
    
    def _detect_border_crossings(self, geo_points: List[GeoPoint]) -> List[DetectedBorder]:
        """
        Detect border crossings between countries.
        
        In production, this would:
        1. Use a geofencing service or border database
        2. Detect when route crosses known border coordinates
        3. Identify the specific border post (Beitbridge, Chirundu, etc.)
        """
        borders = []
        
        # TODO: Implement actual border detection logic
        # This is a simplified simulation
        for i in range(1, len(geo_points)):
            prev_point = geo_points[i-1]
            curr_point = geo_points[i]
            
            # Simulate border detection at sequence 100
            if curr_point.sequence == 100 and prev_point.sequence == 99:
                border = DetectedBorder(
                    point=curr_point,
                    border_name="Beitbridge Border Post",
                    from_country="ZA",
                    to_country="ZW",
                    border_type="ROAD"
                )
                borders.append(border)
                logger.debug(f"Detected border: {border.border_name}")
        
        return borders
    
    def _save_route_waypoints(self, shipment_id: int, geo_points: List[GeoPoint]) -> List[RouteWaypoint]:
        """Save enriched route waypoints to database"""
        waypoints = []
        
        for geo_point in geo_points:
            # Only save significant points to reduce database size
            if geo_point.waypoint_type in ['ORIGIN', 'DESTINATION', 'BORDER_CROSSING', 'PORT']:
                waypoint = RouteWaypoint(
                    shipment_id=shipment_id,
                    sequence=geo_point.sequence,
                    country_code=geo_point.country_code or "UNKNOWN",
                    location_name=geo_point.location_name or f"Point {geo_point.sequence}",
                    waypoint_type=geo_point.waypoint_type,
                    latitude=geo_point.latitude,
                    longitude=geo_point.longitude
                )
                self.db.add(waypoint)
                waypoints.append(waypoint)
        
        self.db.commit()
        logger.debug(f"Saved {len(waypoints)} route waypoints for shipment {shipment_id}")
        return waypoints
    
    def _generate_customs_events(
        self, 
        shipment_id: int, 
        borders: List[DetectedBorder], 
        shipment: FTL_SHIPMENT,
        shipper_handles_entry: bool
    ) -> List[ShipmentCustomsEvent]:
        """
        Generate the complete chain of customs events based on detected borders.
        
        This implements your business logic:
        - Each border crossing generates EXPORT (exit) and IMPORT (entry) events
        - Handles the shipper's optional override for port of entry
        - Accounts for bonded transit if applicable
        """
        customs_events = []
        sequence = 1
        
        # Get origin and destination countries from shipment
        origin_country = shipment.origin_country  # e.g., 'ZA'
        destination_country = shipment.destination_country  # e.g., 'ZW'
        
        # Check if this is an international shipment
        is_international = origin_country != destination_country
        
        if not is_international:
            logger.info(f"Shipment {shipment_id} is domestic, no customs events needed")
            return []
        
        # Handle the "Shipper handles initial port of entry" logic
        initial_import_handled_by_shipper = shipper_handles_entry
        
        # If shipment is from outside SADC and arrives at a port
        # (You'll need to capture this info during booking)
        goods_from_overseas = False  # This should come from shipment data
        port_of_entry = None  # This should come from shipment data
        
        if goods_from_overseas and port_of_entry:
            # First event: IMPORT at port of entry
            import_event = ShipmentCustomsEvent(
                shipment_id=shipment_id,
                sequence=sequence,
                country_code=origin_country,  # Country of the port
                border_point=port_of_entry,
                event_type='IMPORT',
                status='PENDING',
                shipper_handled=initial_import_handled_by_shipper
            )
            customs_events.append(import_event)
            sequence += 1
            
            # Second event: EXPORT from same port (bonded transit)
            export_event = ShipmentCustomsEvent(
                shipment_id=shipment_id,
                sequence=sequence,
                country_code=origin_country,
                border_point=port_of_entry,
                event_type='EXPORT',
                status='PENDING',
                shipper_handled=False  # Platform always handles this
            )
            customs_events.append(export_event)
            sequence += 1
        
        # Generate events for each detected land border crossing
        for border in borders:
            # EXPORT event (exit from first country)
            export_event = ShipmentCustomsEvent(
                shipment_id=shipment_id,
                sequence=sequence,
                country_code=border.from_country,
                border_point=border.border_name,
                event_type='EXPORT',
                status='PENDING',
                shipper_handled=False
            )
            customs_events.append(export_event)
            sequence += 1
            
            # IMPORT event (entry to second country)
            import_event = ShipmentCustomsEvent(
                shipment_id=shipment_id,
                sequence=sequence,
                country_code=border.to_country,
                border_point=border.border_name,
                event_type='IMPORT',
                status='PENDING',
                shipper_handled=False
            )
            customs_events.append(import_event)
            sequence += 1
        
        # If destination is a port for overseas export, add final EXPORT event
        if shipment.destination_address and "harbor" in shipment.destination_address.lower():
            final_export = ShipmentCustomsEvent(
                shipment_id=shipment_id,
                sequence=sequence,
                country_code=destination_country,
                border_point=shipment.destination_address,
                event_type='EXPORT',
                status='PENDING',
                shipper_handled=False
            )
            customs_events.append(final_export)
        
        # Save all events to database
        for event in customs_events:
            self.db.add(event)
        
        self.db.commit()
        return customs_events

###################API Endpoints###################

@app.post("/api/shipments/{shipment_id}/analyze-route")
def analyze_shipment_route(shipment_id: int, shipper_handles_entry: bool = False):
    """API endpoint to analyze a shipment's route and generate customs events"""
    db = SessionLocal()
    try:
        analyzer = RouteAnalyzer(db)
        customs_events = analyzer.analyze_shipment_route(
            shipment_id, 
            shipper_handles_entry
        )
        
        return {
            "success": True,
            "shipment_id": shipment_id,
            "customs_events_generated": len(customs_events),
            "events": [
                {
                    "id": event.id,
                    "sequence": event.sequence,
                    "country_code": event.country_code,
                    "border_point": event.border_point,
                    "event_type": event.event_type,
                    "shipper_handled": event.shipper_handled
                }
                for event in customs_events
            ]
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()