"""
gen_mapa_calor.py — Mapa de calor interactivo del SAC por departamento
======================================================================
Genera un mapa de burbujas geográfico del Perú con métricas SAC
coloreadas por intensidad, más una tabla ranking estilizada.

Usa plotly scatter_mapbox (OpenStreetMap) para el mapa interactivo.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go


# ═══════════════════════════════════════════════════════════════════
# CENTROIDES DE DEPARTAMENTOS DEL PERÚ (lat, lon aproximados)
# ═══════════════════════════════════════════════════════════════════

DEPT_COORDS = {
    "AMAZONAS":       (-6.23, -77.86),
    "ANCASH":         (-9.53, -77.53),
    "APURIMAC":       (-14.05, -72.88),
    "AREQUIPA":       (-15.52, -72.09),
    "AYACUCHO":       (-13.64, -73.98),
    "CAJAMARCA":      (-7.16, -78.51),
    "CUSCO":          (-13.53, -71.97),
    "HUANCAVELICA":   (-12.79, -75.02),
    "HUANUCO":        (-9.93, -76.24),
    "ICA":            (-14.07, -75.73),
    "JUNIN":          (-11.50, -75.00),
    "LA LIBERTAD":    (-7.77, -78.71),
    "LAMBAYEQUE":     (-6.70, -79.91),
    "LIMA":           (-11.76, -76.60),
    "LORETO":         (-4.65, -74.96),
    "MADRE DE DIOS":  (-12.59, -70.04),
    "MOQUEGUA":       (-17.19, -70.93),
    "PASCO":          (-10.40, -75.52),
    "PIURA":          (-5.18, -80.10),
    "PUNO":           (-14.84, -70.02),
    "SAN MARTIN":     (-7.18, -76.73),
    "TACNA":          (-17.62, -70.26),
    "TUMBES":         (-3.57, -80.44),
    "UCAYALI":        (-9.83, -73.09),
}


# ═══════════════════════════════════════════════════════════════════
# MÉTRICAS DISPONIBLES
# ═══════════════════════════════════════════════════════════════════

METRICAS = {
    "Avance de Desembolso (%)": {
        "col_color": "pct_desembolso",
        "format": ".1f",
        "suffix": "%",
        "color_scale": "RdYlGn",
        "description": "Porcentaje de indemnización reconocida que ya fue desembolsada",
    },
    "Avance de Evaluación (%)": {
        "col_color": "pct_evaluacion",
        "format": ".1f",
        "suffix": "%",
        "color_scale": "RdYlGn",
        "description": "Porcentaje de avisos evaluados (cerrados) respecto al total",
    },
    "Hectáreas Indemnizadas": {
        "col_color": "ha_indemnizadas",
        "format": ",.0f",
        "suffix": " ha",
        "color_scale": "YlOrRd",
        "description": "Superficie total indemnizada por departamento",
    },
    "Monto Indemnizado (S/)": {
        "col_color": "monto_indemnizado",
        "format": ",.0f",
        "suffix": "",
        "color_scale": "Blues",
        "description": "Valor total de indemnizaciones reconocidas",
    },
    "Avisos de Siniestro": {
        "col_color": "avisos",
        "format": ",",
        "suffix": "",
        "color_scale": "Purples",
        "description": "Cantidad total de avisos de siniestro reportados",
    },
    "Siniestralidad (%)": {
        "col_color": "siniestralidad",
        "format": ".1f",
        "suffix": "%",
        "color_scale": "RdYlGn_r",
        "description": "Indemnización / Prima Neta × 100",
    },
}


def _build_dept_metrics(datos):
    """
    Construye DataFrame con métricas por departamento para el mapa.
    """
    midagri = datos["midagri"]
    materia = datos["materia"]

    if "DEPARTAMENTO" not in midagri.columns:
        return pd.DataFrame()

    # Agregar por departamento desde midagri
    agg_dict = {"avisos": ("DEPARTAMENTO", "count")}
    if "SUP_INDEMNIZADA" in midagri.columns:
        agg_dict["ha_indemnizadas"] = ("SUP_INDEMNIZADA", "sum")
    if "INDEMNIZACION" in midagri.columns:
        agg_dict["monto_indemnizado"] = ("INDEMNIZACION", "sum")
    if "MONTO_DESEMBOLSADO" in midagri.columns:
        agg_dict["monto_desembolsado"] = ("MONTO_DESEMBOLSADO", "sum")
    if "N_PRODUCTORES" in midagri.columns:
        agg_dict["productores"] = ("N_PRODUCTORES", "sum")

    agg = midagri.groupby("DEPARTAMENTO").agg(**agg_dict).reset_index()

    # Asegurar que todas las columnas existen
    for c in ["ha_indemnizadas", "monto_indemnizado", "monto_desembolsado", "productores"]:
        if c not in agg.columns:
            agg[c] = 0

    # Avisos cerrados para % evaluación
    if "ESTADO_INSPECCION" in midagri.columns:
        cerrados = midagri[midagri["ESTADO_INSPECCION"].astype(str).str.upper() == "CERRADO"]
        cerrados_by_dept = cerrados.groupby("DEPARTAMENTO").size().reset_index(name="cerrados")
        agg = agg.merge(cerrados_by_dept, on="DEPARTAMENTO", how="left")
        agg["cerrados"] = agg["cerrados"].fillna(0)
    else:
        agg["cerrados"] = 0

    # Calcular porcentajes
    agg["pct_evaluacion"] = np.where(
        agg["avisos"] > 0,
        (agg["cerrados"] / agg["avisos"] * 100).round(1),
        0
    )
    agg["pct_desembolso"] = np.where(
        agg["monto_indemnizado"] > 0,
        (agg["monto_desembolsado"] / agg["monto_indemnizado"] * 100).round(1),
        0
    )

    # Siniestralidad
    if "PRIMA_NETA" in materia.columns and "DEPARTAMENTO" in materia.columns:
        primas = materia[["DEPARTAMENTO", "PRIMA_NETA"]].copy()
        primas = primas.dropna(subset=["DEPARTAMENTO"])
        agg = agg.merge(primas, on="DEPARTAMENTO", how="left")
        agg["PRIMA_NETA"] = agg["PRIMA_NETA"].fillna(0)
        agg["siniestralidad"] = np.where(
            agg["PRIMA_NETA"] > 0,
            (agg["monto_indemnizado"] / agg["PRIMA_NETA"] * 100).round(1),
            0
        )
    else:
        agg["siniestralidad"] = 0

    # Empresa aseguradora
    if "EMPRESA_ASEGURADORA" in materia.columns and "DEPARTAMENTO" in materia.columns:
        emp = materia[["DEPARTAMENTO", "EMPRESA_ASEGURADORA"]].dropna()
        emp = emp.drop_duplicates(subset=["DEPARTAMENTO"])
        agg = agg.merge(emp, on="DEPARTAMENTO", how="left")
        agg["EMPRESA_ASEGURADORA"] = agg["EMPRESA_ASEGURADORA"].fillna("N/D")
    else:
        agg["EMPRESA_ASEGURADORA"] = "N/D"

    # Agregar coordenadas
    agg["lat"] = agg["DEPARTAMENTO"].map(lambda d: DEPT_COORDS.get(d, (0, 0))[0])
    agg["lon"] = agg["DEPARTAMENTO"].map(lambda d: DEPT_COORDS.get(d, (0, 0))[1])

    # Nombre bonito
    agg["nombre"] = agg["DEPARTAMENTO"].str.title()

    return agg


def generate_map(datos, metrica_key="Avance de Desembolso (%)"):
    """
    Genera un mapa interactivo de burbujas del Perú usando scatter_mapbox
    con tiles OpenStreetMap (no requiere token Mapbox).
    """
    df = _build_dept_metrics(datos)
    if len(df) == 0:
        return go.Figure()

    meta = METRICAS[metrica_key]
    col = meta["col_color"]

    # Tamaño de burbujas proporcional al valor (normalizado)
    max_val = df[col].max()
    min_val = df[col].min()
    range_val = max_val - min_val if max_val != min_val else 1

    # Tamaño: mínimo 15, máximo 50
    df["_size"] = 15 + (df[col] - min_val) / range_val * 35

    # Hover text enriquecido
    def _hover(r):
        try:
            val_str = f"{r[col]:{meta['format']}}{meta['suffix']}"
        except (ValueError, TypeError):
            val_str = str(r[col])
        return (
            f"<b>{r['nombre']}</b><br>"
            f"<b>{metrica_key}:</b> {val_str}<br>"
            f"Avisos: {int(r['avisos']):,}<br>"
            f"Indemnización: S/ {r['monto_indemnizado']:,.0f}<br>"
            f"Desembolso: S/ {r['monto_desembolsado']:,.0f}<br>"
            f"Ha indemnizadas: {r['ha_indemnizadas']:,.0f}<br>"
            f"Productores: {int(r['productores']):,}<br>"
            f"Empresa: {r['EMPRESA_ASEGURADORA']}"
        )

    df["_hover"] = df.apply(_hover, axis=1)

    fig = go.Figure()

    # Burbujas del mapa
    fig.add_trace(go.Scattermapbox(
        lat=df["lat"],
        lon=df["lon"],
        text=df["_hover"],
        hoverinfo="text",
        marker=dict(
            size=df["_size"],
            color=df[col],
            colorscale=meta["color_scale"],
            colorbar=dict(
                title=dict(
                    text=metrica_key,
                    font=dict(size=11, color="#334155"),
                ),
                thickness=14,
                len=0.6,
                tickfont=dict(size=10, color="#64748b"),
                bgcolor="rgba(255,255,255,0.90)",
                borderwidth=0,
                x=1.02,
            ),
            opacity=0.82,
            sizemode="diameter",
        ),
        mode="markers+text",
        textfont=dict(size=8, color="#1e293b", family="Arial"),
        textposition="top center",
    ))

    # Etiquetas de departamento
    fig.add_trace(go.Scattermapbox(
        lat=df["lat"] + 0.25,
        lon=df["lon"],
        text=df["nombre"],
        mode="text",
        textfont=dict(size=8, color="#334155", family="Arial"),
        hoverinfo="skip",
        showlegend=False,
    ))

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=-9.5, lon=-75.5),
            zoom=4.3,
        ),
        margin=dict(l=0, r=0, t=35, b=0),
        height=620,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, Arial, sans-serif"),
        showlegend=False,
        title=dict(
            text=f"Mapa SAC — {metrica_key}",
            font=dict(size=14, color="#0c2340", family="Segoe UI, Arial"),
            x=0.5,
            xanchor="center",
        ),
    )

    return fig


def get_ranking_table(datos, metrica_key="Avance de Desembolso (%)"):
    """
    Genera DataFrame con ranking de departamentos para la métrica seleccionada.
    Evita columnas duplicadas seleccionando dinámicamente.
    """
    df = _build_dept_metrics(datos)
    if len(df) == 0:
        return pd.DataFrame()

    meta = METRICAS[metrica_key]
    col = meta["col_color"]

    ranking = df.sort_values(col, ascending=False).reset_index(drop=True)
    ranking.index = ranking.index + 1  # 1-based ranking

    # Construir columnas dinámicamente para evitar duplicados
    # Siempre: Departamento + métrica seleccionada + columnas complementarias
    columns_map = {}  # {nombre_original: nombre_display}
    columns_map["nombre"] = "Departamento"
    columns_map[col] = metrica_key

    # Agregar columnas complementarias solo si NO son la métrica actual
    extras = {
        "avisos": "Avisos",
        "monto_indemnizado": "Indemnización (S/)",
        "monto_desembolsado": "Desembolso (S/)",
        "ha_indemnizadas": "Ha Indemn.",
        "pct_desembolso": "% Desemb.",
    }
    for orig, display in extras.items():
        if orig != col and orig in ranking.columns:
            columns_map[orig] = display

    # Seleccionar y renombrar
    cols_to_select = list(columns_map.keys())
    result = ranking[cols_to_select].copy()
    result.columns = [columns_map[c] for c in cols_to_select]

    return result


def get_summary_cards(datos):
    """
    Genera datos resumidos para tarjetas de contexto del mapa.
    """
    df = _build_dept_metrics(datos)
    if len(df) == 0:
        return {}

    df_con_avisos = df[df["avisos"] > 0]
    if len(df_con_avisos) == 0:
        return {}

    return {
        "top_avisos": df.sort_values("avisos", ascending=False).iloc[0]["nombre"],
        "top_avisos_n": int(df["avisos"].max()),
        "top_indemn": df.sort_values("monto_indemnizado", ascending=False).iloc[0]["nombre"],
        "top_indemn_val": df["monto_indemnizado"].max(),
        "top_desemb_pct": df_con_avisos.sort_values("pct_desembolso", ascending=False).iloc[0]["nombre"],
        "top_desemb_pct_val": df_con_avisos["pct_desembolso"].max(),
        "min_desemb_pct": df_con_avisos.sort_values("pct_desembolso").iloc[0]["nombre"],
        "min_desemb_pct_val": df_con_avisos["pct_desembolso"].min(),
        "total_deptos": len(df),
        "deptos_con_avisos": len(df_con_avisos),
    }
