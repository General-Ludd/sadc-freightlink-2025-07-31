# border_detection_service.py
import json
from typing import List, Dict
from dataclasses import dataclass
import numpy as np
from scipy.spatial import KDTree

@dataclass
class BorderReference:
    """Reference data for known border crossings"""
    name: str
    latitude: float
    longitude: float
    country1: str
    country2: str
    border_type: str  # 'ROAD', 'PORT', 'AIRPORT'

class BorderDetectionService:
    """Detects when a route crosses known borders"""
    
    def __init__(self, border_data_file: str = "borders.json"):
        self.borders = self._load_border_data(border_data_file)
        self._build_spatial_index()
    
    def _load_border_data(self, filename: str) -> List[BorderReference]:
        """Load border reference data from file or database"""
        # TODO: Load from your CountryBorderMapping table
        # For now, using a sample of SADC borders
        sample_borders = [
            BorderReference("Beitbridge Border Post", -22.2167, 29.9833, "ZA", "ZW", "ROAD"),
            BorderReference("Chirundu Border Post", -16.0333, 28.8500, "ZM", "ZW", "ROAD"),
            BorderReference("Kasumbalesa Border Post", -12.8333, 28.0833, "ZM", "CD", "ROAD"),
            BorderReference("Durban Harbour", -29.8587, 31.0218, "ZA", None, "PORT"),
            BorderReference("Maputo Port", -25.9667, 32.5833, "MZ", None, "PORT"),
        ]
        return sample_borders
    
    def _build_spatial_index(self):
        """Build KD-tree for fast spatial queries"""
        coordinates = [(b.latitude, b.longitude) for b in self.borders]
        self.kd_tree = KDTree(coordinates)
        self.border_points = coordinates
    
    def find_nearby_borders(self, lat: float, lng: float, max_km: float = 5.0) -> List[BorderReference]:
        """Find borders within specified radius of a point"""
        point = (lat, lng)
        distances, indices = self.kd_tree.query([point], k=len(self.borders))
        
        nearby = []
        for dist, idx in zip(distances[0], indices[0]):
            if dist * 111 <= max_km:  # Convert to km (approx)
                nearby.append(self.borders[idx])
        
        return nearby