"""
Agricultural calendar showing crop planting, harvesting, and risk periods
for Peru departments. Uses historical data from 5 SAC campaigns (2020-2025)
with 66,000+ real siniestro records.

Data source: static_data/calendario_cultivos_historico.json
Methodology: static_data/METODOLOGIA_DATOS.md
"""

import json
import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ── Load historical calendar from JSON ─────────────────────────────────────
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static_data")
_CAL_PATH = os.path.join(_STATIC_DIR, "calendario_cultivos_historico.json")

_CALENDARIO_RAW = {}
if os.path.exists(_CAL_PATH):
    with open(_CAL_PATH, "r", encoding="utf-8") as f:
        _CALENDARIO_RAW = json.load(f)


def _build_calendario_cultivos():
    """Convert JSON historical data to the format used by the rest of the module.

    Input JSON format (per dept/crop):
        {"avisos": {"meses_riesgo":[], "riesgos":[], "meses_siembra":[], "meses_cosecha":[], "total":N},
         "indemnizados": {...}, "perdida_total": {...}}

    Output format (compatible with legacy CALENDARIO_CULTIVOS):
        {"siembra": [months], "cosecha": [months], "riesgo": [risk_names],
         "meses_riesgo": [months], "total_avisos": N, "total_indemnizados": N,
         "riesgos_indemnizados": [...], "riesgos_perdida_total": [...]}

    Data hierarchy for choosing values:
        - siembra: from avisos.meses_siembra (real FECHA_SIEMBRA data)
        - cosecha: from avisos.meses_cosecha (FECHA_AJUSTE where fenologia=MADURACION)
        - riesgo: from indemnizados.riesgos if available, else avisos.riesgos
          (indemnizados are more rigorous — events that actually exceeded the damage threshold)
        - meses_riesgo: from avisos.meses_riesgo (when events occurred)
    """
    cal = {}
    for dept, crops in _CALENDARIO_RAW.items():
        cal[dept] = {}
        for cult, layers in crops.items():
            avisos = layers.get("avisos", {})
            indemn = layers.get("indemnizados", {})
            ptotal = layers.get("perdida_total", {})

            entry = {
                "siembra": avisos.get("meses_siembra", []),
                "cosecha": avisos.get("meses_cosecha", []),
                # Prefer indemnizados riesgos (certified) over avisos (general)
                "riesgo": indemn.get("riesgos", avisos.get("riesgos", [])),
                "meses_riesgo": avisos.get("meses_riesgo", []),
                "grupos_climaticos": avisos.get("grupos_climaticos", []),
                "total_avisos": avisos.get("total", 0),
                "total_indemnizados": indemn.get("total", 0),
                "total_perdida_total": ptotal.get("total", 0),
                "riesgos_avisos": avisos.get("riesgos", []),
                "riesgos_indemnizados": indemn.get("riesgos", []),
                "riesgos_perdida_total": ptotal.get("riesgos", []),
            }

            # If no siembra/cosecha from data, use meses_riesgo as fallback
            if not entry["siembra"] and not entry["cosecha"]:
                entry["siembra"] = entry["meses_riesgo"]

            cal[dept][cult] = entry
    return cal


CALENDARIO_CULTIVOS = _build_calendario_cultivos()

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

    Uses historical data: a crop is at risk if the current month appears in its
    meses_riesgo (months where siniestros historically occurred), or if it's in
    siembra/cosecha period.

    Parameters
    ----------
    depto : str
        Department name (will be normalized).
    month : int or None
        Month number (1-12). Defaults to current month.

    Returns
    -------
    list of dict
        Each dict: {"cultivo": str, "riesgos": list[str], "en_siembra": bool,
                     "en_cosecha": bool, "grupos_climaticos": list[str],
                     "total_avisos": int}
    """
    if month is None:
        month = datetime.now().month

    depto = _normalize_dept(depto)
    crops = CALENDARIO_CULTIVOS.get(depto, {})

    at_risk = []
    for crop_name, info in crops.items():
        in_siembra = month in info.get("siembra", [])
        in_cosecha = month in info.get("cosecha", [])
        in_riesgo = month in info.get("meses_riesgo", [])

        # A crop is at risk if this month has historical siniestros,
        # or if it's in siembra/cosecha period with associated risks
        if (in_riesgo or in_siembra or in_cosecha) and info.get("riesgo"):
            at_risk.append({
                "cultivo": crop_name,
                "riesgos": info["riesgo"],
                "en_siembra": in_siembra,
                "en_cosecha": in_cosecha,
                "en_riesgo_historico": in_riesgo,
                "grupos_climaticos": info.get("grupos_climaticos", []),
                "total_avisos": info.get("total_avisos", 0),
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

    # Risk markers (red diamonds) on historical risk months
    risk_x = []
    risk_y = []
    risk_text = []
    for crop_name, info in crops.items():
        riesgos = info.get("riesgo", [])
        if not riesgos:
            continue
        # Use actual historical risk months if available, else siembra+cosecha
        risk_months = info.get("meses_riesgo", [])
        if not risk_months:
            risk_months = list(set(info.get("siembra", [])) | set(info.get("cosecha", [])))
        for m in risk_months:
            risk_x.append(m)
            risk_y.append(crop_name)
            n_avisos = info.get("total_avisos", 0)
            risk_text.append(f"{', '.join(riesgos)} ({n_avisos} avisos hist.)")

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
            # Check across all risk layers (avisos, indemnizados, perdida_total)
            all_risks = set()
            for r in calendar_crops[cultivo_upper].get("riesgo", []):
                all_risks.add(r.upper())
            for r in calendar_crops[cultivo_upper].get("riesgos_avisos", []):
                all_risks.add(r.upper())
            if tipo_upper in all_risks:
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
