from pydantic import BaseModel
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from decimal import Decimal
import json

from db.database import SessionLocal
from models.nexus.customs_territories import (
    BorderPost, Country, TariffSchedule, TradeDefenseMeasure,
    ExciseTaxRate, CountrySpecialFee, TransitBondFee,
    CustomsProcedure
)

router = APIRouter()

# ======================================================
# HELPERS
# ======================================================

def normalize_required_documents(docs):
    """
    Ensures required_documents is always List[str]
    without changing any other logic.
    """
    if docs is None:
        return []

    if isinstance(docs, list):
        return docs

    if isinstance(docs, str):
        try:
            parsed = json.loads(docs)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return [docs]

    return []

# ======================================================
# SCHEMAS
# ======================================================

class ShipmentQuoteInput(BaseModel):
    polyline: str
    origin_country: str
    destination_country: str
    cargo_hs_code: str
    cargo_value_usd: float
    cargo_description: str

class FeeDetail(BaseModel):
    fee_name: str
    amount_zar: float
    fee_type: str
    payable_to: str
    description: str | None = None

class BorderLegQuote(BaseModel):
    process_type: str
    country: str
    fees: List[FeeDetail]
    required_documents: List[str]

class BorderQuote(BaseModel):
    border_name: str
    sequence_order: int
    legs: List[BorderLegQuote]

class ShipmentQuoteOutput(BaseModel):
    grand_total_cost_zar: float
    borders: List[BorderQuote]

# ======================================================
# DB
# ======================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ======================================================
# MAIN LOGIC
# ======================================================

@router.post("/quote-shipment", response_model=ShipmentQuoteOutput)
def quote_shipment(input_data: ShipmentQuoteInput, db: Session = Depends(get_db)):

    origin = db.query(Country).filter(Country.name == input_data.origin_country).first()
    destination = db.query(Country).filter(Country.name == input_data.destination_country).first()

    if not origin or not destination:
        raise HTTPException(status_code=400, detail="Invalid origin or destination")

    shipment_value = Decimal(input_data.cargo_value_usd)
    grand_total = Decimal(0)
    borders_response = []

    border = db.query(BorderPost).filter(BorderPost.border_name == "Beitbridge").first()
    legs = []

    # =========================
    # EXPORT LEG
    # =========================
    export_fees = []

    export_specials = db.query(CountrySpecialFee).filter(
        CountrySpecialFee.country_id == origin.id,
        CountrySpecialFee.is_active == True
    ).all()

    for fee in export_specials:
        export_fees.append(FeeDetail(
            fee_name=fee.fee_name,
            amount_zar=float(fee.amount_zar),
            fee_type="SPECIAL_FEE",
            payable_to=fee.payable_to or "Export Customs",
            description=fee.description
        ))
        grand_total += fee.amount_zar

    export_docs = []
    export_procedures = db.query(CustomsProcedure).filter(
        CustomsProcedure.country_id == origin.id,
        CustomsProcedure.procedure_type.ilike("%export%")
    ).all()

    for p in export_procedures:
        export_docs.extend(normalize_required_documents(p.required_documents_shipper))

    legs.append(BorderLegQuote(
        process_type="EXPORT",
        country=origin.name,
        fees=export_fees,
        required_documents=sorted(set(export_docs))
    ))

    # =========================
    # IMPORT LEG
    # =========================
    import_fees = []

    tariff = db.query(TariffSchedule).filter(
        TariffSchedule.country_id == destination.id,
        TariffSchedule.hs_code.startswith(input_data.cargo_hs_code)
    ).order_by(TariffSchedule.hs_code.desc()).first()

    import_duty = Decimal(0)

    if tariff:
        import_duty = shipment_value * (tariff.mfn_rate / 100)
        import_fees.append(FeeDetail(
            fee_name="Import Customs Duty",
            amount_zar=float(import_duty),
            fee_type="DUTY",
            payable_to="ZIMRA"
        ))
        grand_total += import_duty

    defense = db.query(TradeDefenseMeasure).filter(
        TradeDefenseMeasure.country_id == destination.id,
        TradeDefenseMeasure.hs_code.startswith(input_data.cargo_hs_code)
    ).first()

    dumping = Decimal(0)
    if defense:
        dumping = shipment_value * (defense.duty_rate / 100)
        import_fees.append(FeeDetail(
            fee_name="Trade Defence Duty",
            amount_zar=float(dumping),
            fee_type=defense.measure_type,
            payable_to="ZIMRA",
            description=defense.description
        ))
        grand_total += dumping

    vat_rate = destination.standard_vat_rate or Decimal(15)
    vat_base = shipment_value + import_duty + dumping
    vat_amount = vat_base * (vat_rate / 100)

    import_fees.append(FeeDetail(
        fee_name="Import VAT",
        amount_zar=float(vat_amount),
        fee_type="VAT",
        payable_to="ZIMRA"
    ))
    grand_total += vat_amount

    import_specials = db.query(CountrySpecialFee).filter(
        CountrySpecialFee.country_id == destination.id,
        CountrySpecialFee.is_active == True
    ).all()

    for fee in import_specials:
        import_fees.append(FeeDetail(
            fee_name=fee.fee_name,
            amount_zar=float(fee.amount_zar),
            fee_type="SPECIAL_FEE",
            payable_to=fee.payable_to or "ZIMRA",
            description=fee.description
        ))
        grand_total += fee.amount_zar

    import_docs = []
    import_procedures = db.query(CustomsProcedure).filter(
        CustomsProcedure.country_id == destination.id,
        CustomsProcedure.procedure_type.ilike("%import%")
    ).all()

    for p in import_procedures:
        import_docs.extend(normalize_required_documents(p.required_documents_shipper))

    legs.append(BorderLegQuote(
        process_type="IMPORT",
        country=destination.name,
        fees=import_fees,
        required_documents=sorted(set(import_docs))
    ))

    borders_response.append(BorderQuote(
        border_name=border.border_name,
        sequence_order=1,
        legs=legs
    ))

    return ShipmentQuoteOutput(
        grand_total_cost_zar=float(grand_total),
        borders=borders_response
    )