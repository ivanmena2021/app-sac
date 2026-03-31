"""Página: Dashboard Nacional — KPIs y status."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import io
import pandas as pd
import streamlit as st
from datetime import datetime

from shared.state import require_data, get_datos
from shared.components import render_metric, page_header, footer

require_data()
datos = get_datos()

page_header("Dashboard Nacional",
            "Panel de indicadores clave del Seguro Agrícola Catastrófico a nivel nacional")

# Status banner
ts = st.session_state.get("update_timestamp", "---")
source = st.session_state.get("source", "manual")
source_label = "descarga automática" if source == "auto" else "carga manual"
extra = ""
if source == "auto":
    r = st.session_state.get("rimac_rows", "?")
    l = st.session_state.get("lp_rows", "?")
    extra = f" | Rímac: {r:,} + La Positiva: {l:,} filas"

st.markdown(f'<div class="status-banner"><div class="dot"></div>'
            f'<span>Datos actualizados: {ts} ({source_label}){extra}</span></div>',
            unsafe_allow_html=True)

# Banner de notificaciones del semáforo
try:
    from semaforo_alertas import get_notification_banner_html
    notif_html = get_notification_banner_html(datos)
    if notif_html:
        st.markdown(notif_html, unsafe_allow_html=True)
except Exception:
    pass

# Botones: descargar consolidado + nueva actualización
col_spacer, col_dl, col_ref = st.columns([2, 1, 1])
with col_dl:
    try:
        df_clean = datos["midagri"].copy()
        for col in df_clean.columns:
            if df_clean[col].dtype == "object":
                df_clean[col] = df_clean[col].astype(str).replace("nan", "")
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_clean.to_excel(writer, index=False, sheet_name="Consolidado SAC")
            if "EMPRESA" in df_clean.columns:
                for emp in sorted(df_clean["EMPRESA"].dropna().unique()):
                    if str(emp).strip() in ("", "nan"):
                        continue
                    df_clean[df_clean["EMPRESA"] == emp].to_excel(
                        writer, index=False, sheet_name=str(emp)[:31])
        buf.seek(0)
        st.download_button(
            "📥 Descargar consolidado", data=buf.getvalue(),
            file_name=f"Consolidado_SAC_2025-2026_{datos['fecha_corte'].replace('/', '-')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_consolidado", use_container_width=True)
    except Exception as e:
        st.error(f"Error: {e}")

with col_ref:
    if st.button("🔄 Nueva actualización", key="refresh_data"):
        st.session_state["processed"] = False
        st.session_state.pop("datos", None)
        st.switch_page("pages/inicio.py")

# KPIs
st.markdown("""
<div class="section-header">
    <div class="icon-box" style="background:#e8f4f8;">📊</div>
    <h3>Panel Nacional</h3>
</div>
""", unsafe_allow_html=True)

row1 = st.columns(4)
m1 = [
    ("Avisos Reportados", f"{datos['total_avisos']:,}", None, "blue"),
    ("Avance Evaluación", f"{datos['pct_ajustados']:.1f}%", f"{datos['total_ajustados']:,} cerrados", "green"),
    ("Indemnización", f"S/ {datos['monto_indemnizado']:,.0f}", None, "amber"),
    ("Avance Desembolso", f"{datos['pct_desembolso']:.1f}%", f"S/ {datos['monto_desembolsado']:,.0f}", "green"),
]
for col, (label, value, delta, accent) in zip(row1, m1):
    with col:
        st.markdown(render_metric(label, value, delta, accent), unsafe_allow_html=True)

st.markdown('<div style="height: 0.5rem;"></div>', unsafe_allow_html=True)

row2 = st.columns(4)
m2 = [
    ("Ha Aseguradas", f"{datos['sup_asegurada']:,.0f}", None, "blue"),
    ("Ha Indemnizadas", f"{datos['ha_indemnizadas']:,.0f}", None, "amber"),
    ("Siniestralidad", f"{datos['indice_siniestralidad']:.2f}%", None, "purple"),
    ("Productores", f"{int(datos['productores_desembolso']):,}", "beneficiados", "green"),
]
for col, (label, value, delta, accent) in zip(row2, m2):
    with col:
        st.markdown(render_metric(label, value, delta, accent), unsafe_allow_html=True)

# Navegación rápida
st.markdown("---")
st.markdown("**Acceso rápido:**")
c1, c2, c3, c4 = st.columns(4)
with c1:
    if st.button("🔍 Consultas", use_container_width=True, key="nav_consultas"):
        st.switch_page("pages/consultas.py")
with c2:
    if st.button("🗺️ Mapa de Calor", use_container_width=True, key="nav_mapa"):
        st.switch_page("pages/mapa_calor.py")
with c3:
    if st.button("📥 Reportes", use_container_width=True, key="nav_reportes"):
        st.switch_page("pages/reportes.py")
with c4:
    if st.button("🚦 Semáforo", use_container_width=True, key="nav_semaforo"):
        st.switch_page("pages/semaforo_page.py")

footer()
