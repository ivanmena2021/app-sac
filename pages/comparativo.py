"""Página: Comparativo de Campañas — 5 históricas + actual."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json
from datetime import datetime, timezone, timedelta

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
from shared.cache import load_json_cached
from data_processor import load_primas_historicas

TZ_PERU = timezone(timedelta(hours=-5))

require_data()
datos = get_datos()
df_actual = datos["midagri"]

page_header("Comparativo de Campañas",
            "Evolución de indicadores SAC: 5 campañas históricas + campaña actual 2025-2026",
            badge="Histórico 2020 — 2026")

# ═══════════════════════════════════════════════════════════════
# CARGAR DATOS HISTÓRICOS
# ═══════════════════════════════════════════════════════════════

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static_data")
RESUMEN_PATH = os.path.join(STATIC_DIR, "resumen_departamental.json")

# Cacheado: json.load se ejecutaba en cada rerun de la página.
resumen_dept = load_json_cached(RESUMEN_PATH)

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

st.divider()
st.markdown("### Evolución Temporal Comparativa")
st.caption("Todas las campañas alineadas por mes agrícola (Ago → Jul) para facilitar la comparación")

SERIES_PATH = os.path.join(STATIC_DIR, "series_temporales.json")
series_data = load_json_cached(SERIES_PATH)

# Series temporales POR DEPARTAMENTO — generadas con gen_series_temporales_dept.py
# desde los Excel de la carpeta comportamiento_historico_sac_2020_xxxx/.
# Formato: {"por_dept": {DEPT: {"avisos": {camp: {YYYY-MM: n}}, "indemnizaciones": {camp: {YYYY-MM: {n,monto}}}}}}
SERIES_DEPT_PATH = os.path.join(STATIC_DIR, "series_temporales_dept.json")
series_dept_data = load_json_cached(SERIES_DEPT_PATH)

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


def _current_campaign_month_idx(campana, today=None):
    """Devuelve el índice 0..11 del mes vigente dentro de la campaña si está en curso.
    None si la campaña ya terminó o aún no empezó (usamos dato completo o nada).
    """
    if today is None:
        today = datetime.now(TZ_PERU).date()
    start_year = int(campana[:4])
    if today.year == start_year and 8 <= today.month <= 12:
        return today.month - 8
    if today.year == start_year + 1 and 1 <= today.month <= 7:
        return today.month + 4
    return None


def _mask_future_months(series, campana):
    """Para la campaña en curso, reemplaza meses posteriores al vigente con np.nan.
    Así Plotly corta la línea y cumsum no inventa datos de meses que no ocurrieron.
    """
    idx = _current_campaign_month_idx(campana)
    if idx is None:
        return series  # histórica o futura: no truncar
    out = list(series)
    for i in range(idx + 1, 12):
        out[i] = np.nan
    return out


def build_current_series_avisos(df, campana):
    """Construye serie de avisos por mes para campaña actual desde DataFrame.
    Meses posteriores al mes vigente quedan como np.nan (aún no ocurrieron).
    """
    date_col = None
    for col in ["FECHA_AVISO", "FECHA_SINIESTRO"]:
        if col in df.columns:
            date_col = col
            break
    if date_col is None:
        return _mask_future_months([0.0] * 12, campana)
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    monthly = dates.dt.to_period("M").value_counts().sort_index()
    raw = {str(p): int(c) for p, c in monthly.items()}
    return _mask_future_months(build_campaign_series(raw, campana), campana)


def build_current_series_indemn(df, campana):
    """Construye series de indemnizaciones por mes para campaña actual.
    Meses posteriores al mes vigente quedan como np.nan (aún no ocurrieron).
    """
    # Buscar columna de fecha de ajuste
    date_col = None
    for col in ["FECHA_AJUSTE_ACTA_FINAL", "FECHA_AJUSTE_ACTA_1",
                "FECHA_PROGRAMACION_AJUSTE", "FECHA_SINIESTRO"]:
        if col in df.columns:
            date_col = col
            break
    if date_col is None:
        empty = _mask_future_months([0.0] * 12, campana)
        return empty, list(empty)

    # Filtrar indemnizables
    ind_mask = pd.Series(False, index=df.index)
    if "DICTAMEN" in df.columns:
        dict_col = df["DICTAMEN"].astype(str).str.strip().str.upper()
        ind_mask = (dict_col.str.contains("INDEMNIZABLE", na=False) &
                    ~dict_col.str.contains("NO INDEMNIZABLE", na=False))

    df_ind = df[ind_mask].copy()
    if df_ind.empty:
        empty = _mask_future_months([0.0] * 12, campana)
        return empty, list(empty)

    df_ind[date_col] = pd.to_datetime(df_ind[date_col], errors="coerce")
    df_ind = df_ind[df_ind[date_col].notna()]
    if df_ind.empty:
        empty = _mask_future_months([0.0] * 12, campana)
        return empty, list(empty)

    periods = df_ind[date_col].dt.to_period("M")
    count_m = periods.value_counts().sort_index()
    count_raw = {str(p): int(c) for p, c in count_m.items()}
    counts = _mask_future_months(build_campaign_series(count_raw, campana), campana)

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
        montos = _mask_future_months(build_campaign_series(monto_raw, campana), campana)
    else:
        montos = _mask_future_months([0.0] * 12, campana)

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
           "Meses alineados al ciclo de campaña agrícola: agosto → julio. "
           "La campaña en curso se corta en el mes vigente (Perú UTC-5); los meses siguientes no se grafican.")

st.caption("Fuente: Datos históricos de 5 campañas SAC (resumen_departamental.json) + "
           "Primas históricas (Primas_Totales_SAC_2020-2026.xlsx) + "
           "Campaña actual desde datos consolidados descargados de aseguradoras.")


# ═══════════════════════════════════════════════════════════════
# COMPARATIVO POR DEPARTAMENTO — un dept × 6 campañas
# ═══════════════════════════════════════════════════════════════

st.divider()

# Normalizar nombres de departamento: el JSON histórico tiene HUÁNUCO y
# SAN MARTÍN con tildes en algunas entradas y sin tildes en otras (duplicados).
# Quitamos acentos y pasamos a mayúsculas para unificar antes del merge.
import unicodedata as _ud

def _norm_dept(name):
    s = str(name).strip().upper()
    # NFD separa letra base y marca diacrítica; filtramos las marcas (Mn).
    return "".join(c for c in _ud.normalize("NFD", s) if _ud.category(c) != "Mn")

# Histórico por dept normalizado: {dept: {camp: {avisos, indemnizados, monto, ha, desembolso}}}
hist_por_dept = {}
for dept_raw, camps in por_campana.items():
    dept_n = _norm_dept(dept_raw)
    if not dept_n:
        continue
    bucket = hist_por_dept.setdefault(dept_n, {})
    for camp_k, vals in camps.items():
        if camp_k in bucket:
            # Merge sumando (para duplicados por mojibake)
            for k, v in vals.items():
                if isinstance(v, (int, float)):
                    bucket[camp_k][k] = bucket[camp_k].get(k, 0) + v
        else:
            bucket[camp_k] = {k: v for k, v in vals.items() if isinstance(v, (int, float))}

# Universo de departamentos = unión de históricos + actuales
_depts_actuales = set()
if "DEPARTAMENTO" in df_actual.columns:
    _depts_actuales = set(
        d for d in df_actual["DEPARTAMENTO"].dropna().astype(str).str.strip().str.upper().unique()
        if d and d != "NAN"
    )
todos_dept = sorted(set(hist_por_dept.keys()) | _depts_actuales)

# Header con selector al costado (patrón del dashboard)
col_hdr_d, col_sel_d = st.columns([2.4, 1.2])
with col_hdr_d:
    st.markdown("### Comparativo por Departamento")
    st.caption("Mismo análisis de las 6 campañas, filtrado a un departamento específico.")
with col_sel_d:
    if not todos_dept:
        st.info("No hay departamentos disponibles.")
        dept_sel = None
    else:
        # Default: primer dept con datos en la campaña actual (o el primero alfabético)
        _def_idx = 0
        for _i, _d in enumerate(todos_dept):
            if _d in _depts_actuales:
                _def_idx = _i
                break
        dept_sel = st.selectbox(
            "Departamento", options=todos_dept, index=_def_idx,
            format_func=lambda d: d.title() if d else d,
            key="comp_dept_selector", label_visibility="collapsed",
        )

if dept_sel:
    # Calcular las métricas del dept para las 6 campañas
    dept_data = {}

    # Históricas
    for camp in CAMPANAS_HIST:
        dc = hist_por_dept.get(dept_sel, {}).get(camp, {})
        avisos_ = dc.get("avisos", 0)
        indemn_ = dc.get("indemnizados", 0)
        monto_ = dc.get("monto_indemnizado", 0)
        ha_ = dc.get("ha_indemnizadas", 0)
        desemb_ = dc.get("monto_desembolsado", 0)
        prima_ = primas_hist.get(camp, {}).get(dept_sel, 0)
        sin_ = round(100 * monto_ / prima_, 1) if prima_ > 0 else 0
        dept_data[camp] = {
            "avisos": avisos_, "indemnizados": indemn_,
            "monto": monto_, "ha": ha_, "desembolso": desemb_,
            "prima_neta": prima_, "siniestralidad": sin_,
        }

    # Campaña actual: filtrar el DataFrame por DEPARTAMENTO
    if "DEPARTAMENTO" in df_actual.columns:
        _dept_col = df_actual["DEPARTAMENTO"].astype(str).str.strip().str.upper()
        df_dept_sel = df_actual[_dept_col == dept_sel]
    else:
        df_dept_sel = df_actual.iloc[0:0]

    avisos_act = len(df_dept_sel)
    indemn_act = 0
    if "DICTAMEN" in df_dept_sel.columns:
        _dc = df_dept_sel["DICTAMEN"].astype(str).str.strip().str.upper()
        indemn_act = int(
            (_dc.str.contains("INDEMNIZABLE", na=False) &
             ~_dc.str.contains("NO INDEMNIZABLE", na=False)).sum()
        )
    def _safe_sum(col):
        if col not in df_dept_sel.columns:
            return 0.0
        return float(pd.to_numeric(df_dept_sel[col], errors="coerce").fillna(0).sum())
    monto_act = _safe_sum("INDEMNIZACION")
    ha_act = _safe_sum("SUP_INDEMNIZADA")
    desemb_act = _safe_sum("MONTO_DESEMBOLSADO")
    prima_act = primas_hist.get(CAMPANA_ACTUAL, {}).get(dept_sel, 0)
    sin_act = round(100 * monto_act / prima_act, 1) if prima_act > 0 else 0
    dept_data[CAMPANA_ACTUAL] = {
        "avisos": avisos_act, "indemnizados": indemn_act,
        "monto": monto_act, "ha": ha_act, "desembolso": desemb_act,
        "prima_neta": prima_act, "siniestralidad": sin_act,
    }

    # Selector de métrica (mismo dict METRICAS usado en el comparativo nacional)
    metrica_sel_d = st.radio(
        "Métrica:", options=list(METRICAS.keys()),
        horizontal=True, key="metrica_comp_dept",
    )
    key_d, fmt_d, desc_d = METRICAS[metrica_sel_d]
    st.caption(desc_d)

    # ── Gráfico de barras 6 campañas para el dept ──
    vals_d = [dept_data[c][key_d] for c in all_camps]
    colors_d = [PALETTE["primary_mid"]] * 5 + [PALETTE["midagri"]]

    fig_d = go.Figure()
    fig_d.add_trace(go.Bar(
        x=all_camps, y=vals_d,
        marker=dict(color=colors_d, line=dict(width=0), cornerradius=8),
        text=[fmt_d.format(v) for v in vals_d],
        textposition="outside",
        textfont=dict(size=12, color=PALETTE["text_soft"], family="Segoe UI"),
        hovertemplate=(
            "<b>Campaña %{x}</b><br>"
            + metrica_sel_d + ": %{text}<extra></extra>"
        ),
        showlegend=False,
    ))
    avg_hist_d = float(np.mean([dept_data[c][key_d] for c in CAMPANAS_HIST])) if CAMPANAS_HIST else 0
    add_reference_line(
        fig_d, y=avg_hist_d, color=PALETTE["danger"],
        label=f"Promedio histórico: {fmt_d.format(avg_hist_d)}",
    )
    apply_theme(
        fig_d,
        title=f"{metrica_sel_d} — {dept_sel.title()}",
        subtitle="Azul = históricas · Verde = campaña actual · Roja = promedio",
        height=450, show_legend=False, yaxis_title=metrica_sel_d,
        legend_position="none",
    )
    if "S/" in fmt_d or "monto" in key_d.lower() or "prima" in key_d.lower():
        fig_d.update_yaxes(tickformat="~s", tickprefix="S/ ")
    render_chart(
        fig_d, key="chart_dept_comp",
        filename=f"comparativo_{key_d}_{dept_sel.lower().replace(' ', '_')}",
    )

    # ── Tabla resumen 6 campañas para el dept ──
    st.markdown("#### Tabla Comparativa del Departamento")
    rows_d = []
    for c in all_camps:
        d = dept_data[c]
        sin_color = "🔴" if d["siniestralidad"] > 70 else ("🟡" if d["siniestralidad"] > 50 else "🟢")
        rows_d.append({
            "Campaña": c + (" ★" if c == CAMPANA_ACTUAL else ""),
            "Avisos": f"{d['avisos']:,}",
            "Indemnizados": f"{d['indemnizados']:,}",
            "Prima Neta": f"S/ {d['prima_neta']:,.0f}" if d["prima_neta"] > 0 else "—",
            "Indemnización": f"S/ {d['monto']:,.0f}",
            "Siniestralidad": f"{sin_color} {d['siniestralidad']:.1f}%",
            "Ha Indemnizadas": f"{d['ha']:,.0f}",
            "Desembolso": f"S/ {d['desembolso']:,.0f}",
        })
    avg_d = {
        k: float(np.mean([dept_data[c][k] for c in CAMPANAS_HIST]))
        for k in ["avisos", "indemnizados", "monto", "ha", "desembolso", "prima_neta", "siniestralidad"]
    }
    rows_d.append({
        "Campaña": "PROMEDIO HISTÓRICO",
        "Avisos": f"{avg_d['avisos']:,.0f}",
        "Indemnizados": f"{avg_d['indemnizados']:,.0f}",
        "Prima Neta": f"S/ {avg_d['prima_neta']:,.0f}" if avg_d["prima_neta"] > 0 else "—",
        "Indemnización": f"S/ {avg_d['monto']:,.0f}",
        "Siniestralidad": f"📊 {avg_d['siniestralidad']:.1f}%",
        "Ha Indemnizadas": f"{avg_d['ha']:,.0f}",
        "Desembolso": f"S/ {avg_d['desembolso']:,.0f}",
    })
    st.dataframe(pd.DataFrame(rows_d), use_container_width=True, hide_index=True, height=330)

    # ── Siniestralidad del dept en cada campaña ──
    st.markdown("#### Siniestralidad del Departamento")
    sin_vals_d = [dept_data[c]["siniestralidad"] for c in all_camps]
    sin_colors_d = [
        PALETTE["danger"] if v > 70 else (PALETTE["warning"] if v > 50 else PALETTE["success"])
        for v in sin_vals_d
    ]
    fig_sin_d = go.Figure()
    fig_sin_d.add_trace(go.Bar(
        x=all_camps, y=sin_vals_d,
        marker=dict(color=sin_colors_d, line=dict(width=0), cornerradius=8),
        text=[f"{v:.1f}%" for v in sin_vals_d],
        textposition="outside",
        textfont=dict(size=12, color=PALETTE["text_soft"]),
        hovertemplate="<b>Campaña %{x}</b><br>Siniestralidad: %{y:.1f}%<extra></extra>",
        showlegend=False,
    ))
    add_reference_line(fig_sin_d, y=70, color=PALETTE["danger"],
                       label="Alto (≥70%)", dash="dot")
    add_reference_line(fig_sin_d, y=50, color=PALETTE["warning"],
                       label="Medio (≥50%)", dash="dot")
    apply_theme(
        fig_sin_d,
        title=f"Siniestralidad — {dept_sel.title()}",
        subtitle="Indemnización / Prima Neta × 100 · '—' si no hay prima del dept",
        height=380, show_legend=False, yaxis_title="Siniestralidad (%)",
        legend_position="none",
    )
    render_chart(
        fig_sin_d, key="chart_sin_dept",
        filename=f"siniestralidad_{dept_sel.lower().replace(' ', '_')}",
    )

    # ══════════════════════════════════════════════════════════════
    # ── Evolución Temporal Comparativa — 6 campañas para el dept ──
    # ══════════════════════════════════════════════════════════════
    st.markdown(f"#### Evolución Mensual Comparativa · {dept_sel.title()}")
    st.caption("Todas las campañas alineadas por mes agrícola (Ago → Jul) para comparar "
               "el comportamiento del departamento año tras año. "
               "La campaña en curso se corta en el mes vigente (Perú UTC-5).")

    # Construir las 3 series (avisos, indemnizados count, indemnizados monto)
    # para las 6 campañas del departamento seleccionado
    _dept_hist_block = series_dept_data.get("por_dept", {}).get(dept_sel, {})
    _hist_avisos = _dept_hist_block.get("avisos", {})
    _hist_indemn = _dept_hist_block.get("indemnizaciones", {})

    all_avisos_dept = {}
    all_ind_count_dept = {}
    all_ind_monto_dept = {}

    # Campañas históricas desde el JSON por depto
    for camp in CAMPANAS_HIST:
        raw_av = _hist_avisos.get(camp, {})
        raw_in = _hist_indemn.get(camp, {})
        all_avisos_dept[camp] = build_campaign_series(raw_av, camp)
        all_ind_count_dept[camp] = build_campaign_series(raw_in, camp, value_key="n")
        all_ind_monto_dept[camp] = build_campaign_series(raw_in, camp, value_key="monto")

    # Campaña actual desde el df filtrado al dept (con corte al mes vigente)
    all_avisos_dept[CAMPANA_ACTUAL] = build_current_series_avisos(df_dept_sel, CAMPANA_ACTUAL)
    _cact, _mact = build_current_series_indemn(df_dept_sel, CAMPANA_ACTUAL)
    all_ind_count_dept[CAMPANA_ACTUAL] = _cact
    all_ind_monto_dept[CAMPANA_ACTUAL] = _mact

    _dept_slug = dept_sel.lower().replace(" ", "_")

    # 6 gráficos en 3 filas de 2 columnas (mismo layout que la sección nacional)
    col_dav1, col_dav2 = st.columns(2)
    with col_dav1:
        render_chart(
            make_evolution_chart(
                all_avisos_dept,
                f"Eventos Reportados por Mes — {dept_sel.title()}",
                "N.° de avisos",
                subtitle="Avisos por FECHA_AVISO",
            ),
            key="chart_dept_avisos_mes",
            filename=f"avisos_mes_{_dept_slug}",
        )
    with col_dav2:
        render_chart(
            make_evolution_chart(
                all_avisos_dept,
                f"Avisos Acumulados — {dept_sel.title()}",
                "N.° de avisos acumulados",
                cumulative=True,
                subtitle="Acumulado desde agosto",
            ),
            key="chart_dept_avisos_acum",
            filename=f"avisos_acum_{_dept_slug}",
        )

    col_dmo1, col_dmo2 = st.columns(2)
    with col_dmo1:
        render_chart(
            make_evolution_chart(
                all_ind_monto_dept,
                f"Indemnizaciones por Mes (S/) — {dept_sel.title()}",
                "Monto (S/)",
                fmt_prefix="S/ ",
                y_is_currency=True,
                subtitle="Reconocidas por FECHA_AJUSTE",
            ),
            key="chart_dept_monto_mes",
            filename=f"monto_indemn_mes_{_dept_slug}",
        )
    with col_dmo2:
        render_chart(
            make_evolution_chart(
                all_ind_monto_dept,
                f"Indemnizaciones Acumuladas (S/) — {dept_sel.title()}",
                "Monto acumulado (S/)",
                fmt_prefix="S/ ",
                cumulative=True,
                y_is_currency=True,
                subtitle="Acumulado desde agosto",
            ),
            key="chart_dept_monto_acum",
            filename=f"monto_indemn_acum_{_dept_slug}",
        )

    col_dic1, col_dic2 = st.columns(2)
    with col_dic1:
        render_chart(
            make_evolution_chart(
                all_ind_count_dept,
                f"Casos Indemnizados por Mes — {dept_sel.title()}",
                "N.° de indemnizados",
                subtitle="Avisos con dictamen INDEMNIZABLE",
            ),
            key="chart_dept_ind_count_mes",
            filename=f"casos_indemnizados_mes_{_dept_slug}",
        )
    with col_dic2:
        render_chart(
            make_evolution_chart(
                all_ind_count_dept,
                f"Indemnizados Acumulados — {dept_sel.title()}",
                "N.° acumulado",
                cumulative=True,
                subtitle="Acumulado desde agosto",
            ),
            key="chart_dept_ind_count_acum",
            filename=f"casos_indemnizados_acum_{_dept_slug}",
        )

    st.caption(
        f"Fuente histórica por depto: archivos Dashboard SAC 2020-2025 a nivel aviso "
        f"(comportamiento_historico_sac_2020_xxxx/, hoja AVISOS), agregados por "
        f"DEPARTAMENTO y mes con `gen_series_temporales_dept.py`. "
        f"Campaña actual: consolidado dinámico filtrado a DEPARTAMENTO = '{dept_sel}'. "
        f"Indemnizaciones se cuentan donde DICTAMEN = INDEMNIZABLE y se fechan por "
        f"FECHA DE AJUSTE (ACTA > COSECHA > PROGRAMACION AJUSTE). "
        f"Validado contra totales del JSON nacional (diff = 0 en las 5 campañas)."
    )

footer()
