"""Página: Explorar Datos + Calidad."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from shared.state import require_data, get_datos
from shared.components import page_header, footer
from data_quality import render_quality_dashboard

require_data()
datos = get_datos()

page_header("Explorar Datos",
            "Visualización directa de los datos consolidados y análisis de calidad")

tab_data, tab_quality = st.tabs(["📊 Datos Consolidados", "📋 Calidad de Datos"])

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
        st.markdown("**Distribución por tipo de siniestro:**")
        import plotly.express as px
        tipo_counts = datos["midagri"]["TIPO_SINIESTRO"].value_counts().head(15)
        fig = px.bar(x=tipo_counts.values, y=tipo_counts.index, orientation="h",
                     labels={"x": "Avisos", "y": "Tipo"}, color_discrete_sequence=["#2980b9"])
        fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)

with tab_quality:
    render_quality_dashboard(datos)

footer()
