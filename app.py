"""
App SAC — Generador Automático de Reportes del Seguro Agrícola Catastrófico
Interfaz Streamlit — Versión 2.0 (Diseño renovado)
"""

import streamlit as st
import os
import sys
import io
from datetime import datetime

# Agregar directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

from data_processor import process_dynamic_data, get_departamento_data
from gen_word_bridge_py import generate_nacional_docx, generate_departamental_docx
from gen_excel_eme import generate_reporte_eme
from gen_word_operatividad import generate_operatividad_docx
from gen_ppt_dinamico import generar_ppt_dinamico
from query_engine import process_query, get_suggested_queries as get_suggested_basic
from query_llm import process_query_llm, is_llm_available, get_suggested_queries as get_suggested_llm
from gen_mapa_calor import generate_map, get_ranking_table, get_summary_cards, NIVELES, get_metricas_for_nivel
from comparativo_campanias import (
    load_campania_anterior, generate_comparison_chart, get_comparison_table,
    get_monthly_detail_table, METRICAS_COMPARACION,
)

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE PÁGINA
# ═══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SAC 2025-2026 — Reportes",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════════════════
# CSS PREMIUM
# ═══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* ══════════════════════════════════════════
       GLOBAL RESET & BASE
       ══════════════════════════════════════════ */
    .block-container { padding-top: 0.8rem; max-width: 1200px; }
    [data-testid="stSidebar"] { background: #f8fafc; }
    [data-testid="stAppViewBlockContainer"] { background: #f4f7fa; }

    /* ══════════════════════════════════════════
       HERO HEADER — Gradient con pattern sutil
       ══════════════════════════════════════════ */
    .hero {
        background: linear-gradient(135deg, #0c2340 0%, #1a5276 35%, #2980b9 70%, #3498db 100%);
        padding: 1.8rem 2.5rem;
        border-radius: 18px;
        margin-bottom: 1.2rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 8px 32px rgba(12,35,64,0.25);
    }
    .hero::before {
        content: '';
        position: absolute;
        top: -60%;
        right: -15%;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
        border-radius: 50%;
    }
    .hero::after {
        content: '';
        position: absolute;
        bottom: -40%;
        left: -10%;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(46,204,113,0.08) 0%, transparent 70%);
        border-radius: 50%;
    }
    .hero h1 {
        color: #fff !important;
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0 0 0.2rem 0;
        position: relative;
        letter-spacing: -0.3px;
    }
    .hero .subtitle {
        color: rgba(255,255,255,0.75);
        font-size: 0.9rem;
        margin: 0;
        position: relative;
        font-weight: 400;
    }
    .hero .hero-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: relative;
    }
    .hero .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(255,255,255,0.12);
        color: rgba(255,255,255,0.9);
        padding: 0.3rem 0.9rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 500;
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.1);
    }

    /* ══════════════════════════════════════════
       ACTION CARD — Pantalla inicial
       ══════════════════════════════════════════ */
    .action-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        padding: 2.5rem 2rem;
        text-align: center;
        box-shadow: 0 4px 24px rgba(0,0,0,0.04);
        transition: all 0.3s ease;
    }
    .action-card:hover {
        box-shadow: 0 8px 40px rgba(0,0,0,0.08);
        transform: translateY(-3px);
    }
    .action-card h2 {
        color: #0c2340;
        margin: 0.8rem 0 0.4rem;
        font-size: 1.5rem;
        font-weight: 700;
    }
    .action-card p {
        color: #64748b;
        font-size: 0.9rem;
        margin: 0;
        max-width: 500px;
        margin-left: auto;
        margin-right: auto;
        line-height: 1.6;
    }

    /* ══════════════════════════════════════════
       STEPPER — Progreso de descarga
       ══════════════════════════════════════════ */
    .stepper {
        display: flex;
        justify-content: center;
        gap: 0;
        margin: 1.5rem 0;
        padding: 0 1rem;
    }
    .step {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .step-circle {
        width: 38px;
        height: 38px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.85rem;
        flex-shrink: 0;
        transition: all 0.3s ease;
    }
    .step-pending .step-circle { background: #e8ecf1; color: #94a3b8; }
    .step-active .step-circle { background: #2980b9; color: #fff; animation: pulse 1.5s infinite; }
    .step-done .step-circle { background: #27ae60; color: #fff; }
    .step-error .step-circle { background: #e74c3c; color: #fff; }
    .step-label { font-size: 0.82rem; font-weight: 500; }
    .step-pending .step-label { color: #94a3b8; }
    .step-active .step-label { color: #2980b9; font-weight: 600; }
    .step-done .step-label { color: #27ae60; }
    .step-error .step-label { color: #e74c3c; }
    .step-connector { width: 40px; height: 2px; background: #e2e8f0; margin: 0 0.3rem; align-self: center; }
    .step-connector.done { background: #27ae60; }
    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(41,128,185,0.4); }
        50% { box-shadow: 0 0 0 10px rgba(41,128,185,0); }
    }

    /* ══════════════════════════════════════════
       METRIC CARDS — Dashboard
       ══════════════════════════════════════════ */
    .metric-card-v2 {
        background: white;
        border-radius: 14px;
        padding: 1.2rem 1.3rem;
        border: 1px solid #e8ecf1;
        box-shadow: 0 2px 12px rgba(0,0,0,0.03);
        transition: all 0.25s ease;
    }
    .metric-card-v2:hover {
        box-shadow: 0 6px 24px rgba(0,0,0,0.07);
        transform: translateY(-2px);
    }
    .metric-card-v2 .label {
        color: #64748b;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .metric-card-v2 .value {
        color: #0c2340;
        font-size: 1.4rem;
        font-weight: 800;
        line-height: 1.2;
    }
    .metric-card-v2 .delta {
        font-size: 0.78rem;
        margin-top: 0.3rem;
        font-weight: 500;
    }
    .delta-positive { color: #27ae60; }
    .delta-neutral { color: #64748b; }
    .delta-warning { color: #f39c12; }

    /* Acentos */
    .accent-blue { border-left: 4px solid #2980b9; }
    .accent-green { border-left: 4px solid #27ae60; }
    .accent-amber { border-left: 4px solid #f39c12; }
    .accent-purple { border-left: 4px solid #8e44ad; }
    .accent-red { border-left: 4px solid #e74c3c; }

    /* ══════════════════════════════════════════
       REPORT CARDS — Pantalla inicial
       ══════════════════════════════════════════ */
    .report-card {
        background: white;
        border: 1px solid #e8ecf1;
        border-radius: 16px;
        padding: 1.6rem;
        height: 100%;
        box-shadow: 0 2px 12px rgba(0,0,0,0.03);
        transition: all 0.25s ease;
    }
    .report-card:hover {
        box-shadow: 0 6px 24px rgba(0,0,0,0.07);
        transform: translateY(-2px);
    }
    .report-card .icon {
        font-size: 2rem;
        margin-bottom: 0.6rem;
        display: inline-block;
        width: 52px;
        height: 52px;
        line-height: 52px;
        text-align: center;
        background: #f0f7ff;
        border-radius: 14px;
    }
    .report-card h3 {
        color: #0c2340;
        margin: 0.5rem 0;
        font-size: 1.05rem;
        font-weight: 700;
    }
    .report-card p {
        color: #64748b;
        font-size: 0.83rem;
        margin: 0.3rem 0 0;
        line-height: 1.6;
    }

    /* ══════════════════════════════════════════
       STATUS BANNER — Datos actualizados
       ══════════════════════════════════════════ */
    .status-banner {
        background: linear-gradient(90deg, #e8f8ee 0%, #d4f1de 100%);
        border: 1px solid #b8e6c8;
        border-radius: 12px;
        padding: 0.7rem 1.2rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin: 0.5rem 0;
    }
    .status-banner .dot {
        width: 8px;
        height: 8px;
        background: #27ae60;
        border-radius: 50%;
        animation: blink 2s infinite;
        flex-shrink: 0;
    }
    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }
    .status-banner span {
        color: #155724;
        font-size: 0.82rem;
        font-weight: 500;
    }

    /* ══════════════════════════════════════════
       SECTION HEADERS
       ══════════════════════════════════════════ */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin: 1rem 0 0.8rem;
    }
    .section-header .icon-box {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        flex-shrink: 0;
    }
    .section-header h3 {
        color: #0c2340;
        font-size: 1.15rem;
        font-weight: 700;
        margin: 0;
    }

    /* ══════════════════════════════════════════
       TABS — Navegación principal (2 tabs)
       ══════════════════════════════════════════ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: linear-gradient(135deg, #0c2340 0%, #1a5276 100%);
        border-radius: 14px;
        padding: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 12px 28px;
        font-weight: 600;
        font-size: 0.95rem;
        color: rgba(255,255,255,0.7);
        transition: all 0.25s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255,255,255,0.12);
        color: rgba(255,255,255,0.95);
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: white !important;
        box-shadow: 0 3px 12px rgba(0,0,0,0.15);
        color: #0c2340 !important;
        font-weight: 700;
    }
    .stTabs [data-baseweb="tab-highlight"] {
        display: none;
    }
    .stTabs [data-baseweb="tab-border"] {
        display: none;
    }

    /* ══════════════════════════════════════════
       SUB-TABS — Navegación secundaria (nested)
       ══════════════════════════════════════════ */
    .stTabs .stTabs [data-baseweb="tab-list"] {
        background: #edf2f7;
        border-radius: 10px;
        padding: 3px;
        gap: 2px;
        margin-top: 0.5rem;
    }
    .stTabs .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
        font-size: 0.84rem;
        color: #64748b;
    }
    .stTabs .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255,255,255,0.6);
        color: #1a5276;
    }
    .stTabs .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: white !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        color: #1a5276 !important;
        font-weight: 600;
    }

    /* ══════════════════════════════════════════
       TAB CONTENT CARDS — Contenido de reportes
       ══════════════════════════════════════════ */
    .tab-intro {
        background: linear-gradient(135deg, #f8fafc, #edf2f7);
        padding: 1.2rem 1.5rem;
        border-radius: 14px;
        border-left: 4px solid #2980b9;
        margin-bottom: 1rem;
    }
    .tab-intro .title {
        font-size: 1rem;
        font-weight: 700;
        color: #0c2340;
        margin-bottom: 0.3rem;
    }
    .tab-intro .desc {
        color: #64748b;
        font-size: 0.85rem;
        line-height: 1.6;
    }

    /* ══════════════════════════════════════════
       CHAT — Consulta area
       ══════════════════════════════════════════ */
    .chat-header {
        background: linear-gradient(135deg, #f0f7ff 0%, #e8f4f8 100%);
        padding: 1.3rem 1.5rem;
        border-radius: 14px;
        border-left: 4px solid #2980b9;
        margin-bottom: 1rem;
    }
    .chat-header .title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #0c2340;
    }
    .chat-header .subtitle {
        color: #64748b;
        font-size: 0.83rem;
        margin-top: 0.2rem;
    }
    .engine-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        padding: 0.3rem 0.9rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .sug-btn {
        display: inline-block;
        background: white;
        border: 1px solid #dce4ec;
        border-radius: 10px;
        padding: 0.5rem 0.8rem;
        font-size: 0.8rem;
        color: #475569;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .sug-btn:hover {
        border-color: #2980b9;
        color: #2980b9;
        background: #f0f7ff;
    }

    .query-result-box {
        background: white;
        padding: 1.5rem;
        border-radius: 14px;
        border: 1px solid #e2e8f0;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 0.92rem;
        line-height: 1.75;
        color: #1a1a1a;
        white-space: pre-wrap;
        box-shadow: 0 2px 12px rgba(0,0,0,0.03);
    }
    .query-context {
        background: #f0f7ff;
        padding: 0.6rem 1rem;
        border-radius: 10px;
        margin-bottom: 0.8rem;
        color: #1a5276;
        font-size: 0.83rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* ══════════════════════════════════════════
       FOOTER
       ══════════════════════════════════════════ */
    .footer {
        text-align: center;
        color: #94a3b8;
        font-size: 0.72rem;
        padding: 1.5rem 0 1rem 0;
        border-top: 1px solid #e2e8f0;
        margin-top: 2rem;
    }

    /* ══════════════════════════════════════════
       BUTTONS & MISC
       ══════════════════════════════════════════ */
    #MainMenu {visibility: hidden;}

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0c2340, #1a5276, #2980b9) !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 0.65rem 1.8rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.3px !important;
        box-shadow: 0 4px 14px rgba(41,128,185,0.25) !important;
        transition: all 0.25s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 22px rgba(41,128,185,0.35) !important;
        transform: translateY(-2px) !important;
    }

    .streamlit-expanderHeader {
        background: #f8fafc;
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.9rem;
    }

    /* download buttons */
    .stDownloadButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        border: 1px solid #d1d9e0 !important;
        transition: all 0.2s ease !important;
    }
    .stDownloadButton > button:hover {
        border-color: #2980b9 !important;
        color: #2980b9 !important;
        background: #f0f7ff !important;
    }

    /* dataframes */
    .stDataFrame { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# FUNCIONES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════

def check_auto_download():
    """Verifica si la descarga automática está disponible."""
    try:
        from auto_download import descargar_rimac, descargar_lapositiva, descargar_ambos
        return True
    except ImportError:
        return False


def check_credentials():
    """Verifica si hay credenciales configuradas."""
    has_rimac = False
    has_lp = False
    try:
        has_rimac = bool(st.secrets.get("rimac", {}).get("email"))
        has_lp = bool(st.secrets.get("lapositiva", {}).get("usuario"))
    except Exception:
        pass
    if not has_rimac:
        has_rimac = bool(os.environ.get("RIMAC_EMAIL"))
    if not has_lp:
        has_lp = bool(os.environ.get("LP_USUARIO"))
    return has_rimac, has_lp


def render_stepper(steps: list):
    """Renderiza un stepper visual de progreso."""
    html_parts = []
    for i, (label, status) in enumerate(steps):
        icon = {"pending": str(i+1), "active": "⟳", "done": "✓", "error": "✗"}[status]
        html_parts.append(
            f'<div class="step step-{status}">'
            f'  <div class="step-circle">{icon}</div>'
            f'  <div class="step-label">{label}</div>'
            f'</div>'
        )
        if i < len(steps) - 1:
            conn_class = "done" if status == "done" else ""
            html_parts.append(f'<div class="step-connector {conn_class}"></div>')

    st.markdown(f'<div class="stepper">{"".join(html_parts)}</div>', unsafe_allow_html=True)


def render_metric(label, value, delta=None, accent="blue"):
    """Renderiza una tarjeta de métrica."""
    delta_html = ""
    if delta:
        delta_html = f'<div class="delta delta-positive">{delta}</div>'
    return (
        f'<div class="metric-card-v2 accent-{accent}">'
        f'  <div class="label">{label}</div>'
        f'  <div class="value">{value}</div>'
        f'  {delta_html}'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════════════
# HERO HEADER
# ═══════════════════════════════════════════════════════════════════════
hora_actual = datetime.now().strftime("%d/%m/%Y %H:%M")
st.markdown(f"""
<div class="hero">
    <div class="hero-row">
        <div>
            <h1>SAC 2025 — 2026</h1>
            <p class="subtitle">Sistema Automatizado de Reportes · Seguro Agrícola Catastrófico</p>
        </div>
        <span class="badge">MIDAGRI · {hora_actual}</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# VERIFICACIONES INICIALES
# ═══════════════════════════════════════════════════════════════════════
auto_available = check_auto_download()
has_rimac, has_lp = check_credentials()
has_all_creds = has_rimac and has_lp


# ═══════════════════════════════════════════════════════════════════════
# ESTADO PRINCIPAL — Sin datos procesados
# ═══════════════════════════════════════════════════════════════════════
if not st.session_state.get("processed"):

    # ─── Botón principal: Un solo click ───
    if auto_available and has_all_creds:
        st.markdown("""
        <div class="action-card">
            <div style="font-size: 3rem;">🚀</div>
            <h2>Actualización con un solo click</h2>
            <p>Descarga los datos más recientes de Rímac y La Positiva, los procesa
            automáticamente y genera el dashboard con todos los reportes listos.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("")  # spacer

        col_center = st.columns([1, 2, 1])[1]
        with col_center:
            btn_auto = st.button(
                "⚡ Actualizar Datos SAC",
                type="primary",
                use_container_width=True,
                key="btn_auto_main"
            )

        # ─── Proceso automático ───
        if btn_auto:
            from auto_download import descargar_rimac, descargar_lapositiva

            progress_placeholder = st.empty()
            status_placeholder = st.empty()

            # Paso 1: Descargar Rímac
            progress_placeholder.markdown("")
            render_stepper([
                ("Rímac", "active"),
                ("La Positiva", "pending"),
                ("Procesando", "pending"),
                ("Listo", "pending"),
            ])
            status_placeholder.info("📡 Conectando con SISGAQSAC (Rímac)...")

            try:
                df_siniestros = descargar_rimac()
                rimac_ok = True
                rimac_rows = len(df_siniestros)
            except Exception as e:
                rimac_ok = False
                status_placeholder.error(f"❌ Error al descargar de Rímac: {str(e)}")
                st.stop()

            # Paso 2: Descargar La Positiva
            progress_placeholder.empty()
            render_stepper([
                ("Rímac", "done"),
                ("La Positiva", "active"),
                ("Procesando", "pending"),
                ("Listo", "pending"),
            ])
            status_placeholder.info(f"✅ Rímac: {rimac_rows:,} filas · 📡 Conectando con Agroevaluaciones (~70s)...")

            try:
                df_midagri = descargar_lapositiva()
                lp_ok = True
                lp_rows = len(df_midagri)
            except Exception as e:
                lp_ok = False
                status_placeholder.error(f"❌ Error al descargar de La Positiva: {str(e)}")
                st.stop()

            # Paso 3: Procesar datos
            progress_placeholder.empty()
            render_stepper([
                ("Rímac", "done"),
                ("La Positiva", "done"),
                ("Procesando", "active"),
                ("Listo", "pending"),
            ])
            status_placeholder.info(
                f"✅ Rímac: {rimac_rows:,} filas · ✅ La Positiva: {lp_rows:,} filas · "
                f"⚙️ Procesando datos..."
            )

            try:
                buf_sin = io.BytesIO()
                df_siniestros.to_excel(buf_sin, index=False)
                buf_sin.seek(0)

                buf_mid = io.BytesIO()
                df_midagri.to_excel(buf_mid, index=False)
                buf_mid.seek(0)

                datos = process_dynamic_data(buf_mid, buf_sin)
                st.session_state["datos"] = datos
                st.session_state["processed"] = True
                st.session_state["update_timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                st.session_state["source"] = "auto"
                st.session_state["rimac_rows"] = rimac_rows
                st.session_state["lp_rows"] = lp_rows
            except Exception as e:
                status_placeholder.error(f"❌ Error al procesar datos: {str(e)}")
                st.stop()

            # Paso 4: Listo
            progress_placeholder.empty()
            render_stepper([
                ("Rímac", "done"),
                ("La Positiva", "done"),
                ("Procesando", "done"),
                ("Listo", "done"),
            ])
            status_placeholder.success(
                f"🎉 ¡Datos actualizados! Rímac ({rimac_rows:,}) + La Positiva ({lp_rows:,}) filas procesadas"
            )
            import time
            time.sleep(1.5)
            st.rerun()

        # ─── Alternativa manual colapsada ───
        st.markdown("")
        with st.expander("📂 Prefiero subir archivos manualmente"):
            st.markdown("Si tiene los archivos Excel descargados, puede subirlos directamente:")
            col_up1, col_up2 = st.columns(2)
            with col_up1:
                midagri_file = st.file_uploader(
                    "Archivo MIDAGRI (La Positiva)",
                    type=["xlsx"], key="midagri_manual",
                    help="Excel descargado de Agroevaluaciones — botón Midagri"
                )
            with col_up2:
                siniestros_file = st.file_uploader(
                    "Archivo Siniestros (Rímac)",
                    type=["xlsx"], key="siniestros_manual",
                    help="Excel descargado de SISGAQSAC"
                )

            if midagri_file and siniestros_file:
                if st.button("🚀 Procesar archivos", type="primary", key="proc_manual"):
                    with st.spinner("Procesando archivos subidos..."):
                        try:
                            datos = process_dynamic_data(midagri_file, siniestros_file)
                            st.session_state["datos"] = datos
                            st.session_state["processed"] = True
                            st.session_state["update_timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                            st.session_state["source"] = "manual"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al procesar: {str(e)}")

    # ─── Sin descarga automática: modo solo manual ───
    else:
        if not auto_available:
            st.info("ℹ️ Playwright no disponible. Use la carga manual de archivos.")
        elif not has_all_creds:
            missing = []
            if not has_rimac:
                missing.append("Rímac (RIMAC_EMAIL, RIMAC_PASSWORD)")
            if not has_lp:
                missing.append("La Positiva (LP_USUARIO, LP_PASSWORD)")
            st.warning(f"⚙️ Credenciales pendientes: {', '.join(missing)}")

        st.markdown("### 📂 Cargar archivos")
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            midagri_file = st.file_uploader(
                "📋 Archivo MIDAGRI (.xlsx)",
                type=["xlsx"], key="midagri_fallback"
            )
        with col_up2:
            siniestros_file = st.file_uploader(
                "📋 Archivo Siniestros (.xlsx)",
                type=["xlsx"], key="siniestros_fallback"
            )

        if midagri_file and siniestros_file:
            col_c = st.columns([1, 2, 1])[1]
            with col_c:
                if st.button("🚀 Procesar datos", type="primary", use_container_width=True, key="proc_fb"):
                    with st.spinner("Procesando..."):
                        try:
                            datos = process_dynamic_data(midagri_file, siniestros_file)
                            st.session_state["datos"] = datos
                            st.session_state["processed"] = True
                            st.session_state["update_timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                            st.session_state["source"] = "manual"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        else:
            st.markdown("")
            st.markdown(
                '<p style="text-align:center; color:#94a3b8;">Suba ambos archivos Excel para comenzar</p>',
                unsafe_allow_html=True,
            )

    # ─── Info cards en estado inicial ───
    st.markdown("---")
    st.markdown(
        '<h3 style="text-align:center; color:#1a5276;">¿Qué reportes genera esta app?</h3>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    col_r1, col_r2 = st.columns(2)
    col_r3, col_r4 = st.columns(2)

    with col_r1:
        st.markdown("""
        <div class="report-card">
            <div class="icon">📄</div>
            <h3>Ayuda Memoria Nacional</h3>
            <p>Resumen de operatividad SAC a nivel nacional: primas, cobertura,
            indemnizaciones, desembolsos y eventos de lluvias intensas.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_r2:
        st.markdown("""
        <div class="report-card">
            <div class="icon">🗺️</div>
            <h3>Ayuda Memoria Departamental</h3>
            <p>Detalle por cada departamento: proceso SAC, panorama general,
            tipo de siniestros y resumen operativo.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_r3:
        st.markdown("""
        <div class="report-card">
            <div class="icon">📋</div>
            <h3>Operatividad SAC</h3>
            <p>Ayuda Memoria de operatividad por empresa de seguros: siniestralidad,
            coberturas, cultivos priorizados y desembolsos por departamento.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_r4:
        st.markdown("""
        <div class="report-card">
            <div class="icon">📊</div>
            <h3>Reporte EME (Excel)</h3>
            <p>Formato de reporte de emergencia con acciones implementadas,
            en implementación y por implementar por región.</p>
        </div>
        """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
# ESTADO CON DATOS — DASHBOARD
# ═══════════════════════════════════════════════════════════════════════
else:
    datos = st.session_state["datos"]

    # ─── Status banner ───
    ts = st.session_state.get("update_timestamp", "—")
    source = st.session_state.get("source", "manual")
    source_label = "descarga automática" if source == "auto" else "carga manual"

    extra_info = ""
    if source == "auto":
        r_rows = st.session_state.get("rimac_rows", "?")
        lp_rows = st.session_state.get("lp_rows", "?")
        extra_info = f" · Rímac: {r_rows:,} filas · La Positiva: {lp_rows:,} filas"

    st.markdown(
        f'<div class="status-banner">'
        f'  <div class="dot"></div>'
        f'  <span>Datos actualizados: {ts} ({source_label}){extra_info}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ─── Botones: descargar consolidado + nueva actualización ───
    col_spacer, col_download, col_refresh = st.columns([2, 1, 1])
    with col_download:
        # Generar Excel consolidado (La Positiva + Rímac) para descarga
        def _build_consolidated_excel(midagri_df):
            """Genera un archivo Excel con base consolidada + hojas por empresa."""
            import io
            buf = io.BytesIO()
            # Limpiar columnas datetime para evitar errores de serialización
            df_clean = midagri_df.copy()
            for col in df_clean.columns:
                if df_clean[col].dtype == "object":
                    df_clean[col] = df_clean[col].astype(str).replace("nan", "")
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_clean.to_excel(writer, index=False, sheet_name="Consolidado SAC")
                if "EMPRESA" in df_clean.columns:
                    for emp in sorted(df_clean["EMPRESA"].dropna().unique()):
                        if str(emp).strip() in ("", "nan"):
                            continue
                        df_emp = df_clean[df_clean["EMPRESA"] == emp]
                        sheet_name = str(emp)[:31]
                        df_emp.to_excel(writer, index=False, sheet_name=sheet_name)
            buf.seek(0)
            return buf.getvalue()

        try:
            excel_bytes = _build_consolidated_excel(datos["midagri"])
            st.download_button(
                label="📥 Descargar consolidado",
                data=excel_bytes,
                file_name=f"Consolidado_SAC_2025-2026_{datos['fecha_corte'].replace('/', '-')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_consolidado",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Error generando Excel: {e}")

    with col_refresh:
        if st.button("🔄 Nueva actualización", key="refresh_data"):
            st.session_state["processed"] = False
            st.session_state.pop("datos", None)
            st.rerun()

    # ─── Dashboard de métricas ───
    st.markdown("""
    <div class="section-header">
        <div class="icon-box" style="background:#e8f4f8;">📊</div>
        <h3>Panel Nacional</h3>
    </div>
    """, unsafe_allow_html=True)

    row1 = st.columns(4)
    metrics_row1 = [
        ("Avisos Reportados", f"{datos['total_avisos']:,}", None, "blue"),
        ("Avance Evaluación", f"{datos['pct_ajustados']:.1f}%", f"{datos['total_ajustados']:,} cerrados", "green"),
        ("Indemnización", f"S/ {datos['monto_indemnizado']:,.0f}", None, "amber"),
        ("Avance Desembolso", f"{datos['pct_desembolso']:.1f}%", f"S/ {datos['monto_desembolsado']:,.0f}", "green"),
    ]
    for col, (label, value, delta, accent) in zip(row1, metrics_row1):
        with col:
            st.markdown(render_metric(label, value, delta, accent), unsafe_allow_html=True)

    st.markdown('<div style="height: 0.5rem;"></div>', unsafe_allow_html=True)

    row2 = st.columns(4)
    metrics_row2 = [
        ("Ha Aseguradas", f"{datos['sup_asegurada']:,.0f}", None, "blue"),
        ("Ha Indemnizadas", f"{datos['ha_indemnizadas']:,.0f}", None, "amber"),
        ("Siniestralidad", f"{datos['indice_siniestralidad']:.2f}%", None, "purple"),
        ("Productores", f"{int(datos['productores_desembolso']):,}", "beneficiados", "green"),
    ]
    for col, (label, value, delta, accent) in zip(row2, metrics_row2):
        with col:
            st.markdown(render_metric(label, value, delta, accent), unsafe_allow_html=True)

    st.markdown('<div style="height:0.8rem;"></div>', unsafe_allow_html=True)

    # ─── Navegación principal: 2 secciones ───
    st.markdown("""
    <div class="section-header">
        <div class="icon-box" style="background:#e8f4f8;">🧭</div>
        <h3>Herramientas SAC</h3>
    </div>
    """, unsafe_allow_html=True)

    tab_analisis, tab_reportes = st.tabs([
        "🔍 Análisis Interactivo",
        "📥 Generar Reportes",
    ])

    # ═══════════════════════════════════════════════════════════════════
    # SECCIÓN 1: ANÁLISIS INTERACTIVO
    # ═══════════════════════════════════════════════════════════════════
    with tab_analisis:
        sub_chat, sub_mapa, sub_compar, sub_explorar = st.tabs([
            "💬 Consultas",
            "🗺️ Mapa de Calor",
            "📈 Comparativo Campañas",
            "🔍 Explorar Datos",
        ])

        # ─── Sub-tab: Consultas ───
        with sub_chat:
            llm_ready = is_llm_available()

            # Header
            engine_label = "IA + SQL" if llm_ready else "Motor Básico"
            engine_color = "#27ae60" if llm_ready else "#f39c12"
            engine_icon = "🤖" if llm_ready else "⚙️"
            st.markdown(f"""
            <div class="chat-header">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div class="title">Consulta de Coyuntura SAC</div>
                        <div class="subtitle">
                            Escriba su consulta en lenguaje natural. El sistema analiza los datos
                            y genera texto profesional listo para copiar y comunicar.
                        </div>
                    </div>
                    <span class="engine-badge" style="background:{engine_color}; color:white;">
                        {engine_icon} {engine_label}
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if not llm_ready:
                st.info(
                    "⚙️ Para habilitar consultas con IA (redacción automática de párrafos), "
                    "agregue `ANTHROPIC_API_KEY` en las variables de entorno de Railway. "
                    "Mientras tanto, funciona el motor básico de filtrado."
                )

            # Consultas sugeridas
            suggested = get_suggested_llm() if llm_ready else get_suggested_basic()
            st.markdown("**Consultas sugeridas:**")
            cols_sug = st.columns(4)
            for i, sug in enumerate(suggested[:8]):
                with cols_sug[i % 4]:
                    if st.button(f"🔹 {sug}", key=f"sug_{i}", use_container_width=True):
                        st.session_state["query_input"] = sug

            st.markdown("---")

            # Input
            query_text = st.text_area(
                "Escriba su consulta:",
                value=st.session_state.get("query_input", ""),
                height=80,
                placeholder="Ej: Resumen de intervenciones en Tumbes, Piura, Lambayeque, Lima y Arequipa",
                key="query_area",
            )

            col_q1, col_q2, col_q3 = st.columns([1, 1, 3])
            with col_q1:
                btn_query = st.button("🔍 Consultar", type="primary", use_container_width=True, key="btn_query")

            # Procesar
            if btn_query and query_text.strip():
                if llm_ready:
                    with st.spinner("🤖 Analizando datos y redactando respuesta..."):
                        result = process_query_llm(query_text, datos)

                    if result["error"]:
                        st.error(f"Error: {result['error']}")
                        # Fallback al motor básico
                        with st.spinner("Usando motor básico..."):
                            basic_response = process_query(query_text, datos)
                            st.session_state["last_query_prose"] = basic_response
                            st.session_state["last_query_sql"] = None
                            st.session_state["last_query_data"] = None
                            st.session_state["last_query_text"] = query_text
                            st.session_state["last_query_engine"] = "básico"
                    else:
                        st.session_state["last_query_prose"] = result["prose"]
                        st.session_state["last_query_sql"] = result["sql"]
                        st.session_state["last_query_data"] = result["data"]
                        st.session_state["last_query_summary"] = result.get("summary")
                        st.session_state["last_query_text"] = query_text
                        st.session_state["last_query_engine"] = "IA"
                else:
                    with st.spinner("Procesando consulta..."):
                        basic_response = process_query(query_text, datos)
                        st.session_state["last_query_prose"] = basic_response
                        st.session_state["last_query_sql"] = None
                        st.session_state["last_query_data"] = None
                        st.session_state["last_query_text"] = query_text
                        st.session_state["last_query_engine"] = "básico"

            # Mostrar respuesta
            if st.session_state.get("last_query_prose"):
                st.markdown("---")

                engine_used = st.session_state.get("last_query_engine", "básico")
                engine_badge_color = "#27ae60" if engine_used == "IA" else "#f39c12"
                st.markdown(
                    f'<div class="query-context">'
                    f'<span><strong>Consulta:</strong> {st.session_state.get("last_query_text", "")}</span>'
                    f'<span class="engine-badge" style="background:{engine_badge_color}; color:white; font-size:0.65rem;">'
                    f'{engine_used}</span></div>',
                    unsafe_allow_html=True,
                )

                # Texto de respuesta
                prose = st.session_state["last_query_prose"]
                st.markdown(f'<div class="query-result-box">{prose}</div>', unsafe_allow_html=True)

                # Botones de descarga
                st.markdown("")
                col_dl1, col_dl2, col_dl3 = st.columns([1, 1, 2])

                with col_dl1:
                    st.download_button(
                        label="📋 Descargar .txt",
                        data=prose,
                        file_name=f"SAC_consulta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        key="dl_txt",
                        use_container_width=True,
                    )

                with col_dl2:
                    st.download_button(
                        label="📄 Descargar .docx (texto)",
                        data=prose.encode("utf-8"),
                        file_name=f"SAC_consulta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        key="dl_docx_txt",
                        use_container_width=True,
                    )

                # SQL y datos (expandible)
                if st.session_state.get("last_query_sql"):
                    with st.expander("🔧 Ver consulta SQL generada"):
                        st.code(st.session_state["last_query_sql"], language="sql")

                if st.session_state.get("last_query_data") is not None:
                    df_result = st.session_state["last_query_data"]
                    if len(df_result) > 0:
                        with st.expander(f"📊 Ver datos ({len(df_result)} filas)"):
                            st.dataframe(df_result, use_container_width=True, hide_index=True)

                # Mostrar resumen verificado (control de calidad)
                if st.session_state.get("last_query_summary"):
                    summary = st.session_state["last_query_summary"]
                    with st.expander("✅ Resumen verificado (cifras calculadas programáticamente)"):
                        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                        col_s1.metric("Total Avisos", f"{summary.get('total_avisos', 0):,}")
                        col_s2.metric("Indemnización", f"S/ {summary.get('total_indemnizacion', 0):,.2f}")
                        col_s3.metric("Desembolso", f"S/ {summary.get('total_desembolso', 0):,.2f}")
                        col_s4.metric("Productores", f"{summary.get('total_productores', 0):,}")
                        col_s5, col_s6, col_s7, col_s8 = st.columns(4)
                        col_s5.metric("Ha Indemnizadas", f"{summary.get('total_ha_indemnizadas', 0):,.2f}")
                        col_s6.metric("% Evaluación", f"{summary.get('pct_avance_evaluacion', 0):.1f}%")
                        col_s7.metric("% Desembolso", f"{summary.get('pct_avance_desembolso', 0):.1f}%")
                        col_s8.metric("Avisos Cerrados", f"{summary.get('avisos_cerrados', 0):,}")

        # ─── Sub-tab: Mapa de Calor ───
        with sub_mapa:
            st.markdown(f"""
            <div class="tab-intro">
                <div class="title">Mapa de Calor SAC · Corte {datos['fecha_corte']}</div>
                <div class="desc">Visualización geográfica interactiva de los indicadores del SAC.
                Seleccione nivel geográfico, métrica y filtre por departamento.</div>
            </div>
            """, unsafe_allow_html=True)

            # ─── Controles: Nivel + Departamento + Métrica ───
            col_ctrl1, col_ctrl2 = st.columns([1, 2])

            with col_ctrl1:
                nivel_seleccionado = st.radio(
                    "Nivel geográfico:",
                    options=list(NIVELES.keys()),
                    horizontal=True,
                    key="nivel_mapa",
                )

            with col_ctrl2:
                # Filtro de departamento (para Provincial y Distrital)
                depto_filter = None
                if nivel_seleccionado in ("Provincial", "Distrital"):
                    depto_options = ["Todos"] + datos.get("departamentos_list", [])
                    depto_sel = st.selectbox(
                        "Filtrar por departamento:",
                        options=depto_options,
                        format_func=lambda x: x.title() if x != "Todos" else "Todos los departamentos",
                        key="depto_filter_mapa",
                    )
                    if depto_sel != "Todos":
                        depto_filter = [depto_sel]

            # Métricas disponibles según nivel
            metricas_nivel = get_metricas_for_nivel(nivel_seleccionado)
            metrica_seleccionada = st.radio(
                "Métrica a visualizar:",
                options=list(metricas_nivel.keys()),
                horizontal=True,
                key="metrica_mapa",
            )

            # Descripción
            meta_info = metricas_nivel[metrica_seleccionada]
            st.markdown(
                f'<div style="background:#f0f7ff; padding:0.5rem 1rem; border-radius:10px; '
                f'color:#1a5276; font-size:0.83rem; margin-bottom:0.8rem;">'
                f'ℹ️ {meta_info["description"]}</div>',
                unsafe_allow_html=True,
            )

            # ─── Tarjetas de contexto ───
            try:
                cards = get_summary_cards(datos, nivel_seleccionado, depto_filter)
                if cards:
                    lbl = cards.get("label", "Unidad")
                    cc1, cc2, cc3, cc4 = st.columns(4)
                    with cc1:
                        st.markdown(render_metric(
                            f"Mayor N° Avisos",
                            f"{cards['top_avisos']}",
                            f"{cards['top_avisos_n']:,} avisos",
                            "blue"
                        ), unsafe_allow_html=True)
                    with cc2:
                        st.markdown(render_metric(
                            "Mayor Indemnización",
                            f"{cards['top_indemn']}",
                            f"S/ {cards['top_indemn_val']:,.0f}",
                            "amber"
                        ), unsafe_allow_html=True)
                    with cc3:
                        st.markdown(render_metric(
                            "Mayor Avance Desemb.",
                            f"{cards['top_desemb_pct']}",
                            f"{cards['top_desemb_pct_val']:.1f}%",
                            "green"
                        ), unsafe_allow_html=True)
                    with cc4:
                        st.markdown(render_metric(
                            f"{cards['units_con_avisos']} {lbl}s",
                            f"con avisos",
                            f"de {cards['total_units']} total",
                            "purple"
                        ), unsafe_allow_html=True)
            except Exception:
                pass

            st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)

            # ─── Mapa y ranking lado a lado ───
            col_mapa, col_ranking = st.columns([3, 2])

            with col_mapa:
                try:
                    fig = generate_map(datos, metrica_seleccionada, nivel_seleccionado, depto_filter)
                    st.plotly_chart(fig, use_container_width=True, config={
                        "displayModeBar": True,
                        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
                        "displaylogo": False,
                    })
                except Exception as e:
                    st.error(f"Error al generar el mapa: {str(e)}")

            with col_ranking:
                nivel_label = NIVELES[nivel_seleccionado]["label"]
                st.markdown(
                    f'<div class="section-header">'
                    f'<div class="icon-box" style="background:#f0e8ff;">🏆</div>'
                    f'<h3>Ranking {nivel_label}</h3></div>',
                    unsafe_allow_html=True,
                )
                try:
                    df_ranking = get_ranking_table(datos, metrica_seleccionada, nivel_seleccionado, depto_filter)
                    if len(df_ranking) > 0:
                        st.dataframe(
                            df_ranking,
                            use_container_width=True,
                            hide_index=False,
                            height=520,
                        )
                    else:
                        st.info("Sin datos para los filtros seleccionados.")
                except Exception as e:
                    st.error(f"Error al generar ranking: {str(e)}")

        # ─── Sub-tab: Comparativo Campañas ───
        with sub_compar:
            df_anterior = load_campania_anterior()

            if df_anterior is None:
                st.warning("No se encontró el archivo consolidado de la campaña 2024-2025.")
            else:
                st.markdown(f"""
                <div class="tab-intro">
                    <div class="title">Comparativo entre Campañas SAC</div>
                    <div class="desc">Evolución mensual de indicadores clave: campaña
                    <strong style="color:{('#8e44ad')}">2024-2025</strong> ({len(df_anterior):,} avisos, 3 empresas)
                    vs campaña <strong style="color:{('#2980b9')}">2025-2026</strong>
                    ({len(datos['midagri']):,} avisos, 2 empresas).</div>
                </div>
                """, unsafe_allow_html=True)

                # Selector de métrica
                metrica_keys = list(METRICAS_COMPARACION.keys())
                metrica_labels = [METRICAS_COMPARACION[k]["label"] for k in metrica_keys]

                metrica_sel = st.radio(
                    "Indicador a comparar:",
                    options=metrica_keys,
                    format_func=lambda k: METRICAS_COMPARACION[k]["label"],
                    horizontal=True,
                    key="metrica_comparativo",
                )

                # Descripción
                meta_info = METRICAS_COMPARACION[metrica_sel]
                st.markdown(
                    f'<div style="background:#f5f0ff; padding:0.5rem 1rem; border-radius:10px; '
                    f'color:#5b2c8e; font-size:0.83rem; margin-bottom:0.8rem;">'
                    f'ℹ️ {meta_info["description"]}</div>',
                    unsafe_allow_html=True,
                )

                # Gráfico
                try:
                    fig = generate_comparison_chart(datos["midagri"], df_anterior, metrica_sel)
                    st.plotly_chart(fig, use_container_width=True, config={
                        "displayModeBar": True,
                        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
                        "displaylogo": False,
                    })
                except Exception as e:
                    st.error(f"Error al generar gráfico: {str(e)}")

                # Tabla resumen y detalle lado a lado
                col_resumen, col_detalle = st.columns([1, 1])

                with col_resumen:
                    st.markdown(
                        '<div class="section-header">'
                        '<div class="icon-box" style="background:#f5f0ff;">📊</div>'
                        '<h3>Resumen General</h3></div>',
                        unsafe_allow_html=True,
                    )
                    try:
                        df_table = get_comparison_table(datos["midagri"], df_anterior)
                        st.dataframe(df_table, use_container_width=True, hide_index=True, height=310)
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

                with col_detalle:
                    st.markdown(
                        '<div class="section-header">'
                        '<div class="icon-box" style="background:#e8f4f8;">📅</div>'
                        '<h3>Detalle Mensual</h3></div>',
                        unsafe_allow_html=True,
                    )
                    try:
                        df_monthly = get_monthly_detail_table(datos["midagri"], df_anterior, metrica_sel)
                        if df_monthly is not None and len(df_monthly) > 0:
                            st.dataframe(df_monthly, use_container_width=True, hide_index=True, height=310)
                        else:
                            st.info("Seleccione una métrica con evolución mensual para ver el detalle.")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

        # ─── Sub-tab: Explorar Datos ───
        with sub_explorar:
            sub_exp1, sub_exp2 = st.tabs(["MIDAGRI (La Positiva)", "Siniestros (Rímac)"])

            with sub_exp1:
                st.markdown(f"**Registros:** {len(datos['midagri']):,}")
                st.dataframe(datos["midagri"].head(200), use_container_width=True, hide_index=True)

            with sub_exp2:
                st.markdown(f"**Registros:** {len(datos['siniestros']):,}")
                st.dataframe(datos["siniestros"].head(200), use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Distribución de Siniestros por Tipo")
            if len(datos["siniestros_por_tipo"]) > 0:
                chart_data = datos["siniestros_por_tipo"].reset_index()
                chart_data.columns = ["Tipo Siniestro", "Cantidad"]
                st.bar_chart(chart_data.set_index("Tipo Siniestro").head(10))

    # ═══════════════════════════════════════════════════════════════════
    # SECCIÓN 2: GENERAR REPORTES
    # ═══════════════════════════════════════════════════════════════════
    with tab_reportes:
        sub_nac, sub_depto, sub_oper, sub_eme, sub_ppt = st.tabs([
            "📄 Ayuda Memoria Nacional",
            "🏔️ Ayuda Memoria Departamental",
            "📋 Operatividad SAC",
            "📊 Reporte EME",
            "📊 Presentación Dinámica",
        ])

        # ─── Sub-tab: Ayuda Memoria Nacional ───
        with sub_nac:
            st.markdown(f"""
            <div class="tab-intro">
                <div class="title">Ayuda Memoria Nacional · Corte {datos['fecha_corte']}</div>
                <div class="desc">Resumen de operatividad SAC a nivel nacional: datos generales, primas y cobertura,
                indemnizaciones y eventos asociados a lluvias intensas.</div>
            </div>
            """, unsafe_allow_html=True)

            col_gen, col_dl = st.columns([1, 1])
            with col_gen:
                if st.button("⚡ Generar documento", type="primary", key="gen_nac", use_container_width=True):
                    with st.spinner("Generando Ayuda Memoria Nacional..."):
                        try:
                            doc_bytes = generate_nacional_docx(datos)
                            fecha_str = datetime.now().strftime("%d_%m_%Y")
                            filename = f"Ayuda_Memoria_Resumen_SAC_2025-2026_{fecha_str}.docx"
                            st.session_state["doc_nacional"] = doc_bytes
                            st.session_state["doc_nacional_name"] = filename
                            st.success("✅ Documento generado")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

            with col_dl:
                if st.session_state.get("doc_nacional"):
                    st.download_button(
                        label="⬇️ Descargar Ayuda Memoria Nacional",
                        data=st.session_state["doc_nacional"],
                        file_name=st.session_state["doc_nacional_name"],
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )

            with st.expander("📋 Vista previa: Cuadro 1 — Primas y Cobertura"):
                st.dataframe(datos["cuadro1"], use_container_width=True, hide_index=True)
            with st.expander("📋 Vista previa: Cuadro 2 — Indemnizaciones y Desembolsos"):
                st.dataframe(datos["cuadro2"], use_container_width=True, hide_index=True)
            with st.expander("📋 Vista previa: Cuadro 3 — Lluvias Intensas"):
                st.dataframe(datos["cuadro3"], use_container_width=True, hide_index=True)

        # ─── Sub-tab: Ayuda Memoria Departamental ───
        with sub_depto:
            depto_seleccionado = st.selectbox(
                "Seleccione el departamento:",
                options=datos["departamentos_list"],
                format_func=lambda x: x.title(),
            )

            if depto_seleccionado:
                depto_data = get_departamento_data(datos, depto_seleccionado)

                # Métricas departamentales
                col_d1, col_d2, col_d3, col_d4 = st.columns(4)
                with col_d1:
                    st.markdown(render_metric("Avisos", str(depto_data["total_avisos"]), None, "blue"), unsafe_allow_html=True)
                with col_d2:
                    st.markdown(render_metric("Indemnización", f"S/ {depto_data['monto_indemnizado']:,.0f}", None, "amber"), unsafe_allow_html=True)
                with col_d3:
                    st.markdown(render_metric("Ha Indemnizadas", f"{depto_data['ha_indemnizadas']:,.0f}", None, "green"), unsafe_allow_html=True)
                with col_d4:
                    st.markdown(render_metric("Desembolso", f"S/ {depto_data['monto_desembolsado']:,.0f}", None, "purple"), unsafe_allow_html=True)

                st.markdown(
                    f"**Aseguradora:** {depto_data['empresa']} · "
                    f"**Prima neta:** S/ {depto_data['prima_neta']:,.2f} · "
                    f"**Superficie asegurada:** {depto_data['sup_asegurada']:,.0f} ha"
                )

                col_gen, col_dl = st.columns([1, 1])
                with col_gen:
                    if st.button("⚡ Generar documento", type="primary", key="gen_depto", use_container_width=True):
                        with st.spinner(f"Generando reporte de {depto_seleccionado.title()}..."):
                            try:
                                doc_bytes = generate_departamental_docx(depto_data)
                                fecha_str = datetime.now().strftime("%d_%m_%Y")
                                filename = f"Ayuda_Memoria_SAC_{depto_seleccionado.title()}_2025-2026_{fecha_str}.docx"
                                st.session_state["doc_depto"] = doc_bytes
                                st.session_state["doc_depto_name"] = filename
                                st.success(f"✅ Documento de {depto_seleccionado.title()} generado")
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

                with col_dl:
                    if st.session_state.get("doc_depto"):
                        st.download_button(
                            label=f"⬇️ Descargar {st.session_state.get('doc_depto_name', 'documento')}",
                            data=st.session_state["doc_depto"],
                            file_name=st.session_state["doc_depto_name"],
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            use_container_width=True,
                        )

                with st.expander("📋 Avisos por Tipo de Siniestro"):
                    if len(depto_data["avisos_tipo"]) > 0:
                        st.dataframe(
                            depto_data["avisos_tipo"].reset_index().rename(
                                columns={"index": "Tipo Siniestro", "TIPO_SINIESTRO": "Tipo Siniestro", "count": "N° Avisos"}
                            ),
                            use_container_width=True, hide_index=True,
                        )
                with st.expander("📋 Distribución por Provincia"):
                    if len(depto_data["dist_provincia"]) > 0:
                        st.dataframe(depto_data["dist_provincia"], use_container_width=True, hide_index=True)

        # ─── Sub-tab: Operatividad SAC ───
        with sub_oper:
            st.markdown(f"""
            <div class="tab-intro">
                <div class="title">Operatividad SAC · Corte {datos['fecha_corte']}</div>
                <div class="desc">Detalle de operatividad por empresa de seguros: avisos, ajustes, siniestralidad por
                departamento, coberturas, cultivos priorizados y desembolsos.</div>
            </div>
            """, unsafe_allow_html=True)

            col_gen_op, col_dl_op = st.columns([1, 1])
            with col_gen_op:
                if st.button("⚡ Generar Operatividad SAC", type="primary", key="gen_oper", use_container_width=True):
                    with st.spinner("Generando Ayuda Memoria Operatividad..."):
                        try:
                            doc_bytes = generate_operatividad_docx(datos)
                            fecha_str = datetime.now().strftime("%d_%m_%Y")
                            filename = f"AM_Operatividad_SAC_2025-2026_{fecha_str}.docx"
                            st.session_state["doc_operatividad"] = doc_bytes
                            st.session_state["doc_operatividad_name"] = filename
                            st.success("✅ Documento generado")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

            with col_dl_op:
                if st.session_state.get("doc_operatividad"):
                    st.download_button(
                        label="⬇️ Descargar Operatividad SAC",
                        data=st.session_state["doc_operatividad"],
                        file_name=st.session_state["doc_operatividad_name"],
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )

            with st.expander("📋 Contenido del documento"):
                st.markdown(
                    "El documento incluye: avisos de siniestros por empresa (La Positiva / Rímac), "
                    "top departamentos y tipos de siniestro, resultados de ajustes y evaluaciones, "
                    "tabla de siniestralidad por departamento/empresa, indemnizaciones por tipo de cobertura "
                    "(complementaria vs catastrófica), cultivos priorizados vs no priorizados, "
                    "y desembolsos con productores beneficiados por departamento."
                )

        # ─── Sub-tab: Reporte EME ───
        with sub_eme:
            st.markdown("""
            <div class="tab-intro">
                <div class="title">Reporte de Emergencia (EME)</div>
                <div class="desc">Formato consolidado por región con acciones implementadas,
                en implementación y por implementar.</div>
            </div>
            """, unsafe_allow_html=True)

            col_gen, col_dl = st.columns([1, 1])
            with col_gen:
                if st.button("⚡ Generar Reporte EME", type="primary", key="gen_eme", use_container_width=True):
                    with st.spinner("Generando reporte Excel..."):
                        try:
                            xls_bytes = generate_reporte_eme(datos)
                            fecha_str = datetime.now().strftime("%d_%m_%Y")
                            filename = f"formato_reporte_EME_{fecha_str}_actualizado.xlsx"
                            st.session_state["xls_eme"] = xls_bytes
                            st.session_state["xls_eme_name"] = filename
                            st.success("✅ Reporte EME generado")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

            with col_dl:
                if st.session_state.get("xls_eme"):
                    st.download_button(
                        label="⬇️ Descargar Reporte EME",
                        data=st.session_state["xls_eme"],
                        file_name=st.session_state["xls_eme_name"],
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

        # ─── Sub-tab: Presentación Dinámica ───
        with sub_ppt:
            st.markdown(f"""
            <div class="tab-intro">
                <div class="title">Presentación Dinámica · Corte {datos['fecha_corte']}</div>
                <div class="desc">Configure el alcance geográfico, tipo de siniestro, empresa y período
                para generar una presentación PowerPoint personalizada.</div>
            </div>
            """, unsafe_allow_html=True)

            df_ppt = datos["midagri"]

            # ── Fila 1: Alcance geográfico (cascada acumulativa) ──
            st.markdown("##### 🗺️ Alcance geográfico")
            st.caption("Construya su presentación nivel por nivel. Cada nivel agrega secciones adicionales.")

            deptos_sel_ppt = []
            provs_sel_ppt = []
            dists_sel_ppt = []

            # Checkbox para incluir resumen nacional
            incluir_nacional = st.checkbox("🌎 Incluir Resumen Nacional", value=True, key="ppt_incluir_nac")

            # Departamentos
            col_depto, col_prov = st.columns([1, 1])
            with col_depto:
                deptos_disponibles = sorted(df_ppt["DEPARTAMENTO"].dropna().unique()) if "DEPARTAMENTO" in df_ppt.columns else []
                deptos_sel_ppt = st.multiselect(
                    "📍 Departamento(s) — sección departamental",
                    deptos_disponibles,
                    key="ppt_deptos",
                    help="Seleccione uno o más departamentos para generar secciones departamentales.",
                )

            # Provincias (filtradas por departamentos seleccionados)
            with col_prov:
                if deptos_sel_ppt:
                    provs_disponibles = sorted(
                        df_ppt[df_ppt["DEPARTAMENTO"].isin(deptos_sel_ppt)]["PROVINCIA"].dropna().unique()
                    ) if "PROVINCIA" in df_ppt.columns else []
                    provs_sel_ppt = st.multiselect(
                        "📍 Provincia(s) — sección provincial",
                        provs_disponibles,
                        key="ppt_provs",
                        help="Seleccione provincias para generar detalle provincial con distritos.",
                    )

            # Distritos (filtrados por provincias seleccionadas)
            if provs_sel_ppt:
                dists_disponibles = sorted(
                    df_ppt[df_ppt["PROVINCIA"].isin(provs_sel_ppt)]["DISTRITO"].dropna().unique()
                ) if "DISTRITO" in df_ppt.columns else []
                dists_sel_ppt = st.multiselect(
                    "📍 Distrito(s) — sección distrital (máx. 5)",
                    dists_disponibles,
                    max_selections=5,
                    key="ppt_dists",
                    help="Opcional: seleccione distritos para generar tarjetas individuales.",
                )

            # Inferir scope basado en las selecciones
            scope_ppt = "nacional"
            if dists_sel_ppt:
                scope_ppt = "distrital"
            elif provs_sel_ppt:
                scope_ppt = "provincial"
            elif deptos_sel_ppt:
                scope_ppt = "departamental"

            # Mostrar resumen de lo que se generará
            secciones_previas = []
            if incluir_nacional:
                secciones_previas.append("Resumen Nacional")
            if deptos_sel_ppt:
                secciones_previas.append(f"Departamental: {', '.join(deptos_sel_ppt)}")
            if provs_sel_ppt:
                secciones_previas.append(f"Provincial: {', '.join(provs_sel_ppt)}")
            if dists_sel_ppt:
                secciones_previas.append(f"Distrital: {', '.join(dists_sel_ppt[:5])}")
            if secciones_previas:
                st.markdown(f"**Secciones a generar:** {' → '.join(secciones_previas)}")
            else:
                st.warning("Seleccione al menos un nivel geográfico.")

            # ── Fila 2: Filtros adicionales ──
            st.markdown("##### 🔧 Filtros adicionales")
            col_tipo, col_emp, col_fecha = st.columns([1.5, 1, 1.5])

            with col_tipo:
                tipos_disponibles = sorted(df_ppt["TIPO_SINIESTRO"].dropna().unique()) if "TIPO_SINIESTRO" in df_ppt.columns else []
                tipos_sel_ppt = st.multiselect(
                    "Tipo(s) de siniestro",
                    tipos_disponibles,
                    key="ppt_tipos",
                    help="Dejar vacío para incluir todos",
                )

            with col_emp:
                empresa_ppt = st.radio(
                    "Aseguradora",
                    ["Ambas", "LA POSITIVA", "RIMAC"],
                    key="ppt_empresa",
                    horizontal=False,
                )

            with col_fecha:
                filtrar_fecha = st.checkbox("Filtrar por período", key="ppt_filtrar_fecha")
                fecha_inicio_ppt = None
                fecha_fin_ppt = None
                if filtrar_fecha:
                    col_fi, col_ff = st.columns(2)
                    with col_fi:
                        fecha_inicio_ppt = st.date_input("Desde", key="ppt_fecha_ini")
                    with col_ff:
                        fecha_fin_ppt = st.date_input("Hasta", key="ppt_fecha_fin")

            # Construir filtros
            filtros_ppt = {
                "scope": scope_ppt,
                "incluir_nacional": incluir_nacional,
                "departamentos": deptos_sel_ppt,
                "provincias": provs_sel_ppt,
                "distritos": dists_sel_ppt,
                "tipos_siniestro": tipos_sel_ppt,
                "empresa": empresa_ppt.lower() if empresa_ppt != "Ambas" else "ambas",
                "fecha_inicio": fecha_inicio_ppt,
                "fecha_fin": fecha_fin_ppt,
                "col_fecha": "FECHA_AVISO",
            }

            # ── Fila 3: Preview ──
            from gen_ppt_dinamico import _aplicar_filtros, _calcular_metricas
            filtros_preview = {k: v for k, v in filtros_ppt.items()
                               if k not in ("scope",)}
            # Para preview, aplicar filtros geográficos también
            df_preview = _aplicar_filtros(df_ppt, filtros_ppt)
            m_prev = _calcular_metricas(df_preview)

            st.info(
                f"📊 **{m_prev['avisos']:,}** avisos · "
                f"**{m_prev['cerrados']:,}** cerrados ({m_prev['pct_eval']:.1f}%) · "
                f"**S/ {m_prev['indemnizacion']:,.0f}** indemnización · "
                f"**S/ {m_prev['desembolso']:,.0f}** desembolso"
            )

            # ── Fila 4: Generar + Descargar ──
            col_gen_ppt, col_dl_ppt = st.columns([1, 1])
            with col_gen_ppt:
                if st.button("⚡ Generar Presentación", type="primary", key="gen_ppt_din", use_container_width=True):
                    if m_prev["avisos"] == 0:
                        st.warning("⚠️ No hay datos con los filtros seleccionados. Ajuste los criterios.")
                    else:
                        with st.spinner("Generando presentación PowerPoint..."):
                            try:
                                ppt_bytes = generar_ppt_dinamico(df_ppt, filtros_ppt, datos["fecha_corte"])
                                fecha_str = datetime.now().strftime("%d_%m_%Y")
                                geo_str = ""
                                if deptos_sel_ppt:
                                    geo_str = f"_{'_'.join(deptos_sel_ppt[:2])}"
                                if provs_sel_ppt:
                                    geo_str += f"_{'_'.join(provs_sel_ppt[:2])}"
                                filename = f"SAC_{scope_ppt}{geo_str}_{fecha_str}.pptx"
                                st.session_state["ppt_dinamico"] = ppt_bytes
                                st.session_state["ppt_dinamico_name"] = filename
                                st.success(f"✅ Presentación generada ({len(ppt_bytes) / 1024:.0f} KB)")
                            except Exception as e:
                                st.error(f"Error al generar PPT: {str(e)}")

            with col_dl_ppt:
                if st.session_state.get("ppt_dinamico"):
                    st.download_button(
                        label="⬇️ Descargar Presentación",
                        data=st.session_state["ppt_dinamico"],
                        file_name=st.session_state.get("ppt_dinamico_name", "SAC_presentacion.pptx"),
                        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        use_container_width=True,
                    )

            with st.expander("ℹ️ ¿Qué incluye la presentación?"):
                st.markdown(
                    "La presentación se construye **acumulativamente** según sus selecciones:\n\n"
                    "- **Nacional** (checkbox): Métricas generales, top departamentos (gráfico), "
                    "distribución por tipo de siniestro, observaciones automáticas\n"
                    "- **Departamental** (multiselect): Sección por cada departamento con métricas, "
                    "provincias, pipeline SAC y observaciones\n"
                    "- **Provincial** (multiselect): Detalle por provincia con distritos, tipos de siniestro, "
                    "pipeline y observaciones contextuales\n"
                    "- **Distrital** (multiselect, máx. 5): Tarjetas de métricas por cada distrito\n\n"
                    "**Ejemplo**: Marque Nacional + seleccione Cajamarca + seleccione Jaén y San Ignacio → "
                    "obtendrá una PPT con resumen nacional, detalle de Cajamarca con highlight en las "
                    "provincias seleccionadas, y secciones detalladas de Jaén y San Ignacio."
                )

    # ═══════════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════════
    st.markdown("""
    <div class="footer">
        SAC 2025-2026 · Dirección de Seguro y Fomento del Financiamiento Agrario · MIDAGRI<br>
        Sistema automatizado para la gestión de reportes del Seguro Agrícola Catastrófico
    </div>
    """, unsafe_allow_html=True)
