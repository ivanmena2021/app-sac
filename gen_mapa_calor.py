"""
gen_mapa_calor.py — Mapa de calor interactivo del SAC
=====================================================
Genera mapas de burbujas geográficos del Perú a nivel departamental,
provincial y distrital, con métricas SAC coloreadas por intensidad.

Usa plotly scatter_mapbox (OpenStreetMap) para el mapa interactivo.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go


# ═══════════════════════════════════════════════════════════════════
# CENTROIDES DE DEPARTAMENTOS (para fallback cuando no hay coords)
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
# NIVELES GEOGRÁFICOS
# ═══════════════════════════════════════════════════════════════════

NIVELES = {
    "Departamental": {
        "group_col": "DEPARTAMENTO",
        "label": "Departamento",
        "zoom": 4.3,
        "has_siniestralidad": True,
    },
    "Provincial": {
        "group_col": "PROVINCIA",
        "label": "Provincia",
        "zoom": 5.5,
        "has_siniestralidad": False,
    },
    "Distrital": {
        "group_col": "DISTRITO",
        "label": "Distrito",
        "zoom": 6.0,
        "has_siniestralidad": False,
    },
}


# ═══════════════════════════════════════════════════════════════════
# MÉTRICAS DISPONIBLES
# ═══════════════════════════════════════════════════════════════════

METRICAS_BASE = {
    "Avance de Desembolso (%)": {
        "col_color": "pct_desembolso",
        "format": ".1f",
        "suffix": "%",
        "color_scale": "RdYlGn",
        "description": "Porcentaje de indemnización reconocida que ya fue desembolsada",
        "only_dept": False,
    },
    "Avance de Evaluación (%)": {
        "col_color": "pct_evaluacion",
        "format": ".1f",
        "suffix": "%",
        "color_scale": "RdYlGn",
        "description": "Porcentaje de avisos evaluados (cerrados) respecto al total",
        "only_dept": False,
    },
    "Hectáreas Indemnizadas": {
        "col_color": "ha_indemnizadas",
        "format": ",.0f",
        "suffix": " ha",
        "color_scale": "YlOrRd",
        "description": "Superficie total indemnizada",
        "only_dept": False,
    },
    "Monto Indemnizado (S/)": {
        "col_color": "monto_indemnizado",
        "format": ",.0f",
        "suffix": "",
        "color_scale": "Blues",
        "description": "Valor total de indemnizaciones reconocidas",
        "only_dept": False,
    },
    "Avisos de Siniestro": {
        "col_color": "avisos",
        "format": ",",
        "suffix": "",
        "color_scale": "Purples",
        "description": "Cantidad total de avisos de siniestro reportados",
        "only_dept": False,
    },
    "Siniestralidad (%)": {
        "col_color": "siniestralidad",
        "format": ".1f",
        "suffix": "%",
        "color_scale": "RdYlGn_r",
        "description": "Indemnización / Prima Neta × 100 (solo nivel departamental)",
        "only_dept": True,
    },
}

# Alias para compatibilidad (se filtra dinámicamente según nivel)
METRICAS = METRICAS_BASE


def get_metricas_for_nivel(nivel_key):
    """Retorna las métricas disponibles para un nivel geográfico."""
    nivel = NIVELES[nivel_key]
    if nivel["has_siniestralidad"]:
        return METRICAS_BASE
    return {k: v for k, v in METRICAS_BASE.items() if not v.get("only_dept")}


# ═══════════════════════════════════════════════════════════════════
# COORDENADAS APROXIMADAS POR PROVINCIA/DISTRITO
# ═══════════════════════════════════════════════════════════════════

# Para provincias y distritos generamos coordenadas a partir del
# centroide del departamento + un pequeño jitter determinístico.
# Esto evita que todos los puntos del mismo departamento se apilen.

def _jitter_coords(name_str, base_lat, base_lon, spread=0.35):
    """Genera coordenadas con dispersión determinística basada en el nombre."""
    h = hash(name_str) % 10000
    dlat = (h % 100 - 50) / 50.0 * spread
    dlon = ((h // 100) % 100 - 50) / 50.0 * spread
    return base_lat + dlat, base_lon + dlon


# ═══════════════════════════════════════════════════════════════════
# CONSTRUCTOR DE MÉTRICAS GENÉRICO
# ═══════════════════════════════════════════════════════════════════

def _build_metrics(datos, nivel_key="Departamental", depto_filter=None):
    """
    Construye DataFrame con métricas agregadas al nivel geográfico indicado.

    Args:
        datos: dict de process_dynamic_data()
        nivel_key: "Departamental" | "Provincial" | "Distrital"
        depto_filter: lista de departamentos para filtrar (Provincial/Distrital)
    """
    midagri = datos["midagri"]
    materia = datos["materia"]
    nivel = NIVELES[nivel_key]
    group_col = nivel["group_col"]

    if group_col not in midagri.columns:
        return pd.DataFrame()

    df = midagri.copy()

    # Filtrar por departamento si se indica
    if depto_filter and "DEPARTAMENTO" in df.columns:
        df = df[df["DEPARTAMENTO"].isin(depto_filter)]

    # Limpiar valores nulos del grupo
    df = df[df[group_col].notna()]
    df[group_col] = df[group_col].astype(str).str.strip().str.upper()
    df = df[~df[group_col].isin(["NAN", "", "NONE", "-"])]

    if len(df) == 0:
        return pd.DataFrame()

    # Agregar métricas
    agg_dict = {"avisos": (group_col, "count")}
    if "SUP_INDEMNIZADA" in df.columns:
        agg_dict["ha_indemnizadas"] = ("SUP_INDEMNIZADA", "sum")
    if "INDEMNIZACION" in df.columns:
        agg_dict["monto_indemnizado"] = ("INDEMNIZACION", "sum")
    if "MONTO_DESEMBOLSADO" in df.columns:
        agg_dict["monto_desembolsado"] = ("MONTO_DESEMBOLSADO", "sum")
    if "N_PRODUCTORES" in df.columns:
        agg_dict["productores"] = ("N_PRODUCTORES", "sum")

    # Para provincial/distrital, incluir departamento como contexto
    if nivel_key != "Departamental" and "DEPARTAMENTO" in df.columns:
        group_cols = ["DEPARTAMENTO", group_col]
    else:
        group_cols = [group_col]

    agg = df.groupby(group_cols).agg(**agg_dict).reset_index()

    # Asegurar columnas existen
    for c in ["ha_indemnizadas", "monto_indemnizado", "monto_desembolsado", "productores"]:
        if c not in agg.columns:
            agg[c] = 0

    # Avisos cerrados
    if "ESTADO_INSPECCION" in df.columns:
        cerrados = df[df["ESTADO_INSPECCION"].astype(str).str.upper() == "CERRADO"]
        cerrados_agg = cerrados.groupby(group_cols).size().reset_index(name="cerrados")
        agg = agg.merge(cerrados_agg, on=group_cols, how="left")
        agg["cerrados"] = agg["cerrados"].fillna(0)
    else:
        agg["cerrados"] = 0

    # Porcentajes
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

    # Siniestralidad solo para departamental
    if nivel["has_siniestralidad"]:
        if "PRIMA_NETA" in materia.columns and "DEPARTAMENTO" in materia.columns:
            primas = materia[["DEPARTAMENTO", "PRIMA_NETA"]].copy().dropna(subset=["DEPARTAMENTO"])
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
            emp = materia[["DEPARTAMENTO", "EMPRESA_ASEGURADORA"]].dropna().drop_duplicates(subset=["DEPARTAMENTO"])
            agg = agg.merge(emp, on="DEPARTAMENTO", how="left")
            agg["EMPRESA_ASEGURADORA"] = agg["EMPRESA_ASEGURADORA"].fillna("N/D")
        else:
            agg["EMPRESA_ASEGURADORA"] = "N/D"
    else:
        agg["siniestralidad"] = 0
        agg["EMPRESA_ASEGURADORA"] = "N/D"

    # ─── Coordenadas ───
    if nivel_key == "Departamental":
        agg["lat"] = agg["DEPARTAMENTO"].map(lambda d: DEPT_COORDS.get(d, (-10, -75))[0])
        agg["lon"] = agg["DEPARTAMENTO"].map(lambda d: DEPT_COORDS.get(d, (-10, -75))[1])
        agg["nombre"] = agg["DEPARTAMENTO"].str.title()
    else:
        # Provincial / Distrital: jitter desde centroide del departamento
        lats, lons, nombres = [], [], []
        for _, row in agg.iterrows():
            depto = row.get("DEPARTAMENTO", "LIMA")
            base_lat, base_lon = DEPT_COORDS.get(depto, (-10, -75))
            entity_name = str(row[group_col])
            jlat, jlon = _jitter_coords(entity_name, base_lat, base_lon,
                                         spread=0.30 if nivel_key == "Provincial" else 0.45)
            lats.append(jlat)
            lons.append(jlon)
            nombres.append(entity_name.title())
        agg["lat"] = lats
        agg["lon"] = lons
        agg["nombre"] = nombres

    return agg


# ═══════════════════════════════════════════════════════════════════
# GENERADOR DE MAPA
# ═══════════════════════════════════════════════════════════════════

def generate_map(datos, metrica_key="Avance de Desembolso (%)",
                 nivel_key="Departamental", depto_filter=None):
    """
    Genera un mapa interactivo de burbujas del Perú usando scatter_mapbox.
    """
    df = _build_metrics(datos, nivel_key, depto_filter)
    if len(df) == 0:
        return go.Figure()

    nivel = NIVELES[nivel_key]
    metricas_nivel = get_metricas_for_nivel(nivel_key)

    # Si la métrica no está disponible para este nivel, usar la primera
    if metrica_key not in metricas_nivel:
        metrica_key = list(metricas_nivel.keys())[0]

    meta = metricas_nivel[metrica_key]
    col = meta["col_color"]

    # Tamaño de burbujas
    max_val = df[col].max()
    min_val = df[col].min()
    range_val = max_val - min_val if max_val != min_val else 1

    # Ajustar tamaños según nivel (más puntos → burbujas más pequeñas)
    if nivel_key == "Departamental":
        size_min, size_max = 15, 45
    elif nivel_key == "Provincial":
        size_min, size_max = 8, 30
    else:
        size_min, size_max = 5, 22

    df["_size"] = size_min + (df[col] - min_val) / range_val * (size_max - size_min)

    # Hover text
    group_col = nivel["group_col"]

    def _hover(r):
        try:
            val_str = f"{r[col]:{meta['format']}}{meta['suffix']}"
        except (ValueError, TypeError):
            val_str = str(r[col])
        parts = [
            f"<b>{r['nombre']}</b>",
        ]
        # Agregar departamento como contexto si no es nivel departamental
        if nivel_key != "Departamental" and "DEPARTAMENTO" in r.index:
            parts.append(f"Dpto: {str(r['DEPARTAMENTO']).title()}")
        parts.append(f"<b>{metrica_key}:</b> {val_str}")
        parts.append(f"Avisos: {int(r['avisos']):,}")
        parts.append(f"Indemnización: S/ {r['monto_indemnizado']:,.0f}")
        parts.append(f"Desembolso: S/ {r['monto_desembolsado']:,.0f}")
        parts.append(f"Ha indemnizadas: {r['ha_indemnizadas']:,.0f}")
        parts.append(f"Productores: {int(r['productores']):,}")
        if nivel_key == "Departamental":
            parts.append(f"Empresa: {r.get('EMPRESA_ASEGURADORA', 'N/D')}")
        return "<br>".join(parts)

    df["_hover"] = df.apply(_hover, axis=1)

    # Calcular centro del mapa
    if depto_filter and len(depto_filter) == 1:
        # Centrar en el departamento seleccionado
        d = depto_filter[0]
        center_lat, center_lon = DEPT_COORDS.get(d, (-9.5, -75.5))
        zoom = nivel["zoom"] + 1.5
    else:
        center_lat, center_lon = -9.5, -75.5
        zoom = nivel["zoom"]

    fig = go.Figure()

    # Burbujas
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
                title=dict(text=metrica_key, font=dict(size=11, color="#334155")),
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
        mode="markers",
    ))

    # Etiquetas solo para departamental (provincial/distrital son muchos)
    if nivel_key == "Departamental":
        fig.add_trace(go.Scattermapbox(
            lat=df["lat"] + 0.25,
            lon=df["lon"],
            text=df["nombre"],
            mode="text",
            textfont=dict(size=8, color="#334155", family="Arial"),
            hoverinfo="skip",
            showlegend=False,
        ))

    nivel_label = nivel["label"]
    n_items = len(df)
    titulo = f"Mapa SAC — {metrica_key} (por {nivel_label}, {n_items} unidades)"

    fig.update_layout(
        mapbox=dict(
            style="open-street-map",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom,
        ),
        margin=dict(l=0, r=0, t=35, b=0),
        height=620,
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, Arial, sans-serif"),
        showlegend=False,
        title=dict(
            text=titulo,
            font=dict(size=13, color="#0c2340", family="Segoe UI, Arial"),
            x=0.5, xanchor="center",
        ),
    )

    return fig


# ═══════════════════════════════════════════════════════════════════
# RANKING TABLE
# ═══════════════════════════════════════════════════════════════════

def get_ranking_table(datos, metrica_key="Avance de Desembolso (%)",
                      nivel_key="Departamental", depto_filter=None, top_n=50):
    """
    Genera DataFrame con ranking para la métrica y nivel seleccionados.
    """
    df = _build_metrics(datos, nivel_key, depto_filter)
    if len(df) == 0:
        return pd.DataFrame()

    nivel = NIVELES[nivel_key]
    metricas_nivel = get_metricas_for_nivel(nivel_key)
    if metrica_key not in metricas_nivel:
        metrica_key = list(metricas_nivel.keys())[0]

    meta = metricas_nivel[metrica_key]
    col = meta["col_color"]

    ranking = df.sort_values(col, ascending=False).head(top_n).reset_index(drop=True)
    ranking.index = ranking.index + 1

    # Construir columnas dinámicamente
    columns_map = {}
    columns_map["nombre"] = nivel["label"]

    # Si no es departamental, agregar departamento como contexto
    if nivel_key != "Departamental" and "DEPARTAMENTO" in ranking.columns:
        columns_map["DEPARTAMENTO"] = "Departamento"

    columns_map[col] = metrica_key

    extras = {
        "avisos": "Avisos",
        "monto_indemnizado": "Indemnización (S/)",
        "monto_desembolsado": "Desembolso (S/)",
        "ha_indemnizadas": "Ha Indemn.",
        "pct_desembolso": "% Desemb.",
        "pct_evaluacion": "% Eval.",
    }
    for orig, display in extras.items():
        if orig != col and orig in ranking.columns:
            columns_map[orig] = display

    cols_to_select = [c for c in columns_map.keys() if c in ranking.columns]
    result = ranking[cols_to_select].copy()
    result.columns = [columns_map[c] for c in cols_to_select]

    return result


# ═══════════════════════════════════════════════════════════════════
# TARJETAS RESUMEN
# ═══════════════════════════════════════════════════════════════════

def get_summary_cards(datos, nivel_key="Departamental", depto_filter=None):
    """
    Genera datos resumidos para tarjetas de contexto del mapa.
    """
    df = _build_metrics(datos, nivel_key, depto_filter)
    if len(df) == 0:
        return {}

    nivel = NIVELES[nivel_key]
    df_con_avisos = df[df["avisos"] > 0]
    if len(df_con_avisos) == 0:
        return {}

    return {
        "label": nivel["label"],
        "top_avisos": df.sort_values("avisos", ascending=False).iloc[0]["nombre"],
        "top_avisos_n": int(df["avisos"].max()),
        "top_indemn": df.sort_values("monto_indemnizado", ascending=False).iloc[0]["nombre"],
        "top_indemn_val": df["monto_indemnizado"].max(),
        "top_desemb_pct": df_con_avisos.sort_values("pct_desembolso", ascending=False).iloc[0]["nombre"],
        "top_desemb_pct_val": df_con_avisos["pct_desembolso"].max(),
        "min_desemb_pct": df_con_avisos.sort_values("pct_desembolso").iloc[0]["nombre"],
        "min_desemb_pct_val": df_con_avisos["pct_desembolso"].min(),
        "total_units": len(df),
        "units_con_avisos": len(df_con_avisos),
    }
