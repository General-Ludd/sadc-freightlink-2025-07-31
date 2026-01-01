from fastapi import APIRouter, Depends, HTTPException, status
from requests import Session
from typing import Optional
from datetime import timedelta
from utils.administration_auth import verify_admin_password, get_current_admin
from models.nexus.customs_territories import Country, Customs_Duty_Authority, CountryTradeAgreement, BorderPost, BorderClearanceProfile, TariffSchedule, TradeDefenseMeasure, CountrySpecialFee, TransitBondFee, CustomsProcedure, ExciseTaxRate, AntiDumpingMeasure, CurrencyExchangeRate
from schemas.nexus.customs import CountryBase, Customs_Duty_Authority_Base, CountryTradeAgreementBase, TariffScheduleBase, CountrySpecialFeeBase, TransitBondFeeBase, TradeDefenseMeasureBase

def admin_create_country(
    db: Session,
    country_data: CountryBase,  # Should be CountryCreate if you want to include all fields
    authority_data: Customs_Duty_Authority_Base,
):
    # Note: CountryBase doesn't include 'name' field, but your Country model likely needs it
    # You might need to use CountryCreate instead
    country = Country(
        iso_code=country_data.iso_code,
        name=country_data.name,  # This field exists in CountryBase
        currency_code=country_data.currency_code,
        is_sadc_member=country_data.is_sadc_member,
        is_comesa_member=country_data.is_comesa_member,  # Fixed typo
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

    return {"country_id": country.id, "authority_id": authority.id}  # Fixed return


def create_customs_authority(
    country_id: int,
    db: Session,
    authority_data: Customs_Duty_Authority_Base,
):
    try:
        country = db.query(Country).filter(Country.id == country_id).first()
        if not country:
            raise HTTPException(status_code=404, detail="Country not found")

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
        return authority
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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


def create_tariff_schedule(  # Fixed function name spelling
    country_id: int,
    db: Session,
    tariff_data: TariffScheduleBase,
):
    try:
        country = db.query(Country).filter(Country.id == country_id).first()
        if not country:
            raise HTTPException(status_code=404, detail="Country not found")

        tariff = TariffSchedule(
            country_id=country.id,  # Added comma
            hs_code=tariff_data.hs_code,  # Added comma
            hs_description=tariff_data.hs_description,
            mfn_rate=tariff_data.mfn_rate,
            preferential_rate=tariff_data.preferential_rate,
            agreement_source=tariff_data.agreement_source,
            uom=tariff_data.uom,  # Added comma
            excise_duty_rate=tariff_data.excise_duty_rate,
            start_date=tariff_data.start_date,
            end_date=tariff_data.end_date
        )
        db.add(tariff)  # Fixed variable name
        db.commit()
        db.refresh(tariff)
        return tariff
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def create_trade_defense_measure(
    country_id: int,
    db: Session,
    measure_data: TradeDefenseMeasureBase,
):
    try:
        country = db.query(Country).filter(Country.id == country_id).first()  # Added parentheses
        if not country:
            raise HTTPException(status_code=404, detail="Country not found")

        measure = TradeDefenseMeasure(
            country_id=country_id,  # Use the parameter, not from measure_data
            measure_type=measure_data.measure_type,  # Added comma
            hs_code=measure_data.hs_code,
            exporting_country_iso=measure_data.exporting_country_iso,
            description=measure_data.description,
            duty_rate=measure_data.duty_rate,
            effective_date=measure_data.effective_date,
            expiry_date=measure_data.expiry_date,
            legal_reference=measure_data.legal_reference,
        )
        db.add(measure)
        db.commit()
        db.refresh(measure)
        return measure
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def create_special_fee(
    country_id: int,
    db: Session,
    fee_data: CountrySpecialFeeBase,  # Now this schema exists
):
    try: 
        country = db.query(Country).filter(Country.id == country_id).first()
        if not country:
            raise HTTPException(status_code=404, detail="Country not found")

        fee = CountrySpecialFee(
            country_id=country.id,
            fee_code=fee_data.fee_code,
            fee_name=fee_data.fee_name,
            amount_zar=fee_data.amount_zar,
            percentage_rate=fee_data.percentage_rate,
            threshold_amount_zar=fee_data.threshold_amount_zar,
            description=fee_data.description,
            payable_to=fee_data.payable_to,
            is_mandatory=fee_data.is_mandatory,
            is_active=fee_data.is_active,
            effective_date=fee_data.effective_date,
            expiry_date=fee_data.expiry_date,
        )
        db.add(fee)
        db.commit()
        db.refresh(fee)
        return fee
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))  # Fixed missing parentheses


def create_transit_bond(
    country_id: int,
    db: Session,
    bond_data: TransitBondFeeBase,  # Now this schema exists
):
    try:
        country = db.query(Country).filter(Country.id == country_id).first()
        if not country:
            raise HTTPException(status_code=404, detail="Country not found")

        bond = TransitBondFee(
            country_id=country.id,
            amount_zar=bond_data.amount_zar,
            bond_validity_days=bond_data.bond_validity_days,
            description=bond_data.description,
            is_active=bond_data.is_active,
            effective_date=bond_data.effective_date,
            expiry_date=bond_data.expiry_date,
        )
        db.add(bond)
        db.commit()
        db.refresh(bond)
        return bond
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))  # Fixed missing parentheses