"""Página: Consultas — Motor de consultas en lenguaje natural."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from datetime import datetime

from shared.state import require_data, get_datos
from shared.components import page_header, footer, render_metric
from query_engine import process_query, get_suggested_queries as get_suggested_basic
from query_llm import process_query_llm, is_llm_available, get_suggested_queries as get_suggested_llm

require_data()
datos = get_datos()

llm_ready = is_llm_available()
engine_label = "IA + SQL" if llm_ready else "Motor Básico"
engine_color = "#27ae60" if llm_ready else "#f39c12"
engine_icon = "🤖" if llm_ready else "⚙️"

page_header("Consultas SAC",
            "Escriba su consulta en lenguaje natural. El sistema analiza los datos y genera texto profesional.",
            badge=engine_label)

st.markdown(f"""
<div class="chat-header">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <div>
            <div class="title">Consulta de Coyuntura SAC</div>
            <div class="subtitle">Redacción automática de informes a partir de datos consolidados.</div>
        </div>
        <span class="engine-badge" style="background:{engine_color}; color:white;">{engine_icon} {engine_label}</span>
    </div>
</div>
""", unsafe_allow_html=True)

if not llm_ready:
    st.info("Para habilitar consultas con IA, agregue ANTHROPIC_API_KEY en las variables de entorno.")

# Consultas sugeridas
suggested = get_suggested_llm() if llm_ready else get_suggested_basic()
st.markdown("**Consultas sugeridas:**")
cols = st.columns(4)
for i, sug in enumerate(suggested[:8]):
    with cols[i % 4]:
        if st.button(sug, key=f"sug_{i}", use_container_width=True):
            st.session_state["query_input"] = sug

st.divider()

query_text = st.text_area(
    "Escriba su consulta:",
    value=st.session_state.get("query_input", ""),
    height=80,
    placeholder="Ej: Resumen de intervenciones en Tumbes, Piura, Lambayeque, Lima y Arequipa",
    key="query_area",
)

col_q1, col_q2, col_q3 = st.columns([1, 1, 3])
with col_q1:
    btn_query = st.button("Consultar", type="primary", use_container_width=True, key="btn_query")

if btn_query and query_text.strip():
    if llm_ready:
        with st.spinner("Analizando datos y redactando respuesta..."):
            result = process_query_llm(query_text, datos)
        if result["error"]:
            st.error(f"Error: {result['error']}")
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
    st.divider()
    engine_used = st.session_state.get("last_query_engine", "básico")
    badge_color = "#27ae60" if engine_used == "IA" else "#f39c12"
    st.markdown(
        f'<div class="query-context">'
        f'<span><strong>Consulta:</strong> {st.session_state.get("last_query_text", "")}</span>'
        f'<span class="engine-badge" style="background:{badge_color}; color:white; font-size:0.65rem;">'
        f'{engine_used}</span></div>',
        unsafe_allow_html=True)

    prose = st.session_state["last_query_prose"]
    st.markdown(f'<div class="query-result-box">{prose}</div>', unsafe_allow_html=True)

    st.markdown("")
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        st.download_button("Descargar .txt", data=prose,
                           file_name=f"SAC_consulta_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                           mime="text/plain", key="dl_txt", use_container_width=True)

    if st.session_state.get("last_query_sql"):
        with st.expander("Ver consulta SQL generada"):
            st.code(st.session_state["last_query_sql"], language="sql")

    if st.session_state.get("last_query_data") is not None:
        df_result = st.session_state["last_query_data"]
        if len(df_result) > 0:
            with st.expander(f"Ver datos ({len(df_result)} filas)"):
                st.dataframe(df_result, use_container_width=True, hide_index=True)

    if st.session_state.get("last_query_summary"):
        summary = st.session_state["last_query_summary"]
        with st.expander("Resumen verificado"):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(render_metric("Total Avisos",
                    f"{summary.get('total_avisos', 0):,}", None, "blue"),
                    unsafe_allow_html=True)
            with c2:
                st.markdown(render_metric("Indemnización",
                    f"S/ {summary.get('total_indemnizacion', 0):,.2f}", None, "amber"),
                    unsafe_allow_html=True)
            with c3:
                st.markdown(render_metric("Desembolso",
                    f"S/ {summary.get('total_desembolso', 0):,.2f}", None, "purple"),
                    unsafe_allow_html=True)
            with c4:
                st.markdown(render_metric("Productores",
                    f"{summary.get('total_productores', 0):,}", None, "green"),
                    unsafe_allow_html=True)

footer()
