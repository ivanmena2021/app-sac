"""
App SAC — Generador Automático de Reportes del Seguro Agrícola Catastrófico
Interfaz Streamlit (tipo Shiny App)
"""

import streamlit as st
import os
import sys
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
    page_title="SAC - Generador de Reportes",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1F4E79 0%, #2E75B6 100%);
        padding: 1.5rem 2rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-header h1 {
        color: white !important;
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        color: #D6E4F0;
        margin: 0.3rem 0 0 0;
        font-size: 0.95rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #1F4E79;
        margin-bottom: 0.5rem;
    }
    .metric-card h3 {
        margin: 0;
        color: #1F4E79;
        font-size: 1.5rem;
    }
    .metric-card p {
        margin: 0;
        color: #666;
        font-size: 0.85rem;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 20px;
        background: #f0f2f6;
        border-radius: 8px 8px 0 0;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="main-header">
    <h1>🌾 Generador de Reportes SAC 2025-2026</h1>
    <p>Seguro Agrícola Catastrófico — MIDAGRI | Suba los archivos dinámicos para generar los reportes automáticamente</p>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR — CARGA DE ARCHIVOS
# ═══════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 📂 Carga de Archivos")
    st.markdown("---")

    st.markdown("**1. Archivo MIDAGRI** (Reporte Listar Todos los Avisos)")
    midagri_file = st.file_uploader(
        "Subir archivo MIDAGRI (.xlsx)",
        type=["xlsx"],
        key="midagri",
        help="Archivo Excel descargado del sistema MIDAGRI con todos los avisos de siniestro."
    )

    st.markdown("---")

    st.markdown("**2. Sistema de Registro de Siniestros**")
    siniestros_file = st.file_uploader(
        "Subir archivo Siniestros (.xlsx)",
        type=["xlsx"],
        key="siniestros",
        help="Archivo Excel del Sistema de Registro de Siniestros de las aseguradoras."
    )

    st.markdown("---")

    # ─── Descarga Automática ───
    st.markdown("### 🔄 Descarga Automática")
    auto_download_available = False
    try:
        from auto_download import descargar_rimac, descargar_lapositiva
        auto_download_available = True
    except ImportError:
        pass

    if auto_download_available:
        # Verificar credenciales en secrets
        has_rimac_creds = False
        has_lp_creds = False
        try:
            has_rimac_creds = bool(st.secrets.get("rimac", {}).get("email"))
            has_lp_creds = bool(st.secrets.get("lapositiva", {}).get("usuario"))
        except Exception:
            pass

        if not has_rimac_creds or not has_lp_creds:
            st.warning("⚙️ Configure las credenciales en Settings > Secrets")
        else:
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                btn_rimac = st.button("📥 Rímac", key="dl_rimac", use_container_width=True)
            with col_dl2:
                btn_lp = st.button("📥 La Positiva", key="dl_lp", use_container_width=True)

            btn_ambos = st.button("📥 Descargar Ambos", type="primary",
                                  key="dl_ambos", use_container_width=True)

            if btn_rimac or btn_ambos:
                with st.spinner("Descargando desde SISGAQSAC (Rímac)..."):
                    try:
                        import io
                        df_r = descargar_rimac()
                        buffer = io.BytesIO()
                        df_r.to_excel(buffer, index=False)
                        st.session_state["auto_siniestros"] = buffer.getvalue()
                        st.session_state["auto_siniestros_rows"] = len(df_r)
                        st.success(f"✅ Rímac: {len(df_r):,} filas")
                    except Exception as e:
                        st.error(f"Error Rímac: {str(e)}")

            if btn_lp or btn_ambos:
                with st.spinner("Descargando desde Agroevaluaciones (~70s)..."):
                    try:
                        import io
                        df_lp = descargar_lapositiva()
                        buffer = io.BytesIO()
                        df_lp.to_excel(buffer, index=False)
                        st.session_state["auto_midagri"] = buffer.getvalue()
                        st.session_state["auto_midagri_rows"] = len(df_lp)
                        st.success(f"✅ La Positiva: {len(df_lp):,} filas")
                    except Exception as e:
                        st.error(f"Error La Positiva: {str(e)}")

            # Si hay datos auto-descargados, usarlos como archivos
            if st.session_state.get("auto_siniestros") and st.session_state.get("auto_midagri"):
                st.info(
                    f"📦 Datos listos: Rímac ({st.session_state['auto_siniestros_rows']:,}) "
                    f"+ La Positiva ({st.session_state['auto_midagri_rows']:,})"
                )
                if st.button("🚀 Procesar datos descargados", type="primary",
                             use_container_width=True, key="proc_auto"):
                    import io
                    siniestros_file = io.BytesIO(st.session_state["auto_siniestros"])
                    midagri_file = io.BytesIO(st.session_state["auto_midagri"])
                    st.session_state["auto_procesar"] = True
    else:
        st.caption("Playwright no disponible. Use carga manual.")

    st.markdown("---")

    if midagri_file and siniestros_file:
        st.success("✅ Ambos archivos cargados")
        procesar = st.button("🚀 Procesar datos", type="primary", use_container_width=True)
    elif not st.session_state.get("auto_procesar"):
        st.info("📌 Suba ambos archivos o use descarga automática")
        procesar = False
    else:
        procesar = False

    # Si se pidió procesar desde descarga automática
    if st.session_state.get("auto_procesar"):
        procesar = True
        import io
        midagri_file = io.BytesIO(st.session_state["auto_midagri"])
        siniestros_file = io.BytesIO(st.session_state["auto_siniestros"])
        st.session_state["auto_procesar"] = False

    st.markdown("---")
    st.markdown(
        "<small style='color: #888;'>Datos estáticos: Materia Asegurada SAC 2025-2026 "
        "y Resumen SAC 2025-2026 (incluidos en la app).</small>",
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════════════
# PROCESAMIENTO
# ═══════════════════════════════════════════════════════════════════════
if procesar:
    with st.spinner("Procesando datos... Por favor espere."):
        try:
            datos = process_dynamic_data(midagri_file, siniestros_file)
            st.session_state["datos"] = datos
            st.session_state["processed"] = True
        except Exception as e:
            st.error(f"Error al procesar los datos: {str(e)}")
            st.session_state["processed"] = False

# ═══════════════════════════════════════════════════════════════════════
# CONTENIDO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
if st.session_state.get("processed"):
    datos = st.session_state["datos"]

    # ─── Dashboard de métricas ───
    st.markdown("### 📊 Resumen Nacional")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Avisos Reportados", f"{datos['total_avisos']:,}")
    with col2:
        st.metric("Avisos Ajustados", f"{datos['total_ajustados']:,}", f"{datos['pct_ajustados']:.1f}%")
    with col3:
        st.metric("Indemnización Total", f"S/ {datos['monto_indemnizado']:,.2f}")
    with col4:
        st.metric("Desembolsos", f"S/ {datos['monto_desembolsado']:,.2f}", f"{datos['pct_desembolso']:.1f}%")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Hectáreas Aseguradas", f"{datos['sup_asegurada']:,.2f}")
    with col6:
        st.metric("Ha Indemnizadas", f"{datos['ha_indemnizadas']:,.2f}")
    with col7:
        st.metric("Siniestralidad", f"{datos['indice_siniestralidad']:.2f}%")
    with col8:
        st.metric("Productores Beneficiados", f"{int(datos['productores_desembolso']):,}")

    st.markdown("---")

    # ─── Tabs para generación de reportes ───
    tab1, tab2, tab3, tab4 = st.tabs([
        "📄 Ayuda Memoria Nacional",
        "📄 Ayuda Memoria Departamental",
        "📊 Reporte EME (Excel)",
        "📈 Explorar Datos",
    ])

    # ═══ TAB 1: Ayuda Memoria Nacional ═══
    with tab1:
        st.markdown("### Ayuda Memoria: Resumen Operatividad SAC 2025-2026")
        st.markdown(f"Fecha de corte: **{datos['fecha_corte']}**")

        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.markdown("**Contenido del documento:**")
            st.markdown(
                "- Activación del SAC (procedimiento)\n"
                "- Datos Generales a Nivel Nacional\n"
                "- Cuadro 1: Primas y Cobertura por Departamento\n"
                "- Cuadro 2: Indemnizaciones y Desembolsos por Departamento\n"
                "- Cuadro 3: Eventos Asociados a Lluvias Intensas"
            )

        with col_b:
            if st.button("🔄 Generar Ayuda Memoria Nacional", type="primary", key="gen_nacional"):
                with st.spinner("Generando documento Word..."):
                    try:
                        doc_bytes = generate_nacional_docx(datos)
                        fecha_str = datetime.now().strftime("%d_%m_%Y")
                        filename = f"Ayuda_Memoria_Resumen_SAC_2025-2026_{fecha_str}.docx"
                        st.session_state["doc_nacional"] = doc_bytes
                        st.session_state["doc_nacional_name"] = filename
                        st.success("✅ Documento generado exitosamente")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            if st.session_state.get("doc_nacional"):
                st.download_button(
                    label="⬇️ Descargar Ayuda Memoria Nacional",
                    data=st.session_state["doc_nacional"],
                    file_name=st.session_state["doc_nacional_name"],
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        # Preview de cuadros
        with st.expander("📋 Vista previa: Cuadro 1 — Primas y Cobertura"):
            st.dataframe(datos["cuadro1"], use_container_width=True, hide_index=True)

        with st.expander("📋 Vista previa: Cuadro 2 — Indemnizaciones y Desembolsos"):
            st.dataframe(datos["cuadro2"], use_container_width=True, hide_index=True)

        with st.expander("📋 Vista previa: Cuadro 3 — Lluvias Intensas"):
            st.dataframe(datos["cuadro3"], use_container_width=True, hide_index=True)

    # ═══ TAB 2: Ayuda Memoria Departamental ═══
    with tab2:
        st.markdown("### Ayuda Memoria Departamental del SAC")

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
                st.metric("Avisos", depto_data["total_avisos"])
            with col_d2:
                st.metric("Indemnización", f"S/ {depto_data['monto_indemnizado']:,.2f}")
            with col_d3:
                st.metric("Ha Indemnizadas", f"{depto_data['ha_indemnizadas']:,.2f}")
            with col_d4:
                st.metric("Desembolso", f"S/ {depto_data['monto_desembolsado']:,.2f}")

            st.markdown(f"**Aseguradora:** {depto_data['empresa']} | "
                        f"**Prima neta:** S/ {depto_data['prima_neta']:,.2f} | "
                        f"**Superficie asegurada:** {depto_data['sup_asegurada']:,.0f} ha")

            col_gen, col_dl = st.columns([1, 1])
            with col_gen:
                if st.button("🔄 Generar Ayuda Memoria Departamental", type="primary", key="gen_depto"):
                    with st.spinner(f"Generando documento para {depto_seleccionado.title()}..."):
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
                        label="⬇️ Descargar Ayuda Memoria Departamental",
                        data=st.session_state["doc_depto"],
                        file_name=st.session_state["doc_depto_name"],
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                    )

            # Preview
            with st.expander("📋 Avisos por Tipo de Siniestro"):
                if len(depto_data["avisos_tipo"]) > 0:
                    st.dataframe(
                        depto_data["avisos_tipo"].reset_index().rename(
                            columns={"index": "Tipo Siniestro", "TIPO_SINIESTRO": "Tipo Siniestro", "count": "N° Avisos"}
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

            with st.expander("📋 Distribución por Provincia"):
                if len(depto_data["dist_provincia"]) > 0:
                    st.dataframe(depto_data["dist_provincia"], use_container_width=True, hide_index=True)

    # ═══ TAB 3: Reporte EME ═══
    with tab3:
        st.markdown("### Formato Reporte EME — Actualización Nacional")
        st.markdown("Reporte consolidado por región con acciones implementadas, en implementación y por implementar.")

        col_e1, col_e2 = st.columns([1, 1])
        with col_e1:
            if st.button("🔄 Generar Reporte EME (Excel)", type="primary", key="gen_eme"):
                with st.spinner("Generando reporte Excel..."):
                    try:
                        xls_bytes = generate_reporte_eme(datos)
                        fecha_str = datetime.now().strftime("%d_%m_%Y")
                        filename = f"formato_reporte_EME_{fecha_str}_actualizado.xlsx"
                        st.session_state["xls_eme"] = xls_bytes
                        st.session_state["xls_eme_name"] = filename
                        st.success("✅ Reporte EME generado exitosamente")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

        with col_e2:
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
        st.markdown("### Explorar Datos Cargados")

        sub_tab1, sub_tab2 = st.tabs(["MIDAGRI", "Siniestros"])

        with sub_tab1:
            st.markdown(f"**Registros MIDAGRI:** {len(datos['midagri']):,}")
            st.dataframe(datos["midagri"].head(100), use_container_width=True, hide_index=True)

        with sub_tab2:
            st.markdown(f"**Registros Siniestros:** {len(datos['siniestros']):,}")
            st.dataframe(datos["siniestros"].head(100), use_container_width=True, hide_index=True)

        # Gráficos
        st.markdown("---")
        st.markdown("### Distribución de Siniestros por Tipo")
        if len(datos["siniestros_por_tipo"]) > 0:
            chart_data = datos["siniestros_por_tipo"].reset_index()
            chart_data.columns = ["Tipo Siniestro", "Cantidad"]
            st.bar_chart(chart_data.set_index("Tipo Siniestro").head(10))

else:
    # Estado inicial — sin datos cargados
    st.markdown("---")

    col_info1, col_info2, col_info3 = st.columns(3)

    with col_info1:
        st.markdown("""
        <div class="metric-card">
            <h3>📄</h3>
            <p><strong>Ayuda Memoria Nacional</strong><br>
            Resumen de operatividad del SAC a nivel nacional con cuadros de primas,
            indemnizaciones y eventos de lluvias intensas.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_info2:
        st.markdown("""
        <div class="metric-card">
            <h3>📄</h3>
            <p><strong>Ayuda Memoria Departamental</strong><br>
            Detalle por departamento: proceso SAC, panorama general, eventos recientes
            y resumen operativo.</p>
        </div>
        """, unsafe_allow_html=True)

    with col_info3:
        st.markdown("""
        <div class="metric-card">
            <h3>📊</h3>
            <p><strong>Reporte EME (Excel)</strong><br>
            Formato de reporte de emergencia con acciones implementadas,
            en implementación y por implementar por región.</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        "**Instrucciones:** Suba los 2 archivos dinámicos en el panel lateral izquierdo "
        "(archivo MIDAGRI y archivo del Sistema de Registro de Siniestros) y presione "
        "**Procesar datos** para comenzar."
    )
