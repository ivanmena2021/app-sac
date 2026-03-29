"""
clima_riesgo.py — Pronóstico meteorológico y análisis de riesgo climático SAC
===============================================================================
Consulta la API gratuita Open-Meteo (sin key) para obtener pronósticos a 7 días
a nivel distrital usando una estrategia Grid-Snap que reduce ~1,200 distritos
a ~80-120 puntos de consulta únicos.

Soporta drill-down: Departamento → Provincia → Distrito.
Fallback automático a nivel departamental si no hay datos distritales.
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

from gen_mapa_calor import DEPT_COORDS, _jitter_coords
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

# Spread (grados) por departamento — proporcional a su área geográfica
DEPT_SPREAD = {
    "LORETO": 2.5, "UCAYALI": 1.8, "MADRE DE DIOS": 1.5,
    "CUSCO": 1.2, "JUNIN": 1.0, "AREQUIPA": 1.3,
    "PUNO": 1.2, "ANCASH": 0.9, "SAN MARTIN": 1.0,
    "AMAZONAS": 1.0, "PIURA": 0.9, "CAJAMARCA": 0.8,
    "LA LIBERTAD": 0.9, "HUANUCO": 0.8, "PASCO": 0.7,
    "LIMA": 1.1, "AYACUCHO": 0.9, "HUANCAVELICA": 0.7,
    "APURIMAC": 0.6, "ICA": 0.8, "MOQUEGUA": 0.7,
    "TACNA": 0.6, "TUMBES": 0.4, "LAMBAYEQUE": 0.5,
}

GRID_RESOLUTION = 0.25  # grados (~28 km)

# Bounding box de Perú
PERU_LAT_MIN, PERU_LAT_MAX = -18.35, -0.04
PERU_LON_MIN, PERU_LON_MAX = -81.33, -68.65


# ═══════════════════════════════════════════════════════════════════
# COORDENADAS DISTRITALES (Grid-Snap)
# ═══════════════════════════════════════════════════════════════════

def _clamp(val, vmin, vmax):
    return max(vmin, min(vmax, val))


@st.cache_data(ttl=None, show_spinner=False)
def _build_district_coords(_df_hash: str, districts: tuple) -> dict:
    """Genera coordenadas aproximadas para cada distrito.

    Args:
        _df_hash: hash para cache invalidation
        districts: tuple de (DEPARTAMENTO, PROVINCIA, DISTRITO)

    Returns:
        dict {(dept, prov, dist): (lat, lon)}
    """
    coords = {}
    for dept, prov, dist in districts:
        base = DEPT_COORDS.get(dept)
        if not base:
            continue
        spread = DEPT_SPREAD.get(dept, 0.8)
        key_str = f"{dept}_{prov}_{dist}"
        lat, lon = _jitter_coords(key_str, base[0], base[1], spread=spread)
        lat = _clamp(lat, PERU_LAT_MIN, PERU_LAT_MAX)
        lon = _clamp(lon, PERU_LON_MIN, PERU_LON_MAX)
        coords[(dept, prov, dist)] = (round(lat, 4), round(lon, 4))
    return coords


def _snap_to_grid(lat, lon, resolution=GRID_RESOLUTION):
    """Redondea coordenadas a la cuadrícula más cercana."""
    return (round(round(lat / resolution) * resolution, 4),
            round(round(lon / resolution) * resolution, 4))


def _build_grid_mapping(district_coords):
    """Agrupa distritos por punto de cuadrícula.

    Returns:
        grid_points: {(grid_lat, grid_lon): [(dept, prov, dist), ...]}
        district_to_grid: {(dept, prov, dist): (grid_lat, grid_lon)}
    """
    grid_points = {}
    district_to_grid = {}
    for key, (lat, lon) in district_coords.items():
        grid_pt = _snap_to_grid(lat, lon)
        grid_points.setdefault(grid_pt, []).append(key)
        district_to_grid[key] = grid_pt
    return grid_points, district_to_grid


# ═══════════════════════════════════════════════════════════════════
# API LAYER
# ═══════════════════════════════════════════════════════════════════

def _api_get(url, timeout=10):
    """GET request usando urllib (stdlib, sin dependencias extra)."""
    req = urllib.request.Request(url, headers={"User-Agent": "SAC-App/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _fetch_single_forecast(lat, lon):
    """Fetch forecast para un punto. Retorna daily dict o None."""
    try:
        params = (
            f"?latitude={lat}&longitude={lon}"
            f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min,"
            f"windspeed_10m_max,weathercode"
            f"&timezone=America/Lima&forecast_days=7"
        )
        data = _api_get(OPEN_METEO_FORECAST + params)
        return data.get("daily", {})
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_forecast_grid(grid_points_tuple: tuple) -> dict:
    """Obtiene pronóstico 7 días para cada punto de cuadrícula.

    Args:
        grid_points_tuple: tuple de (lat, lon) — hashable para cache

    Returns:
        dict {(lat, lon): daily_dict o None}
    """
    results = {}
    for lat, lon in grid_points_tuple:
        results[(lat, lon)] = _fetch_single_forecast(lat, lon)
        time.sleep(0.05)
    return results


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_forecast_all():
    """Obtiene pronóstico 7 días para los 24 departamentos (path legacy)."""
    results = {}
    for dept, (lat, lon) in DEPT_COORDS.items():
        results[dept] = _fetch_single_forecast(lat, lon)
        time.sleep(0.05)
    return results


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_historical_precip_grid(grid_points_tuple: tuple,
                                   start_date: str, end_date: str) -> dict:
    """Obtiene precipitación histórica por punto de cuadrícula."""
    results = {}
    for lat, lon in grid_points_tuple:
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
                results[(lat, lon)] = df
            time.sleep(0.05)
        except Exception:
            results[(lat, lon)] = None
    return results


@st.cache_data(ttl=86400, show_spinner=False)
def _fetch_historical_precip_dept(start_date: str, end_date: str):
    """Obtiene precipitación histórica por departamento (path legacy)."""
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


def _map_forecasts_to_districts(grid_forecasts, district_to_grid):
    """Asigna forecast del grid point más cercano a cada distrito."""
    result = {}
    for dist_key, grid_pt in district_to_grid.items():
        result[dist_key] = grid_forecasts.get(grid_pt)
    return result


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
    return max(niveles, key=lambda n: order.get(n, 0))


def compute_department_risk(dept, forecast):
    """Calcula riesgo para una ubicación a partir de su forecast.
    `dept` se usa para el cruce con calendario agrícola."""
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

    T = RISK_THRESHOLDS
    nivel_lluvia_day = _classify(max_precip_day, T["precip_daily_amber"], T["precip_daily_red"])
    nivel_lluvia_7d = _classify(precip_7d, T["precip_7day_amber"], T["precip_7day_red"])
    nivel_lluvia = _max_nivel(nivel_lluvia_day, nivel_lluvia_7d)

    nivel_temp_high = _classify(max_temp, T["temp_high_amber"], T["temp_high_red"]) if max_temp else "verde"
    nivel_temp_low = _classify(min_temp, T["temp_low_amber"], T["temp_low_red"], invert=True) if min_temp else "verde"
    nivel_temp = _max_nivel(nivel_temp_high, nivel_temp_low)

    nivel_viento = _classify(max_wind, T["wind_amber"], T["wind_red"]) if max_wind else "verde"

    score_lluvia = _nivel_to_score(nivel_lluvia) * 0.40
    score_temp = _nivel_to_score(nivel_temp) * 0.30
    score_viento = _nivel_to_score(nivel_viento) * 0.15

    calendar_bonus = 0
    try:
        risk_crops = get_current_risk_crops(dept)
        crop_risks = set()
        for c in risk_crops:
            crop_risks.update(c.get("riesgos", []))
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


def _compute_district_risks(district_forecasts, district_coords):
    """Calcula riesgo para cada distrito. Hereda calendario del depto padre."""
    risks = {}
    for key in district_coords:
        dept = key[0]  # (dept, prov, dist)
        forecast = district_forecasts.get(key)
        risks[key] = compute_department_risk(dept, forecast)
    return risks


def _aggregate_to_level(district_risks, level="departamento"):
    """Agrega riesgos distritales a nivel depto o provincia.

    Para cada grupo: score = max, nivel = peor, métricas = max.
    """
    groups = {}
    for (dept, prov, dist), risk in district_risks.items():
        if level == "departamento":
            group_key = dept
        elif level == "provincia":
            group_key = (dept, prov)
        else:
            group_key = (dept, prov, dist)
        groups.setdefault(group_key, []).append(risk)

    aggregated = {}
    for key, risk_list in groups.items():
        valid = [r for r in risk_list if not r.get("sin_datos")]
        if not valid:
            aggregated[key] = risk_list[0]
            continue
        aggregated[key] = {
            "nivel": _max_nivel(*[r["nivel"] for r in valid]),
            "score": max(r["score"] for r in valid),
            "precip_7d": max(r["precip_7d"] for r in valid),
            "max_precip_day": max(r["max_precip_day"] for r in valid),
            "temp_max": max((r["temp_max"] for r in valid if r["temp_max"] is not None), default=None),
            "temp_min": min((r["temp_min"] for r in valid if r["temp_min"] is not None), default=None),
            "wind_max": max((r["wind_max"] for r in valid if r["wind_max"] is not None), default=None),
            "nivel_lluvia": _max_nivel(*[r["nivel_lluvia"] for r in valid]),
            "nivel_temp": _max_nivel(*[r["nivel_temp"] for r in valid]),
            "nivel_viento": _max_nivel(*[r["nivel_viento"] for r in valid]),
            "sin_datos": False,
        }
    return aggregated


# ═══════════════════════════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════════════════════════

def _risk_emoji(nivel):
    return {"verde": "🟢", "ambar": "🟡", "rojo": "🔴"}.get(nivel, "⚪")


def _render_kpis(risks, level_label="Deptos"):
    """KPI cards adaptativas al nivel geográfico."""
    rojos = sum(1 for r in risks.values() if r["nivel"] == "rojo")
    ambars = sum(1 for r in risks.values() if r["nivel"] == "ambar")
    valid = [r for r in risks.values() if not r.get("sin_datos")]
    avg_precip = np.mean([r["precip_7d"] for r in valid]) if valid else 0
    avg_score = np.mean([r["score"] for r in valid]) if valid else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{level_label} Alerta Roja", rojos,
              help=f"{level_label} con riesgo alto en los próximos 7 días")
    c2.metric(f"{level_label} Alerta Ámbar", ambars,
              help=f"{level_label} con riesgo moderado")
    c3.metric("Precip. Promedio 7d", f"{avg_precip:.0f} mm",
              help="Precipitación acumulada promedio")
    c4.metric("Score Riesgo Promedio", f"{avg_score:.0f}/100",
              help="0 = sin riesgo, 100 = riesgo extremo")


def _render_risk_map(risks, coords, view_level="departamento",
                     selected_dept=None, selected_prov=None):
    """Mapa de riesgo con zoom adaptativo por nivel."""
    names, lats, lons, mcolors, sizes, hovers = [], [], [], [], [], []

    for key, risk in risks.items():
        coord = coords.get(key)
        if not coord:
            continue

        # Determinar label según nivel
        if isinstance(key, tuple):
            if view_level == "distrito":
                label = key[2]  # distrito
            elif view_level == "provincia":
                label = key[1] if len(key) > 1 else str(key)
            else:
                label = key[0]
        else:
            label = str(key)

        names.append(label)
        lats.append(coord[0])
        lons.append(coord[1])
        mcolors.append(COLORS.get(risk["nivel"], "#ccc"))
        sizes.append(max(10, risk["score"] * 0.35 + 8))
        hover = (
            f"<b>{label}</b><br>"
            f"Riesgo: {risk['nivel'].upper()} ({risk['score']}/100)<br>"
            f"Precip 7d: {risk['precip_7d']} mm<br>"
            f"Temp: {risk['temp_min']}°C – {risk['temp_max']}°C<br>"
            f"Viento máx: {risk['wind_max']} km/h"
        )
        hovers.append(hover)

    if not lats:
        st.info("Sin datos geográficos para mostrar en el mapa.")
        return

    # Zoom adaptativo
    zoom_map = {"departamento": 4.3, "provincia": 6.0, "distrito": 7.5}
    zoom = zoom_map.get(view_level, 4.3)
    center_lat = np.mean(lats)
    center_lon = np.mean(lons)

    fig = go.Figure(go.Scattermapbox(
        lat=lats, lon=lons,
        mode="markers+text",
        marker=dict(size=sizes, color=mcolors, opacity=0.85),
        text=names,
        textposition="top center",
        textfont=dict(size=8 if view_level == "distrito" else 9, color="#333"),
        hovertext=hovers,
        hoverinfo="text",
    ))
    fig.update_layout(
        mapbox=dict(style="open-street-map",
                    center=dict(lat=center_lat, lon=center_lon), zoom=zoom),
        margin=dict(l=0, r=0, t=0, b=0),
        height=520,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_forecast_table(location_label, forecast):
    """Tabla de pronóstico 7 días para cualquier ubicación."""
    if not forecast or not forecast.get("time"):
        st.info(f"Sin datos de pronóstico para {location_label}.")
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

        emoji = _risk_emoji(nivel_gen)
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


def _render_semaforo_grid(risks, location_col="Departamento"):
    """Tabla semáforo climático genérica."""
    def _cell(nivel):
        bg = COLORS.get(nivel, "#eee")
        label = {"verde": "Verde", "ambar": "Ámbar", "rojo": "Rojo"}.get(nivel, "—")
        text_color = "#fff" if nivel in ("rojo", "verde") else "#333"
        return (f'<td style="background:{bg};color:{text_color};text-align:center;'
                f'padding:4px 8px;font-size:12px;font-weight:600;">{label}</td>')

    rows_html = []
    for key in sorted(risks.keys(), key=lambda k: str(k)):
        r = risks[key]
        # Extraer nombre legible
        if isinstance(key, tuple):
            name = key[-1]  # último elemento (distrito o provincia)
        else:
            name = str(key)

        if r.get("sin_datos"):
            cells = '<td colspan="4" style="text-align:center;color:#999;font-size:12px;">Sin datos</td>'
        else:
            cells = (
                _cell(r["nivel_lluvia"])
                + _cell(r["nivel_temp"])
                + _cell(r["nivel_viento"])
                + _cell(r["nivel"])
            )
        rows_html.append(
            f'<tr><td style="padding:4px 8px;font-size:12px;font-weight:500;">'
            f'{name}</td>{cells}</tr>'
        )

    header = (
        '<tr style="background:#2C5F2D;color:#fff;">'
        f'<th style="padding:6px 8px;text-align:left;">{location_col}</th>'
        '<th style="padding:6px 8px;text-align:center;">Lluvia</th>'
        '<th style="padding:6px 8px;text-align:center;">Temperatura</th>'
        '<th style="padding:6px 8px;text-align:center;">Viento</th>'
        '<th style="padding:6px 8px;text-align:center;">General</th>'
        '</tr>'
    )

    html = (
        '<div style="overflow-x:auto;max-height:500px;overflow-y:auto;">'
        '<table style="width:100%;border-collapse:collapse;border-radius:8px;overflow:hidden;'
        'box-shadow:0 1px 3px rgba(0,0,0,0.1);">'
        f'{header}{"".join(rows_html)}'
        '</table></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_correlation(datos, historical_grid, district_to_grid=None,
                         view_level="departamento"):
    """Scatter: precipitación mensual vs. siniestros."""
    df = datos.get("midagri")
    if df is None or df.empty:
        return

    if not historical_grid or all(v is None for v in historical_grid.values()):
        st.info("No se pudieron obtener datos históricos de precipitación para la correlación.")
        return

    date_col = "FECHA_SINIESTRO" if "FECHA_SINIESTRO" in df.columns else "FECHA_AVISO"
    if date_col not in df.columns:
        return

    # Determinar columna de agrupación
    if view_level == "distrito" and "DISTRITO" in df.columns and district_to_grid:
        group_col = "DISTRITO"
        geo_label = "distrito"
    else:
        group_col = "DEPARTAMENTO"
        geo_label = "departamento"

    df_sin = df[[date_col, "DEPARTAMENTO"]].copy()
    if group_col == "DISTRITO":
        df_sin["DISTRITO"] = df["DISTRITO"]
        df_sin["PROVINCIA"] = df["PROVINCIA"]
    df_sin = df_sin.dropna(subset=[date_col])
    df_sin["mes"] = pd.to_datetime(df_sin[date_col], errors="coerce").dt.to_period("M")
    df_sin = df_sin.dropna(subset=["mes"])

    sin_monthly = df_sin.groupby([group_col, "mes"]).size().reset_index(name="siniestros")
    sin_monthly["mes_str"] = sin_monthly["mes"].astype(str)

    # Combinar precipitación histórica
    precip_frames = []
    if view_level == "distrito" and district_to_grid:
        # Mapear cada distrito a su grid point y usar precip de ese grid
        for grid_pt, pdf in historical_grid.items():
            if pdf is not None and not pdf.empty:
                # Encontrar distritos que mapean a este grid point
                dists_for_grid = [k for k, g in district_to_grid.items() if g == grid_pt]
                for (dept, prov, dist) in dists_for_grid:
                    p = pdf.copy()
                    p["mes"] = p["fecha"].dt.to_period("M")
                    monthly = p.groupby("mes")["precip_mm"].sum().reset_index()
                    monthly[group_col] = dist
                    monthly["mes_str"] = monthly["mes"].astype(str)
                    precip_frames.append(monthly)
    else:
        for key, pdf in historical_grid.items():
            if pdf is not None and not pdf.empty:
                p = pdf.copy()
                p["mes"] = p["fecha"].dt.to_period("M")
                monthly = p.groupby("mes")["precip_mm"].sum().reset_index()
                # key es dept string o (lat, lon) tuple
                dept_name = key if isinstance(key, str) else None
                if dept_name:
                    monthly[group_col] = dept_name
                    monthly["mes_str"] = monthly["mes"].astype(str)
                    precip_frames.append(monthly)

    if not precip_frames:
        st.info("Sin datos de precipitación histórica suficientes.")
        return

    precip_all = pd.concat(precip_frames, ignore_index=True)
    merged = sin_monthly.merge(
        precip_all,
        on=[group_col, "mes_str"],
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
        text=merged[group_col] + " — " + merged["mes_str"],
        hoverinfo="text+x+y",
    ))

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

    title_suffix = f"por {geo_label.capitalize()}"
    fig.update_layout(
        title=f"Correlación: Precipitación Mensual vs. Siniestros ({title_suffix})",
        xaxis_title="Precipitación mensual (mm)",
        yaxis_title="Cantidad de siniestros",
        height=400,
        showlegend=False,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# DRILL-DOWN SELECTOR
# ═══════════════════════════════════════════════════════════════════

def _render_drill_down(district_risks, district_coords):
    """Selectores cascadados: Depto → Provincia → Distrito.

    Returns:
        (selected_dept, selected_prov, selected_dist, view_level,
         filtered_risks, filtered_coords)
    """
    # Extraer estructura jerárquica
    dept_set = sorted(set(k[0] for k in district_risks.keys()))
    dept_agg = _aggregate_to_level(district_risks, "departamento")

    # Ordenar por score desc
    dept_sorted = sorted(dept_set, key=lambda d: dept_agg.get(d, {}).get("score", 0), reverse=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        selected_dept = st.selectbox(
            "Departamento",
            dept_sorted,
            format_func=lambda d: (
                f"{d} — {_risk_emoji(dept_agg[d]['nivel'])} "
                f"{dept_agg[d]['score']}/100"
            ),
            key="clima_drill_dept",
        )

    # Filtrar provincias del departamento seleccionado
    prov_set = sorted(set(k[1] for k in district_risks.keys() if k[0] == selected_dept))
    prov_agg = {}
    for (d, p, di), r in district_risks.items():
        if d == selected_dept:
            prov_agg.setdefault((d, p), []).append(r)
    prov_risks = {}
    for (d, p), rlist in prov_agg.items():
        valid = [r for r in rlist if not r.get("sin_datos")]
        if valid:
            prov_risks[p] = {
                "nivel": _max_nivel(*[r["nivel"] for r in valid]),
                "score": max(r["score"] for r in valid),
            }
        else:
            prov_risks[p] = {"nivel": "verde", "score": 0}

    prov_sorted = sorted(prov_set, key=lambda p: prov_risks.get(p, {}).get("score", 0), reverse=True)

    with c2:
        prov_options = ["— Todas —"] + prov_sorted
        selected_prov_raw = st.selectbox(
            "Provincia",
            prov_options,
            format_func=lambda p: (
                p if p == "— Todas —"
                else f"{p} — {_risk_emoji(prov_risks[p]['nivel'])} {prov_risks[p]['score']}/100"
            ),
            key="clima_drill_prov",
        )
    selected_prov = None if selected_prov_raw == "— Todas —" else selected_prov_raw

    # Filtrar distritos si hay provincia seleccionada
    selected_dist = None
    if selected_prov:
        dist_set = sorted(set(
            k[2] for k in district_risks.keys()
            if k[0] == selected_dept and k[1] == selected_prov
        ))
        dist_risks_map = {}
        for (d, p, di), r in district_risks.items():
            if d == selected_dept and p == selected_prov:
                dist_risks_map[di] = r

        dist_sorted = sorted(dist_set, key=lambda di: dist_risks_map.get(di, {}).get("score", 0), reverse=True)

        with c3:
            dist_options = ["— Todos —"] + dist_sorted
            selected_dist_raw = st.selectbox(
                "Distrito",
                dist_options,
                format_func=lambda di: (
                    di if di == "— Todos —"
                    else f"{di} — {_risk_emoji(dist_risks_map[di]['nivel'])} {dist_risks_map[di]['score']}/100"
                ),
                key="clima_drill_dist",
            )
        selected_dist = None if selected_dist_raw == "— Todos —" else selected_dist_raw
    else:
        with c3:
            st.selectbox("Distrito", ["Seleccione provincia"], disabled=True,
                         key="clima_drill_dist_disabled")

    # Determinar nivel de vista y filtrar datos
    if selected_dist:
        view_level = "distrito"
        key = (selected_dept, selected_prov, selected_dist)
        filtered_risks = {key: district_risks[key]} if key in district_risks else {}
        filtered_coords = {key: district_coords[key]} if key in district_coords else {}
    elif selected_prov:
        view_level = "distrito"
        filtered_risks = {
            k: v for k, v in district_risks.items()
            if k[0] == selected_dept and k[1] == selected_prov
        }
        filtered_coords = {
            k: v for k, v in district_coords.items()
            if k[0] == selected_dept and k[1] == selected_prov
        }
    else:
        view_level = "provincia"
        # Mostrar provincias del departamento
        filtered_risks = {}
        filtered_coords = {}
        prov_risks_full = _aggregate_to_level(
            {k: v for k, v in district_risks.items() if k[0] == selected_dept},
            "provincia"
        )
        for (d, p), risk in prov_risks_full.items():
            # Buscar una coordenada representativa para la provincia
            for k, c in district_coords.items():
                if k[0] == d and k[1] == p:
                    filtered_risks[(d, p)] = risk
                    filtered_coords[(d, p)] = c
                    break

    return (selected_dept, selected_prov, selected_dist, view_level,
            filtered_risks, filtered_coords)


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
        Pronóstico a 7 días con granularidad distrital · Datos de Open-Meteo (actualización cada hora)</span>
    </div>
    """, unsafe_allow_html=True)

    # Explicación de criterios
    with st.expander("ℹ️ ¿Cómo funciona? — Umbrales, Grid-Snap y fuente de datos", expanded=False):
        st.markdown("""
**Fuente:** [Open-Meteo API](https://open-meteo.com/) — pronóstico global gratuito, sin API key.

**Estrategia Grid-Snap:** Los ~1,200 distritos se agrupan en una cuadrícula de **0.25°
(~28 km)**, reduciendo a ~80-120 puntos de consulta únicos. Cada distrito hereda el
pronóstico del punto de cuadrícula más cercano.

**Drill-down:** Departamento → Provincia → Distrito. Use los selectores para navegar.

**Umbrales de riesgo agrícola:**

| Métrica | 🟢 Verde (Normal) | 🟡 Ámbar (Riesgo) | 🔴 Rojo (Extremo) |
|---------|-------------------|--------------------|--------------------|
| Precip. diaria | < 20 mm | 20–50 mm | > 50 mm |
| Precip. acumulada 7d | < 80 mm | 80–150 mm | > 150 mm |
| Temp. máxima | ≤ 32°C | 32–36°C | > 36°C |
| Temp. mínima | ≥ 10°C | 5–10°C | < 5°C (helada) |
| Viento máximo | < 40 km/h | 40–60 km/h | > 60 km/h |

**Cruce con calendario agrícola:** Si un departamento tiene cultivos en período de
siembra/cosecha con riesgos asociados y el pronóstico coincide, el riesgo se escala.

**Score (0–100):** Precipitación 40% + Temperatura 30% + Viento 15% + Calendario 15%.
        """)

    # ── Detectar datos distritales ──
    df = datos.get("midagri")
    has_district = (
        df is not None and not df.empty
        and "DISTRITO" in df.columns
        and "PROVINCIA" in df.columns
    )

    if has_district:
        _render_district_flow(datos, df)
    else:
        _render_legacy_flow(datos)


