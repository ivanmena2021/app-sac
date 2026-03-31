"""Página: Comparativo de Campañas."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from shared.state import require_data, get_datos
from shared.components import page_header, footer
from comparativo_campanias import (load_campania_anterior, generate_comparison_chart,
                                    get_comparison_table, get_monthly_detail_table, METRICAS_COMPARACION)

require_data()
datos = get_datos()
df_actual = datos["midagri"]

page_header("Comparativo de Campañas",
            "Comparación de indicadores SAC entre la campaña actual y la anterior")

df_anterior = load_campania_anterior()
if df_anterior is None or df_anterior.empty:
    st.info("No se encontraron datos de la campaña anterior para comparar.")
else:
    n_actual = len(df_actual)
    n_anterior = len(df_anterior)
    st.markdown(f"""
    <div class="tab-intro">
        <div class="title">Campañas: 2025-2026 (actual: {n_actual:,} avisos) vs 2024-2025 ({n_anterior:,} avisos)</div>
        <div class="desc">Seleccione una métrica para comparar la evolución entre campañas.</div>
    </div>
    """, unsafe_allow_html=True)

    metrica_sel = st.radio("Métrica:", options=list(METRICAS_COMPARACION.keys()),
                            horizontal=True, key="metrica_comp")

    try:
        fig = generate_comparison_chart(df_actual, df_anterior, metrica_sel)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Error al generar gráfico: {e}")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Resumen por departamento**")
        try:
            df_comp = get_comparison_table(df_actual, df_anterior)
            if df_comp is not None and not df_comp.empty:
                st.dataframe(df_comp, use_container_width=True, hide_index=True, height=400)
        except Exception:
            pass
    with col2:
        st.markdown("**Detalle mensual**")
        try:
            df_month = get_monthly_detail_table(df_actual, df_anterior, metrica_sel)
            if df_month is not None and not df_month.empty:
                st.dataframe(df_month, use_container_width=True, hide_index=True, height=400)
        except Exception:
            pass

footer()
