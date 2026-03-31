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
colors = ["#2980b9"] * 5 + ["#408B14"]  # Azul para históricas, verde MIDAGRI para actual

fig = go.Figure()
fig.add_trace(go.Bar(
    x=all_camps, y=values,
    marker_color=colors,
    text=[fmt.format(v) for v in values],
    textposition="outside",
    textfont=dict(size=11),
))

# Línea de promedio histórico
avg_hist = np.mean([all_data[c][key] for c in CAMPANAS_HIST])
fig.add_hline(y=avg_hist, line_dash="dash", line_color="#e74c3c", line_width=1.5,
              annotation_text=f"Prom. histórico: {fmt.format(avg_hist)}",
              annotation_position="top left",
              annotation_font_color="#e74c3c")

fig.update_layout(
    title=dict(text=f"{metrica_sel} por Campaña Agrícola", font=dict(size=16)),
    xaxis_title="", yaxis_title=metrica_sel,
    height=420, margin=dict(l=40, r=20, t=60, b=40),
    plot_bgcolor="white", paper_bgcolor="white",
    yaxis=dict(gridcolor="#eee"),
    showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)

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
sin_colors = ["#e74c3c" if v > 70 else ("#f39c12" if v > 50 else "#27ae60") for v in sin_vals]

fig_sin = go.Figure()
fig_sin.add_trace(go.Bar(
    x=all_camps, y=sin_vals,
    marker_color=sin_colors,
    text=[f"{v:.1f}%" for v in sin_vals],
    textposition="outside",
))
fig_sin.add_hline(y=70, line_dash="dot", line_color="#e74c3c", line_width=1,
                  annotation_text="Umbral alto (70%)", annotation_position="top right",
                  annotation_font_color="#e74c3c", annotation_font_size=10)
fig_sin.update_layout(
    title=dict(text="Siniestralidad = Indemnización / Prima Neta (%)", font=dict(size=14)),
    height=350, margin=dict(l=40, r=20, t=50, b=40),
    plot_bgcolor="white", paper_bgcolor="white",
    yaxis=dict(gridcolor="#eee", title="Siniestralidad (%)"),
)
st.plotly_chart(fig_sin, use_container_width=True)

st.caption("Fuente: Datos históricos de 5 campañas SAC (resumen_departamental.json) + "
           "Primas históricas (Primas_Totales_SAC_2020-2026.xlsx) + "
           "Campaña actual desde datos consolidados descargados de aseguradoras.")

footer()
