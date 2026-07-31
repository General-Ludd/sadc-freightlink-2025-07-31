from __future__ import annotations
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import calendar, uuid

VAT_RATE = Decimal("0.15")

def money(value)->Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def calculate_vat(amount):
    return money(amount) * VAT_RATE

def calculate_total_excl_vat(amount):
    return money(amount)

def calculate_total_incl_vat(amount):
    return money(amount) + calculate_vat(amount)

def is_business_day(d:date)->bool:
    return d.weekday()<5

def next_business_day(d:date)->date:
    while not is_business_day(d):
        d += timedelta(days=1)
    return d

def add_business_days(start:date, days:int)->date:
    current=start
    added=0
    while added<days:
        current+=timedelta(days=1)
        if is_business_day(current):
            added+=1
    return current

def calculate_due_date(trigger_date:date,payment_days:int)->date:
    return next_business_day(trigger_date+timedelta(days=payment_days))

def next_statement_date(today:date, cycle:str, days=None)->date:
    days=days or []
    if cycle=="Twice Monthly" and days:
        days=sorted(days)
        for d in days:
            if today.day<=d:
                return date(today.year,today.month,d)
        y,m=today.year,today.month+1
        if m==13:
            y,m=y+1,1
        return date(y,m,days[0])
    if cycle=="Monthly":
        last=calendar.monthrange(today.year,today.month)[1]
        return date(today.year,today.month,last)
    return today

def generate_reference(prefix:str)->str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"

def generate_invoice_number(invoice_type:str)->str:
    stamp=datetime.utcnow().strftime("%Y%m%d")
    return f"INV-{invoice_type[:3].upper()}-{stamp}-{uuid.uuid4().hex[:6].upper()}"