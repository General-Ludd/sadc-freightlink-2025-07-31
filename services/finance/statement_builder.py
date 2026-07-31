"""
statement_builder.py
Builds invoice batches for statement submissions.
"""
from decimal import Decimal

class StatementBuilder:
    def build_statement(self, financial_account, invoices:list):
        subtotal=Decimal("0")
        vat=Decimal("0")
        total=Decimal("0")
        refs=[]
        for inv in invoices:
            subtotal+=Decimal(str(inv.total if hasattr(inv,"total") else inv.get("total",0)))
            vat+=Decimal(str(inv.vat if hasattr(inv,"vat") else inv.get("vat",0)))
            refs.append(inv.id if hasattr(inv,"id") else inv.get("invoice_number"))
        total=subtotal
        return {
            "company_id": getattr(financial_account,"company_id",None),
            "financial_account_id": getattr(financial_account,"id",None),
            "invoice_count": len(invoices),
            "invoice_references": refs,
            "subtotal": float(subtotal),
            "vat": float(vat),
            "total": float(total),
            "status":"READY_FOR_SUBMISSION"
        }

    def filter_pending_invoices(self,invoices):
        return [i for i in invoices if not getattr(i,"is_paid",False)]

statement_builder=StatementBuilder()