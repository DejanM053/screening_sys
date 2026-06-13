"""GET /export/{payment_id} — regulatory-format export (JSON/PDF)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fpdf import FPDF

from app.models import AuditLogRecord, ExportResponse


def build_export(payment_id: str, records: List[AuditLogRecord]) -> ExportResponse:
    return ExportResponse(
        payment_id=payment_id,
        records=records,
        generated_at=datetime.now(timezone.utc),
    )


def render_pdf(export: ExportResponse) -> bytes:
    """Render a regulator-facing PDF summary of the audit trail for a payment."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Sanctions Screening Audit Export", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Payment ID: {export.payment_id}", ln=True)
    pdf.cell(0, 8, f"Generated at: {export.generated_at.isoformat()}", ln=True)
    pdf.cell(0, 8, f"Records: {len(export.records)}", ln=True)
    pdf.ln(4)

    for record in export.records:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"Record #{record.id}", ln=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, f"Wallet address: {record.wallet_address or 'N/A'}")
        pdf.multi_cell(0, 6, f"Entity ID: {record.entity_id or 'N/A'}")
        pdf.multi_cell(0, 6, f"Screening timestamp: {record.screening_timestamp.isoformat()}")
        pdf.multi_cell(0, 6, f"Verdict: {record.verdict}")
        pdf.multi_cell(0, 6, f"Algorithm version: {record.algorithm_version}")
        pdf.multi_cell(
            0,
            6,
            f"List versions — OFAC: {record.list_version_ofac or 'N/A'}, "
            f"OFSI: {record.list_version_ofsi or 'N/A'}",
        )
        if record.retention_until:
            pdf.multi_cell(0, 6, f"Retain until: {record.retention_until.isoformat()}")
        pdf.ln(3)

    return bytes(pdf.output())
