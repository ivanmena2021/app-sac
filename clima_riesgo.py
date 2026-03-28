"""
clima_riesgo.py — Pronóstico meteorológico y análisis de riesgo climático SAC
===============================================================================
Consulta la API gratuita Open-Meteo (sin key) para obtener pronósticos a 7 días
por departamento y cruza con datos de siniestros del SAC.
"""

import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gen_mapa_calor import DEPT_COORDS
from calendario_agricola import get_current_risk_crops
from data_processor import LLUVIA_TYPES

# ═══════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════

OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

RISK_THRESHOLDS = {
    "precip_daily_amber": 20,
    "precip_daily_red": 50,
    "precip_7day_amber": 80,
    "precip_7day_red": 150,
    "temp_high_amber": 32,
    "temp_high_red": 36,
    "temp_low_amber": 10,
    "temp_low_red": 5,
    "wind_amber": 40,
    "wind_red": 60,
}

WEATHER_TO_SINIESTRO = {
    "heavy_rain": {"INUNDACION", "INUNDACIÓN", "HUAYCO", "LLUVIAS EXCESIVAS",
                   "DESLIZAMIENTO", "DESLIZAMIENTOS"},
    "frost": {"HELADA", "FRIAJE"},
    "drought": {"SEQUIA", "SEQUÍA"},
    "hail": {"GRANIZADA", "GRANIZO"},
}

COLORS = {"verde": "#27ae60", "ambar": "#f39c12", "rojo": "#e74c3c"}

WMO_CODES = {
    0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado",
    3: "Nublado", 45: "Niebla", 48: "Niebla con escarcha",
    51: "Llovizna leve", 53: "Llovizna moderada", 55: "Llovizna intensa",
    61: "Lluvia leve", 63: "Lluvia moderada", 65: "Lluvia intensa",
    71: "Nieve leve", 73: "Nieve moderada", 75: "Nieve intensa",
    80: "Chubascos leves", 81: "Chubascos moderados", 82: "Chubascos intensos",
    85: "Nieve leve", 86: "Nieve intensa",
    95: "Tormenta eléctrica", 96: "Tormenta con granizo leve",
    99: "Tormenta con granizo fuerte",
}


# ═══════════════════════════════════════════════════════════════════
# API LAYER
# ═══════════════════════════════════════════════════════════════════

