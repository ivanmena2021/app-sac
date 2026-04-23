"""Página: Mapa de Calor — Visualización geográfica interactiva."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from shared.state import require_data, get_datos
from shared.components import render_metric, page_header, footer
from shared.charts import render_chart
from gen_mapa_calor import generate_map, get_ranking_table, get_summary_cards, NIVELES, get_metricas_for_nivel

require_data()
datos = get_datos()

page_header("Mapa de Calor SAC",
            f"Visualización geográfica interactiva de los indicadores del SAC · Corte {datos['fecha_corte']}",
            badge="Geografía")

# Controles
col1, col2 = st.columns([1, 2])
with col1:
    nivel_seleccionado = st.radio("Nivel geográfico:", options=list(NIVELES.keys()),
                                   horizontal=True, key="nivel_mapa")
with col2:
    depto_filter = None
    if nivel_seleccionado in ("Provincial", "Distrital"):
        depto_options = ["Todos"] + datos.get("departamentos_list", [])
        depto_sel = st.selectbox("Filtrar por departamento:", options=depto_options,
                                  format_func=lambda x: x.title() if x != "Todos" else "Todos",
                                  key="depto_filter_mapa")
        if depto_sel != "Todos":
            depto_filter = [depto_sel]

metricas_nivel = get_metricas_for_nivel(nivel_seleccionado)
metrica_seleccionada = st.radio("Métrica a visualizar:", options=list(metricas_nivel.keys()),
                                 horizontal=True, key="metrica_mapa")

meta_info = metricas_nivel[metrica_seleccionada]
st.markdown(f'<div style="background:#f0f7ff; padding:0.5rem 1rem; border-radius:10px; '
            f'color:#1a5276; font-size:0.83rem; margin-bottom:0.8rem;">'
            f'{meta_info["description"]}</div>', unsafe_allow_html=True)

# Summary cards
try:
    cards = get_summary_cards(datos, nivel_seleccionado, depto_filter)
    if cards:
        cc1, cc2, cc3, cc4 = st.columns(4)
        with cc1:
            st.markdown(render_metric("Mayor N° Avisos", f"{cards['top_avisos']}",
                                       f"{cards['top_avisos_n']:,} avisos", "blue"), unsafe_allow_html=True)
        with cc2:
            st.markdown(render_metric("Mayor Indemnización", f"{cards['top_indemn']}",
                                       f"S/ {cards['top_indemn_val']:,.0f}", "amber"), unsafe_allow_html=True)
        with cc3:
            st.markdown(render_metric("Mayor Avance Desemb.", f"{cards['top_desemb_pct']}",
                                       f"{cards['top_desemb_pct_val']:.1f}%", "green"), unsafe_allow_html=True)
        with cc4:
            st.markdown(render_metric(f"{cards['units_con_avisos']} {cards.get('label', 'Unidad')}s",
                                       "con avisos", f"de {cards['total_units']} total", "purple"), unsafe_allow_html=True)
except Exception:
    pass

# Mapa + ranking
col_mapa, col_ranking = st.columns([3, 2])
with col_mapa:
    try:
        fig = generate_map(datos, metrica_seleccionada, nivel_seleccionado, depto_filter)
        _depto_str = "_".join(depto_filter).lower() if depto_filter else "peru"
        _metrica_str = metrica_seleccionada.lower().replace(" ", "_").replace("(%)", "pct").replace("(s/)", "soles").replace("/", "_")
        fname = f"mapa_sac_{nivel_seleccionado.lower()}_{_metrica_str}_{_depto_str}"
        render_chart(fig, key="chart_mapa_sac", filename=fname,
                     download_label="Descargar mapa")
    except Exception as e:
        st.error(f"Error al generar mapa: {e}")

with col_ranking:
    nivel_label = NIVELES[nivel_seleccionado]["label"]
    st.markdown(f'<div class="section-header"><div class="icon-box" style="background:#f0e8ff;">🏆</div>'
                f'<h3>Ranking {nivel_label}</h3></div>', unsafe_allow_html=True)
    try:
        df_ranking = get_ranking_table(datos, metrica_seleccionada, nivel_seleccionado, depto_filter)
        if len(df_ranking) > 0:
            st.dataframe(df_ranking, use_container_width=True, hide_index=False, height=520)
        else:
            st.info("Sin datos para los filtros seleccionados.")
    except Exception as e:
        st.error(f"Error al generar ranking: {e}")

footer()
