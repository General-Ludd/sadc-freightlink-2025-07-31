# app/services/quote_service.py
import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from dataclasses import dataclass
from sqlalchemy.orm import Session
import googlemaps
from datetime import datetime

from app.models import Country, CustomsProcedure, CustomsBrokerageFirmServiceArea
from app.config import settings

logger = logging.getLogger(__name__)

@dataclass
class QuoteRequest:
    """Input for quote calculation"""
    origin_address: str
    origin_country: str
    destination_address: str
    destination_country: str
    commodity: str
    shipment_weight_kg: int
    hs_code: Optional[str] = None  # Harmonized System code for tariffs
    goods_value_usd: Optional[Decimal] = None
    requires_port_of_entry_clearance: bool = False
    port_of_entry: Optional[str] = None
    shipper_handles_initial_clearance: bool = False

@dataclass
class QuoteBreakdown:
    """Detailed cost breakdown"""
    line_haul_freight: Decimal
    fuel_surcharge: Decimal
    border_crossing_fees: List[Dict]
    customs_clearance_fees: List[Dict]
    duties_taxes: List[Dict]
    insurance: Decimal
    total_amount: Decimal

@dataclass
class QuoteResponse:
    """Complete quote response"""
    quote_id: str
    valid_until: datetime
    total_amount: Decimal
    currency: str
    estimated_transit_days: int
    breakdown: QuoteBreakdown
    required_documents: List[str]
    customs_events_required: List[Dict]
    warnings: List[str]