def _api_get(url, timeout=10):
    """GET request usando urllib (stdlib, sin dependencias extra)."""
    req = urllib.request.Request(url, headers={"User-Agent": "SAC-App/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_forecast_all():
    """Obtiene pronóstico 7 días para los 24 departamentos."""
    results = {}
    for dept, (lat, lon) in DEPT_COORDS.items():
        try:
            params = (
                f"?latitude={lat}&longitude={lon}"
                f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min,"
                f"windspeed_10m_max,weathercode"
                f"&timezone=America/Lima&forecast_days=7"
            )
            data = _api_get(OPEN_METEO_FORECAST + params)
            results[dept] = data.get("daily", {})
            time.sleep(0.05)
        except Exception:
            results[dept] = None
    return results


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_historical_precip(start_date: str, end_date: str):
    """Obtiene precipitación histórica diaria por departamento."""
    results = {}
    for dept, (lat, lon) in DEPT_COORDS.items():
        try:
            params = (
                f"?latitude={lat}&longitude={lon}"
                f"&daily=precipitation_sum"
                f"&timezone=America/Lima"
                f"&start_date={start_date}&end_date={end_date}"
            )
            data = _api_get(OPEN_METEO_ARCHIVE + params, timeout=15)
            daily = data.get("daily", {})
            if daily and daily.get("time"):
                df = pd.DataFrame({
                    "fecha": pd.to_datetime(daily["time"]),
                    "precip_mm": daily.get("precipitation_sum", []),
                })
                df["departamento"] = dept
                results[dept] = df
            time.sleep(0.05)
        except Exception:
            results[dept] = None
    return results


# ═══════════════════════════════════════════════════════════════════
# MOTOR DE RIESGO
# ═══════════════════════════════════════════════════════════════════

def _classify(value, amber_thresh, red_thresh, invert=False):
    """Clasifica un valor en verde/ambar/rojo."""
    if value is None:
        return "verde"
    if invert:
        if value < red_thresh:
            return "rojo"
        if value < amber_thresh:
            return "ambar"
        return "verde"
    if value >= red_thresh:
        return "rojo"
    if value >= amber_thresh:
        return "ambar"
    return "verde"


def _nivel_to_score(nivel):
    return {"verde": 0, "ambar": 50, "rojo": 100}.get(nivel, 0)


def _max_nivel(*niveles):
    order = {"verde": 0, "ambar": 1, "rojo": 2}
    max_n = max(niveles, key=lambda n: order.get(n, 0))
    return max_n


def compute_department_risk(dept, forecast):
    """Calcula riesgo para un departamento a partir de su forecast."""
    if not forecast or not forecast.get("time"):
        return {
            "nivel": "verde", "score": 0,
            "precip_7d": 0, "max_precip_day": 0,
            "temp_max": None, "temp_min": None, "wind_max": None,
            "nivel_lluvia": "verde", "nivel_temp": "verde", "nivel_viento": "verde",
            "sin_datos": True,
        }

    precip = forecast.get("precipitation_sum", [])
    t_max = forecast.get("temperature_2m_max", [])
    t_min = forecast.get("temperature_2m_min", [])
    wind = forecast.get("windspeed_10m_max", [])

    precip_clean = [p for p in precip if p is not None]
    t_max_clean = [t for t in t_max if t is not None]
    t_min_clean = [t for t in t_min if t is not None]
    wind_clean = [w for w in wind if w is not None]

    precip_7d = sum(precip_clean)
    max_precip_day = max(precip_clean) if precip_clean else 0
    max_temp = max(t_max_clean) if t_max_clean else None
    min_temp = min(t_min_clean) if t_min_clean else None
    max_wind = max(wind_clean) if wind_clean else None

    # Clasificar indicadores
    T = RISK_THRESHOLDS
    nivel_lluvia_day = _classify(max_precip_day, T["precip_daily_amber"], T["precip_daily_red"])
    nivel_lluvia_7d = _classify(precip_7d, T["precip_7day_amber"], T["precip_7day_red"])
    nivel_lluvia = _max_nivel(nivel_lluvia_day, nivel_lluvia_7d)

    nivel_temp_high = _classify(max_temp, T["temp_high_amber"], T["temp_high_red"]) if max_temp else "verde"
    nivel_temp_low = _classify(min_temp, T["temp_low_amber"], T["temp_low_red"], invert=True) if min_temp else "verde"
    nivel_temp = _max_nivel(nivel_temp_high, nivel_temp_low)

    nivel_viento = _classify(max_wind, T["wind_amber"], T["wind_red"]) if max_wind else "verde"

    # Score base ponderado
    score_lluvia = _nivel_to_score(nivel_lluvia) * 0.40
    score_temp = _nivel_to_score(nivel_temp) * 0.30
    score_viento = _nivel_to_score(nivel_viento) * 0.15

    # Bonus por cruce con calendario agrícola
    calendar_bonus = 0
    try:
        risk_crops = get_current_risk_crops(dept)
        crop_risks = set()
        for c in risk_crops:
            crop_risks.update(c.get("riesgos", []))
        # Si hay cultivos vulnerables a lluvia y se pronostica lluvia fuerte
        if crop_risks & WEATHER_TO_SINIESTRO["heavy_rain"] and nivel_lluvia in ("ambar", "rojo"):
            calendar_bonus = 15
        elif crop_risks & WEATHER_TO_SINIESTRO["frost"] and nivel_temp in ("ambar", "rojo"):
            calendar_bonus = 15
        elif crop_risks & WEATHER_TO_SINIESTRO["drought"] and precip_7d < 5:
            calendar_bonus = 10
    except Exception:
        pass

    score = min(100, int(score_lluvia + score_temp + score_viento + calendar_bonus))
    nivel_general = "rojo" if score >= 60 else ("ambar" if score >= 30 else "verde")

    return {
        "nivel": nivel_general, "score": score,
        "precip_7d": round(precip_7d, 1),
        "max_precip_day": round(max_precip_day, 1),
        "temp_max": round(max_temp, 1) if max_temp else None,
        "temp_min": round(min_temp, 1) if min_temp else None,
        "wind_max": round(max_wind, 1) if max_wind else None,
        "nivel_lluvia": nivel_lluvia, "nivel_temp": nivel_temp,
        "nivel_viento": nivel_viento, "sin_datos": False,
    }


# ═══════════════════════════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════════════════════════

def _color_dot(nivel):
    c = COLORS.get(nivel, "#ccc")
    label = {"verde": "Verde", "ambar": "Ámbar", "rojo": "Rojo"}.get(nivel, "?")
    return f'<span style="color:{c};font-size:18px;">&#9679;</span> {label}'


def _render_kpis(risks):
    rojos = sum(1 for r in risks.values() if r["nivel"] == "rojo")
    ambars = sum(1 for r in risks.values() if r["nivel"] == "ambar")
    valid = [r for r in risks.values() if not r.get("sin_datos")]
    avg_precip = np.mean([r["precip_7d"] for r in valid]) if valid else 0
    avg_score = np.mean([r["score"] for r in valid]) if valid else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Deptos Alerta Roja", rojos, help="Departamentos con riesgo alto en los próximos 7 días")
    c2.metric("Deptos Alerta Ámbar", ambars, help="Departamentos con riesgo moderado")
    c3.metric("Precip. Promedio 7d", f"{avg_precip:.0f} mm", help="Precipitación acumulada promedio nacional")
    c4.metric("Score Riesgo Promedio", f"{avg_score:.0f}/100", help="0 = sin riesgo, 100 = riesgo extremo")


def _render_risk_map(risks):
    depts, lats, lons, colors, sizes, hovers = [], [], [], [], [], []
    for dept, risk in risks.items():
        coords = DEPT_COORDS.get(dept)
        if not coords:
            continue
        depts.append(dept)
        lats.append(coords[0])
        lons.append(coords[1])
        colors.append(COLORS.get(risk["nivel"], "#ccc"))
        sizes.append(max(12, risk["score"] * 0.4 + 10))
        hover = (
            f"<b>{dept}</b><br>"
            f"Riesgo: {risk['nivel'].upper()} ({risk['score']}/100)<br>"
            f"Precip 7d: {risk['precip_7d']} mm<br>"
            f"Temp: {risk['temp_min']}°C – {risk['temp_max']}°C<br>"
            f"Viento máx: {risk['wind_max']} km/h"
        )
        hovers.append(hover)

    fig = go.Figure(go.Scattermapbox(
        lat=lats, lon=lons,
        mode="markers+text",
        marker=dict(size=sizes, color=colors, opacity=0.85),
        text=depts,
        textposition="top center",
        textfont=dict(size=9, color="#333"),
        hovertext=hovers,
        hoverinfo="text",
    ))
    fig.update_layout(
        mapbox=dict(style="open-street-map", center=dict(lat=-9.5, lon=-75.5), zoom=4.3),
        margin=dict(l=0, r=0, t=0, b=0),
        height=520,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_forecast_table(dept, forecast):
    """Tabla de pronóstico 7 días para un departamento."""
    if not forecast or not forecast.get("time"):
        st.info(f"Sin datos de pronóstico para {dept}.")
        return

    rows = []
    dates = forecast.get("time", [])
    precip = forecast.get("precipitation_sum", [])
    t_max = forecast.get("temperature_2m_max", [])
    t_min = forecast.get("temperature_2m_min", [])
    wind = forecast.get("windspeed_10m_max", [])
    codes = forecast.get("weathercode", [])

    T = RISK_THRESHOLDS
    for i, d in enumerate(dates):
        p = precip[i] if i < len(precip) else None
        tmx = t_max[i] if i < len(t_max) else None
        tmn = t_min[i] if i < len(t_min) else None
        w = wind[i] if i < len(wind) else None
        code = codes[i] if i < len(codes) else None

        nivel_p = _classify(p, T["precip_daily_amber"], T["precip_daily_red"])
        nivel_t = _max_nivel(
            _classify(tmx, T["temp_high_amber"], T["temp_high_red"]) if tmx else "verde",
            _classify(tmn, T["temp_low_amber"], T["temp_low_red"], invert=True) if tmn else "verde",
        )
        nivel_w = _classify(w, T["wind_amber"], T["wind_red"]) if w else "verde"
        nivel_gen = _max_nivel(nivel_p, nivel_t, nivel_w)

        emoji = {"verde": "🟢", "ambar": "🟡", "rojo": "🔴"}.get(nivel_gen, "⚪")
        clima_desc = WMO_CODES.get(code, f"Código {code}") if code is not None else "—"

        rows.append({
            "Fecha": d,
            "Clima": clima_desc,
            "Precip (mm)": round(p, 1) if p is not None else "—",
            "Temp Máx (°C)": round(tmx, 1) if tmx is not None else "—",
            "Temp Mín (°C)": round(tmn, 1) if tmn is not None else "—",
            "Viento (km/h)": round(w, 1) if w is not None else "—",
            "Alerta": f"{emoji} {nivel_gen.capitalize()}",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_semaforo_grid(risks):
    """Tabla semáforo climático: 24 deptos × indicadores."""
    def _cell(nivel):
        bg = COLORS.get(nivel, "#eee")
        label = {"verde": "Verde", "ambar": "Ámbar", "rojo": "Rojo"}.get(nivel, "—")
        text_color = "#fff" if nivel in ("rojo", "verde") else "#333"
        return f'<td style="background:{bg};color:{text_color};text-align:center;padding:4px 8px;font-size:12px;font-weight:600;">{label}</td>'

    rows_html = []
    for dept in sorted(risks.keys()):
        r = risks[dept]
        if r.get("sin_datos"):
            cells = '<td colspan="4" style="text-align:center;color:#999;font-size:12px;">Sin datos</td>'
        else:
            cells = (
                _cell(r["nivel_lluvia"])
                + _cell(r["nivel_temp"])
                + _cell(r["nivel_viento"])
                + _cell(r["nivel"])
            )
        rows_html.append(f'<tr><td style="padding:4px 8px;font-size:12px;font-weight:500;">{dept}</td>{cells}</tr>')

    header = (
        '<tr style="background:#2C5F2D;color:#fff;">'
        '<th style="padding:6px 8px;text-align:left;">Departamento</th>'
        '<th style="padding:6px 8px;text-align:center;">Lluvia</th>'
        '<th style="padding:6px 8px;text-align:center;">Temperatura</th>'
        '<th style="padding:6px 8px;text-align:center;">Viento</th>'
        '<th style="padding:6px 8px;text-align:center;">General</th>'
        '</tr>'
    )

    html = (
        '<div style="overflow-x:auto;">'
        '<table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;'
        'box-shadow:0 1px 3px rgba(0,0,0,0.1);">'
        f'{header}{"".join(rows_html)}'
        '</table></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_correlation(datos, historical):
    """Scatter: precipitación mensual vs. siniestros por departamento."""
    df = datos.get("midagri")
    if df is None or df.empty:
        return

    if not historical or all(v is None for v in historical.values()):
        st.info("No se pudieron obtener datos históricos de precipitación para la correlación.")
        return

    # Agrupar siniestros por depto + mes
    date_col = "FECHA_SINIESTRO" if "FECHA_SINIESTRO" in df.columns else "FECHA_AVISO"
    if date_col not in df.columns:
        return

    df_sin = df[[date_col, "DEPARTAMENTO"]].dropna().copy()
    df_sin["mes"] = pd.to_datetime(df_sin[date_col], errors="coerce").dt.to_period("M")
    df_sin = df_sin.dropna(subset=["mes"])
    sin_monthly = df_sin.groupby(["DEPARTAMENTO", "mes"]).size().reset_index(name="siniestros")
    sin_monthly["mes_str"] = sin_monthly["mes"].astype(str)

    # Combinar precipitación histórica
    precip_frames = []
    for dept, pdf in historical.items():
        if pdf is not None and not pdf.empty:
            p = pdf.copy()
            p["mes"] = p["fecha"].dt.to_period("M")
            monthly = p.groupby("mes")["precip_mm"].sum().reset_index()
            monthly["departamento"] = dept
            monthly["mes_str"] = monthly["mes"].astype(str)
            precip_frames.append(monthly)

    if not precip_frames:
        st.info("Sin datos de precipitación histórica suficientes.")
        return

    precip_all = pd.concat(precip_frames, ignore_index=True)
    merged = sin_monthly.merge(
        precip_all,
        left_on=["DEPARTAMENTO", "mes_str"],
        right_on=["departamento", "mes_str"],
        how="inner",
    )

    if merged.empty:
        st.info("No se pudo cruzar datos de siniestros con precipitación.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=merged["precip_mm"],
        y=merged["siniestros"],
        mode="markers",
        marker=dict(size=7, opacity=0.6, color="#408B14"),
        text=merged["DEPARTAMENTO"] + " — " + merged["mes_str"],
        hoverinfo="text+x+y",
    ))

    # Línea de tendencia
    if len(merged) > 2:
        z = np.polyfit(merged["precip_mm"], merged["siniestros"], 1)
        p_line = np.poly1d(z)
        x_range = np.linspace(merged["precip_mm"].min(), merged["precip_mm"].max(), 50)
        fig.add_trace(go.Scatter(
            x=x_range, y=p_line(x_range),
            mode="lines", line=dict(color="#e74c3c", dash="dash", width=2),
            name="Tendencia",
        ))
        corr = merged["precip_mm"].corr(merged["siniestros"])
        fig.add_annotation(
            x=0.95, y=0.95, xref="paper", yref="paper",
            text=f"r = {corr:.2f}",
            showarrow=False, font=dict(size=14, color="#e74c3c"),
            bgcolor="rgba(255,255,255,0.8)", borderpad=4,
        )

    fig.update_layout(
        title="Correlación: Precipitación Mensual vs. Siniestros",
        xaxis_title="Precipitación mensual (mm)",
        yaxis_title="Cantidad de siniestros",
        height=400,
        showlegend=False,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

def render_clima_tab(datos):
    """Punto de entrada: renderiza la pestaña Clima y Riesgo."""

    st.markdown("""
    <div style="background:linear-gradient(135deg,#1a73e8 0%,#0d47a1 100%);
         padding:18px 24px;border-radius:10px;margin-bottom:18px;">
        <span style="color:#fff;font-size:22px;font-weight:700;">
        🌦️ Clima y Riesgo — Pronóstico Meteorológico SAC</span><br>
        <span style="color:#bbdefb;font-size:13px;">
        Pronóstico a 7 días por departamento · Datos de Open-Meteo (actualización cada hora)</span>
    </div>
    """, unsafe_allow_html=True)

    # Explicación de criterios
    with st.expander("ℹ️ ¿Cómo funciona? — Umbrales y fuente de datos", expanded=False):
        st.markdown("""
**Fuente:** [Open-Meteo API](https://open-meteo.com/) — pronóstico global gratuito, sin API key.
Se consultan **24 puntos** (centroide de cada departamento) con forecast diario a 7 días.

**Umbrales de riesgo agrícola:**

| Métrica | 🟢 Verde (Normal) | 🟡 Ámbar (Riesgo) | 🔴 Rojo (Extremo) |
|---------|-------------------|--------------------|--------------------|
| Precip. diaria | < 20 mm | 20–50 mm | > 50 mm |
| Precip. acumulada 7d | < 80 mm | 80–150 mm | > 150 mm |
| Temp. máxima | ≤ 32°C | 32–36°C | > 36°C |
| Temp. mínima | ≥ 10°C | 5–10°C | < 5°C (helada) |
| Viento máximo | < 40 km/h | 40–60 km/h | > 60 km/h |

**Cruce con calendario agrícola:** Si un departamento tiene cultivos en período de
siembra/cosecha con riesgos asociados (inundación, helada, etc.) y el pronóstico
coincide, el nivel de riesgo se escala automáticamente.

**Score (0–100):** Precipitación 40% + Temperatura 30% + Viento 15% + Calendario agrícola 15%.
        """)

    # ── Obtener datos ──
    with st.spinner("Consultando datos meteorológicos para 24 departamentos..."):
        forecast_data = _fetch_forecast_all()

    if not forecast_data or all(v is None for v in forecast_data.values()):
        st.error(
            "No se pudo conectar a la API meteorológica. "
            "Verifique su conexión a internet e intente nuevamente."
        )
        return

    available = sum(1 for v in forecast_data.values() if v is not None)
    if available < 24:
        st.warning(f"Se obtuvieron datos de {available}/24 departamentos. Algunos pueden no mostrarse.")

    # ── Calcular riesgos ──
    risks = {}
    for dept in DEPT_COORDS:
        risks[dept] = compute_department_risk(dept, forecast_data.get(dept))

    # ── KPIs ──
    _render_kpis(risks)

    # ── Mapa ──
    st.markdown("#### Mapa de Riesgo Climático")
    _render_risk_map(risks)

    # ── Forecast detallado por departamento ──
    st.markdown("#### Pronóstico 7 Días por Departamento")
    dept_list = sorted(DEPT_COORDS.keys())
    # Poner primero los de mayor riesgo
    dept_sorted = sorted(dept_list, key=lambda d: risks.get(d, {}).get("score", 0), reverse=True)
    selected_dept = st.selectbox(
        "Seleccione departamento",
        dept_sorted,
        format_func=lambda d: f"{d} — {'🔴' if risks[d]['nivel']=='rojo' else '🟡' if risks[d]['nivel']=='ambar' else '🟢'} {risks[d]['nivel'].upper()} ({risks[d]['score']}/100)",
        key="clima_dept_select",
    )
    _render_forecast_table(selected_dept, forecast_data.get(selected_dept))

    # ── Semáforo climático ──
    st.markdown("#### Semáforo Climático por Departamento")
    _render_semaforo_grid(risks)

    # ── Correlación histórica ──
    st.markdown("#### Correlación Histórica: Precipitación vs. Siniestros")
    with st.expander("Mostrar análisis de correlación", expanded=False):
        st.caption(
            "Cruza la precipitación mensual histórica (Open-Meteo) con la cantidad "
            "de siniestros registrados por departamento y mes."
        )
        try:
            df = datos.get("midagri")
            if df is not None and not df.empty:
                date_col = "FECHA_SINIESTRO" if "FECHA_SINIESTRO" in df.columns else "FECHA_AVISO"
                dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
                if not dates.empty:
                    start = dates.min().strftime("%Y-%m-%d")
                    end = (dates.max() - timedelta(days=5)).strftime("%Y-%m-%d")
                    with st.spinner("Obteniendo datos históricos de precipitación..."):
                        hist_data = _fetch_historical_precip(start, end)
                    _render_correlation(datos, hist_data)
                else:
                    st.info("No hay fechas válidas en los datos para la correlación.")
            else:
                st.info("Cargue datos de siniestros para ver la correlación.")
        except Exception as e:
            st.info(f"No se pudo generar la correlación histórica: {e}")
