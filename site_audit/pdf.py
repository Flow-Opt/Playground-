from __future__ import annotations

import io
from dataclasses import asdict
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .audit import AuditReport


def render_pdf(report: AuditReport) -> bytes:
    """Render a lightweight, FlowOpt-branded PDF summary.

    Intentionally simple so it runs locally without external services.
    """

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="FlowOpt – Automatiseringspotentieel",
    )

    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body = styles["BodyText"]

    story = []

    story.append(Paragraph("FlowOpt – Automatiseringspotentieel Scan", h1))
    story.append(Paragraph(f"Gegenereerd: {datetime.now().strftime('%Y-%m-%d %H:%M')}", body))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Samenvatting", h2))

    summary = [
        ["URL (input)", report.input_url],
        ["Finale URL", report.final_url],
        ["HTTP status", str(report.http_status)],
        ["Redirects", str(report.redirect_count)],
        ["Score (0–100)", str(report.score)],
        ["Aanbevolen aanpak", report.recommendation],
    ]

    t = Table(summary, colWidths=[45 * mm, 125 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (1, 0), colors.whitesmoke),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )

    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Signalen", h2))
    signals = [
        ["robots.txt", "aanwezig" if report.robots.present else "ontbreekt"],
        ["robots Disallow", "ja" if report.robots.any_disallow else "nee"],
        ["sitemap.xml", "aanwezig" if report.sitemap_present else "ontbreekt"],
        ["Login formulier", "ja" if report.login_form_detected else "nee"],
        ["CAPTCHA hints", "ja" if report.captcha_hints_detected else "nee"],
        ["Structured data", "ja" if report.structured_data_detected else "nee"],
        ["RSS/Atom", "ja" if report.feed_detected else "nee"],
        ["API hints", "ja" if report.api_hints_detected else "nee"],
        ["Platform hints", ", ".join(report.platform_hints) if report.platform_hints else "-"],
    ]

    t2 = Table(signals, colWidths=[45 * mm, 125 * mm])
    t2.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )

    story.append(t2)
    story.append(Spacer(1, 10))

    if report.reasons:
        story.append(Paragraph("Waarom deze score", h2))
        for r in report.reasons:
            story.append(Paragraph(f"• {r}", body))
        story.append(Spacer(1, 6))

    if report.warnings:
        story.append(Paragraph("Waarschuwingen", h2))
        for w in report.warnings:
            story.append(Paragraph(f"• {w}", body))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "Disclaimer: Dit is een heuristische triage-scan. Controleer altijd robots.txt/ToS en juridische kaders voordat je data verzamelt of automatiseert.",
            body,
        )
    )

    doc.build(story)
    return buf.getvalue()