def _render_district_flow(datos, df):
    """Flujo principal con granularidad distrital (Grid-Snap)."""

    # 1. Construir coordenadas distritales
    districts = tuple(
        df[["DEPARTAMENTO", "PROVINCIA", "DISTRITO"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    df_hash = str(len(districts))
    district_coords = _build_district_coords(df_hash, districts)

    if not district_coords:
        st.warning("No se pudieron generar coordenadas distritales.")
        _render_legacy_flow(datos)
        return

    # 2. Grid-snap
    grid_points, district_to_grid = _build_grid_mapping(district_coords)
    n_grid = len(grid_points)

    # 3. Fetch forecast
    with st.spinner(f"Consultando datos meteorológicos ({n_grid} puntos de cuadrícula)..."):
        grid_forecasts = _fetch_forecast_grid(tuple(sorted(grid_points.keys())))

    if not grid_forecasts or all(v is None for v in grid_forecasts.values()):
        st.error("No se pudo conectar a la API meteorológica. Verifique su conexión a internet.")
        return

    available = sum(1 for v in grid_forecasts.values() if v is not None)
    if available < n_grid:
        st.warning(f"Se obtuvieron datos de {available}/{n_grid} puntos. Algunos distritos pueden no mostrarse.")

    # 4. Mapear forecasts a distritos
    district_forecasts = _map_forecasts_to_districts(grid_forecasts, district_to_grid)

    # 5. Calcular riesgos
    district_risks = _compute_district_risks(district_forecasts, district_coords)

    # 6. Agregar a nivel departamental para KPIs nacionales
    dept_risks = _aggregate_to_level(district_risks, "departamento")

    # 7. Info de grid
    st.caption(
        f"📊 {len(district_coords):,} distritos → {n_grid} puntos de cuadrícula · "
        f"{available}/{n_grid} con datos"
    )

    # 8. KPIs nacionales (siempre a nivel depto)
    _render_kpis(dept_risks, "Deptos")

    # 9. Drill-down selector
    st.markdown("#### Navegación Geográfica")
    (selected_dept, selected_prov, selected_dist, view_level,
     filtered_risks, filtered_coords) = _render_drill_down(district_risks, district_coords)

    # 10. Mapa
    level_labels = {"departamento": "Departamento", "provincia": "Provincia", "distrito": "Distrito"}
    st.markdown(f"#### Mapa de Riesgo — Nivel {level_labels.get(view_level, view_level)}")
    _render_risk_map(filtered_risks, filtered_coords, view_level, selected_dept, selected_prov)

    # 11. Forecast detallado
    st.markdown("#### Pronóstico 7 Días")
    if selected_dist:
        key = (selected_dept, selected_prov, selected_dist)
        label = f"{selected_dist} ({selected_prov}, {selected_dept})"
        _render_forecast_table(label, district_forecasts.get(key))
    elif selected_prov:
        # Mostrar forecast del primer distrito de la provincia (representativo)
        first_key = next(
            (k for k in sorted(district_risks.keys())
             if k[0] == selected_dept and k[1] == selected_prov),
            None
        )
        if first_key:
            label = f"{selected_prov} ({selected_dept})"
            _render_forecast_table(label, district_forecasts.get(first_key))
    else:
        # Mostrar forecast representativo del departamento
        first_key = next(
            (k for k in sorted(district_risks.keys()) if k[0] == selected_dept),
            None
        )
        if first_key:
            _render_forecast_table(selected_dept, district_forecasts.get(first_key))

    # 12. Semáforo
    location_col = level_labels.get(view_level, "Ubicación")
    st.markdown(f"#### Semáforo Climático — {location_col}s")
    _render_semaforo_grid(filtered_risks, location_col)

    # 13. Correlación histórica
    st.markdown("#### Correlación Histórica: Precipitación vs. Siniestros")
    with st.expander("Mostrar análisis de correlación", expanded=False):
        st.caption(
            "Cruza la precipitación mensual histórica con la cantidad de siniestros "
            "registrados. Nivel: departamental (para mayor fiabilidad estadística)."
        )
        try:
            date_col = "FECHA_SINIESTRO" if "FECHA_SINIESTRO" in df.columns else "FECHA_AVISO"
            dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
            if not dates.empty:
                start = dates.min().strftime("%Y-%m-%d")
                end = (dates.max() - timedelta(days=5)).strftime("%Y-%m-%d")
                with st.spinner("Obteniendo datos históricos de precipitación..."):
                    hist_data = _fetch_historical_precip_dept(start, end)
                _render_correlation(datos, hist_data, district_to_grid, "departamento")
            else:
                st.info("No hay fechas válidas en los datos para la correlación.")
        except Exception as e:
            st.info(f"No se pudo generar la correlación histórica: {e}")


def _render_legacy_flow(datos):
    """Flujo legacy a nivel departamental (sin datos distritales)."""

    with st.spinner("Consultando datos meteorológicos para 24 departamentos..."):
        forecast_data = _fetch_forecast_all()

    if not forecast_data or all(v is None for v in forecast_data.values()):
        st.error("No se pudo conectar a la API meteorológica. Verifique su conexión a internet.")
        return

    available = sum(1 for v in forecast_data.values() if v is not None)
    if available < 24:
        st.warning(f"Se obtuvieron datos de {available}/24 departamentos.")

    risks = {}
    for dept in DEPT_COORDS:
        risks[dept] = compute_department_risk(dept, forecast_data.get(dept))

    _render_kpis(risks, "Deptos")

    st.markdown("#### Mapa de Riesgo Climático")
    # Adaptar risks y coords para la interfaz genérica del mapa
    coords_simple = {d: DEPT_COORDS[d] for d in risks if d in DEPT_COORDS}
    _render_risk_map(risks, coords_simple, "departamento")

    st.markdown("#### Pronóstico 7 Días por Departamento")
    dept_sorted = sorted(DEPT_COORDS.keys(),
                         key=lambda d: risks.get(d, {}).get("score", 0), reverse=True)
    selected_dept = st.selectbox(
        "Seleccione departamento",
        dept_sorted,
        format_func=lambda d: (
            f"{d} — {_risk_emoji(risks[d]['nivel'])} "
            f"{risks[d]['nivel'].upper()} ({risks[d]['score']}/100)"
        ),
        key="clima_dept_select_legacy",
    )
    _render_forecast_table(selected_dept, forecast_data.get(selected_dept))

    st.markdown("#### Semáforo Climático por Departamento")
    _render_semaforo_grid(risks, "Departamento")

    st.markdown("#### Correlación Histórica: Precipitación vs. Siniestros")
    with st.expander("Mostrar análisis de correlación", expanded=False):
        st.caption(
            "Cruza la precipitación mensual histórica con la cantidad de siniestros "
            "registrados por departamento y mes."
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
                        hist_data = _fetch_historical_precip_dept(start, end)
                    _render_correlation(datos, hist_data)
                else:
                    st.info("No hay fechas válidas para la correlación.")
            else:
                st.info("Cargue datos de siniestros para ver la correlación.")
        except Exception as e:
            st.info(f"No se pudo generar la correlación histórica: {e}")
