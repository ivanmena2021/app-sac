"""
gen_mapa_calor.py — Mapa de calor interactivo del SAC por departamento
======================================================================
Genera un mapa de burbujas geográfico (scatter_geo) del Perú con métricas
SAC coloreadas por intensidad, más una tabla ranking estilizada.

Usa plotly para el mapa interactivo (compatible con st.plotly_chart).
"""

import pandas as pd
import numpy as np
import plotly.express as px
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
        "color_scale": "RdYlGn",     # rojo → amarillo → verde
        "reverse": False,
        "description": "Porcentaje de indemnización reconocida que ya fue desembolsada",
    },
    "Avance de Evaluación (%)": {
        "col_color": "pct_evaluacion",
        "format": ".1f",
        "suffix": "%",
        "color_scale": "RdYlGn",
        "reverse": False,
        "description": "Porcentaje de avisos evaluados (cerrados) respecto al total",
    },
    "Hectáreas Indemnizadas": {
        "col_color": "ha_indemnizadas",
        "format": ",.0f",
        "suffix": " ha",
        "color_scale": "YlOrRd",     # amarillo → naranja → rojo
        "reverse": False,
        "description": "Superficie total indemnizada por departamento",
    },
    "Monto Indemnizado (S/)": {
        "col_color": "monto_indemnizado",
        "format": ",.0f",
        "suffix": "",
        "color_scale": "Blues",
        "reverse": False,
        "description": "Valor total de indemnizaciones reconocidas",
    },
    "Avisos de Siniestro": {
        "col_color": "avisos",
        "format": ",",
        "suffix": "",
        "color_scale": "Purples",
        "reverse": False,
        "description": "Cantidad total de avisos de siniestro reportados",
    },
    "Siniestralidad (%)": {
        "col_color": "siniestralidad",
        "format": ".1f",
        "suffix": "%",
        "color_scale": "RdYlGn_r",   # verde → amarillo → rojo
        "reverse": False,
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
    agg = midagri.groupby("DEPARTAMENTO").agg(
        avisos=("DEPARTAMENTO", "count"),
        ha_indemnizadas=("SUP_INDEMNIZADA", "sum") if "SUP_INDEMNIZADA" in midagri.columns else ("DEPARTAMENTO", "count"),
        monto_indemnizado=("INDEMNIZACION", "sum") if "INDEMNIZACION" in midagri.columns else ("DEPARTAMENTO", "count"),
        monto_desembolsado=("MONTO_DESEMBOLSADO", "sum") if "MONTO_DESEMBOLSADO" in midagri.columns else ("DEPARTAMENTO", "count"),
        productores=("N_PRODUCTORES", "sum") if "N_PRODUCTORES" in midagri.columns else ("DEPARTAMENTO", "count"),
    ).reset_index()

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

    # Siniestralidad (necesita prima neta del materia asegurada)
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
    Genera un mapa interactivo de burbujas del Perú con la métrica seleccionada.

    Returns:
        plotly.graph_objects.Figure
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

    # Tamaño: mínimo 12, máximo 45
    df["_size"] = 12 + (df[col] - min_val) / range_val * 33

    # Hover text enriquecido
    df["_hover"] = df.apply(lambda r: (
        f"<b>{r['nombre']}</b><br>"
        f"<b>{metrica_key}:</b> {r[col]:{meta['format']}}{meta['suffix']}<br>"
        f"Avisos: {int(r['avisos']):,}<br>"
        f"Indemnización: S/ {r['monto_indemnizado']:,.0f}<br>"
        f"Desembolso: S/ {r['monto_desembolsado']:,.0f}<br>"
        f"Ha indemnizadas: {r['ha_indemnizadas']:,.0f}<br>"
        f"Productores: {int(r['productores']):,}<br>"
        f"Empresa: {r['EMPRESA_ASEGURADORA']}"
    ), axis=1)

    fig = go.Figure()

    fig.add_trace(go.Scattergeo(
        lat=df["lat"],
        lon=df["lon"],
        text=df["_hover"],
        hoverinfo="text",
        marker=dict(
            size=df["_size"],
            color=df[col],
            colorscale=meta["color_scale"],
            reversescale=meta["reverse"],
            colorbar=dict(
                title=dict(
                    text=metrica_key,
                    font=dict(size=11, color="#334155"),
                ),
                thickness=14,
                len=0.6,
                tickfont=dict(size=10, color="#64748b"),
                bgcolor="rgba(255,255,255,0.85)",
                borderwidth=0,
                x=1.02,
            ),
            line=dict(width=1.2, color="rgba(255,255,255,0.8)"),
            opacity=0.88,
            sizemode="diameter",
        ),
        mode="markers+text",
        textfont=dict(size=7.5, color="#1e293b", family="Arial"),
        textposition="top center",
    ))

    # Etiquetas de departamento (texto pequeño)
    fig.add_trace(go.Scattergeo(
        lat=df["lat"] + 0.15,
        lon=df["lon"],
        text=df["nombre"],
        mode="text",
        textfont=dict(size=7, color="#475569", family="Arial"),
        hoverinfo="skip",
        showlegend=False,
    ))

    fig.update_geos(
        visible=True,
        resolution=50,
        scope="south america",
        center=dict(lat=-9.5, lon=-75.5),
        projection_scale=4.8,
        showland=True,
        landcolor="#f1f5f9",
        showocean=True,
        oceancolor="#e0f2fe",
        showcountries=True,
        countrycolor="#cbd5e1",
        countrywidth=0.8,
        showcoastlines=True,
        coastlinecolor="#94a3b8",
        coastlinewidth=0.6,
        showlakes=True,
        lakecolor="#bae6fd",
        showrivers=True,
        rivercolor="#bae6fd",
        riverwidth=0.5,
        showframe=False,
        bgcolor="rgba(0,0,0,0)",
        lonaxis=dict(range=[-82, -68]),
        lataxis=dict(range=[-18.5, -0.5]),
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=30, b=0),
        height=600,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
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
    """
    df = _build_dept_metrics(datos)
    if len(df) == 0:
        return pd.DataFrame()

    meta = METRICAS[metrica_key]
    col = meta["col_color"]

    ranking = df.sort_values(col, ascending=False).reset_index(drop=True)
    ranking.index = ranking.index + 1  # 1-based ranking

    # Seleccionar columnas relevantes
    result = ranking[["nombre", "avisos", col, "monto_indemnizado", "monto_desembolsado", "ha_indemnizadas"]].copy()
    result = result.rename(columns={
        "nombre": "Departamento",
        "avisos": "Avisos",
        col: metrica_key,
        "monto_indemnizado": "Indemnización (S/)",
        "monto_desembolsado": "Desembolso (S/)",
        "ha_indemnizadas": "Ha Indemn.",
    })

    return result


def get_summary_cards(datos):
    """
    Genera datos resumidos para tarjetas de contexto del mapa.
    """
    df = _build_dept_metrics(datos)
    if len(df) == 0:
        return {}

    return {
        "top_avisos": df.sort_values("avisos", ascending=False).iloc[0]["nombre"],
        "top_avisos_n": int(df["avisos"].max()),
        "top_indemn": df.sort_values("monto_indemnizado", ascending=False).iloc[0]["nombre"],
        "top_indemn_val": df["monto_indemnizado"].max(),
        "top_desemb_pct": df.sort_values("pct_desembolso", ascending=False).iloc[0]["nombre"],
        "top_desemb_pct_val": df["pct_desembolso"].max(),
        "min_desemb_pct": df[df["avisos"] > 0].sort_values("pct_desembolso").iloc[0]["nombre"],
        "min_desemb_pct_val": df[df["avisos"] > 0]["pct_desembolso"].min(),
        "total_deptos": len(df),
        "deptos_con_avisos": len(df[df["avisos"] > 0]),
    }
