"""Página: Explorar Datos + Calidad."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from shared.state import require_data, get_datos
from shared.components import page_header, footer
from shared.charts import apply_theme, render_chart, PALETTE
from data_quality import render_quality_dashboard

require_data()
datos = get_datos()

page_header("Explorar Datos",
            "Visualización directa de los datos consolidados y análisis de calidad",
            badge="Datos + Calidad")

tab_data, tab_quality = st.tabs(["Datos Consolidados", "Calidad de Datos"])

with tab_data:
    sub1, sub2 = st.tabs(["MIDAGRI (La Positiva)", "Siniestros (Rímac)"])
    with sub1:
        st.markdown(f"**Registros:** {len(datos['midagri']):,}")
        st.dataframe(datos["midagri"].head(200), use_container_width=True, hide_index=True)
    with sub2:
        if datos.get("siniestros") is not None and not datos["siniestros"].empty:
            st.markdown(f"**Registros:** {len(datos['siniestros']):,}")
            st.dataframe(datos["siniestros"].head(200), use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos separados de siniestros (Rímac).")

    if "TIPO_SINIESTRO" in datos["midagri"].columns:
        st.markdown("**Distribución por tipo de siniestro**")
        import plotly.graph_objects as go
        tipo_counts = datos["midagri"]["TIPO_SINIESTRO"].value_counts().head(15)
        total = int(tipo_counts.sum()) or 1
        # Gradiente: más alto → azul más intenso
        max_v = int(tipo_counts.max()) if len(tipo_counts) else 1
        colors = [
            f"rgba(26,82,118,{0.45 + 0.55 * (v / max_v):.3f})"
            for v in tipo_counts.values
        ]
        fig = go.Figure(go.Bar(
            x=tipo_counts.values, y=tipo_counts.index,
            orientation="h",
            marker=dict(color=colors, line=dict(width=0), cornerradius=4),
            text=[f"{v:,} ({v/total:.0%})" for v in tipo_counts.values],
            textposition="outside",
            textfont=dict(size=11, color=PALETTE["text_soft"]),
            hovertemplate="<b>%{y}</b><br>Avisos: %{x:,}<extra></extra>",
        ))
        fig.update_yaxes(autorange="reversed")
        apply_theme(
            fig,
            title="Top 15 Tipos de Siniestro",
            subtitle=f"De un total de {total:,} avisos",
            height=460, show_legend=False,
            xaxis_title="N.° de avisos", yaxis_title="",
        )
        render_chart(fig, key="chart_tipos_siniestro",
                     filename="distribucion_tipos_siniestro")

with tab_quality:
    render_quality_dashboard(datos)

footer()
