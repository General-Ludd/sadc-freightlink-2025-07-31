"""
invoice_builder.py
Universal invoice builder.
"""
from decimal import Decimal
from services.finance.finance_utils import (
    generate_invoice_number,
    calculate_vat,
    calculate_total_excl_vat,
    calculate_total_incl_vat,
)

class InvoiceBuilder:
    def build_shipment_invoice(self, shipment)->dict:
        subtotal=Decimal(str(shipment.total_amount))
        return self._build(
            "SHIPMENT",
            shipment.reference_number,
            [{
                "description": f"Freight Charge {shipment.origin} -> {shipment.destination}",
                "quantity":1,
                "unit_price":float(subtotal),
                "total":float(subtotal)
            }]
        )

    def build_lane_invoice(self,lane)->dict:
        return self._build("LANE",lane.reference_number,[])

    def build_interim_invoice(self,billing_cycle:str,invoices:list)->dict:
        subtotal=sum(Decimal(str(i["subtotal"])) for i in invoices)
        return self._build("INTERIM",billing_cycle,[],subtotal)

    def _build(self,invoice_type,reference,line_items,subtotal=None):
        if subtotal is None:
            subtotal=sum(Decimal(str(i["total"])) for i in line_items)
        vat=calculate_vat(subtotal)
        total=calculate_total_incl_vat(subtotal)
        return {
            "invoice_number":generate_invoice_number(invoice_type),
            "invoice_type":invoice_type,
            "reference":reference,
            "line_items":line_items,
            "subtotal":float(calculate_total_excl_vat(subtotal)),
            "vat":float(vat),
            "total":float(total),
            "status":"DRAFT"
        }