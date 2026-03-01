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
    /* ── Reset & Base ── */
    .block-container { padding-top: 1rem; max-width: 1200px; }
    [data-testid="stSidebar"] { background: #f8fafc; }

    /* ── Hero Header ── */
    .hero {
        background: linear-gradient(135deg, #0F2B46 0%, #1a5276 40%, #2980b9 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(15,43,70,0.3);
    }
    .hero::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
        border-radius: 50%;
    }
    .hero h1 {
        color: #fff !important;
        font-size: 2rem;
        font-weight: 700;
        margin: 0 0 0.3rem 0;
        position: relative;
    }
    .hero .subtitle {
        color: #a8d8f0;
        font-size: 0.95rem;
        margin: 0;
        position: relative;
    }
    .hero .badge {
        display: inline-block;
        background: rgba(255,255,255,0.15);
        color: #fff;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        margin-top: 0.5rem;
        position: relative;
        backdrop-filter: blur(4px);
    }

    /* ── Tarjeta de acción principal ── */
    .action-card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        transition: all 0.3s ease;
    }
    .action-card:hover {
        box-shadow: 0 4px 24px rgba(0,0,0,0.1);
        transform: translateY(-2px);
    }
    .action-card h2 {
        color: #1a5276;
        margin: 0.5rem 0;
        font-size: 1.4rem;
    }
    .action-card p {
        color: #64748b;
        font-size: 0.9rem;
        margin: 0;
    }

    /* ── Stepper de progreso ── */
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
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.85rem;
        flex-shrink: 0;
    }
    .step-pending .step-circle {
        background: #e2e8f0;
        color: #94a3b8;
    }
    .step-active .step-circle {
        background: #2980b9;
        color: #fff;
        animation: pulse 1.5s infinite;
    }
    .step-done .step-circle {
        background: #27ae60;
        color: #fff;
    }
    .step-error .step-circle {
        background: #e74c3c;
        color: #fff;
    }
    .step-label {
        font-size: 0.82rem;
        font-weight: 500;
    }
    .step-pending .step-label { color: #94a3b8; }
    .step-active .step-label { color: #2980b9; font-weight: 600; }
    .step-done .step-label { color: #27ae60; }
    .step-error .step-label { color: #e74c3c; }
    .step-connector {
        width: 40px;
        height: 2px;
        background: #e2e8f0;
        margin: 0 0.3rem;
        align-self: center;
    }
    .step-connector.done { background: #27ae60; }

    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(41,128,185,0.4); }
        50% { box-shadow: 0 0 0 8px rgba(41,128,185,0); }
    }

    /* ── Metric Cards ── */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin: 1rem 0;
    }
    @media (max-width: 768px) {
        .metric-grid { grid-template-columns: repeat(2, 1fr); }
    }
    .metric-card-v2 {
        background: #fff;
        border-radius: 12px;
        padding: 1.2rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 8px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
    }
    .metric-card-v2:hover {
        box-shadow: 0 3px 16px rgba(0,0,0,0.08);
        transform: translateY(-1px);
    }
    .metric-card-v2 .label {
        color: #64748b;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
        margin-bottom: 0.4rem;
    }
    .metric-card-v2 .value {
        color: #0F2B46;
        font-size: 1.5rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .metric-card-v2 .delta {
        font-size: 0.8rem;
        margin-top: 0.2rem;
    }
    .delta-positive { color: #27ae60; }
    .delta-neutral { color: #64748b; }

    /* ── Colores de acento por tipo ── */
    .accent-blue { border-left: 4px solid #2980b9; }
    .accent-green { border-left: 4px solid #27ae60; }
    .accent-amber { border-left: 4px solid #f39c12; }
    .accent-purple { border-left: 4px solid #8e44ad; }

    /* ── Sección de reportes ── */
    .report-card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.5rem;
        height: 100%;
        box-shadow: 0 1px 8px rgba(0,0,0,0.04);
        transition: all 0.2s ease;
    }
    .report-card:hover {
        box-shadow: 0 3px 16px rgba(0,0,0,0.08);
    }
    .report-card .icon {
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    .report-card h3 {
        color: #1a5276;
        margin: 0.3rem 0;
        font-size: 1.1rem;
    }
    .report-card p {
        color: #64748b;
        font-size: 0.85rem;
        margin: 0.3rem 0 1rem 0;
    }

    /* ── Status banner ── */
    .status-banner {
        background: linear-gradient(90deg, #d4edda 0%, #c3e6cb 100%);
        border: 1px solid #b1dfbb;
        border-radius: 10px;
        padding: 0.8rem 1.2rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin: 1rem 0;
    }
    .status-banner .dot {
        width: 8px;
        height: 8px;
        background: #27ae60;
        border-radius: 50%;
        animation: blink 2s infinite;
    }
    @keyframes blink {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.3; }
    }
    .status-banner span {
        color: #155724;
        font-size: 0.88rem;
        font-weight: 500;
    }

    /* ── Footer ── */
    .footer {
        text-align: center;
        color: #94a3b8;
        font-size: 0.75rem;
        padding: 2rem 0 1rem 0;
        border-top: 1px solid #e2e8f0;
        margin-top: 2rem;
    }

    /* ── Tabs styling ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: #f1f5f9;
        border-radius: 10px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 20px;
        font-weight: 500;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #fff;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }

    /* ── Ocultar hamburger menu default ── */
    #MainMenu {visibility: hidden;}

    /* ── Botón primario mejorado ── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #1a5276, #2980b9) !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.6rem 1.5rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.3px !important;
        box-shadow: 0 2px 8px rgba(41,128,185,0.3) !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 4px 16px rgba(41,128,185,0.4) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Expander mejorado ── */
    .streamlit-expanderHeader {
        background: #f8fafc;
        border-radius: 8px;
        font-weight: 500;
    }
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
    <h1>🌾 SAC 2025 — 2026</h1>
    <p class="subtitle">Sistema de Reportes del Seguro Agrícola Catastrófico · MIDAGRI</p>
    <span class="badge">🕐 {hora_actual}</span>
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

    col_r1, col_r2, col_r3 = st.columns(3)
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

    # ─── Botón para nueva actualización ───
    col_refresh = st.columns([3, 1])[1]
    with col_refresh:
        if st.button("🔄 Nueva actualización", key="refresh_data"):
            st.session_state["processed"] = False
            st.session_state.pop("datos", None)
            st.rerun()

    # ─── Dashboard de métricas ───
    st.markdown('<h3 style="color:#0F2B46; margin-top:0.5rem;">📊 Panel Nacional</h3>', unsafe_allow_html=True)

    row1 = st.columns(4)
    metrics_row1 = [
        ("Avisos Reportados", f"{datos['total_avisos']:,}", None, "blue"),
        ("Avisos Ajustados", f"{datos['total_ajustados']:,}", f"{datos['pct_ajustados']:.1f}% del total", "green"),
        ("Indemnización Total", f"S/ {datos['monto_indemnizado']:,.0f}", None, "amber"),
        ("Desembolsos", f"S/ {datos['monto_desembolsado']:,.0f}", f"{datos['pct_desembolso']:.1f}% ejecutado", "green"),
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
        ("Productores Beneficiados", f"{int(datos['productores_desembolso']):,}", None, "green"),
    ]
    for col, (label, value, delta, accent) in zip(row2, metrics_row2):
        with col:
            st.markdown(render_metric(label, value, delta, accent), unsafe_allow_html=True)

    st.markdown("---")

    # ─── Generación de reportes ───
    st.markdown('<h3 style="color:#0F2B46;">📥 Generar Reportes</h3>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📄 Ayuda Memoria Nacional",
        "🗺️ Ayuda Memoria Departamental",
        "📊 Reporte EME",
        "🔍 Explorar Datos",
    ])

    # ═══ TAB 1: Ayuda Memoria Nacional ═══
    with tab1:
        st.markdown(f"**Fecha de corte:** {datos['fecha_corte']}")
        st.markdown(
            "Documento Word con el resumen de operatividad del SAC a nivel nacional: "
            "datos generales, primas y cobertura, indemnizaciones y eventos asociados a lluvias intensas."
        )

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

    # ═══ TAB 2: Ayuda Memoria Departamental ═══
    with tab2:
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

    # ═══ TAB 3: Reporte EME ═══
    with tab3:
        st.markdown("Reporte consolidado por región con acciones implementadas, en implementación y por implementar.")

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

    # ═══ TAB 4: Explorar Datos ═══
    with tab4:
        sub_tab1, sub_tab2 = st.tabs(["MIDAGRI (La Positiva)", "Siniestros (Rímac)"])

        with sub_tab1:
            st.markdown(f"**Registros:** {len(datos['midagri']):,}")
            st.dataframe(datos["midagri"].head(200), use_container_width=True, hide_index=True)

        with sub_tab2:
            st.markdown(f"**Registros:** {len(datos['siniestros']):,}")
            st.dataframe(datos["siniestros"].head(200), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("### Distribución de Siniestros por Tipo")
        if len(datos["siniestros_por_tipo"]) > 0:
            chart_data = datos["siniestros_por_tipo"].reset_index()
            chart_data.columns = ["Tipo Siniestro", "Cantidad"]
            st.bar_chart(chart_data.set_index("Tipo Siniestro").head(10))


# ═══════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="footer">
    SAC 2025-2026 · Dirección de Gestión del Riesgo Agrario y Ambiental · MIDAGRI<br>
    Sistema desarrollado para la gestión del Seguro Agrícola Catastrófico
</div>
""", unsafe_allow_html=True)
