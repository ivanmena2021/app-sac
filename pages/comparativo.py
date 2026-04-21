"""Página: Comparativo de Campañas — 5 históricas + actual."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from shared.state import require_data, get_datos
from shared.components import render_metric, page_header, footer
from shared.charts import (
    apply_theme, render_chart, add_reference_line, style_bar, style_line,
    add_last_point_annotation, fmt_compact, PALETTE,
)
from data_processor import load_primas_historicas

require_data()
datos = get_datos()
df_actual = datos["midagri"]

page_header("Comparativo de Campañas",
            "Evolución de indicadores SAC: 5 campañas históricas + campaña actual 2025-2026")

# ═══════════════════════════════════════════════════════════════
# CARGAR DATOS HISTÓRICOS
# ═══════════════════════════════════════════════════════════════

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static_data")
RESUMEN_PATH = os.path.join(STATIC_DIR, "resumen_departamental.json")

resumen_dept = {}
if os.path.exists(RESUMEN_PATH):
    with open(RESUMEN_PATH, "r", encoding="utf-8") as f:
        resumen_dept = json.load(f)

primas_hist = load_primas_historicas()

CAMPANAS_HIST = ["2020-2021", "2021-2022", "2022-2023", "2023-2024", "2024-2025"]
CAMPANA_ACTUAL = "2025-2026"

# Calcular métricas nacionales por campaña histórica
hist_data = {}
por_campana = resumen_dept.get("por_campana", {})
for camp in CAMPANAS_HIST:
    avisos = 0; indemnizados = 0; monto = 0; ha = 0; desemb = 0; prima = 0
    for dept, camps in por_campana.items():
        if camp in camps:
            c = camps[camp]
            avisos += c.get("avisos", 0)
            indemnizados += c.get("indemnizados", 0)
            monto += c.get("monto_indemnizado", 0)
            ha += c.get("ha_indemnizadas", 0)
            desemb += c.get("monto_desembolsado", 0)
        p = primas_hist.get(camp, {}).get(dept, 0)
        prima += p
    sin_pct = round(100 * monto / prima, 1) if prima > 0 else 0
    hist_data[camp] = {
        "avisos": avisos, "indemnizados": indemnizados,
        "monto": monto, "ha": ha, "desembolso": desemb,
        "prima_neta": prima, "siniestralidad": sin_pct,
    }

# Métricas de campaña actual (dinámicas)
actual_data = {
    "avisos": datos["total_avisos"],
    "indemnizados": int(datos.get("ha_indemnizadas", 0)),  # fallback
    "monto": datos["monto_indemnizado"],
    "ha": datos["ha_indemnizadas"],
    "desembolso": datos["monto_desembolsado"],
    "prima_neta": datos.get("prima_neta", 0),
    "siniestralidad": datos.get("indice_siniestralidad", 0),
}

# Recalcular indemnizados correctamente
if "DICTAMEN" in df_actual.columns:
    dict_col = df_actual["DICTAMEN"].astype(str).str.strip().str.upper()
    actual_data["indemnizados"] = int(
        (dict_col.str.contains("INDEMNIZABLE", na=False) &
         ~dict_col.str.contains("NO INDEMNIZABLE", na=False)).sum()
    )

all_camps = CAMPANAS_HIST + [CAMPANA_ACTUAL]
all_data = {c: hist_data[c] for c in CAMPANAS_HIST}
all_data[CAMPANA_ACTUAL] = actual_data

# ═══════════════════════════════════════════════════════════════
# SELECTOR DE MÉTRICA
# ═══════════════════════════════════════════════════════════════

METRICAS = {
    "Avisos": ("avisos", "{:,}", "Número total de avisos de siniestro reportados"),
    "Indemnización (S/)": ("monto", "S/ {:,.0f}", "Monto total indemnizado"),
    "Siniestralidad (%)": ("siniestralidad", "{:.1f}%", "Indemnización / Prima Neta × 100"),
    "Prima Neta (S/)": ("prima_neta", "S/ {:,.0f}", "Prima neta de la campaña"),
    "Ha Indemnizadas": ("ha", "{:,.0f}", "Hectáreas con indemnización"),
    "Desembolso (S/)": ("desembolso", "S/ {:,.0f}", "Monto desembolsado a productores"),
}

metrica_sel = st.radio("Métrica:", options=list(METRICAS.keys()),
                        horizontal=True, key="metrica_comp_multi")

key, fmt, desc = METRICAS[metrica_sel]
st.caption(desc)

# ═══════════════════════════════════════════════════════════════
# GRÁFICO DE BARRAS — 6 campañas
# ═══════════════════════════════════════════════════════════════

values = [all_data[c][key] for c in all_camps]
# Históricas en azul corporativo, actual en verde MIDAGRI (resaltado)
colors = [PALETTE["primary_mid"]] * 5 + [PALETTE["midagri"]]

fig = go.Figure()
fig.add_trace(go.Bar(
    x=all_camps, y=values,
    marker=dict(
        color=colors,
        line=dict(width=0),
        cornerradius=8,
    ),
    text=[fmt.format(v) for v in values],
    textposition="outside",
    textfont=dict(size=12, color=PALETTE["text_soft"], family="Segoe UI"),
    hovertemplate=(
        "<b>Campaña %{x}</b><br>"
        + metrica_sel + ": %{text}<extra></extra>"
    ),
    showlegend=False,
))

# Línea de promedio histórico
avg_hist = np.mean([all_data[c][key] for c in CAMPANAS_HIST])
add_reference_line(
    fig, y=avg_hist, color=PALETTE["danger"],
    label=f"Promedio histórico: {fmt.format(avg_hist)}",
)

apply_theme(
    fig,
    title=f"{metrica_sel} por Campaña Agrícola",
    subtitle="Azul = históricas · Verde = campaña actual · Roja = promedio",
    height=470, show_legend=False, yaxis_title=metrica_sel,
    legend_position="none",
)
# Formato compacto eje Y si es monto
if "S/" in fmt or "monto" in key.lower() or "prima" in key.lower():
    fig.update_yaxes(tickformat="~s", tickprefix="S/ ")
render_chart(fig, key="chart_metrica_comp",
             filename=f"comparativo_{key}_por_campana")

# ═══════════════════════════════════════════════════════════════
# TABLA RESUMEN — 6 campañas
# ═══════════════════════════════════════════════════════════════

st.markdown("#### Tabla Comparativa")

rows = []
for c in all_camps:
    d = all_data[c]
    sin_color = "🔴" if d["siniestralidad"] > 70 else ("🟡" if d["siniestralidad"] > 50 else "🟢")
    rows.append({
        "Campaña": c + (" ★" if c == CAMPANA_ACTUAL else ""),
        "Avisos": f"{d['avisos']:,}",
        "Prima Neta": f"S/ {d['prima_neta']:,.0f}" if d['prima_neta'] > 0 else "—",
        "Indemnización": f"S/ {d['monto']:,.0f}",
        "Siniestralidad": f"{sin_color} {d['siniestralidad']:.1f}%",
        "Ha Indemnizadas": f"{d['ha']:,.0f}",
        "Desembolso": f"S/ {d['desembolso']:,.0f}",
    })

# Fila de promedio
avg = {k: np.mean([all_data[c][k] for c in CAMPANAS_HIST]) for k in ["avisos", "monto", "ha", "desembolso", "prima_neta", "siniestralidad"]}
rows.append({
    "Campaña": "PROMEDIO HISTÓRICO",
    "Avisos": f"{avg['avisos']:,.0f}",
    "Prima Neta": f"S/ {avg['prima_neta']:,.0f}",
    "Indemnización": f"S/ {avg['monto']:,.0f}",
    "Siniestralidad": f"📊 {avg['siniestralidad']:.1f}%",
    "Ha Indemnizadas": f"{avg['ha']:,.0f}",
    "Desembolso": f"S/ {avg['desembolso']:,.0f}",
})

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=330)

# ═══════════════════════════════════════════════════════════════
# COMPARATIVO DEPARTAMENTAL — campaña actual vs promedio
# ═══════════════════════════════════════════════════════════════

st.markdown("#### Comparativo Departamental — Actual vs. Promedio Histórico")

dept_list = sorted(datos.get("departamentos_list", []))
if dept_list:
    dept_rows = []
    for dept in dept_list:
        # Actual
        dept_df = df_actual[df_actual["DEPARTAMENTO"].astype(str).str.strip().str.upper() == dept.upper()]
        actual_avisos = len(dept_df)
        actual_indemn = float(pd.to_numeric(dept_df.get("INDEMNIZACION", 0), errors="coerce").fillna(0).sum())

        # Promedio histórico
        dept_camps = por_campana.get(dept.upper(), {})
        hist_avisos = []
        hist_monto = []
        for camp in CAMPANAS_HIST:
            if camp in dept_camps:
                hist_avisos.append(dept_camps[camp].get("avisos", 0))
                hist_monto.append(dept_camps[camp].get("monto_indemnizado", 0))

        avg_av = np.mean(hist_avisos) if hist_avisos else 0
        avg_mn = np.mean(hist_monto) if hist_monto else 0

        var_av = round(100 * (actual_avisos - avg_av) / avg_av, 1) if avg_av > 0 else 0
        var_mn = round(100 * (actual_indemn - avg_mn) / avg_mn, 1) if avg_mn > 0 else 0

        dept_rows.append({
            "Departamento": dept.title(),
            "Avisos Actual": actual_avisos,
            "Avisos Prom. Hist.": f"{avg_av:.0f}",
            "Var. Avisos": f"{'+' if var_av > 0 else ''}{var_av}%",
            "Indemn. Actual": f"S/ {actual_indemn:,.0f}",
            "Indemn. Prom. Hist.": f"S/ {avg_mn:,.0f}",
            "Var. Indemn.": f"{'+' if var_mn > 0 else ''}{var_mn}%",
        })

    st.dataframe(pd.DataFrame(dept_rows), use_container_width=True, hide_index=True, height=500)

# ═══════════════════════════════════════════════════════════════
# GRÁFICO SINIESTRALIDAD HISTÓRICA
# ═══════════════════════════════════════════════════════════════

st.markdown("#### Evolución de Siniestralidad")

sin_vals = [all_data[c]["siniestralidad"] for c in all_camps]
sin_colors = [
    PALETTE["danger"] if v > 70 else (PALETTE["warning"] if v > 50 else PALETTE["success"])
    for v in sin_vals
]

fig_sin = go.Figure()
fig_sin.add_trace(go.Bar(
    x=all_camps, y=sin_vals,
    marker=dict(color=sin_colors, line=dict(width=0), cornerradius=8),
    text=[f"{v:.1f}%" for v in sin_vals],
    textposition="outside",
    textfont=dict(size=12, color=PALETTE["text_soft"]),
    hovertemplate="<b>Campaña %{x}</b><br>Siniestralidad: %{y:.1f}%<extra></extra>",
    showlegend=False,
))
add_reference_line(fig_sin, y=70, color=PALETTE["danger"],
                   label="Alto (≥70%)", dash="dot")
add_reference_line(fig_sin, y=50, color=PALETTE["warning"],
                   label="Medio (≥50%)", dash="dot")

apply_theme(
    fig_sin,
    title="Evolución de Siniestralidad",
    subtitle="Indemnización / Prima Neta × 100 — colores según umbral",
    height=410, show_legend=False, yaxis_title="Siniestralidad (%)",
    legend_position="none",
)
render_chart(fig_sin, key="chart_siniestralidad",
             filename="evolucion_siniestralidad_campanas")


# ═══════════════════════════════════════════════════════════════
# SERIES TEMPORALES — Evolución mensual comparativa
# ═══════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown("### Evolución Temporal Comparativa")
st.caption("Todas las campañas alineadas por mes agrícola (Ago → Jul) para facilitar la comparación")

SERIES_PATH = os.path.join(STATIC_DIR, "series_temporales.json")
series_data = {}
if os.path.exists(SERIES_PATH):
    with open(SERIES_PATH, "r", encoding="utf-8") as f:
        series_data = json.load(f)

# Orden de meses en campaña agrícola (Ago del año inicial → Jul del siguiente)
MESES_CAMPANA = ["Ago", "Sep", "Oct", "Nov", "Dic", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul"]

# Colores por campaña — cada campaña un color distinto
CAMP_COLORS = {
    "2020-2021": "#636EFA",
    "2021-2022": "#EF553B",
    "2022-2023": "#00CC96",
    "2023-2024": "#AB63FA",
    "2024-2025": "#FFA15A",
    "2025-2026": "#408B14",
}


def _period_to_campana_month(period_str, campana):
    """Convierte '2021-03' → índice en la campaña agrícola (0=Ago, 11=Jul)."""
    try:
        year, month = int(period_str[:4]), int(period_str[5:7])
    except (ValueError, IndexError):
        return None
    # Año inicio de la campaña
    start_year = int(campana[:4])
    # Ago(8)-Dic(12) del start_year → índices 0-4
    # Ene(1)-Jul(7) del start_year+1 → índices 5-11
    if year == start_year and 8 <= month <= 12:
        return month - 8  # Ago=0, Sep=1, ..., Dic=4
    elif year == start_year + 1 and 1 <= month <= 7:
        return month + 4   # Ene=5, Feb=6, ..., Jul=11
    return None


def build_campaign_series(raw_dict, campana, value_key=None):
    """Convierte dict {'2021-03': valor, ...} a array de 12 meses alineados a campaña agrícola."""
    values = [0.0] * 12
    for period_str, val in raw_dict.items():
        idx = _period_to_campana_month(period_str, campana)
        if idx is not None:
            if value_key and isinstance(val, dict):
                values[idx] = val.get(value_key, 0)
            elif isinstance(val, (int, float)):
                values[idx] = val
            elif isinstance(val, dict):
                values[idx] = val.get("n", 0)
    return values


def build_current_series_avisos(df, campana):
    """Construye serie de avisos por mes para campaña actual desde DataFrame."""
    date_col = None
    for col in ["FECHA_AVISO", "FECHA_SINIESTRO"]:
        if col in df.columns:
            date_col = col
            break
    if date_col is None:
        return [0.0] * 12
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    monthly = dates.dt.to_period("M").value_counts().sort_index()
    raw = {str(p): int(c) for p, c in monthly.items()}
    return build_campaign_series(raw, campana)


def build_current_series_indemn(df, campana):
    """Construye series de indemnizaciones por mes para campaña actual."""
    # Buscar columna de fecha de ajuste
    date_col = None
    for col in ["FECHA_AJUSTE_ACTA_FINAL", "FECHA_AJUSTE_ACTA_1",
                "FECHA_PROGRAMACION_AJUSTE", "FECHA_SINIESTRO"]:
        if col in df.columns:
            date_col = col
            break
    if date_col is None:
        return [0.0] * 12, [0.0] * 12

    # Filtrar indemnizables
    ind_mask = pd.Series(False, index=df.index)
    if "DICTAMEN" in df.columns:
        dict_col = df["DICTAMEN"].astype(str).str.strip().str.upper()
        ind_mask = (dict_col.str.contains("INDEMNIZABLE", na=False) &
                    ~dict_col.str.contains("NO INDEMNIZABLE", na=False))

    df_ind = df[ind_mask].copy()
    if df_ind.empty:
        return [0.0] * 12, [0.0] * 12

    df_ind[date_col] = pd.to_datetime(df_ind[date_col], errors="coerce")
    df_ind = df_ind[df_ind[date_col].notna()]
    if df_ind.empty:
        return [0.0] * 12, [0.0] * 12

    periods = df_ind[date_col].dt.to_period("M")
    count_m = periods.value_counts().sort_index()
    count_raw = {str(p): int(c) for p, c in count_m.items()}
    counts = build_campaign_series(count_raw, campana)

    # Montos
    monto_col = None
    for mc in ["INDEMNIZACION", "MONTO_INDEMNIZADO"]:
        if mc in df_ind.columns:
            monto_col = mc
            break

    if monto_col:
        df_ind["_monto"] = pd.to_numeric(df_ind[monto_col], errors="coerce").fillna(0)
        monto_m = df_ind.groupby(periods)["_monto"].sum()
        monto_raw = {str(p): float(v) for p, v in monto_m.items()}
        montos = build_campaign_series(monto_raw, campana)
    else:
        montos = [0.0] * 12

    return counts, montos


# ── Construir datos para los gráficos ──

all_avisos_series = {}
all_indemn_count_series = {}
all_indemn_monto_series = {}

# Campañas históricas desde JSON
for camp in CAMPANAS_HIST:
    raw_av = series_data.get("avisos", {}).get(camp, {})
    raw_in = series_data.get("indemnizaciones", {}).get(camp, {})
    all_avisos_series[camp] = build_campaign_series(raw_av, camp)
    all_indemn_count_series[camp] = build_campaign_series(raw_in, camp, value_key="n")
    all_indemn_monto_series[camp] = build_campaign_series(raw_in, camp, value_key="monto")

# Campaña actual desde datos dinámicos
all_avisos_series[CAMPANA_ACTUAL] = build_current_series_avisos(df_actual, CAMPANA_ACTUAL)
curr_counts, curr_montos = build_current_series_indemn(df_actual, CAMPANA_ACTUAL)
all_indemn_count_series[CAMPANA_ACTUAL] = curr_counts
all_indemn_monto_series[CAMPANA_ACTUAL] = curr_montos


def make_evolution_chart(series_dict, title, yaxis_title, fmt_prefix="", cumulative=False,
                          subtitle=None, y_is_currency=False):
    """Crea un gráfico de líneas con 6 campañas superpuestas, tema SAC."""
    fig = go.Figure()
    for camp in all_camps:
        vals = series_dict.get(camp, [0]*12)
        if cumulative:
            vals = list(np.cumsum(vals))
        is_current = camp == CAMPANA_ACTUAL
        width = 4 if is_current else 1.8
        fig.add_trace(go.Scatter(
            x=MESES_CAMPANA, y=vals,
            mode="lines+markers",
            name=camp,
            line=dict(color=CAMP_COLORS.get(camp, "#999"), width=width,
                      shape="spline", smoothing=0.8),
            marker=dict(
                size=10 if is_current else 5,
                line=dict(width=2 if is_current else 0, color="#ffffff"),
            ),
            opacity=1.0 if is_current else 0.65,
            hovertemplate=(
                f"<b>{camp}</b><br>"
                f"%{{x}}: {fmt_prefix}%{{y:,.0f}}<extra></extra>"
            ),
        ))

    # Anotación del valor actual sobre la curva de la campaña actual
    add_last_point_annotation(
        fig, CAMPANA_ACTUAL,
        value=None, color=CAMP_COLORS[CAMPANA_ACTUAL],
        currency=y_is_currency, prefix="Actual: ",
    )

    apply_theme(
        fig, title=title, subtitle=subtitle, height=470,
        xaxis_title=None,
        yaxis_title=yaxis_title, y_is_currency=False,
        legend_position="bottom",
    )
    # Ticks compactos en el eje Y (ej. 15M en vez de 15,000,000)
    fig.update_yaxes(
        tickformat="~s",  # Plotly's SI suffixes (K, M, G)
        tickprefix="S/ " if y_is_currency else "",
        separatethousands=True,
    )
    fig.update_layout(hovermode="x unified")
    return fig


# ── 4 gráficos en 2 filas de 2 columnas ──

col_a, col_b = st.columns(2)

with col_a:
    render_chart(
        make_evolution_chart(
            all_avisos_series,
            "Eventos Reportados por Mes",
            "N.° de avisos",
            subtitle="Avisos nuevos registrados cada mes",
        ),
        key="chart_avisos_mes", filename="avisos_por_mes_campanas",
    )

with col_b:
    render_chart(
        make_evolution_chart(
            all_avisos_series,
            "Avisos Acumulados",
            "N.° de avisos acumulados",
            cumulative=True,
            subtitle="Acumulado desde el inicio de la campaña (agosto)",
        ),
        key="chart_avisos_acum", filename="avisos_acumulados_campanas",
    )

col_c, col_d = st.columns(2)

with col_c:
    render_chart(
        make_evolution_chart(
            all_indemn_monto_series,
            "Indemnizaciones por Mes",
            "Monto (S/)",
            fmt_prefix="S/ ",
            subtitle="Monto reconocido en cada mes (fecha de ajuste)",
            y_is_currency=True,
        ),
        key="chart_indemn_mes", filename="indemnizaciones_por_mes_campanas",
    )

with col_d:
    render_chart(
        make_evolution_chart(
            all_indemn_monto_series,
            "Indemnizaciones Acumuladas",
            "Monto acumulado (S/)",
            fmt_prefix="S/ ",
            cumulative=True,
            subtitle="Acumulado desde el inicio de la campaña (agosto)",
            y_is_currency=True,
        ),
        key="chart_indemn_acum", filename="indemnizaciones_acumuladas_campanas",
    )

# ── Gráficos adicionales de conteo de indemnizados ──

st.markdown("#### Evolución de Casos Indemnizados")

col_e, col_f = st.columns(2)

with col_e:
    render_chart(
        make_evolution_chart(
            all_indemn_count_series,
            "Casos Indemnizados por Mes",
            "N.° de indemnizados",
            subtitle="Avisos con dictamen INDEMNIZABLE por mes",
        ),
        key="chart_ind_count_mes", filename="casos_indemnizados_por_mes",
    )

with col_f:
    render_chart(
        make_evolution_chart(
            all_indemn_count_series,
            "Indemnizados Acumulados",
            "N.° acumulado de indemnizados",
            cumulative=True,
            subtitle="Acumulado desde el inicio de la campaña (agosto)",
        ),
        key="chart_ind_count_acum", filename="casos_indemnizados_acumulados",
    )

st.caption("Nota: Eventos reportados se registran por FECHA_AVISO (o FECHA_SINIESTRO como proxy). "
           "Indemnizaciones se registran por FECHA_AJUSTE (fecha de reconocimiento en evaluación). "
           "Meses alineados al ciclo de campaña agrícola: agosto → julio.")

st.caption("Fuente: Datos históricos de 5 campañas SAC (resumen_departamental.json) + "
           "Primas históricas (Primas_Totales_SAC_2020-2026.xlsx) + "
           "Campaña actual desde datos consolidados descargados de aseguradoras.")

footer()
