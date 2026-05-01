"""Página: Predicción de cierre de campaña SAC 2025-2026."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from shared.state import require_data, get_datos
from shared.components import render_metric, page_header, footer
from shared.charts import apply_theme, render_chart, add_reference_line, PALETTE
from shared.cache import load_json_cached
from prediccion_siniestralidad import (
    predecir_cierre_campana,
    proyectar_serie_mensual,
    serie_actual_desde_df,
    CAMPANAS_HIST,
    MESES_CAMPANA,
)
from data_processor import load_primas_historicas

require_data()
datos = get_datos()
df_actual = datos["midagri"]

page_header("Predicción de Cierre de Campaña",
            "Modelo predictivo de indemnizaciones y siniestralidad al fin de la campaña 2025-2026",
            badge="Modelo · M5 regresión")

# ═══════════════════════════════════════════════════════════════
# 1. EXTRAER SERIE ACTUAL Y CALCULAR PREDICCIÓN
# ═══════════════════════════════════════════════════════════════

serie_n, serie_m, mes_corte_idx = serie_actual_desde_df(df_actual)
mes_corte = MESES_CAMPANA[mes_corte_idx]
mes_label = f"Mes {mes_corte_idx + 1}/12 — {mes_corte}"

# Prima neta de la campaña actual
primas = load_primas_historicas()
prima_actual = sum(primas.get("2025-2026", {}).values()) if primas.get("2025-2026") else 0
if prima_actual <= 0:
    prima_actual = float(datos.get("prima_neta", 0))

# Predicción
pred = predecir_cierre_campana(
    serie_actual_n=serie_n,
    serie_actual_monto=serie_m,
    mes_corte_idx=mes_corte_idx,
    prima_neta_actual=prima_actual,
)


# ═══════════════════════════════════════════════════════════════
# 2. PANEL DE KPIs
# ═══════════════════════════════════════════════════════════════

st.markdown("### Estado actual de la campaña 2025-2026")
st.caption(f"Datos consolidados al cierre del mes vigente: **{mes_label}**")

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(render_metric(
        "Indemnizados acumulados",
        f"{int(pred['acumulado_n_actual']):,}",
        f"avance al {mes_corte}",
        "blue"
    ), unsafe_allow_html=True)
with k2:
    st.markdown(render_metric(
        "Monto indemnizado",
        f"S/ {pred['acumulado_monto_actual']:,.0f}",
        f"al {mes_corte}",
        "amber"
    ), unsafe_allow_html=True)
with k3:
    st.markdown(render_metric(
        "Prima neta campaña",
        f"S/ {pred['prima_neta']:,.0f}",
        "asegurada total",
        "purple"
    ), unsafe_allow_html=True)
with k4:
    sin_actual = pred["siniestralidad_actual"]
    st.markdown(render_metric(
        "Siniestralidad parcial",
        f"{sin_actual:.1f}%",
        "indemnizado / prima",
        "green" if sin_actual < 50 else ("amber" if sin_actual < 70 else "blue")
    ), unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════
# 3. PROYECCIÓN AL CIERRE
# ═══════════════════════════════════════════════════════════════

st.markdown("### Proyección al cierre de campaña (Jul 2026)")

modelo_principal = pred["predicciones"]["M5_regresion"]
int_n = pred["intervalo_n"]
int_m = pred["intervalo_monto"]
int_s = pred["intervalo_siniestralidad"]

p1, p2, p3, p4 = st.columns(4)
with p1:
    st.markdown(render_metric(
        "Indemnizados (proyección)",
        f"{int(modelo_principal['total_n']):,}",
        f"rango: {int(int_n[0]):,} – {int(int_n[1]):,}",
        "blue"
    ), unsafe_allow_html=True)
with p2:
    st.markdown(render_metric(
        "Monto indemnizado (proyección)",
        f"S/ {modelo_principal['total_monto']:,.0f}",
        f"rango: S/ {int_m[0]:,.0f} – {int_m[1]:,.0f}",
        "amber"
    ), unsafe_allow_html=True)
with p3:
    sin_proj = modelo_principal["siniestralidad"]
    color = "green" if sin_proj < 50 else ("amber" if sin_proj < 70 else "blue")
    st.markdown(render_metric(
        "Siniestralidad final",
        f"{sin_proj:.1f}%",
        f"rango: {int_s[0]:.1f}% – {int_s[1]:.1f}%",
        color
    ), unsafe_allow_html=True)
with p4:
    crece_n = modelo_principal["total_n"] - pred["acumulado_n_actual"]
    crece_m = modelo_principal["total_monto"] - pred["acumulado_monto_actual"]
    st.markdown(render_metric(
        "Pendiente de procesar",
        f"{int(crece_n):,} casos",
        f"S/ {crece_m:,.0f} adicionales",
        "purple"
    ), unsafe_allow_html=True)

st.caption(
    f"**Modelo recomendado:** {pred['modelo_recomendado']} (regresión lineal sobre el "
    f"avance entre campañas). MAE en validación leave-one-out: "
    f"**{pred['desempeno_validacion']['MAE_casos']:.1f}% en casos**, "
    f"**{pred['desempeno_validacion']['MAE_monto']:.1f}% en monto**. "
    f"En la última campaña histórica (2024-25) acertó con error de "
    f"{pred['desempeno_validacion']['ultima_campana_test']['err_casos']:.1f}% en casos."
)


# ═══════════════════════════════════════════════════════════════
# 4. CURVA DE AVANCE: HISTÓRICA + PROYECTADA
# ═══════════════════════════════════════════════════════════════

st.divider()
st.markdown("### Curva de avance acumulado")
st.caption(
    "Compara el avance acumulado de indemnizaciones de las 5 campañas históricas "
    "con el avance actual (línea verde gruesa, hasta el mes vigente) y la proyección "
    "del modelo (línea verde punteada, mes vigente → Jul)."
)

# Curvas históricas
with open(os.path.join(os.path.dirname(__file__), "..", "static_data", "series_temporales.json"),
          encoding="utf-8") as f:
    nacional = json.load(f)


def _serie_camp(camp, sub_key):
    out = [0.0] * 12
    raw = nacional["indemnizaciones"].get(camp, {})
    for p, v in raw.items():
        try:
            y, m = int(p[:4]), int(p[5:7])
        except Exception:
            continue
        sy = int(camp[:4])
        idx = None
        if y == sy and 8 <= m <= 12:
            idx = m - 8
        elif y == sy + 1 and 1 <= m <= 7:
            idx = m + 4
        if idx is not None and isinstance(v, dict):
            out[idx] = v.get(sub_key, 0)
    return out


def make_advance_chart(metric_key: str, title: str, yaxis_title: str, fmt_prefix: str = ""):
    """Gráfico de curvas acumuladas históricas + actual + proyección."""
    fig = go.Figure()

    # Históricas
    colors_hist = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"]
    for camp, color in zip(CAMPANAS_HIST, colors_hist):
        s = _serie_camp(camp, metric_key)
        cum = np.cumsum(s)
        fig.add_trace(go.Scatter(
            x=MESES_CAMPANA, y=cum,
            mode="lines+markers", name=camp,
            line=dict(color=color, width=2),
            marker=dict(size=5),
            opacity=0.7,
            hovertemplate=f"<b>{camp}</b><br>%{{x}}: {fmt_prefix}%{{y:,.0f}}<extra></extra>",
        ))

    # Actual hasta el mes vigente
    serie = serie_n if metric_key == "n" else serie_m
    cum_actual = list(np.cumsum(serie[: mes_corte_idx + 1]))
    fig.add_trace(go.Scatter(
        x=MESES_CAMPANA[: mes_corte_idx + 1], y=cum_actual,
        mode="lines+markers", name="2025-2026 (actual)",
        line=dict(color=PALETTE["midagri"], width=4),
        marker=dict(size=9, line=dict(width=2, color="#fff")),
        hovertemplate=f"<b>2025-2026</b><br>%{{x}}: {fmt_prefix}%{{y:,.0f}}<extra></extra>",
    ))

    # Proyección desde el mes vigente hasta Jul
    curvas_hist = [_serie_camp(c, metric_key) for c in CAMPANAS_HIST]
    proyectada = proyectar_serie_mensual(
        serie_actual=serie,
        mes_corte_idx=mes_corte_idx,
        curvas_hist_camp=curvas_hist,
        metodo="M5",
    )
    cum_proy = list(np.cumsum(proyectada))
    # Línea punteada solo del corte en adelante
    fig.add_trace(go.Scatter(
        x=MESES_CAMPANA[mes_corte_idx:], y=cum_proy[mes_corte_idx:],
        mode="lines+markers", name="2025-2026 (proyección M5)",
        line=dict(color=PALETTE["midagri"], width=3, dash="dash"),
        marker=dict(size=7, symbol="diamond"),
        hovertemplate=f"<b>Proyección</b><br>%{{x}}: {fmt_prefix}%{{y:,.0f}}<extra></extra>",
    ))

    apply_theme(
        fig, title=title,
        subtitle=f"Mes vigente: {mes_corte}. La proyección asume continuidad de la tendencia operativa observada.",
        height=460, yaxis_title=yaxis_title, legend_position="bottom",
        y_is_currency=(metric_key == "monto"),
    )
    if metric_key == "monto":
        fig.update_yaxes(tickformat="~s", tickprefix="S/ ")
    return fig


col_a, col_b = st.columns(2)
with col_a:
    render_chart(
        make_advance_chart("n", "Casos indemnizados acumulados", "N.° de indemnizados"),
        key="chart_pred_casos", filename="proyeccion_indemnizados",
    )
with col_b:
    render_chart(
        make_advance_chart("monto", "Monto indemnizado acumulado",
                          "Monto (S/)", fmt_prefix="S/ "),
        key="chart_pred_monto", filename="proyeccion_monto",
    )


# ═══════════════════════════════════════════════════════════════
# 5. COMPARATIVA DE MODELOS
# ═══════════════════════════════════════════════════════════════

st.divider()
st.markdown("### Comparativa de modelos predictivos")
st.caption(
    "El sistema entrena 3 modelos en paralelo y reporta el rango entre el más "
    "conservador y el más optimista. El modelo recomendado (M5) tiene el menor "
    "MAE en validación leave-one-out."
)

rows = []
modelo_meta = {
    "M5_regresion": ("Regresión lineal sobre tendencia de avance",
                    "Captura aceleración operativa", 16.0, 29.1),
    "M4_ultima":    ("Sólo última campaña (2024-25)",
                    "Asume operativa similar al año pasado", 27.6, 31.4),
    "M3_ultimas_2": ("Promedio de últimas 2 campañas",
                    "Suaviza ruido entre campañas recientes", 40.5, 42.6),
}
for m_key, p in pred["predicciones"].items():
    nombre, desc, mae_n, mae_m = modelo_meta[m_key]
    is_main = m_key == pred["modelo_recomendado"]
    rows.append({
        "Modelo": ("★ " if is_main else "  ") + nombre,
        "Descripción": desc,
        "Casos proy.": f"{int(p['total_n']):,}",
        "Monto proy.": f"S/ {p['total_monto']:,.0f}",
        "Siniestralidad proy.": f"{p['siniestralidad']:.1f}%",
        "MAE (val.)": f"{mae_n:.1f}% / {mae_m:.1f}%",
    })

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# 6. AVANCE % HISTÓRICO POR MES — TABLA DE TRANSPARENCIA
# ═══════════════════════════════════════════════════════════════

st.markdown("#### Avance histórico al mes vigente")
st.caption(
    f"Para construir la predicción, el modelo compara el avance acumulado al mes **{mes_corte}** "
    "en cada campaña histórica. La regresión proyecta el siguiente punto en la secuencia."
)

avances_table = pd.DataFrame({
    "Campaña": list(pred["avances_historicos_n"].keys()) + ["**Proyectado 2025-2026**"],
    f"Avance casos al {mes_corte}": [f"{v:.1%}" for v in pred["avances_historicos_n"].values()] +
                                      [f"**{pred['avance_proyectado_n_M5']:.1%}**"],
    f"Avance monto al {mes_corte}": [f"{v:.1%}" for v in pred["avances_historicos_monto"].values()] +
                                     [f"**{pred['avance_proyectado_monto_M5']:.1%}**"],
})
st.dataframe(avances_table, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# 7. LIMITACIONES Y SUPUESTOS
# ═══════════════════════════════════════════════════════════════

st.divider()
with st.expander("Supuestos, limitaciones y desempeño del modelo (transparencia)", expanded=False):
    st.markdown(f"""
