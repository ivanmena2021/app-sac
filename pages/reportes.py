"""Página: Generar Reportes — todos los tipos de reportes SAC."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from datetime import datetime

from shared.state import require_data, get_datos
from shared.components import render_metric, page_header, footer
from data_processor import get_departamento_data, load_primas_historicas
from gen_word_bridge_py import generate_nacional_docx, generate_departamental_docx
from gen_excel_eme import generate_reporte_eme
from gen_word_operatividad import generate_operatividad_docx
from gen_ppt_dinamico import generar_ppt_dinamico
from gen_ppt_historico import generar_ppt_historico
from batch_reports import render_batch_tab

require_data()
datos = get_datos()

page_header("Generar Reportes",
            "Documentos Word, Excel y PowerPoint del Seguro Agrícola Catastrófico")

tab_nac, tab_depto, tab_oper, tab_eme, tab_ppt, tab_batch, tab_hist = st.tabs([
    "Nacional",
    "Departamental",
    "Operatividad",
    "EME",
    "PPT Dinámica",
    "Todos",
    "Histórico",
])

# ═══ Nacional ═══
with tab_nac:
    st.markdown(f'<div class="tab-intro"><div class="title">Ayuda Memoria Nacional · Corte {datos["fecha_corte"]}</div>'
                f'<div class="desc">Resumen nacional: primas, cobertura, indemnizaciones y eventos.</div></div>',
                unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Generar documento", type="primary", key="gen_nac", use_container_width=True):
            with st.spinner("Generando Ayuda Memoria Nacional..."):
                try:
                    doc_bytes = generate_nacional_docx(datos)
                    fecha_str = datetime.now().strftime("%d_%m_%Y")
                    st.session_state["doc_nacional"] = doc_bytes
                    st.session_state["doc_nacional_name"] = f"Ayuda_Memoria_Resumen_SAC_2025-2026_{fecha_str}.docx"
                    st.success("Documento generado")
                except Exception as e:
                    st.error(f"Error: {e}")
    with c2:
        if st.session_state.get("doc_nacional"):
            st.download_button("⬇️ Descargar", data=st.session_state["doc_nacional"],
                               file_name=st.session_state["doc_nacional_name"],
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               use_container_width=True)

    with st.expander("Cuadro 1 — Primas y Cobertura"):
        st.dataframe(datos["cuadro1"], use_container_width=True, hide_index=True)
    with st.expander("Cuadro 2 — Indemnizaciones y Desembolsos"):
        st.dataframe(datos["cuadro2"], use_container_width=True, hide_index=True)
    with st.expander("Cuadro 3 — Lluvias Intensas"):
        st.dataframe(datos["cuadro3"], use_container_width=True, hide_index=True)

    # PDF Ejecutivo
    st.markdown("---")
    cp1, cp2 = st.columns([1, 1])
    with cp1:
        if st.button("Generar PDF Ejecutivo", key="gen_pdf_exec"):
            with st.spinner("Generando PDF..."):
                try:
                    from gen_pdf_resumen import generate_executive_pdf
                    pdf_bytes = generate_executive_pdf(datos)
                    st.session_state["pdf_exec"] = pdf_bytes
                    st.session_state["pdf_exec_name"] = f"Resumen_Ejecutivo_SAC_{datetime.now().strftime('%d_%m_%Y')}.pdf"
                    st.success("PDF generado")
                except Exception as e:
                    st.error(f"Error: {e}")
    with cp2:
        if st.session_state.get("pdf_exec"):
            st.download_button("⬇️ Descargar PDF", data=st.session_state["pdf_exec"],
                               file_name=st.session_state["pdf_exec_name"], mime="application/pdf",
                               use_container_width=True)

# ═══ Departamental ═══
with tab_depto:
    depto_sel = st.selectbox("Seleccione departamento:", options=datos["departamentos_list"],
                              format_func=lambda x: x.title())
    if depto_sel:
        depto_data = get_departamento_data(datos, depto_sel)
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(render_metric("Avisos", str(depto_data["total_avisos"]), None, "blue"), unsafe_allow_html=True)
        with c2: st.markdown(render_metric("Indemnización", f"S/ {depto_data['monto_indemnizado']:,.0f}", None, "amber"), unsafe_allow_html=True)
        with c3: st.markdown(render_metric("Ha Indemnizadas", f"{depto_data['ha_indemnizadas']:,.0f}", None, "green"), unsafe_allow_html=True)
        with c4: st.markdown(render_metric("Desembolso", f"S/ {depto_data['monto_desembolsado']:,.0f}", None, "purple"), unsafe_allow_html=True)

        st.markdown(f"**Aseguradora:** {depto_data['empresa']} · **Prima:** S/ {depto_data['prima_neta']:,.2f} · **Ha aseguradas:** {depto_data['sup_asegurada']:,.0f}")

        cg, cd = st.columns([1, 1])
        with cg:
            if st.button("Generar documento", type="primary", key="gen_depto", use_container_width=True):
                with st.spinner(f"Generando reporte de {depto_sel.title()}..."):
                    try:
                        doc_bytes = generate_departamental_docx(depto_data)
                        st.session_state["doc_depto"] = doc_bytes
                        st.session_state["doc_depto_name"] = f"Ayuda_Memoria_SAC_{depto_sel.title()}_{datetime.now().strftime('%d_%m_%Y')}.docx"
                        st.success(f"Documento de {depto_sel.title()} generado")
                    except Exception as e:
                        st.error(f"Error: {e}")
        with cd:
            if st.session_state.get("doc_depto"):
                st.download_button(f"⬇️ Descargar", data=st.session_state["doc_depto"],
                                   file_name=st.session_state["doc_depto_name"],
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                   use_container_width=True)

# ═══ Operatividad ═══
with tab_oper:
    st.markdown(f'<div class="tab-intro"><div class="title">Operatividad SAC · Corte {datos["fecha_corte"]}</div>'
                f'<div class="desc">Detalle por empresa: siniestralidad, coberturas, cultivos y desembolsos.</div></div>',
                unsafe_allow_html=True)
    cg, cd = st.columns([1, 1])
    with cg:
        if st.button("Generar Operatividad", type="primary", key="gen_oper", use_container_width=True):
            with st.spinner("Generando..."):
                try:
                    doc_bytes = generate_operatividad_docx(datos)
                    st.session_state["doc_operatividad"] = doc_bytes
                    st.session_state["doc_operatividad_name"] = f"AM_Operatividad_SAC_{datetime.now().strftime('%d_%m_%Y')}.docx"
                    st.success("Documento generado")
                except Exception as e:
                    st.error(f"Error: {e}")
    with cd:
        if st.session_state.get("doc_operatividad"):
            st.download_button("⬇️ Descargar", data=st.session_state["doc_operatividad"],
                               file_name=st.session_state["doc_operatividad_name"],
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               use_container_width=True)

# ═══ EME ═══
with tab_eme:
    st.markdown('<div class="tab-intro"><div class="title">Reporte de Emergencia (EME)</div>'
                '<div class="desc">Formato consolidado por región con acciones implementadas.</div></div>',
                unsafe_allow_html=True)
    cg, cd = st.columns([1, 1])
    with cg:
        if st.button("Generar Reporte EME", type="primary", key="gen_eme", use_container_width=True):
            with st.spinner("Generando Excel..."):
                try:
                    xls_bytes = generate_reporte_eme(datos)
                    st.session_state["xls_eme"] = xls_bytes
                    st.session_state["xls_eme_name"] = f"formato_reporte_EME_{datetime.now().strftime('%d_%m_%Y')}.xlsx"
                    st.success("Reporte EME generado")
                except Exception as e:
                    st.error(f"Error: {e}")
    with cd:
        if st.session_state.get("xls_eme"):
            st.download_button("⬇️ Descargar EME", data=st.session_state["xls_eme"],
                               file_name=st.session_state["xls_eme_name"],
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)

# ═══ PPT Dinámica ═══
with tab_ppt:
    st.markdown(f'<div class="tab-intro"><div class="title">Presentación Dinámica · Corte {datos["fecha_corte"]}</div>'
                f'<div class="desc">Configure alcance geográfico, siniestro y período para generar una PPT personalizada.</div></div>',
                unsafe_allow_html=True)

    df_ppt = datos["midagri"]
    incluir_nacional = st.checkbox("Incluir Resumen Nacional", value=True, key="ppt_incluir_nac")

    col_emp, col_dep, col_prov = st.columns([0.8, 1.1, 1.1])
    with col_emp:
        empresa_ppt = st.radio("Aseguradora", ["Ambas", "LA POSITIVA", "RIMAC"], key="ppt_empresa")
    with col_dep:
        deptos_ppt = sorted(df_ppt["DEPARTAMENTO"].dropna().unique()) if "DEPARTAMENTO" in df_ppt.columns else []
        deptos_sel = st.multiselect("Departamento(s)", deptos_ppt, key="ppt_deptos")
    with col_prov:
        provs_sel, dists_sel = [], []
        if deptos_sel and "PROVINCIA" in df_ppt.columns:
            provs_disp = sorted(df_ppt[df_ppt["DEPARTAMENTO"].isin(deptos_sel)]["PROVINCIA"].dropna().unique())
            provs_sel = st.multiselect("Provincia(s)", provs_disp, key="ppt_provs")

    if provs_sel and "DISTRITO" in df_ppt.columns:
        dists_disp = sorted(df_ppt[df_ppt["PROVINCIA"].isin(provs_sel)]["DISTRITO"].dropna().unique())
        dists_sel = st.multiselect("Distrito(s) — máx. 5", dists_disp, max_selections=5, key="ppt_dists")

    scope = "nacional"
    if dists_sel: scope = "distrital"
    elif provs_sel: scope = "provincial"
    elif deptos_sel: scope = "departamental"

    st.divider()
    st.markdown("##### Análisis complementario (opcional)")
    tipos_disp = sorted(df_ppt["TIPO_SINIESTRO"].dropna().unique()) if "TIPO_SINIESTRO" in df_ppt.columns else []
    tipos_sel = st.multiselect("Tipo(s) de siniestro", tipos_disp, key="ppt_tipos")
    filtrar_fecha = st.checkbox("Filtrar por período", key="ppt_filtrar_fecha")
    fecha_ini, fecha_fin = None, None
    if filtrar_fecha:
        cf1, cf2 = st.columns(2)
        with cf1: fecha_ini = st.date_input("Desde", key="ppt_fecha_ini")
        with cf2: fecha_fin = st.date_input("Hasta", key="ppt_fecha_fin")

    filtros = {
        "scope": scope, "incluir_nacional": incluir_nacional,
        "departamentos": deptos_sel, "provincias": provs_sel, "distritos": dists_sel,
        "tipos_siniestro": tipos_sel, "empresa": empresa_ppt.lower() if empresa_ppt != "Ambas" else "ambas",
        "fecha_inicio": fecha_ini, "fecha_fin": fecha_fin, "col_fecha": "FECHA_AVISO",
    }

    cg, cd = st.columns([1, 1])
    with cg:
        if st.button("Generar Presentación", type="primary", key="gen_ppt_din", use_container_width=True):
            with st.spinner("Generando PowerPoint..."):
                try:
                    ppt_bytes = generar_ppt_dinamico(df_ppt, filtros, datos["fecha_corte"])
                    geo_str = "_".join(deptos_sel[:2]) if deptos_sel else ""
                    fname = f"SAC_{scope}_{geo_str}_{datetime.now().strftime('%d_%m_%Y')}.pptx"
                    st.session_state["ppt_dinamico"] = ppt_bytes
                    st.session_state["ppt_dinamico_name"] = fname
                    st.success(f"Presentación generada ({len(ppt_bytes)/1024:.0f} KB)")
                except Exception as e:
                    st.error(f"Error: {e}")
    with cd:
        if st.session_state.get("ppt_dinamico"):
            st.download_button("⬇️ Descargar PPT", data=st.session_state["ppt_dinamico"],
                               file_name=st.session_state.get("ppt_dinamico_name", "SAC.pptx"),
                               mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                               use_container_width=True)

# ═══ Generar Todos ═══
with tab_batch:
    render_batch_tab(datos)

# ═══ Análisis Histórico ═══
with tab_hist:
    st.markdown("""
    <div style="background:linear-gradient(135deg,#2C5F2D 0%,#1a3a1a 100%);
         padding:14px 20px;border-radius:10px;margin-bottom:14px;">
        <span style="color:#fff;font-size:18px;font-weight:700;">
        📈 Análisis Histórico de Siniestralidad</span><br>
        <span style="color:#d4edda;font-size:12px;">
        PPT con siniestralidad de 5 campañas + la actual. Siniestralidad = Indemnización / Prima Neta.</span>
    </div>
    """, unsafe_allow_html=True)

    dept_list_hist = datos.get("departamentos_list", [])
    if dept_list_hist:
        sel_hist = st.selectbox("Seleccione departamento:", sorted(dept_list_hist), key="hist_dept_select")
        cg, cd = st.columns([1, 1])
        with cg:
            if st.button("Generar PPT Histórica", type="primary", key="gen_hist_ppt"):
                with st.spinner(f"Generando análisis histórico de {sel_hist}..."):
                    try:
                        primas = load_primas_historicas()
                        ppt_bytes = generar_ppt_historico(sel_hist, datos, primas)
                        fname = f"Historico_SAC_{sel_hist}_{datetime.now().strftime('%d_%m_%Y')}.pptx"
                        st.session_state["ppt_historico"] = ppt_bytes
                        st.session_state["ppt_historico_name"] = fname
                        st.success(f"PPT generada: {fname}")
                    except Exception as e:
                        st.error(f"Error: {e}")
        with cd:
            if st.session_state.get("ppt_historico"):
                st.download_button("⬇️ Descargar PPT Histórica",
                                   data=st.session_state["ppt_historico"],
                                   file_name=st.session_state.get("ppt_historico_name", "historico.pptx"),
                                   mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                                   use_container_width=True, key="dl_hist_ppt")

footer()
