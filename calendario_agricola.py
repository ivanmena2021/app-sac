"""
Agricultural calendar showing crop planting, harvesting, and risk periods
for Peru departments. Includes cross-referencing with actual SAC siniestros data.
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ── Static crop calendar data ──────────────────────────────────────────────
CALENDARIO_CULTIVOS = {
    "PIURA": {
        "ARROZ": {"siembra": [1, 2, 3, 7, 8], "cosecha": [5, 6, 7, 11, 12], "riesgo": ["SEQUIA", "INUNDACION"]},
        "MAIZ AMARILLO DURO": {"siembra": [1, 2, 12], "cosecha": [5, 6, 7], "riesgo": ["SEQUIA"]},
    },
    "LAMBAYEQUE": {
        "ARROZ": {"siembra": [1, 2, 3], "cosecha": [6, 7, 8], "riesgo": ["SEQUIA", "INUNDACION"]},
        "CANA DE AZUCAR": {"siembra": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "cosecha": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "riesgo": ["HELADA"]},
    },
    "SAN MARTIN": {
        "ARROZ": {"siembra": [1, 2, 3, 8, 9], "cosecha": [5, 6, 7, 12, 1], "riesgo": ["INUNDACION", "SEQUIA"]},
        "CAFE": {"siembra": [10, 11, 12], "cosecha": [4, 5, 6, 7], "riesgo": ["LLUVIA INTENSA"]},
        "CACAO": {"siembra": [10, 11, 12], "cosecha": [4, 5, 6, 7, 8], "riesgo": ["LLUVIA INTENSA"]},
    },
    "CAJAMARCA": {
        "ARROZ": {"siembra": [12, 1, 2], "cosecha": [5, 6, 7], "riesgo": ["HELADA", "SEQUIA"]},
        "PAPA": {"siembra": [10, 11, 12], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "GRANIZADA"]},
        "MAIZ AMILACEO": {"siembra": [10, 11], "cosecha": [4, 5, 6], "riesgo": ["HELADA", "SEQUIA"]},
    },
    "JUNIN": {
        "PAPA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "GRANIZADA"]},
        "CAFE": {"siembra": [10, 11, 12], "cosecha": [3, 4, 5, 6, 7], "riesgo": ["LLUVIA INTENSA"]},
        "MAIZ AMILACEO": {"siembra": [9, 10, 11], "cosecha": [4, 5, 6], "riesgo": ["HELADA"]},
    },
    "PUNO": {
        "PAPA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "GRANIZADA"]},
        "QUINUA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "GRANIZADA", "SEQUIA"]},
        "CEBADA": {"siembra": [10, 11], "cosecha": [4, 5], "riesgo": ["HELADA"]},
    },
    "CUSCO": {
        "PAPA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "GRANIZADA"]},
        "MAIZ AMILACEO": {"siembra": [9, 10, 11], "cosecha": [3, 4, 5, 6], "riesgo": ["HELADA"]},
    },
    "AYACUCHO": {
        "PAPA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "SEQUIA"]},
        "QUINUA": {"siembra": [10, 11], "cosecha": [4, 5], "riesgo": ["HELADA"]},
    },
    "HUANCAVELICA": {
        "PAPA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "GRANIZADA"]},
        "CEBADA": {"siembra": [10, 11], "cosecha": [4, 5], "riesgo": ["HELADA"]},
    },
    "APURIMAC": {
        "PAPA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "GRANIZADA"]},
        "MAIZ AMILACEO": {"siembra": [10, 11], "cosecha": [4, 5, 6], "riesgo": ["HELADA"]},
    },
    "ANCASH": {
        "PAPA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA"]},
        "MAIZ AMARILLO DURO": {"siembra": [9, 10], "cosecha": [3, 4, 5], "riesgo": ["SEQUIA"]},
    },
    "AREQUIPA": {
        "ARROZ": {"siembra": [8, 9, 10], "cosecha": [1, 2, 3, 4], "riesgo": ["HELADA"]},
        "AJO": {"siembra": [3, 4], "cosecha": [10, 11], "riesgo": ["HELADA"]},
    },
    "HUANUCO": {
        "PAPA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "LLUVIA INTENSA"]},
        "CAFE": {"siembra": [10, 11, 12], "cosecha": [4, 5, 6, 7], "riesgo": ["LLUVIA INTENSA"]},
    },
    "ICA": {
        "ALGODON": {"siembra": [8, 9, 10], "cosecha": [2, 3, 4], "riesgo": ["SEQUIA"]},
        "ESPARRAGO": {"siembra": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "cosecha": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "riesgo": ["SEQUIA"]},
    },
    "LA LIBERTAD": {
        "ARROZ": {"siembra": [12, 1, 2], "cosecha": [5, 6, 7], "riesgo": ["INUNDACION"]},
        "CANA DE AZUCAR": {"siembra": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "cosecha": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "riesgo": ["INUNDACION"]},
    },
    "AMAZONAS": {
        "ARROZ": {"siembra": [1, 2, 3], "cosecha": [6, 7, 8], "riesgo": ["INUNDACION", "LLUVIA INTENSA"]},
        "CAFE": {"siembra": [10, 11, 12], "cosecha": [4, 5, 6, 7], "riesgo": ["LLUVIA INTENSA"]},
    },
    "LORETO": {
        "ARROZ": {"siembra": [1, 2, 6, 7], "cosecha": [5, 6, 10, 11], "riesgo": ["INUNDACION"]},
        "PLATANO": {"siembra": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "cosecha": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "riesgo": ["INUNDACION"]},
    },
    "MADRE DE DIOS": {
        "ARROZ": {"siembra": [1, 2, 3], "cosecha": [6, 7, 8], "riesgo": ["INUNDACION"]},
        "PLATANO": {"siembra": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "cosecha": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "riesgo": ["INUNDACION"]},
    },
    "PASCO": {
        "PAPA": {"siembra": [10, 11], "cosecha": [3, 4, 5], "riesgo": ["HELADA", "GRANIZADA"]},
    },
    "TUMBES": {
        "ARROZ": {"siembra": [1, 2, 3], "cosecha": [6, 7, 8], "riesgo": ["INUNDACION"]},
        "PLATANO": {"siembra": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "cosecha": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "riesgo": ["INUNDACION"]},
    },
    "MOQUEGUA": {
        "ALFALFA": {"siembra": [3, 4], "cosecha": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "riesgo": ["HELADA", "SEQUIA"]},
    },
    "TACNA": {
        "OLIVO": {"siembra": [7, 8, 9], "cosecha": [3, 4, 5], "riesgo": ["HELADA"]},
    },
    "UCAYALI": {
        "ARROZ": {"siembra": [1, 2, 3], "cosecha": [6, 7, 8], "riesgo": ["INUNDACION"]},
        "PLATANO": {"siembra": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "cosecha": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], "riesgo": ["INUNDACION"]},
    },
}

MONTH_NAMES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
               "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# Colors
COLOR_SIEMBRA = "#27ae60"       # green
COLOR_COSECHA = "#f39c12"       # gold
COLOR_OVERLAP = "#2ecc71"       # light green
COLOR_RISK = "#e74c3c"          # red
COLOR_BG_EVEN = "#f8f9fa"
COLOR_BG_ODD = "#ffffff"


def _normalize_dept(name):
    """Uppercase + strip accents for department matching."""
    if not isinstance(name, str):
        return name
    name = name.strip().upper()
    replacements = {
        "\u00c1": "A", "\u00c9": "E", "\u00cd": "I", "\u00d3": "O", "\u00da": "U",
        "\u00e1": "A", "\u00e9": "E", "\u00ed": "I", "\u00f3": "O", "\u00fa": "U",
        "\u00d1": "N", "\u00f1": "N",
    }
    for accent, plain in replacements.items():
        name = name.replace(accent, plain)
    return name


def get_department_list():
    """Return sorted list of departments available in the calendar."""
    return sorted(CALENDARIO_CULTIVOS.keys())


def get_current_risk_crops(depto, month=None):
    """Return list of crops currently in a risk-prone period for the department.

    Parameters
    ----------
    depto : str
        Department name (will be normalized).
    month : int or None
        Month number (1-12). Defaults to current month.

    Returns
    -------
    list of dict
        Each dict: {"cultivo": str, "riesgos": list[str]}
    """
    if month is None:
        month = datetime.now().month

    depto = _normalize_dept(depto)
    crops = CALENDARIO_CULTIVOS.get(depto, {})

    at_risk = []
    for crop_name, info in crops.items():
        # A crop is at risk if current month is in siembra or cosecha period
        # and the crop has associated risks
        in_siembra = month in info.get("siembra", [])
        in_cosecha = month in info.get("cosecha", [])
        if (in_siembra or in_cosecha) and info.get("riesgo"):
            at_risk.append({
                "cultivo": crop_name,
                "riesgos": info["riesgo"],
                "en_siembra": in_siembra,
                "en_cosecha": in_cosecha,
            })

    return at_risk


def generate_calendar_chart(depto):
    """Generate a Gantt-style calendar chart for a department.

    X axis: 12 months. Y axis: crop names.
    Green bars for siembra, gold for cosecha, red markers for risk months.

    Parameters
    ----------
    depto : str
        Department name.

    Returns
    -------
    plotly.graph_objects.Figure or None
    """
    depto = _normalize_dept(depto)
    crops = CALENDARIO_CULTIVOS.get(depto)
    if not crops:
        return None

    crop_names = list(crops.keys())
    fig = go.Figure()

    for y_idx, crop_name in enumerate(crop_names):
        info = crops[crop_name]
        siembra_months = set(info.get("siembra", []))
        cosecha_months = set(info.get("cosecha", []))

        # Draw month cells for siembra
        for m in siembra_months:
            is_overlap = m in cosecha_months
            color = COLOR_OVERLAP if is_overlap else COLOR_SIEMBRA
            fig.add_trace(go.Bar(
                x=[1],
                y=[crop_name],
                base=[m - 0.5],
                orientation="h",
                marker=dict(color=color, opacity=0.8,
                            line=dict(width=0.5, color="white")),
                showlegend=False,
                hovertemplate=(
                    f"<b>{crop_name}</b><br>"
                    f"{MONTH_NAMES[m - 1]}: "
                    f"{'Siembra + Cosecha' if is_overlap else 'Siembra'}"
                    "<extra></extra>"
                ),
            ))

        # Draw month cells for cosecha (only non-overlap)
        for m in cosecha_months - siembra_months:
            fig.add_trace(go.Bar(
                x=[1],
                y=[crop_name],
                base=[m - 0.5],
                orientation="h",
                marker=dict(color=COLOR_COSECHA, opacity=0.8,
                            line=dict(width=0.5, color="white")),
                showlegend=False,
                hovertemplate=(
                    f"<b>{crop_name}</b><br>"
                    f"{MONTH_NAMES[m - 1]}: Cosecha"
                    "<extra></extra>"
                ),
            ))

    # Risk markers (red diamonds) on all risk-relevant months
    risk_x = []
    risk_y = []
    risk_text = []
    for crop_name, info in crops.items():
        riesgos = info.get("riesgo", [])
        if not riesgos:
            continue
        # Risk months = union of siembra + cosecha
        risk_months = set(info.get("siembra", [])) | set(info.get("cosecha", []))
        for m in risk_months:
            risk_x.append(m)
            risk_y.append(crop_name)
            risk_text.append(", ".join(riesgos))

    if risk_x:
        fig.add_trace(go.Scatter(
            x=risk_x,
            y=risk_y,
            mode="markers",
            marker=dict(
                symbol="diamond",
                size=8,
                color=COLOR_RISK,
                line=dict(width=1, color="white"),
            ),
            showlegend=False,
            hovertemplate="<b>%{y}</b><br>Riesgos: %{text}<extra></extra>",
            text=risk_text,
        ))

    # Current month indicator
    current_month = datetime.now().month
    fig.add_vline(
        x=current_month,
        line=dict(color="#2c3e50", width=2, dash="dash"),
        annotation_text=f"Hoy ({MONTH_NAMES[current_month - 1]})",
        annotation_position="top",
    )

    # Layout
    fig.update_layout(
        title=dict(text=f"Calendario Agricola - {depto}", font=dict(size=16)),
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(1, 13)),
            ticktext=MONTH_NAMES,
            range=[0.5, 12.5],
            title="",
            gridcolor="#ecf0f1",
        ),
        yaxis=dict(
            title="",
            autorange="reversed",
        ),
        barmode="overlay",
        height=max(250, 60 * len(crop_names) + 100),
        margin=dict(l=10, r=10, t=50, b=30),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )

    return fig


def _find_column(df, candidates):
    """Find first matching column (case-insensitive)."""
    cols_upper = {c.upper(): c for c in df.columns}
    for cand in candidates:
        if cand.upper() in cols_upper:
            return cols_upper[cand.upper()]
    return None


def _cross_reference_siniestros(datos, depto):
    """Cross-reference actual siniestros data with the crop calendar.

    Returns DataFrame with columns:
        Cultivo, Tipo Siniestro, Avisos, En Calendario, Coincide
    showing how actual claims align with expected risk periods.
    """
    midagri = datos.get("midagri")
    if midagri is None or midagri.empty:
        return pd.DataFrame()

    depto = _normalize_dept(depto)

    dept_col = _find_column(midagri, ["DEPARTAMENTO", "DEPTO", "DEPT"])
    cultivo_col = _find_column(midagri, ["CULTIVO", "CROP", "PRODUCTO"])
    siniestro_col = _find_column(midagri, ["TIPO_SINIESTRO", "TIPO SINIESTRO",
                                            "SINIESTRO", "TIPO_EVENTO", "EVENTO"])

    if dept_col is None:
        return pd.DataFrame()

    df = midagri.copy()
    df["_dept_norm"] = df[dept_col].apply(_normalize_dept)
    df_dept = df[df["_dept_norm"] == depto]

    if df_dept.empty:
        return pd.DataFrame()

    calendar_crops = CALENDARIO_CULTIVOS.get(depto, {})

    # Group by cultivo and siniestro type
    group_cols = []
    if cultivo_col:
        group_cols.append(cultivo_col)
    if siniestro_col:
        group_cols.append(siniestro_col)

    if not group_cols:
        return pd.DataFrame()

    grouped = df_dept.groupby(group_cols).size().reset_index(name="Avisos")

    results = []
    for _, row in grouped.iterrows():
        cultivo = row.get(cultivo_col, "") if cultivo_col else ""
        tipo = row.get(siniestro_col, "") if siniestro_col else ""
        avisos = row["Avisos"]

        # Check if this crop/risk combo is in the calendar
        cultivo_upper = str(cultivo).strip().upper()
        tipo_upper = str(tipo).strip().upper()

        en_calendario = "No"
        coincide = "N/A"

        if cultivo_upper in calendar_crops:
            en_calendario = "Si"
            expected_risks = [r.upper() for r in calendar_crops[cultivo_upper].get("riesgo", [])]
            if tipo_upper in expected_risks:
                coincide = "Si - Riesgo esperado"
            else:
                coincide = "No - Riesgo no esperado"

        results.append({
            "Cultivo": cultivo,
            "Tipo Siniestro": tipo,
            "Avisos": avisos,
            "En Calendario": en_calendario,
            "Coincide": coincide,
        })

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results).sort_values("Avisos", ascending=False).reset_index(drop=True)


def render_calendario_tab(datos):
    """Render the agricultural calendar Streamlit tab.

    Components:
    1. Department selector
    2. Current month risk alert banner
    3. Calendar Gantt chart
    4. Cross-reference with actual siniestros data
    5. Legend explaining colors
    """
    st.subheader("Calendario Agricola - Periodos de Siembra, Cosecha y Riesgo")

    # 1. Department selector
    dept_list = datos.get("departamentos_list", get_department_list())
    # Normalize for matching with calendar keys
    dept_list_normalized = sorted(set(
        _normalize_dept(d) for d in dept_list
        if _normalize_dept(d) in CALENDARIO_CULTIVOS
    ))

    if not dept_list_normalized:
        dept_list_normalized = get_department_list()

    selected_dept = st.selectbox(
        "Seleccionar departamento:",
        options=dept_list_normalized,
        index=0,
        key="calendario_dept_selector",
    )

    # 2. Current month risk alert banner
    current_month = datetime.now().month
    at_risk = get_current_risk_crops(selected_dept, month=current_month)

    if at_risk:
        risk_lines = []
        for item in at_risk:
            status_parts = []
            if item["en_siembra"]:
                status_parts.append("en siembra")
            if item["en_cosecha"]:
                status_parts.append("en cosecha")
            status = " y ".join(status_parts)
            riesgos = ", ".join(item["riesgos"])
            risk_lines.append(
                f"  - **{item['cultivo']}** ({status}) - Riesgos: {riesgos}"
            )
        risk_msg = "\n".join(risk_lines)
        st.warning(
            f"**Alerta - {MONTH_NAMES[current_month - 1]} {datetime.now().year}**: "
            f"Cultivos en periodo de riesgo en {selected_dept}:\n\n{risk_msg}"
        )
    else:
        st.info(
            f"No hay cultivos en periodo de riesgo activo en {selected_dept} "
            f"para {MONTH_NAMES[current_month - 1]}."
        )

    # 3. Calendar Gantt chart
    fig = generate_calendar_chart(selected_dept)
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"No hay datos de calendario disponibles para {selected_dept}.")

    # 4. Cross-reference with actual siniestros
    st.subheader("Cruce con Siniestros Reales")
    cross_df = _cross_reference_siniestros(datos, selected_dept)
    if not cross_df.empty:
        st.dataframe(cross_df, use_container_width=True, hide_index=True)

        # Summary stats
        total_avisos = cross_df["Avisos"].sum()
        coincide_count = cross_df[cross_df["Coincide"].str.contains("Si", na=False)]["Avisos"].sum()
        if total_avisos > 0:
            pct = (coincide_count / total_avisos) * 100
            st.metric(
                label="Coincidencia con riesgos esperados",
                value=f"{pct:.1f}%",
                delta=f"{int(coincide_count)} de {int(total_avisos)} avisos",
            )
    else:
        st.info(f"No hay datos de siniestros disponibles para {selected_dept}.")

    # 5. Legend
    st.markdown("---")
    st.markdown("**Leyenda:**")
    legend_cols = st.columns(4)
    with legend_cols[0]:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="width:20px;height:14px;background:{COLOR_SIEMBRA};'
            f'border-radius:3px;"></div> Siembra</div>',
            unsafe_allow_html=True,
        )
    with legend_cols[1]:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="width:20px;height:14px;background:{COLOR_COSECHA};'
            f'border-radius:3px;"></div> Cosecha</div>',
            unsafe_allow_html=True,
        )
    with legend_cols[2]:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="width:20px;height:14px;background:{COLOR_OVERLAP};'
            f'border-radius:3px;"></div> Siembra + Cosecha</div>',
            unsafe_allow_html=True,
        )
    with legend_cols[3]:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="width:14px;height:14px;background:{COLOR_RISK};'
            f'clip-path:polygon(50% 0%,100% 50%,50% 100%,0% 50%);"></div>'
            f' Riesgo</div>',
            unsafe_allow_html=True,
        )