**Modelo principal: M5 (regresión lineal sobre el avance entre campañas)**

Cómo funciona:
1. Para cada campaña histórica, calculamos el % de indemnizaciones acumuladas a cada mes (Ago…Jul).
2. Observamos que el avance al mes Abr pasó de **28% en 2020-21** a **71% en 2024-25** — clara tendencia de aceleración.
3. Ajustamos una recta sobre esos 5 puntos y proyectamos el avance esperado para 2025-2026.
4. Dividimos el acumulado actual por el avance proyectado para estimar el total final.

**Desempeño en validación leave-one-out:**
- MAE casos: **{pred['desempeno_validacion']['MAE_casos']:.1f}%**
- MAE monto: **{pred['desempeno_validacion']['MAE_monto']:.1f}%**
- En la última campaña testeada (2024-25): error de **{pred['desempeno_validacion']['ultima_campana_test']['err_casos']:.1f}% en casos** y **{pred['desempeno_validacion']['ultima_campana_test']['err_monto']:.1f}% en monto**.

**Limitaciones importantes:**
""")
    for lim in pred["limitaciones"]:
        st.markdown(f"- {lim}")

    st.markdown("""
**Cómo interpretar el rango:**
- El **valor central** es la mejor estimación del modelo M5.
- El **rango (mín–máx)** son las predicciones de los 3 modelos. Si M5 y M4 difieren mucho, hay alta incertidumbre.
- La **siniestralidad final** es el indicador más relevante: si supera 70% se considera campaña de alto siniestro.

**Cuándo no usar este modelo:**
- En los meses Ago-Nov, donde el avance histórico es ~0-5% y la división se vuelve inestable.
- Después de un evento climático extraordinario (sequía severa, El Niño extremo) que rompa la estacionalidad.
- Si cambian los procesos del SAC (nuevas reglas de validación, cambio de aseguradoras, etc.).
""")

st.caption(
    "Fuente: serie histórica de 5 campañas SAC (2020-2021 a 2024-2025) desde "
    "`series_temporales.json` (generada con `gen_series_temporales_dept.py`) + "
    "datos dinámicos de la campaña actual filtrados por DICTAMEN = INDEMNIZABLE "
    "y agrupados por FECHA DE AJUSTE."
)

footer()
