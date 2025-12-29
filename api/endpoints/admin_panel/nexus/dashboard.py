from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from requests import Session
from sqlalchemy.orm import aliased
from sqlalchemy import or_, and_
from db.database import SessionLocal
from models.administration import Platform_Super_Admins, Platform_Super_and_Support_Admins_Permissions
from models.nexus.customs_territories import Country, CountryTradeAgreement, BorderPost, BorderClearanceProfile, TariffSchedule, TradeDefenseMeasure, CountrySpecialFee, TransitBondFee, CustomsProcedure, ExciseTaxRate
from schemas.administration import CreateAdministrationUser, AdminPermissionsSchema
from schemas.auth import LoginRequest, LoginResponse
from services.vehicle_service import create_shipper_trailer
from services.user_service import create_admin_super_user
from utils.auth import get_current_user
from utils.administration_auth import verify_admin_password, get_current_admin
from utils.admin_jwt_handler import create_admin_access_token
router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/countries")
def get_nexus_supported_countries_optimized(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # Query all countries and their border posts in one go
        countries_data = db.query(
            Country,
            BorderPost
        ).outerjoin(
            BorderPost,
            ((BorderPost.to_country_id == Country.id) & (BorderPost.fee_type == "ENTRY")) |
            ((BorderPost.from_country_id == Country.id) & (BorderPost.fee_type == "EXIT"))
        ).all()
        
        # Group border posts by country
        country_map = {}
        for country, border_post in countries_data:
            if country.id not in country_map:
                country_map[country.id] = {
                    "country": country,
                    "border_posts": []
                }
            if border_post:
                country_map[country.id]["border_posts"].append(border_post)
        
        # Build response
        result = []
        for country_id, data in country_map.items():
            country = data["country"]
            border_posts = data["border_posts"]
            
            border_points_list = [
                {
                    "id": bp.id,
                    "name": bp.border_name,
                    "fee_type": bp.fee_type,
                    "from_country_id": bp.from_country_id,
                    "to_country_id": bp.to_country_id,
                }
                for bp in border_posts
            ]
            
            result.append({
                "is_active": country.is_active,
                "name": country.name,
                "id": country.id,
                "iso_code": country.iso_code,
                "currency_code": country.currency_code,
                "standard_vat_rate": float(country.standard_vat_rate) if country.standard_vat_rate else None,
                "requires_ctn": country.requires_ctn,
                "border_points_count": len(border_points_list)
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/customs-procedures")
def get_nexus_customs_procedures(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        countries = db.query(Country).all()
        
        result = []
        for country in countries:
            # Query border posts for this country using bitwise operators
            border_posts = db.query(BorderPost).filter(
                (BorderPost.to_country_id == country.id) & (BorderPost.fee_type == "ENTRY") |
                (BorderPost.from_country_id == country.id) & (BorderPost.fee_type == "EXIT")
            ).all()

            customs_procedures = db.query(CustomsProcedure).filter(CustomsProcedure.country_id == country.id).all()
            
            # Convert border posts to dictionaries
            border_points_list = [
                {
                    "id": bp.id,
                    "name": bp.border_name,
                    "fee_type": bp.fee_type,
                    "from_country_id": bp.from_country_id,
                    "to_country_id": bp.to_country_id,
                }
                for bp in border_posts
            ]
            
            result.append({
                "is_active": country.is_active,
                "name": country.name,
                "id": country.id,
                "iso_code": country.iso_code,
                "currency_code": country.currency_code,
                "standard_vat_rate": float(country.standard_vat_rate) if country.standard_vat_rate else None,
                "requires_ctn": country.requires_ctn,
                "border_points_count": len(border_points_list),
                "customs_procedures": len(customs_procedures)
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, Depends

@router.get("/trade-agreements")
def get_trade_agreements(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        # Query trade agreements and group by code to identify unique agreements
        # Use DISTINCT to get unique codes and names
        distinct_agreements = db.query(
            TradeAgreement.code,
            TradeAgreement.name
        ).distinct().all()
        
        result = []
        
        for code, name in distinct_agreements:
            # For each unique agreement code, get aggregated data
            agreement_data = db.query(
                func.min(TradeAgreement.id).label('min_id'),
                func.min(TradeAgreement.name).label('agreement_name'),
                func.min(TradeAgreement.effective_date).label('effective_date'),
                func.min(TradeAgreement.notes).label('notes'),
                func.bool_or(TradeAgreement.is_active).label('is_active'),  # True if any is active
                func.count(TradeAgreement.country_id).label('member_count'),
                func.array_agg(TradeAgreement.country_id).label('country_ids')
            ).filter(
                TradeAgreement.code == code
            ).group_by(
                TradeAgreement.code
            ).first()
            
            if not agreement_data:
                continue
            
            # Format effective date
            if agreement_data.effective_date:
                effective_date = agreement_data.effective_date.strftime("%-m/%-d/%Y")
            else:
                effective_date = "N/A"
            
            # Format status
            status = "Active" if agreement_data.is_active else "Inactive"
            
            # Get country names for the agreement
            country_names = []
            if agreement_data.country_ids:
                countries = db.query(Country.name).filter(
                    Country.id.in_(agreement_data.country_ids)
                ).all()
                country_names = [country[0] for country in countries]
            
            result.append({
                "id": agreement_data.min_id,  # Use the minimum ID for reference
                "code": code,
                "name": name,
                "formal_name": name,  # You could enhance this if needed
                "short_name": code,   # Use code as short name
                "members": agreement_data.member_count,
                "member_countries": country_names,
                "country_ids": agreement_data.country_ids,
                "effective_date": effective_date,
                "status": status,
                "notes": agreement_data.notes
            })
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/countries-tarrif-schedule/summary-list")
def get_countries_tarrif_summary_list(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        current_date = date.today()
        
        # Get all countries with their counts using a single optimized query
        # This query joins all necessary tables and aggregates data
        countries_data = db.query(
            Country,
            func.count(
                case(
                    (BorderPost.to_country_id == Country.id, BorderPost.id),
                    (BorderPost.from_country_id == Country.id, BorderPost.id),
                    else_=None
                )
            ).label('border_points_count'),
            func.count(
                case(
                    (
                        (TariffSchedule.country_id == Country.id) &
                        (TariffSchedule.start_date <= current_date) &
                        ((TariffSchedule.end_date >= current_date) | (TariffSchedule.end_date.is_(None))),
                        TariffSchedule.id
                    ),
                    else_=None
                )
            ).label('current_tariffs'),
            func.count(
                case(
                    (
                        (TariffSchedule.country_id == Country.id) &
                        (TariffSchedule.start_date > current_date),
                        TariffSchedule.id
                    ),
                    else_=None
                )
            ).label('future_tariffs'),
            func.string_agg(func.distinct(TradeAgreement.code), ', ').label('memberships_string')
        ).outerjoin(
            BorderPost,
            (BorderPost.to_country_id == Country.id) | (BorderPost.from_country_id == Country.id)
        ).outerjoin(
            TariffSchedule,
            TariffSchedule.country_id == Country.id
        ).outerjoin(
            TradeAgreement,
            (TradeAgreement.country_id == Country.id) & (TradeAgreement.is_active == True)
        ).group_by(
            Country.id
        ).order_by(
            Country.name
        ).all()
        
        # If using SQLite or MySQL instead of PostgreSQL, use group_concat:
        # func.group_concat(func.distinct(TradeAgreement.code)).label('memberships_string')
        
        summary_list = []
        
        for country, border_count, current_tariffs, future_tariffs, memberships_string in countries_data:
            # Format CTN requirement
            requires_ctn = "Yes" if country.requires_ctn else "No"
            
            # Get customs agency - check if attribute exists
            customs_agency = "Unknown"
            if hasattr(country, 'customs_agency'):
                customs_agency = country.customs_agency if country.customs_agency else "Unknown"
            
            # Parse memberships string into list
            memberships_list = []
            if memberships_string:
                # Split by comma and clean up
                memberships_list = [m.strip() for m in memberships_string.split(',') if m.strip()]
            
            # Format VAT rate to remove trailing zeros if it's a decimal
            vat_rate = country.standard_vat_rate
            if isinstance(vat_rate, float):
                vat_rate = f"{vat_rate:g}"  # Removes trailing zeros
            
            # Build the formatted summary block
            summary_block = f"""{country.name} flag
{country.name}
ID: {country.id} | {country.iso_code}
Currency Code
{country.currency_code}
Standard VAT Rate
{vat_rate}%
Requires CTN
{requires_ctn}
Border Points
{border_count}
Customs Agency
{customs_agency}
Current Tariffs
{current_tariffs}
Future Tariffs
{future_tariffs}
Memberships
"""
            
            # Add each membership on a new line
            if memberships_list:
                for membership in memberships_list:
                    summary_block += f"{membership}\n"
            else:
                summary_block += "None\n"
            
            # Add the "View Tariffs" line
            summary_block += "View Tariffs"
            
            summary_list.append(summary_block)
        
        return summary_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


from datetime import date
from sqlalchemy import func, case
from sqlalchemy.orm import Session
from fastapi import HTTPException, Depends

@router.get("/border-posts/summary")
def get_border_posts_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_admin),
):
    try:
        current_date = date.today()
        
        # Query border posts with their countries and active clearance profiles
        border_posts_data = db.query(
            BorderPost,
            Country_from.name.label('from_country_name'),
            Country_to.name.label('to_country_name'),
            BorderClearanceProfile
        ).join(
            Country_from, BorderPost.from_country_id == Country_from.id
        ).join(
            Country_to, BorderPost.to_country_id == Country_to.id
        ).outerjoin(
            BorderClearanceProfile,
            (BorderClearanceProfile.border_post_id == BorderPost.id) &
            (BorderClearanceProfile.is_active == True) &
            (BorderClearanceProfile.effective_date <= current_date) &
            ((BorderClearanceProfile.expiry_date >= current_date) | 
             (BorderClearanceProfile.expiry_date.is_(None)))
        ).filter(
            BorderPost.is_active == True,
            BorderPost.effective_date <= current_date,
            (BorderPost.expiry_date >= current_date) | (BorderPost.expiry_date.is_(None))
        ).order_by(
            BorderPost.border_name
        ).all()
        
        # Group border posts by ID (since we might have multiple clearance profiles)
        border_post_summaries = {}
        
        for bp, from_country, to_country, profile in border_posts_data:
            if bp.id not in border_post_summaries:
                # Format ID with BP prefix
                border_id = f"BP{bp.id:03d}"
                
                # Determine if it's a port
                is_port = "Yes" if bp.is_port else "No"
                
                # Get congestion level from profile
                congestion = "Medium"
                avg_clearance = "N/A"
                peak_delay = "N/A"
                night_ops = "Not Allowed"
                
                if profile:
                    congestion = profile.congestion_level.title()
                    avg_clearance = f"{profile.avg_clearance_hours} hours"
                    peak_delay = f"{profile.peak_delay_hours} hours" if profile.peak_delay_hours else "N/A"
                    night_ops = "Allowed" if profile.night_operations_allowed else "Not Allowed"
                    clearance_leg = profile.clearance_leg
                
                border_post_summaries[bp.id] = {
                    "border_name": bp.border_name,
                    "is_active": "Active" if bp.is_active else "Inactive",
                    "from_country_name": from_country,
                    "to_country_name": to_country,
                    "border_id": border_id,
                    "clearance_leg": clearance_leg,
                    "is_port": is_port,
                    "congestion": congestion,
                    "avg_clearance": avg_clearance,
                    "peak_delay": peak_delay,
                    "night_operations": night_ops,
                    "description": bp.description or "",
                    "fee_type": bp.fee_type,
                    "amount_zar": float(bp.amount_zar) if bp.amount_zar else 0.0
                }
        
        # Format the output as strings
        summary_list = []
        
        for bp_data in border_post_summaries.values():
            # Build the formatted summary block
            summary_block = f"""{bp_data['border_name']}
{bp_data['is_active']}
{bp_data['from_country_name']}
{bp_data['from_country_name']}
{bp_data['to_country_name']}
{bp_data['to_country_name']}
ID
{bp_data['border_id']}
Clearance Leg
{bp_data['clearance_leg']}
Is Port
{bp_data['is_port']}
Congestion
{bp_data['congestion']}
Avg. Clearance
{bp_data['avg_clearance']}
Peak Delay
{bp_data['peak_delay']}
Night Operations
{bp_data['night_operations']}
{bp_data['description']}
View Details"""
            
            summary_list.append(summary_block)
        
        return summary_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))