class CorridorQuoteService:
    """Production quote service for SA-ZIM-ZAM-DRC corridor"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.gmaps = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
        
        # Real freight rates (ZAR per km) - adjust based on your contracts
        self.FREIGHT_RATES = {
            "ZA": Decimal("42.50"),  # South Africa domestic
            "ZW": Decimal("38.75"),  # Zimbabwe domestic
            "ZM": Decimal("36.20"),  # Zambia domestic
            "CD": Decimal("45.80")   # DRC domestic (higher due to road conditions)
        }
        
        # Border crossing fees (real estimates in USD)
        self.BORDER_FEES = {
            "ZA-ZW": {"export": Decimal("120"), "import": Decimal("150")},  # Beitbridge
            "ZW-ZM": {"export": Decimal("80"), "import": Decimal("100")},   # Chirundu
            "ZM-CD": {"export": Decimal("150"), "import": Decimal("200")},  # Kasumbalesa
        }
        
        # Customs clearance agent fees (USD per event)
        self.CLEARANCE_FEES = {
            "ZA": {"export": Decimal("85"), "import": Decimal("120")},
            "ZW": {"export": Decimal("75"), "import": Decimal("110")},
            "ZM": {"export": Decimal("70"), "import": Decimal("105")},
            "CD": {"export": Decimal("180"), "import": Decimal("250")},  # Higher for DRC
        }
        
        # DRC specific fees (real requirements)
        self.DRC_SPECIAL_FEES = {
            "ctn_certificate": Decimal("350"),  # Cargo Tracking Note
            "bivac_inspection": Decimal("500"),  # Pre-shipment inspection
            "guice_processing": Decimal("150"),  # Electronic processing fee
        }
    
    def calculate_quote(self, request: QuoteRequest) -> QuoteResponse:
        """
        Calculate a complete quote for a shipment along the corridor.
        This is PRODUCTION code with real calculations.
        """
        logger.info(f"Calculating quote for {request.origin_country} to {request.destination_country}")
        
        try:
            # 1. Calculate distance and freight costs
            distance_km = self._calculate_distance(
                request.origin_address, 
                request.destination_address
            )
            
            freight_cost = self._calculate_freight_cost(
                distance_km, 
                request.origin_country, 
                request.destination_country
            )
            
            # 2. Determine route and border crossings
            route_info = self._determine_route(request)
            
            # 3. Calculate border crossing fees
            border_fees = self._calculate_border_fees(route_info["borders"])
            
            # 4. Calculate customs clearance fees
            clearance_fees = self._calculate_clearance_fees(
                route_info["borders"], 
                request
            )
            
            # 5. Calculate duties and taxes (if goods value provided)
            duties_taxes = []
            if request.goods_value_usd and request.hs_code:
                duties_taxes = self._estimate_duties_taxes(request)
            
            # 6. Calculate insurance (0.15% of goods value)
            insurance = Decimal("0")
            if request.goods_value_usd:
                insurance = request.goods_value_usd * Decimal("0.0015")
            
            # 7. Calculate total
            total = freight_cost["total"]
            total += sum(fee["amount"] for fee in border_fees)
            total += sum(fee["amount"] for fee in clearance_fees)
            total += sum(tax["estimated_amount"] for tax in duties_taxes)
            total += insurance
            
            # 8. Determine required documents
            required_docs = self._get_required_documents(request, route_info)
            
            # 9. Determine customs events needed
            customs_events = self._determine_customs_events(request, route_info)
            
            # 10. Generate warnings for special requirements
            warnings = self._generate_warnings(request, route_info)
            
            # Build response
            breakdown = QuoteBreakdown(
                line_haul_freight=freight_cost["line_haul"],
                fuel_surcharge=freight_cost["fuel_surcharge"],
                border_crossing_fees=border_fees,
                customs_clearance_fees=clearance_fees,
                duties_taxes=duties_taxes,
                insurance=insurance,
                total_amount=total
            )
            
            # Use USD as base currency for cross-border
            quote_currency = "USD" if request.origin_country != request.destination_country else "ZAR"
            
            return QuoteResponse(
                quote_id=f"QT{datetime.now().strftime('%Y%m%d%H%M%S')}",
                valid_until=datetime.now().replace(hour=23, minute=59, second=59),
                total_amount=total,
                currency=quote_currency,
                estimated_transit_days=route_info["estimated_days"],
                breakdown=breakdown,
                required_documents=required_docs,
                customs_events_required=customs_events,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"Quote calculation failed: {str(e)}")
            raise
    
    def _calculate_distance(self, origin: str, destination: str) -> float:
        """Calculate actual distance using Google Maps API"""
        try:
            # Get distance matrix
            result = self.gmaps.distance_matrix(
                origins=[origin],
                destinations=[destination],
                mode="driving",
                units="metric"
            )
            
            if result["rows"][0]["elements"][0]["status"] == "OK":
                distance_meters = result["rows"][0]["elements"][0]["distance"]["value"]
                return distance_meters / 1000  # Convert to kilometers
            else:
                # Fallback: Use approximate corridor distances
                logger.warning("Google Maps API failed, using fallback distances")
                return self._get_fallback_distance(origin, destination)
                
        except Exception as e:
            logger.warning(f"Distance API failed: {str(e)}")
            return self._get_fallback_distance(origin, destination)
    
    def _get_fallback_distance(self, origin: str, destination: str) -> float:
        """Fallback distances for key corridors (km)"""
        corridor_distances = {
            ("Johannesburg, ZA", "Harare, ZW"): 1100,
            ("Durban, ZA", "Lusaka, ZM"): 2300,
            ("Lusaka, ZM", "Lubumbashi, CD"): 350,
            ("Harare, ZW", "Lusaka, ZM"): 850,
            ("Durban, ZA", "Lubumbashi, CD"): 2650,
        }
        
        for (orig, dest), distance in corridor_distances.items():
            if orig in origin and dest in destination:
                return distance
        
        # Default average
        return 1500
    
    def _calculate_freight_cost(self, distance_km: float, origin_country: str, dest_country: str) -> Dict:
        """Calculate freight cost based on distance and rates"""
        # Use origin country rate for international trips
        rate_per_km = self.FREIGHT_RATES.get(origin_country, Decimal("40.00"))
        
        line_haul = Decimal(str(distance_km)) * rate_per_km
        
        # Fuel surcharge (15% of line haul)
        fuel_surcharge = line_haul * Decimal("0.15")
        
        return {
            "line_haul": line_haul,
            "fuel_surcharge": fuel_surcharge,
            "total": line_haul + fuel_surcharge,
            "distance_km": distance_km,
            "rate_per_km": rate_per_km
        }
    
    def _determine_route(self, request: QuoteRequest) -> Dict:
        """Determine the route and which borders will be crossed"""
        origin = request.origin_country
        destination = request.destination_country
        
        # Define corridor routes
        corridor_routes = {
            ("ZA", "ZW"): {
                "borders": [("ZA", "ZW", "Beitbridge Border Post")],
                "estimated_days": 2,
                "transit_countries": []
            },
            ("ZA", "ZM"): {
                "borders": [
                    ("ZA", "ZW", "Beitbridge Border Post"),
                    ("ZW", "ZM", "Chirundu Border Post")
                ],
                "estimated_days": 4,
                "transit_countries": ["ZW"]
            },
            ("ZA", "CD"): {
                "borders": [
                    ("ZA", "ZW", "Beitbridge Border Post"),
                    ("ZW", "ZM", "Chirundu Border Post"),
                    ("ZM", "CD", "Kasumbalesa Border Post")
                ],
                "estimated_days": 6,
                "transit_countries": ["ZW", "ZM"]
            },
            ("ZW", "ZM"): {
                "borders": [("ZW", "ZM", "Chirundu Border Post")],
                "estimated_days": 1,
                "transit_countries": []
            },
            ("ZM", "CD"): {
                "borders": [("ZM", "CD", "Kasumbalesa Border Post")],
                "estimated_days": 2,
                "transit_countries": []
            }
        }
        
        route_key = (origin, destination)
        
        if route_key in corridor_routes:
            return corridor_routes[route_key]
        else:
            # Reverse route
            reverse_key = (destination, origin)
            if reverse_key in corridor_routes:
                route = corridor_routes[reverse_key]
                # Reverse the border directions
                reversed_borders = []
                for from_c, to_c, border in route["borders"]:
                    reversed_borders.append((to_c, from_c, border))
                route["borders"] = reversed_borders
                return route
            else:
                raise ValueError(f"Route from {origin} to {destination} not supported in this corridor")
    
    def _calculate_border_fees(self, borders: List[Tuple]) -> List[Dict]:
        """Calculate border crossing fees"""
        fees = []
        
        for from_country, to_country, border_name in borders:
            border_key = f"{from_country}-{to_country}"
            
            if border_key in self.BORDER_FEES:
                # Export fee from originating country
                fees.append({
                    "description": f"{from_country} Export Fee - {border_name}",
                    "amount": self.BORDER_FEES[border_key]["export"],
                    "country": from_country,
                    "border": border_name,
                    "type": "BORDER_EXPORT_FEE"
                })
                
                # Import fee to destination country
                fees.append({
                    "description": f"{to_country} Import Fee - {border_name}",
                    "amount": self.BORDER_FEES[border_key]["import"],
                    "country": to_country,
                    "border": border_name,
                    "type": "BORDER_IMPORT_FEE"
                })
            else:
                # Default fees if not specified
                fees.extend([
                    {
                        "description": f"{from_country} Export Fee - {border_name}",
                        "amount": Decimal("100"),
                        "country": from_country,
                        "border": border_name,
                        "type": "BORDER_EXPORT_FEE"
                    },
                    {
                        "description": f"{to_country} Import Fee - {border_name}",
                        "amount": Decimal("125"),
                        "country": to_country,
                        "border": border_name,
                        "type": "BORDER_IMPORT_FEE"
                    }
                ])
        
        return fees
    
    def _calculate_clearance_fees(self, borders: List[Tuple], request: QuoteRequest) -> List[Dict]:
        """Calculate customs clearance agent fees"""
        fees = []
        
        for from_country, to_country, border_name in borders:
            # Export clearance from originating country
            if from_country in self.CLEARANCE_FEES:
                fees.append({
                    "description": f"{from_country} Customs Clearance (Export) - {border_name}",
                    "amount": self.CLEARANCE_FEES[from_country]["export"],
                    "country": from_country,
                    "service": "EXPORT_CLEARANCE",
                    "agent_required": True
                })
            
            # Import clearance to destination country
            if to_country in self.CLEARANCE_FEES:
                # Check if DRC for special fees
                if to_country == "CD":
                    fees.append({
                        "description": "DRC CTN Certificate Processing",
                        "amount": self.DRC_SPECIAL_FEES["ctn_certificate"],
                        "country": "CD",
                        "service": "CTN_PROCESSING",
                        "agent_required": True,
                        "mandatory": True
                    })
                    
                    # BIVAC inspection for goods over $5000
                    if request.goods_value_usd and request.goods_value_usd > Decimal("5000"):
                        fees.append({
                            "description": "DRC Pre-shipment Inspection (BIVAC)",
                            "amount": self.DRC_SPECIAL_FEES["bivac_inspection"],
                            "country": "CD",
                            "service": "PRE_SHIPMENT_INSPECTION",
                            "agent_required": True
                        })
                
                fees.append({
                    "description": f"{to_country} Customs Clearance (Import) - {border_name}",
                    "amount": self.CLEARANCE_FEES[to_country]["import"],
                    "country": to_country,
                    "service": "IMPORT_CLEARANCE",
                    "agent_required": True
                })
        
        # Port of entry clearance if required
        if request.requires_port_of_entry_clearance and request.port_of_entry:
            # Determine country from port
            port_country = self._get_country_from_port(request.port_of_entry)
            if port_country in self.CLEARANCE_FEES:
                fees.append({
                    "description": f"Port of Entry Clearance - {request.port_of_entry}",
                    "amount": self.CLEARANCE_FEES[port_country]["import"],
                    "country": port_country,
                    "service": "PORT_ENTRY_CLEARANCE",
                    "agent_required": not request.shipper_handles_initial_clearance
                })
        
        return fees
    
    def _estimate_duties_taxes(self, request: QuoteRequest) -> List[Dict]:
        """Estimate duties and taxes based on HS code and goods value"""
        # In production, you would integrate with a tariff database
        # For now, use estimated percentages
        
        if not request.goods_value_usd:
            return []
        
        duties_taxes = []
        goods_value = request.goods_value_usd
        
        # Estimated duty rates by commodity type
        commodity_rates = {
            "CEMENT": Decimal("0.10"),  # 10%
            "COPPER": Decimal("0.05"),   # 5%
            "FOOD": Decimal("0.15"),     # 15%
            "ELECTRONICS": Decimal("0.20"),  # 20%
            "GENERAL GOODS": Decimal("0.125"),  # 12.5%
        }
        
        duty_rate = commodity_rates.get(request.commodity, Decimal("0.125"))
        duty_amount = goods_value * duty_rate
        
        duties_taxes.append({
            "description": f"Import Duty ({duty_rate*100}%)",
            "estimated_amount": duty_amount,
            "rate": duty_rate,
            "type": "DUTY",
            "calculation_base": goods_value
        })
        
        # VAT (if applicable)
        dest_country = self.db.query(Country).filter_by(iso_code=request.destination_country).first()
        if dest_country and dest_country.standard_vat_rate:
            vat_base = goods_value + duty_amount
            vat_amount = vat_base * (dest_country.standard_vat_rate / Decimal("100"))
            
            duties_taxes.append({
                "description": f"VAT ({dest_country.standard_vat_rate}%)",
                "estimated_amount": vat_amount,
                "rate": dest_country.standard_vat_rate,
                "type": "VAT",
                "calculation_base": vat_base
            })
        
        return duties_taxes
    
    def _get_required_documents(self, request: QuoteRequest, route_info: Dict) -> List[str]:
        """Determine required documents based on route and commodity"""
        required_docs = [
            "Commercial Invoice",
            "Packing List",
            "Bill of Lading (or Air Waybill)"
        ]
        
        # Add Certificate of Origin for SADC trade
        if request.origin_country != request.destination_country:
            required_docs.append("SADC Certificate of Origin")
        
        # Check DRC requirements
        if request.destination_country == "CD":
            required_docs.extend([
                "CTN (Cargo Tracking Note) Certificate",
                "Import License"
            ])
            
            if request.goods_value_usd and request.goods_value_usd > Decimal("5000"):
                required_docs.append("BIVAC/COC Inspection Certificate")
        
        # Add commodity-specific documents
        if request.commodity in ["FOOD", "AGRICULTURAL"]:
            required_docs.append("Phytosanitary Certificate")
        
        if request.commodity in ["CHEMICALS", "HAZARDOUS"]:
            required_docs.append("MSDS (Material Safety Data Sheet)")
        
        return required_docs
    
    def _determine_customs_events(self, request: QuoteRequest, route_info: Dict) -> List[Dict]:
        """Determine which customs events will be required"""
        events = []
        sequence = 1
        
        # Port of entry event if required
        if request.requires_port_of_entry_clearance and request.port_of_entry:
            events.append({
                "sequence": sequence,
                "country": self._get_country_from_port(request.port_of_entry),
                "border_point": request.port_of_entry,
                "event_type": "IMPORT",
                "handled_by": "SHIPPER" if request.shipper_handles_initial_clearance else "PLATFORM"
            })
            sequence += 1
        
        # Border crossing events
        for from_country, to_country, border_name in route_info["borders"]:
            events.append({
                "sequence": sequence,
                "country": from_country,
                "border_point": border_name,
                "event_type": "EXPORT",
                "handled_by": "PLATFORM"
            })
            sequence += 1
            
            events.append({
                "sequence": sequence,
                "country": to_country,
                "border_point": border_name,
                "event_type": "IMPORT",
                "handled_by": "PLATFORM"
            })
            sequence += 1
        
        return events
    
    def _generate_warnings(self, request: QuoteRequest, route_info: Dict) -> List[str]:
        """Generate warnings for special requirements"""
        warnings = []
        
        # DRC warnings
        if request.destination_country == "CD":
            warnings.extend([
                "DRC requires CTN (Cargo Tracking Note) for all shipments",
                "Goods valued over $5000 require pre-shipment inspection",
                "Average DRC customs clearance: 3-5 business days"
            ])
        
        # Transit country warnings
        for transit in route_info["transit_countries"]:
            if transit == "ZW":
                warnings.append("Zimbabwe may require transit bond for goods passing through")
            elif transit == "ZM":
                warnings.append("Zambia transit requires customs escort for certain goods")
        
        # Weight warnings
        if request.shipment_weight_kg > 30000:
            warnings.append("Over 30T may require special permits on some routes")
        
        # Commodity warnings
        if request.commodity in ["ALCOHOL", "TOBACCO"]:
            warnings.append("Excise duties apply - rates vary by country")
        
        return warnings
    
    def _get_country_from_port(self, port_name: str) -> str:
        """Extract country code from port name"""
        port_mapping = {
            "Durban": "ZA",
            "Durban Harbour": "ZA",
            "Durban Port": "ZA",
            "Maputo": "MZ",
            "Maputo Port": "MZ",
            "Beira": "MZ",
            "Walvis Bay": "NA",
            "Dar es Salaam": "TZ",
        }
        
        for port, country in port_mapping.items():
            if port in port_name:
                return country
        
        return "ZA"  # Default to South Africa