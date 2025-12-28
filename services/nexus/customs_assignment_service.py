# customs_assignment_service.py
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session, load_only
from sqlalchemy import and_, or_, func, desc

from models import (
    ShipmentCustomsEvent, 
    CustomsBrokerageFirm, 
    CustomsBrokerageFirmServiceArea,
    CustomsClearingAgent,
    CustomsBrokerageFirmCredential
)

logger = logging.getLogger(__name__)

@dataclass
class AssignmentResult:
    """Result of an assignment attempt"""
    event_id: int
    firm_id: Optional[int]
    success: bool
    reason: str
    score: float = 0.0

class CustomsEventAssigner:
    """Service for intelligently assigning customs events to brokerage firms"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        
    def assign_pending_events(self, limit: int = 50) -> List[AssignmentResult]:
        """
        Main method: Assign pending customs events to brokerage firms.
        
        Args:
            limit: Maximum number of events to process in one run
            
        Returns:
            List of assignment results
        """
        results = []
        
        # Get pending events that need assignment
        pending_events = self.get_pending_events(limit)
        
        if not pending_events:
            logger.info("No pending events to assign")
            return results
        
        logger.info(f"Processing {len(pending_events)} pending customs events")
        
        for event in pending_events:
            try:
                # Skip if shipper handles this event
                if event.shipper_handled:
                    result = AssignmentResult(
                        event_id=event.id,
                        firm_id=None,
                        success=False,
                        reason="Event is handled by shipper"
                    )
                    results.append(result)
                    continue
                
                # Find the best firm for this event
                firm, score, reason = self.find_best_firm_for_event(event)
                
                if firm:
                    # Assign the event
                    event.assigned_firm_id = firm.id
                    event.updated_at = datetime.utcnow()
                    
                    # Optionally assign to a specific agent within the firm
                    agent = self.assign_to_agent(firm, event)
                    if agent:
                        # You might want to add an assigned_agent_id field to ShipmentCustomsEvent
                        pass
                    
                    self.db.add(event)
                    result = AssignmentResult(
                        event_id=event.id,
                        firm_id=firm.id,
                        success=True,
                        reason=f"Assigned to {firm.legal_name}",
                        score=score
                    )
                    logger.info(f"Assigned event {event.id} to firm {firm.id} (score: {score:.2f})")
                else:
                    result = AssignmentResult(
                        event_id=event.id,
                        firm_id=None,
                        success=False,
                        reason=reason
                    )
                    logger.warning(f"No firm found for event {event.id}: {reason}")
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to assign event {event.id}: {str(e)}")
                result = AssignmentResult(
                    event_id=event.id,
                    firm_id=None,
                    success=False,
                    reason=f"Error: {str(e)}"
                )
                results.append(result)
        
        # Commit all assignments at once
        try:
            self.db.commit()
            logger.info(f"Successfully assigned {sum(1 for r in results if r.success)} events")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to commit assignments: {str(e)}")
            # Mark all results as failed
            for result in results:
                result.success = False
                result.reason = f"Commit failed: {str(e)}"
        
        return results
    
    def get_pending_events(self, limit: int) -> List[ShipmentCustomsEvent]:
        """Get pending events that need assignment"""
        return self.db.query(ShipmentCustomsEvent).filter(
            and_(
                ShipmentCustomsEvent.assigned_firm_id.is_(None),
                ShipmentCustomsEvent.shipper_handled == False,
                ShipmentCustomsEvent.status == 'PENDING'
            )
        ).limit(limit).all()
    
    def find_best_firm_for_event(self, event: ShipmentCustomsEvent) -> Tuple[Optional[CustomsBrokerageFirm], float, str]:
        """
        Find the best brokerage firm for a given customs event.
        
        Uses a scoring system based on:
        1. Service area match (country + border point)
        2. Service type match (IMPORT/EXPORT)
        3. Firm capacity (current workload)
        4. Firm performance (clearance speed)
        5. Credentials/verification status
        """
        # Step 1: Get all firms that serve this country and border point
        eligible_firms = self.get_eligible_firms(event)
        
        if not eligible_firms:
            return None, 0.0, "No firms serve this country/border combination"
        
        # Step 2: Score each eligible firm
        scored_firms = []
        for firm in eligible_firms:
            score, reasons = self.score_firm_for_event(firm, event)
            scored_firms.append((firm, score, reasons))
        
        # Step 3: Sort by score (highest first) and pick the best
        scored_firms.sort(key=lambda x: x[1], reverse=True)
        
        best_firm, best_score, best_reasons = scored_firms[0]
        
        # Only assign if score meets minimum threshold
        if best_score < 0.3:  # Adjust threshold as needed
            return None, best_score, f"Best firm score too low: {best_score:.2f}"
        
        logger.debug(f"Best firm for event {event.id}: {best_firm.legal_name} with score {best_score:.2f}")
        return best_firm, best_score, f"Assigned with score {best_score:.2f}"
    
    def get_eligible_firms(self, event: ShipmentCustomsEvent) -> List[CustomsBrokerageFirm]:
        """Get all firms eligible to handle this event based on service areas"""
        # First, get all service areas that match this event's country and border
        service_areas = self.db.query(CustomsBrokerageFirmServiceArea).join(
            CustomsBrokerageFirm,
            CustomsBrokerageFirmServiceArea.firm_id == CustomsBrokerageFirm.id
        ).filter(
            and_(
                CustomsBrokerageFirmServiceArea.country_iso == event.country_code,
                CustomsBrokerageFirmServiceArea.border_point == event.border_point,
                CustomsBrokerageFirmServiceArea.is_active == True,
                CustomsBrokerageFirm.is_active == True,
                CustomsBrokerageFirm.is_verified == True,
                # Check if service type is supported
                CustomsBrokerageFirmServiceArea.service_types.contains([event.event_type])
            )
        ).all()
        
        # Extract unique firms
        firm_ids = set(sa.firm_id for sa in service_areas)
        if not firm_ids:
            return []
        
        return self.db.query(CustomsBrokerageFirm).filter(
            CustomsBrokerageFirm.id.in_(list(firm_ids))
        ).all()
    
    def score_firm_for_event(self, firm: CustomsBrokerageFirm, event: ShipmentCustomsEvent) -> Tuple[float, List[str]]:
        """Calculate a suitability score for a firm handling an event"""
        score = 0.0
        max_score = 100.0
        reasons = []
        
        # 1. Service area match (40 points max)
        service_area = self.get_firm_service_area_for_event(firm, event)
        if service_area:
            score += 40.0
            reasons.append("Service area match")
        
        # 2. Current workload (30 points max)
        workload_score = self.calculate_workload_score(firm)
        score += workload_score * 30.0
        reasons.append(f"Workload score: {workload_score:.2f}")
        
        # 3. Performance history (20 points max)
        performance_score = self.calculate_performance_score(firm, event.country_code)
        score += performance_score * 20.0
        reasons.append(f"Performance score: {performance_score:.2f}")
        
        # 4. Credentials for this country (10 points max)
        credential_score = self.calculate_credential_score(firm, event.country_code)
        score += credential_score * 10.0
        reasons.append(f"Credential score: {credential_score:.2f}")
        
        # Normalize to 0-1 range
        normalized_score = score / max_score
        
        return normalized_score, reasons
    
    def get_firm_service_area_for_event(self, firm: CustomsBrokerageFirm, event: ShipmentCustomsEvent) -> Optional[CustomsBrokerageFirmServiceArea]:
        """Get the specific service area that matches this event"""
        return self.db.query(CustomsBrokerageFirmServiceArea).filter(
            and_(
                CustomsBrokerageFirmServiceArea.firm_id == firm.id,
                CustomsBrokerageFirmServiceArea.country_iso == event.country_code,
                CustomsBrokerageFirmServiceArea.border_point == event.border_point,
                CustomsBrokerageFirmServiceArea.service_types.contains([event.event_type])
            )
        ).first()
    
    def calculate_workload_score(self, firm: CustomsBrokerageFirm) -> float:
        """Calculate workload score (0-1, higher is better)"""
        # Count pending events assigned to this firm
        pending_count = self.db.query(ShipmentCustomsEvent).filter(
            and_(
                ShipmentCustomsEvent.assigned_firm_id == firm.id,
                ShipmentCustomsEvent.status.in_(['PENDING', 'DOCS_SUBMITTED', 'UNDER_REVIEW'])
            )
        ).count()
        
        # Define thresholds
        if pending_count == 0:
            return 1.0  # No workload, full score
        elif pending_count <= 5:
            return 0.8  # Light workload
        elif pending_count <= 10:
            return 0.5  # Moderate workload
        elif pending_count <= 20:
            return 0.2  # Heavy workload
        else:
            return 0.1  # Very heavy workload
    
    def calculate_performance_score(self, firm: CustomsBrokerageFirm, country_code: str) -> float:
        """Calculate performance score based on historical clearance times"""
        # Get completed events for this firm in this country
        completed_events = self.db.query(ShipmentCustomsEvent).filter(
            and_(
                ShipmentCustomsEvent.assigned_firm_id == firm.id,
                ShipmentCustomsEvent.country_code == country_code,
                ShipmentCustomsEvent.status == 'CLEARED',
                ShipmentCustomsEvent.cleared_at.isnot(None),
                ShipmentCustomsEvent.submitted_at.isnot(None)
            )
        ).limit(50).all()
        
        if not completed_events:
            return 0.5  # Default score if no history
        
        # Calculate average clearance time in hours
        total_hours = 0
        for event in completed_events:
            clearance_time = (event.cleared_at - event.submitted_at).total_seconds() / 3600
            total_hours += clearance_time
        
        avg_hours = total_hours / len(completed_events)
        
        # Score based on average clearance time
        if avg_hours <= 24:
            return 1.0  # Excellent: cleared within 24 hours
        elif avg_hours <= 48:
            return 0.8  # Good: cleared within 48 hours
        elif avg_hours <= 72:
            return 0.6  # Average: cleared within 72 hours
        elif avg_hours <= 120:
            return 0.4  # Below average
        else:
            return 0.2  # Poor
    
    def calculate_credential_score(self, firm: CustomsBrokerageFirm, country_code: str) -> float:
        """Calculate score based on firm's credentials for the country"""
        # Count verified credentials for this country
        credential_count = self.db.query(CustomsBrokerageFirmCredential).filter(
            and_(
                CustomsBrokerageFirmCredential.firm_id == firm.id,
                CustomsBrokerageFirmCredential.country_iso == country_code,
                CustomsBrokerageFirmCredential.is_verified == True
            )
        ).count()
        
        # More credentials = higher score
        if credential_count >= 3:
            return 1.0
        elif credential_count == 2:
            return 0.7
        elif credential_count == 1:
            return 0.4
        else:
            return 0.0
    
    def assign_to_agent(self, firm: CustomsBrokerageFirm, event: ShipmentCustomsEvent) -> Optional[CustomsClearingAgent]:
        """Assign to a specific agent within the firm (optional)"""
        # Get active agents for this firm
        agents = self.db.query(CustomsClearingAgent).filter(
            and_(
                CustomsClearingAgent.firm_id == firm.id,
                CustomsClearingAgent.is_active == True
            )
        ).all()
        
        if not agents:
            return None
        
        # Simple round-robin or load-based assignment
        # For now, return the first available agent
        return agents[0] if agents else None