"""Página: Inicio — Carga y actualización de datos SAC."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import io
import streamlit as st
from datetime import datetime, timezone, timedelta

# Timezone Perú (UTC-5)
TZ_PERU = timezone(timedelta(hours=-5))

from shared.components import page_header, render_stepper, footer
from shared.data_loader import check_auto_download, check_credentials
from shared.state import is_data_loaded
from data_processor import process_dynamic_data

# Si ya hay datos, mostrar opción de ir al dashboard
if is_data_loaded():
    page_header("Inicio", "Los datos ya están cargados. Puede ir al Dashboard o recargar.")

    ts = st.session_state.get("update_timestamp", "")
    src = st.session_state.get("source", "")
    st.markdown(f"""
    <div class="status-banner">
        <div class="dot"></div>
        <span>Datos actualizados el <b>{ts}</b> ({src})</span>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Ir al Dashboard", type="primary", use_container_width=True, key="goto_dash"):
            st.switch_page("pages/dashboard.py")
    with c2:
        if st.button("Recargar datos", use_container_width=True, key="reload_data"):
            st.session_state["processed"] = False
            st.session_state["datos"] = None
            st.session_state["datos_filtered"] = None
            st.rerun()

    footer()

else:
    # ── Sin datos: mostrar opciones de carga ──
    auto_available = check_auto_download()
    has_rimac, has_lp = check_credentials()
    has_all_creds = has_rimac and has_lp

    # Hero header
    hora_actual = datetime.now(TZ_PERU).strftime("%d/%m/%Y %H:%M")
    st.markdown(f"""
    <div class="hero">
        <div class="hero-row">
            <div>
                <h1>SAC 2025 — 2026</h1>
                <p class="subtitle">Herramientas de reporte y análisis del Seguro Agrícola Catastrófico</p>
            </div>
            <div class="badge">🌾 MIDAGRI · {hora_actual}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if auto_available and has_all_creds:
        st.markdown("""
        <div class="action-card">
            <div style="font-size: 3rem;">🚀</div>
            <h2>Actualización con un solo click</h2>
            <p>Descarga los datos más recientes de Rímac y La Positiva, los procesa
            automáticamente y genera el dashboard con todos los reportes listos.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("")
        col_center = st.columns([1, 2, 1])[1]
        with col_center:
            btn_auto = st.button("Actualizar Datos SAC", type="primary",
                                  use_container_width=True, key="btn_auto_main")

        if btn_auto:
            from auto_download import descargar_rimac, descargar_lapositiva

            progress_ph = st.empty()
            status_ph = st.empty()

            # Paso 1: Rímac
            with progress_ph.container():
                st.markdown(render_stepper([
                    ("Rímac", "active"), ("La Positiva", "pending"),
                    ("Procesando", "pending"), ("Listo", "pending"),
                ]), unsafe_allow_html=True)
            status_ph.info("Conectando con SISGAQSAC (Rímac)...")

            try:
                df_siniestros = descargar_rimac()
                rimac_rows = len(df_siniestros)
            except Exception as e:
                status_ph.error(f"Error al descargar de Rímac: {e}")
                st.stop()

            # Paso 2: La Positiva
            with progress_ph.container():
                st.markdown(render_stepper([
                    ("Rímac", "done"), ("La Positiva", "active"),
                    ("Procesando", "pending"), ("Listo", "pending"),
                ]), unsafe_allow_html=True)
            status_ph.info(f"Rímac: {rimac_rows:,} filas · Conectando con Agroevaluaciones...")

            try:
                df_midagri = descargar_lapositiva()
                lp_rows = len(df_midagri)
            except Exception as e:
                status_ph.error(f"Error al descargar de La Positiva: {e}")
                st.stop()

            # Paso 3: Procesar
            with progress_ph.container():
                st.markdown(render_stepper([
                    ("Rímac", "done"), ("La Positiva", "done"),
                    ("Procesando", "active"), ("Listo", "pending"),
                ]), unsafe_allow_html=True)
            status_ph.info(f"Rímac: {rimac_rows:,} · La Positiva: {lp_rows:,} · Procesando...")

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
                st.session_state["update_timestamp"] = datetime.now(TZ_PERU).strftime("%d/%m/%Y %H:%M:%S")
                st.session_state["source"] = "auto"
                st.session_state["rimac_rows"] = rimac_rows
                st.session_state["lp_rows"] = lp_rows
            except Exception as e:
                status_ph.error(f"Error al procesar: {e}")
                st.stop()

            with progress_ph.container():
                st.markdown(render_stepper([
                    ("Rímac", "done"), ("La Positiva", "done"),
                    ("Procesando", "done"), ("Listo", "done"),
                ]), unsafe_allow_html=True)
            status_ph.success(f"Datos actualizados. Rímac ({rimac_rows:,}) + La Positiva ({lp_rows:,})")
            import time; time.sleep(1.5)
            st.rerun()

        # Manual colapsado
        st.markdown("")
        with st.expander("Prefiero subir archivos manualmente"):
            st.markdown("Si tiene los archivos Excel descargados, puede subirlos directamente:")
            col_up1, col_up2 = st.columns(2)
            with col_up1:
                midagri_file = st.file_uploader("Archivo MIDAGRI (La Positiva)", type=["xlsx"], key="midagri_manual")
            with col_up2:
                siniestros_file = st.file_uploader("Archivo Siniestros (Rímac)", type=["xlsx"], key="siniestros_manual")

            if midagri_file and siniestros_file:
                if st.button("Procesar archivos", type="primary", key="proc_manual"):
                    with st.spinner("Procesando archivos subidos..."):
                        try:
                            datos = process_dynamic_data(midagri_file, siniestros_file)
                            st.session_state["datos"] = datos
                            st.session_state["processed"] = True
                            st.session_state["update_timestamp"] = datetime.now(TZ_PERU).strftime("%d/%m/%Y %H:%M:%S")
                            st.session_state["source"] = "manual"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    else:
        # Sin descarga automática
        if not auto_available:
            st.info("Playwright no disponible. Use la carga manual de archivos.")
        elif not has_all_creds:
            missing = []
            if not has_rimac: missing.append("Rímac")
            if not has_lp: missing.append("La Positiva")
            st.warning(f"Credenciales pendientes: {', '.join(missing)}")

        st.markdown("### Cargar archivos")
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            midagri_file = st.file_uploader("Archivo MIDAGRI (.xlsx)", type=["xlsx"], key="midagri_fb")
        with col_up2:
            siniestros_file = st.file_uploader("Archivo Siniestros (.xlsx)", type=["xlsx"], key="siniestros_fb")

        if midagri_file and siniestros_file:
            col_c = st.columns([1, 2, 1])[1]
            with col_c:
                if st.button("Procesar datos", type="primary", use_container_width=True, key="proc_fb"):
                    with st.spinner("Procesando..."):
                        try:
                            datos = process_dynamic_data(midagri_file, siniestros_file)
                            st.session_state["datos"] = datos
                            st.session_state["processed"] = True
                            st.session_state["update_timestamp"] = datetime.now(TZ_PERU).strftime("%d/%m/%Y %H:%M:%S")
                            st.session_state["source"] = "manual"
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    # Info cards
    st.divider()
    st.markdown('<h3 style="text-align:center; color:#1a5276;">¿Qué reportes genera esta app?</h3>', unsafe_allow_html=True)
    st.markdown("")
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)
    with c1:
        st.markdown('<div class="report-card"><div class="icon">📄</div><h3>Ayuda Memoria Nacional</h3><p>Resumen de operatividad SAC a nivel nacional.</p></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="report-card"><div class="icon">🗺️</div><h3>Ayuda Memoria Departamental</h3><p>Detalle por cada departamento.</p></div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="report-card"><div class="icon">📋</div><h3>Operatividad SAC</h3><p>Siniestralidad, coberturas y desembolsos por empresa.</p></div>', unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="report-card"><div class="icon">📊</div><h3>Reporte EME</h3><p>Formato de reporte de emergencia por región.</p></div>', unsafe_allow_html=True)

    footer()
