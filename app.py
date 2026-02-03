from __future__ import annotations

import io
import json
from dataclasses import asdict
from datetime import datetime

import streamlit as st

from site_audit.audit import audit_url
from site_audit.pdf import render_pdf


st.set_page_config(
    page_title="FlowOpt – Automatiseringspotentieel Scan",
    page_icon="🧪",
    layout="centered",
)


def _badge(score: int) -> tuple[str, str]:
    if score >= 75:
        return "HOOG", "#16a34a"
    if score >= 50:
        return "MIDDEL", "#ca8a04"
    return "LAAG", "#dc2626"


st.title("FlowOpt – Automatiseringspotentieel Scan")
st.caption("Vul een URL in en ontvang een score (0–100) + advies voor de beste automatiseringsaanpak.")

with st.sidebar:
    st.header("Instellingen")
    timeout = st.slider("Timeout per request (seconden)", min_value=3, max_value=30, value=12, step=1)
    user_agent = st.text_input(
        "User-Agent",
        value="FlowOptSiteAudit/0.1 (+https://www.flowopt.nl)",
        help="Sommige sites blokkeren onbekende user agents.",
    )
    st.divider()
    st.caption("Let op: dit is een heuristische scan. Check altijd robots.txt/ToS en haal geen data op die je niet mag gebruiken.")

url = st.text_input("Website URL", placeholder="https://example.com")

col1, col2 = st.columns([1, 1])
with col1:
    run = st.button("Scan uitvoeren", type="primary", use_container_width=True)
with col2:
    st.button("Reset", use_container_width=True, on_click=lambda: st.session_state.clear())

if run:
    if not url.strip():
        st.error("Vul een geldige URL in.")
        st.stop()

    with st.spinner("Bezig met scannen…"):
        report = audit_url(url, timeout=float(timeout), user_agent=user_agent)

    score = int(report.score)
    label, color = _badge(score)

    st.subheader("Resultaat")
    st.markdown(
        f"""
<div style="border:1px solid #e5e7eb;border-radius:12px;padding:14px 16px;">
  <div style="display:flex;align-items:center;gap:12px;">
    <div style="font-size:28px;font-weight:700;">{score}</div>
    <div style="font-size:14px;">
      <div><b>Score (0–100)</b></div>
      <div style="color:{color};font-weight:700;">{label}</div>
    </div>
  </div>
  <div style="margin-top:10px;"><b>Aanbevolen aanpak:</b> {report.recommendation}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.write("")
    st.write(f"**Finale URL:** {report.final_url}")
    st.write(f"**HTTP status:** {report.http_status}  |  **Redirects:** {report.redirect_count}")

    st.subheader("Signalen")
    c1, c2, c3 = st.columns(3)
    c1.metric("robots.txt", "aanwezig" if report.robots.present else "ontbreekt")
    c2.metric("sitemap.xml", "aanwezig" if report.sitemap_present else "ontbreekt")
    c3.metric("Login formulier", "ja" if report.login_form_detected else "nee")

    c4, c5, c6 = st.columns(3)
    c4.metric("CAPTCHA hints", "ja" if report.captcha_hints_detected else "nee")
    c5.metric("Structured data", "ja" if report.structured_data_detected else "nee")
    c6.metric("API hints", "ja" if report.api_hints_detected else "nee")

    if report.platform_hints:
        st.write(f"**Platform hints:** {', '.join(report.platform_hints)}")

    st.subheader("Toelichting")
    if report.reasons:
        st.markdown("**Waarom deze score:**")
        for r in report.reasons:
            st.write(f"- {r}")

    if report.warnings:
        st.markdown("**Waarschuwingen:**")
        for w in report.warnings:
            st.warning(w)

    st.subheader("Rapport")

    payload = asdict(report)
    payload["generated_at"] = datetime.now().isoformat(timespec="seconds")

    json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    st.download_button(
        "Download JSON",
        data=json_bytes,
        file_name="flowopt-site-audit.json",
        mime="application/json",
        use_container_width=True,
    )

    # PDF (FlowOpt branded, simple)
    pdf = render_pdf(report)
    st.download_button(
        "Download PDF (FlowOpt)",
        data=pdf,
        file_name="flowopt-site-audit.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    with st.expander("Bekijk JSON in de app"):
        st.code(json.dumps(payload, indent=2, ensure_ascii=False), language="json")
