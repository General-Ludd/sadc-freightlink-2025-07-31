from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from datetime import timedelta
from utils.administration_auth import verify_admin_password, get_current_admin
from models.nexus.customs_territories import Country, Customs_Duty_Authority, CountryTradeAgreement, BorderPost, BorderClearanceProfile, TariffSchedule, TradeDefenseMeasure, CountrySpecialFee, TransitBondFee, CustomsProcedure, ExciseTaxRate, AntiDumpingMeasure, CurrencyExchangeRate
from schemas.nexus.customs import CountryBase, Customs_Duty_Authority_Base, CountryTradeAgreementBase, TariffScheduleBase

def admin_create_country(
    db: Session,
    country_data: CountryBase,
    authority_data: Customs_Duty_Authority_Base,
):
    country = Country(
        iso_code=country_data.iso_code,
        name=country_data.name,
        currency_code=country_data.currency_code,
        is_sadc_member=country_data.is_sadc_member,
        is_comesa_member=country_data.is_comesa_member,
        is_sacu_member=country_data.is_sacu_member,
        requires_ctn=country_data.requires_ctn,
        standard_vat_rate=country_data.standard_vat_rate,
        is_active=country_data.is_active,
    )
    db.add(country)
    db.commit()
    db.refresh(country)

    authority = Customs_Duty_Authority(
        country_id=country.id,
        country=country.name,
        agency_name=authority_data.agency_name,
        agency_code=authority_data.agency_code,
        bank_name=authority_data.bank_name,
        branch_code=authority_data.branch_code,
        bank_account_number=authority_data.bank_account_number,
        account_type=authority_data.account_type,
        website=authority_data.website,
        email=authority_data.email,
        phone_number=authority_data.phone_number,
    )
    db.add(authority)
    db.commit()
    db.refresh(authority)

    # Step 6: Return all details
    return {"shipment_id": shipment.id}


def create_trade_agreement(
    country_id: int,
    db: Session,
    agreement_data: CountryTradeAgreementBase,
):
    agreement = CountryTradeAgreement(
        country_id=country_id,
        agreement_name=agreement_data.agreement_name,
        agreement_code=agreement_data.agreement_code,
        is_active=agreement_data.is_active,
        effective_date=agreement_data.effective_date,
        notes=agreement_data.notes,
    )
    db.add(agreement)
    db.commit()
    db.refresh(agreement)
    return agreement