"""
comparativo_departamentos.py — Comparación lado a lado de múltiples departamentos SAC
Genera tablas y gráficos comparativos de KPIs por departamento seleccionado.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ─── Colores para departamentos ───
DEPT_COLORS = [
    "#0c2340",  # navy
    "#1a5276",  # teal oscuro
    "#2980b9",  # azul
    "#27ae60",  # verde
    "#e67e22",  # naranja
]

# ─── Métricas disponibles ───
METRIC_CONFIG = {
    "Avisos": {
        "key": "avisos",
        "label": "Total de Avisos",
        "formato": "{:,.0f}",
        "suffix": "",
    },
    "Indemnización": {
        "key": "monto_indemnizado",
        "label": "Monto Indemnizado (S/)",
        "formato": "S/ {:,.0f}",
        "suffix": "",
    },
    "Desembolso": {
        "key": "monto_desembolsado",
        "label": "Monto Desembolsado (S/)",
        "formato": "S/ {:,.0f}",
        "suffix": "",
    },
    "Siniestralidad": {
        "key": "siniestralidad",
        "label": "Índice de Siniestralidad (%)",
        "formato": "{:.1f}%",
        "suffix": "%",
    },
}

MAX_DEPTOS = 5


def _safe_numeric(value, default=0):
    """Convert value to float safely, returning default on failure."""
    try:
        result = float(value)
        return result if not np.isnan(result) else default
    except (ValueError, TypeError):
        return default


def _get_dept_metrics(datos, depto):
    """Extract key metrics for one department from datos dict.

    Returns dict with: avisos, ha_indemnizadas, monto_indemnizado,
    monto_desembolsado, productores, siniestralidad, pct_desembolso.
    """
    depto_upper = depto.strip().upper()
    midagri = datos.get("midagri", pd.DataFrame())
    materia = datos.get("materia", pd.DataFrame())

    # Filter midagri by department
    if "DEPARTAMENTO" in midagri.columns:
        df_dept = midagri[midagri["DEPARTAMENTO"] == depto_upper]
    else:
        df_dept = pd.DataFrame()

    avisos = len(df_dept)

    ha_indemnizadas = _safe_numeric(
        df_dept["SUP_INDEMNIZADA"].sum() if "SUP_INDEMNIZADA" in df_dept.columns else 0
    )
    monto_indemnizado = _safe_numeric(
        df_dept["INDEMNIZACION"].sum() if "INDEMNIZACION" in df_dept.columns else 0
    )
    monto_desembolsado = _safe_numeric(
        df_dept["MONTO_DESEMBOLSADO"].sum() if "MONTO_DESEMBOLSADO" in df_dept.columns else 0
    )

    # Productores: only those with indemnizacion > 0
    if "N_PRODUCTORES" in df_dept.columns and "INDEMNIZACION" in df_dept.columns:
        mask = pd.to_numeric(df_dept["INDEMNIZACION"], errors="coerce").fillna(0) > 0
        productores = _safe_numeric(
            pd.to_numeric(df_dept.loc[mask, "N_PRODUCTORES"], errors="coerce").fillna(0).sum()
        )
    elif "N_PRODUCTORES" in df_dept.columns:
        productores = _safe_numeric(df_dept["N_PRODUCTORES"].sum())
    else:
        productores = 0

    # Prima neta from materia for siniestralidad
    if "DEPARTAMENTO" in materia.columns and "PRIMA_NETA" in materia.columns:
        mat_dept = materia[materia["DEPARTAMENTO"] == depto_upper]
        prima_neta = _safe_numeric(
            mat_dept["PRIMA_NETA"].iloc[0] if len(mat_dept) > 0 else 0
        )
    else:
        prima_neta = 0

    siniestralidad = (monto_indemnizado / prima_neta * 100) if prima_neta > 0 else 0
    pct_desembolso = (monto_desembolsado / monto_indemnizado * 100) if monto_indemnizado > 0 else 0

    return {
        "departamento": depto_upper,
        "avisos": int(avisos),
        "ha_indemnizadas": round(ha_indemnizadas, 2),
        "monto_indemnizado": round(monto_indemnizado, 2),
        "monto_desembolsado": round(monto_desembolsado, 2),
        "productores": int(productores),
        "siniestralidad": round(siniestralidad, 2),
        "pct_desembolso": round(pct_desembolso, 2),
        "prima_neta": round(prima_neta, 2),
    }


def generate_comparison_table(datos, deptos):
    """Returns DataFrame with one row per department, columns for each KPI.

    Columns: Departamento, Avisos, Ha Indemnizadas, Monto Indemnizado (S/),
             Monto Desembolsado (S/), Productores, Siniestralidad (%),
             % Desembolso.
    """
    if not deptos:
        return pd.DataFrame()

    rows = []
    for depto in deptos:
        m = _get_dept_metrics(datos, depto)
        rows.append({
            "Departamento": m["departamento"],
            "Avisos": m["avisos"],
            "Ha Indemnizadas": m["ha_indemnizadas"],
            "Monto Indemnizado (S/)": m["monto_indemnizado"],
            "Monto Desembolsado (S/)": m["monto_desembolsado"],
            "Productores": m["productores"],
            "Siniestralidad (%)": m["siniestralidad"],
            "% Desembolso": m["pct_desembolso"],
        })

    df = pd.DataFrame(rows)
    return df


def generate_comparison_chart(datos, deptos, metric_key):
    """Plotly grouped bar chart comparing departments on a given metric.

    Parameters
    ----------
    datos : dict
        The datos dictionary from process_dynamic_data.
    deptos : list[str]
        List of department names to compare.
    metric_key : str
        One of the keys from METRIC_CONFIG: "Avisos", "Indemnización",
        "Desembolso", "Siniestralidad".

    Returns
    -------
    go.Figure
    """
    if not deptos or metric_key not in METRIC_CONFIG:
        return go.Figure()

    config = METRIC_CONFIG[metric_key]
    internal_key = config["key"]

    dept_names = []
    values = []
    colors = []

    for idx, depto in enumerate(deptos):
        m = _get_dept_metrics(datos, depto)
        dept_names.append(m["departamento"])
        values.append(m[internal_key])
        colors.append(DEPT_COLORS[idx % len(DEPT_COLORS)])

    # Build hover text
    hover_texts = [config["formato"].format(v) for v in values]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dept_names,
        y=values,
        marker_color=colors,
        text=hover_texts,
        textposition="outside",
        textfont=dict(size=12, color="#333"),
        hovertemplate="%{x}: %{text}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=config["label"],
            font=dict(size=16, color="#0c2340"),
            x=0.5,
        ),
        xaxis=dict(
            title="Departamento",
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            title=config["label"],
            gridcolor="rgba(0,0,0,0.08)",
            tickfont=dict(size=11),
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        margin=dict(l=60, r=30, t=60, b=60),
        height=420,
        showlegend=False,
    )

    return fig


def _render_summary_cards(metrics_list):
    """Render compact summary cards for the selected departments."""
    if not metrics_list:
        return

    cols = st.columns(len(metrics_list))
    for idx, (col, m) in enumerate(zip(cols, metrics_list)):
        color = DEPT_COLORS[idx % len(DEPT_COLORS)]
        with col:
            st.markdown(f"""
            <div class="metric-card-v2" style="border-left: 4px solid {color}; padding: 12px 16px;">
                <div style="font-size: 0.85rem; color: #666; margin-bottom: 4px;">
                    {m['departamento']}
                </div>
                <div style="font-size: 1.1rem; font-weight: 700; color: {color};">
                    {m['avisos']:,} avisos
                </div>
                <div style="font-size: 0.78rem; color: #888; margin-top: 2px;">
                    Siniestralidad: {m['siniestralidad']:.1f}%
                </div>
            </div>
            """, unsafe_allow_html=True)


def render_comparativo_departamentos(datos):
    """Streamlit UI for multi-department comparison.

    1. Multiselect for departments (max 5)
    2. Metric selector radio
    3. Summary cards
    4. Comparison table
    5. Bar chart
    """
    st.markdown("""
    <div style="background: linear-gradient(135deg, #0c2340, #1a5276);
                padding: 1rem 1.5rem; border-radius: 12px; margin-bottom: 1rem;">
        <h3 style="color: white; margin: 0; font-size: 1.2rem;">
            📊 Comparativo entre Departamentos
        </h3>
        <p style="color: rgba(255,255,255,0.7); margin: 4px 0 0 0; font-size: 0.85rem;">
            Seleccione hasta {max_deptos} departamentos para comparar indicadores clave
        </p>
    </div>
    """.format(max_deptos=MAX_DEPTOS), unsafe_allow_html=True)

    # Department list
    dept_list = datos.get("departamentos_list", [])
    if not dept_list:
        st.warning("No hay departamentos disponibles. Verifique que los datos fueron cargados correctamente.")
        return

    # ─── Controls ───
    col_select, col_metric = st.columns([3, 1])

    with col_select:
        selected_deptos = st.multiselect(
            "Departamentos a comparar",
            options=dept_list,
            default=dept_list[:2] if len(dept_list) >= 2 else dept_list[:1],
            max_selections=MAX_DEPTOS,
            help=f"Seleccione entre 2 y {MAX_DEPTOS} departamentos",
        )

    with col_metric:
        selected_metric = st.radio(
            "Indicador",
            options=list(METRIC_CONFIG.keys()),
            index=0,
            horizontal=False,
        )

    if not selected_deptos:
        st.info("Seleccione al menos un departamento para ver la comparación.")
        return

    if len(selected_deptos) < 2:
        st.info("Seleccione al menos 2 departamentos para una comparación efectiva.")

    # ─── Compute metrics ───
    metrics_list = [_get_dept_metrics(datos, d) for d in selected_deptos]

    # ─── Summary cards ───
    _render_summary_cards(metrics_list)

    st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

    # ─── Comparison table ───
    st.markdown("#### Tabla Comparativa")
    df_table = generate_comparison_table(datos, selected_deptos)
    if not df_table.empty:
        st.dataframe(
            df_table.style.format({
                "Ha Indemnizadas": "{:,.2f}",
                "Monto Indemnizado (S/)": "S/ {:,.0f}",
                "Monto Desembolsado (S/)": "S/ {:,.0f}",
                "Siniestralidad (%)": "{:.1f}%",
                "% Desembolso": "{:.1f}%",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

    # ─── Bar chart ───
    st.markdown("#### Gráfico Comparativo")
    fig = generate_comparison_chart(datos, selected_deptos, selected_metric)
    st.plotly_chart(fig, use_container_width=True)
