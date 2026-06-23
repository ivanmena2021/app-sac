"""
SAC 2025-2026 — Dashboard de Reportes Automatizados
====================================================
Seguro Agrícola Catastrófico · MIDAGRI

Entry point: configura la página, inyecta CSS global,
define la navegación multipage y gestiona el filtro de fechas.
"""
import os
import sys
import streamlit as st
import datetime as _dt

# Asegurar que el directorio raíz esté en el path
sys.path.insert(0, os.path.dirname(__file__))

from shared.css import inject_css
from shared.state import init_session_state, is_data_loaded
from shared.auth import require_auth
from data_processor import filter_by_date_range

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN DE PÁGINA
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="SAC 2025-2026 — Dashboard",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS global (una sola vez)
inject_css()

# Session state
init_session_state()

# ═══════════════════════════════════════════════════════════════
# SIDEBAR — Branding + Navegación + Filtros
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    # Branding MIDAGRI — logo oficial + sub-rótulo SAC
    _logo = os.path.join(os.path.dirname(__file__), "assets", "midagri_logo.png")
    st.markdown('<div class="sidebar-brand">', unsafe_allow_html=True)
    if os.path.exists(_logo):
        st.image(_logo, use_container_width=True)
    st.markdown(
        '<h2>SAC 2025–2026</h2>'
        '<p>Seguro Agrícola Catastrófico</p>'
        '<span class="badge-sb">MIDAGRI · FOGASA</span>'
        '</div>',
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════
# AUTENTICACIÓN — gate central: como app.py corre en cada carga de
# página (st.navigation), esto protege las 12 páginas y deep-links.
# Si no está autenticado: muestra login y st.stop() (nada de abajo
# se ejecuta). Sin SAC_AUTH_USERS configurada: pasa con advertencia.
# ═══════════════════════════════════════════════════════════════
require_auth()

# ═══════════════════════════════════════════════════════════════
# NAVEGACIÓN MULTIPAGE
# ═══════════════════════════════════════════════════════════════

pg = st.navigation({
    "Principal": [
        st.Page("pages/inicio.py", title="Inicio", icon=":material/home:", default=True),
        st.Page("pages/dashboard.py", title="Dashboard Nacional", icon=":material/dashboard:"),
    ],
    "Análisis": [
        st.Page("pages/consultas.py", title="Consultas", icon=":material/chat:"),
        st.Page("pages/mapa_calor.py", title="Mapa de Calor", icon=":material/map:"),
        st.Page("pages/comparativo.py", title="Comparativo Campañas", icon=":material/compare_arrows:"),
        st.Page("pages/comparar_deptos.py", title="Comparar Departamentos", icon=":material/bar_chart:"),
        st.Page("pages/prediccion.py", title="Predicción de Cierre", icon=":material/insights:"),
        st.Page("pages/escenario_page.py", title="Escenario El Niño", icon=":material/cyclone:"),
        st.Page("pages/explorar_datos.py", title="Explorar Datos", icon=":material/search:"),
        st.Page("pages/calendario.py", title="Calendario Agrícola", icon=":material/event:"),
        st.Page("pages/clima_riesgo_page.py", title="Clima y Riesgo", icon=":material/cloud:"),
    ],
    "Reportes y Alertas": [
        st.Page("pages/reportes.py", title="Generar Reportes", icon=":material/description:"),
        st.Page("pages/semaforo_page.py", title="Semáforo de Alertas", icon=":material/traffic:"),
    ],
})

# ═══════════════════════════════════════════════════════════════
# SIDEBAR — Filtro global de fechas (solo si hay datos)
# ═══════════════════════════════════════════════════════════════

if is_data_loaded():
    datos = st.session_state.get("datos")
    if datos:
        try:
            midagri_df = datos["midagri"]
            date_col = "FECHA_SINIESTRO" if "FECHA_SINIESTRO" in midagri_df.columns else "FECHA_AVISO"
            if date_col in midagri_df.columns:
                valid_dates = midagri_df[date_col].dropna()
                if len(valid_dates) > 0:
                    min_date = valid_dates.min().date()
                    max_date = valid_dates.max().date()

                    with st.sidebar:
                        st.divider()
                        # M3 fix: filtro en expander colapsado para no saturar
                        # el sidebar (en pantallas chicas se cortaba abajo).
                        # Si hay un filtro activo, se autoexpande para visibilidad.
                        _has_filter_active = (st.session_state.get("date_preset", "Todo") != "Todo")
                        with st.expander("Filtro de Fechas", expanded=_has_filter_active):
                            _ref_label = "Fecha de Siniestro" if date_col == "FECHA_SINIESTRO" else "Fecha de Aviso"
                            st.caption(f"Columna: **{_ref_label}** · "
                                       f"{min_date.strftime('%d/%m/%Y')} — {max_date.strftime('%d/%m/%Y')}")

                            preset = st.radio(
                                "Período", ["Todo", "30 días", "90 días", "Este año", "Personalizado"],
                                key="date_preset", horizontal=True, label_visibility="collapsed")

                            if preset == "30 días":
                                f_start = max_date - _dt.timedelta(days=30); f_end = max_date
                            elif preset == "90 días":
                                f_start = max_date - _dt.timedelta(days=90); f_end = max_date
                            elif preset == "Este año":
                                f_start = _dt.date(max_date.year, 1, 1); f_end = max_date
                            elif preset == "Personalizado":
                                dr = st.date_input("Rango", [min_date, max_date],
                                                   min_value=min_date, max_value=max_date,
                                                   key="custom_date_range")
                                f_start, f_end = (dr[0], dr[1]) if isinstance(dr, (list, tuple)) and len(dr) == 2 else (min_date, max_date)
                            else:
                                f_start, f_end = min_date, max_date

                            if (f_start, f_end) != (min_date, max_date):
                                st.session_state["datos_filtered"] = filter_by_date_range(datos, f_start, f_end)
                                st.caption(f"Filtrado: {f_start.strftime('%d/%m/%Y')} — {f_end.strftime('%d/%m/%Y')}")
                            else:
                                st.session_state["datos_filtered"] = None

                        # Status indicator (fuera del expander, siempre visible)
                        ts = st.session_state.get("update_timestamp", "")
                        src = st.session_state.get("source", "")
                        if ts:
                            st.markdown(f"""
                            <div style="background:#e8f8ee; border-radius:8px; padding:0.5rem 0.8rem;
                                 margin-top:0.5rem; font-size:0.75rem; color:#155724;">
                                <strong>Datos actualizados</strong><br>{ts} ({src})
                            </div>
                            """, unsafe_allow_html=True)
        except Exception:
            pass

# ═══════════════════════════════════════════════════════════════
# EJECUTAR PÁGINA SELECCIONADA
# ═══════════════════════════════════════════════════════════════

pg.run()
