"""
comparativo_campanias.py — Comparación evolutiva entre campañas SAC
Genera gráficos y tablas comparando indicadores clave mes a mes
entre la campaña 2024-2025 y la campaña 2025-2026.
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static_data")

# ─── Colores por campaña ───
COLOR_2425 = "#8e44ad"   # morado
COLOR_2526 = "#2980b9"   # azul
COLOR_2425_LIGHT = "rgba(142,68,173,0.12)"
COLOR_2526_LIGHT = "rgba(41,128,185,0.12)"

# ─── Meses del ciclo SAC (septiembre a agosto del año siguiente) ───
MESES_CICLO = [
    "Sep", "Oct", "Nov", "Dic",
    "Ene", "Feb", "Mar", "Abr",
    "May", "Jun", "Jul", "Ago",
]

# Mapeo mes numérico → posición en el ciclo (Sep=0, Oct=1, ..., Ago=11)
MES_TO_POS = {9: 0, 10: 1, 11: 2, 12: 3, 1: 4, 2: 5, 3: 6, 4: 7, 5: 8, 6: 9, 7: 10, 8: 11}


def load_campania_anterior():
    """Carga el consolidado homogenizado de la campaña 2024-2025."""
    path = os.path.join(STATIC_DIR, "consolidado_sac_2024_2025.xlsx")
    if not os.path.exists(path):
        return None
    df = pd.read_excel(path)
    # Asegurar tipos
    for col in ["INDEMNIZACION", "MONTO_DESEMBOLSADO", "SUP_INDEMNIZADA",
                 "N_PRODUCTORES", "SUP_ASEGURADA", "PRIMA_NETA_DPTO"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["FECHA_SINIESTRO", "FECHA_AVISO", "FECHA_ATENCION",
                 "FECHA_AJUSTE_ACTA", "FECHA_DESEMBOLSO"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


# ═══════════════════════════════════════════════════════════════════
# MÉTRICAS DISPONIBLES PARA COMPARACIÓN
# ═══════════════════════════════════════════════════════════════════
METRICAS_COMPARACION = {
    "avisos_acumulados": {
        "label": "Avisos Reportados (acumulado)",
        "description": "Evolución acumulada del número de avisos de siniestro",
        "col_fecha": "FECHA_AVISO",
        "agg": "count",
        "col_valor": "CODIGO_AVISO",
        "formato": "{:,.0f}",
        "suffix": "avisos",
    },
    "indemnizacion_mensual": {
        "label": "Monto Indemnizado por Mes (S/)",
        "description": "Monto total de indemnizaciones reconocidas cada mes",
        "col_fecha": "FECHA_AJUSTE_ACTA",  # para 2024-2025
        "col_fecha_alt": "FECHA_ATENCION",  # fallback para 2025-2026
        "agg": "sum",
        "col_valor": "INDEMNIZACION",
        "filter": {"DICTAMEN": "INDEMNIZABLE"},
        "formato": "S/ {:,.0f}",
        "suffix": "soles",
    },
    "indemnizacion_acumulada": {
        "label": "Monto Indemnizado Acumulado (S/)",
        "description": "Evolución acumulada del monto total indemnizado",
        "col_fecha": "FECHA_AJUSTE_ACTA",
        "col_fecha_alt": "FECHA_ATENCION",
        "agg": "sum",
        "col_valor": "INDEMNIZACION",
        "filter": {"DICTAMEN": "INDEMNIZABLE"},
        "cumulative": True,
        "formato": "S/ {:,.0f}",
        "suffix": "soles",
    },
    "ha_indemnizadas_mensual": {
        "label": "Hectáreas Indemnizadas por Mes",
        "description": "Superficie indemnizada cada mes",
        "col_fecha": "FECHA_AJUSTE_ACTA",
        "col_fecha_alt": "FECHA_ATENCION",
        "agg": "sum",
        "col_valor": "SUP_INDEMNIZADA",
        "filter": {"DICTAMEN": "INDEMNIZABLE"},
        "formato": "{:,.0f}",
        "suffix": "ha",
    },
    "ha_indemnizadas_acumulada": {
        "label": "Hectáreas Indemnizadas Acumuladas",
        "description": "Evolución acumulada de la superficie indemnizada",
        "col_fecha": "FECHA_AJUSTE_ACTA",
        "col_fecha_alt": "FECHA_ATENCION",
        "agg": "sum",
        "col_valor": "SUP_INDEMNIZADA",
        "filter": {"DICTAMEN": "INDEMNIZABLE"},
        "cumulative": True,
        "formato": "{:,.0f}",
        "suffix": "ha",
    },
    "desembolso_acumulado": {
        "label": "Desembolso Acumulado (S/)",
        "description": "Evolución acumulada del monto desembolsado a productores",
        "col_fecha": "FECHA_DESEMBOLSO",
        "agg": "sum",
        "col_valor": "MONTO_DESEMBOLSADO",
        "cumulative": True,
        "formato": "S/ {:,.0f}",
        "suffix": "soles",
    },
    "productores_acumulado": {
        "label": "Productores Beneficiados (acumulado)",
        "description": "Evolución acumulada del número de productores con desembolso",
        "col_fecha": "FECHA_DESEMBOLSO",
        "agg": "sum",
        "col_valor": "N_PRODUCTORES",
        "cumulative": True,
        "formato": "{:,.0f}",
        "suffix": "productores",
    },
    "avisos_por_tipo": {
        "label": "Avisos por Tipo de Siniestro",
        "description": "Distribución comparativa de tipos de siniestro entre campañas",
        "special": "bar_tipo",
    },
}


def _get_fecha_col(df, meta):
    """Determina qué columna de fecha usar para un dataset."""
    col = meta["col_fecha"]
    if col in df.columns and df[col].notna().sum() > 0:
        return col
    alt = meta.get("col_fecha_alt")
    if alt and alt in df.columns:
        return alt
    return col


def _build_monthly_series(df, meta, campania_label):
    """
    Construye una serie mensual indexada por posición en el ciclo SAC.
    Retorna DataFrame con columnas: [pos, mes_label, valor]
    """
    if "special" in meta:
        return None

    # Aplicar filtro si existe
    df_work = df.copy()
    if "filter" in meta:
        for col_f, val_f in meta["filter"].items():
            if col_f in df_work.columns:
                df_work = df_work[df_work[col_f].astype(str).str.upper() == val_f.upper()]

    col_fecha = _get_fecha_col(df_work, meta)
    col_valor = meta["col_valor"]

    if col_fecha not in df_work.columns:
        return pd.DataFrame(columns=["pos", "mes_label", "valor"])

    # Asegurar que la columna de fecha sea datetime
    df_work[col_fecha] = pd.to_datetime(df_work[col_fecha], errors="coerce")
    df_work = df_work[df_work[col_fecha].notna()].copy()
    if len(df_work) == 0:
        return pd.DataFrame(columns=["pos", "mes_label", "valor"])

    df_work["_mes"] = df_work[col_fecha].dt.month

    # Agregar por mes
    if meta["agg"] == "count":
        monthly = df_work.groupby("_mes")[col_valor].count().reset_index()
        monthly.columns = ["_mes", "valor"]
    else:
        if col_valor not in df_work.columns:
            return pd.DataFrame(columns=["pos", "mes_label", "valor"])
        monthly = df_work.groupby("_mes")[col_valor].sum().reset_index()
        monthly.columns = ["_mes", "valor"]

    # Mapear a posición en ciclo SAC
    monthly["pos"] = monthly["_mes"].map(MES_TO_POS)
    monthly = monthly.dropna(subset=["pos"])
    monthly["pos"] = monthly["pos"].astype(int)
    monthly = monthly.sort_values("pos")
    monthly["mes_label"] = monthly["pos"].map(lambda p: MESES_CICLO[p] if 0 <= p < 12 else "?")

    # Acumulado si corresponde
    if meta.get("cumulative"):
        monthly["valor"] = monthly["valor"].cumsum()

    return monthly[["pos", "mes_label", "valor"]]


def generate_comparison_chart(df_actual, df_anterior, metrica_key):
    """
    Genera un gráfico plotly comparando ambas campañas para una métrica dada.
    df_actual: DataFrame consolidado de 2025-2026 (con columnas estándar).
    df_anterior: DataFrame consolidado de 2024-2025 (homogenizado).
    """
    meta = METRICAS_COMPARACION[metrica_key]

    # Caso especial: avisos por tipo
    if meta.get("special") == "bar_tipo":
        return _chart_avisos_por_tipo(df_actual, df_anterior)

    series_ant = _build_monthly_series(df_anterior, meta, "2024-2025")
    series_act = _build_monthly_series(df_actual, meta, "2025-2026")

    is_cumulative = meta.get("cumulative", False)
    chart_mode = "lines+markers" if is_cumulative else "lines+markers"
    fill_mode = "tozeroy" if not is_cumulative else None

    fig = go.Figure()

    # Campaña anterior
    if series_ant is not None and len(series_ant) > 0:
        fig.add_trace(go.Scatter(
            x=series_ant["mes_label"],
            y=series_ant["valor"],
            name="2024-2025",
            mode=chart_mode,
            line=dict(color=COLOR_2425, width=2.5, dash="dot"),
            marker=dict(size=7, symbol="diamond"),
            fill=fill_mode if not is_cumulative else None,
            fillcolor=COLOR_2425_LIGHT if not is_cumulative else None,
            hovertemplate=f"2024-2025<br>%{{x}}: %{{y:,.0f}} {meta['suffix']}<extra></extra>",
        ))

    # Campaña actual
    if series_act is not None and len(series_act) > 0:
        fig.add_trace(go.Scatter(
            x=series_act["mes_label"],
            y=series_act["valor"],
            name="2025-2026",
            mode=chart_mode,
            line=dict(color=COLOR_2526, width=3),
            marker=dict(size=8),
            fill=fill_mode if not is_cumulative else None,
            fillcolor=COLOR_2526_LIGHT if not is_cumulative else None,
            hovertemplate=f"2025-2026<br>%{{x}}: %{{y:,.0f}} {meta['suffix']}<extra></extra>",
        ))

    fig.update_layout(
        title=dict(text=meta["label"], font=dict(size=16, color="#0c2340")),
        xaxis=dict(
            title="Mes del ciclo SAC",
            categoryorder="array",
            categoryarray=MESES_CICLO,
            tickfont=dict(size=11),
        ),
        yaxis=dict(
            title=meta["suffix"].capitalize(),
            tickformat=",",
            gridcolor="#e8ecf1",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            font=dict(size=12),
        ),
        plot_bgcolor="white",
        margin=dict(l=60, r=20, t=60, b=40),
        height=420,
        hovermode="x unified",
    )

    return fig


def _chart_avisos_por_tipo(df_actual, df_anterior):
    """Gráfico de barras agrupadas: avisos por tipo de siniestro, ambas campañas."""
    # 2024-2025
    tipo_ant = df_anterior.groupby("TIPO_SINIESTRO").size().reset_index(name="count_2425")
    tipo_ant = tipo_ant.sort_values("count_2425", ascending=False).head(10)

    # 2025-2026
    tipo_act = df_actual.groupby("TIPO_SINIESTRO").size().reset_index(name="count_2526")

    # Merge
    merged = tipo_ant.merge(tipo_act, on="TIPO_SINIESTRO", how="outer").fillna(0)
    merged = merged.sort_values("count_2425", ascending=False).head(10)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=merged["TIPO_SINIESTRO"],
        y=merged["count_2425"],
        name="2024-2025",
        marker_color=COLOR_2425,
        opacity=0.85,
    ))
    fig.add_trace(go.Bar(
        x=merged["TIPO_SINIESTRO"],
        y=merged["count_2526"],
        name="2025-2026",
        marker_color=COLOR_2526,
        opacity=0.85,
    ))

    fig.update_layout(
        title=dict(text="Avisos por Tipo de Siniestro", font=dict(size=16, color="#0c2340")),
        barmode="group",
        xaxis=dict(tickangle=-30, tickfont=dict(size=10)),
        yaxis=dict(title="N° de Avisos", tickformat=",", gridcolor="#e8ecf1"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        margin=dict(l=60, r=20, t=60, b=80),
        height=420,
    )
    return fig


def get_comparison_table(df_actual, df_anterior):
    """
    Genera tabla resumen comparando indicadores clave entre ambas campañas.
    """
    def safe_sum(df, col):
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").sum()
        return 0

    def safe_count(df):
        return len(df)

    def cerrados(df):
        if "ESTADO_INSPECCION" in df.columns:
            return (df["ESTADO_INSPECCION"].astype(str).str.upper() == "CERRADO").sum()
        return 0

    n_ant = safe_count(df_anterior)
    n_act = safe_count(df_actual)

    indemn_ant = safe_sum(df_anterior, "INDEMNIZACION")
    indemn_act = safe_sum(df_actual, "INDEMNIZACION")

    ha_ant = safe_sum(df_anterior, "SUP_INDEMNIZADA")
    ha_act = safe_sum(df_actual, "SUP_INDEMNIZADA")

    desemb_ant = safe_sum(df_anterior, "MONTO_DESEMBOLSADO")
    desemb_act = safe_sum(df_actual, "MONTO_DESEMBOLSADO")

    prod_ant = safe_sum(df_anterior, "N_PRODUCTORES")
    prod_act = safe_sum(df_actual, "N_PRODUCTORES")

    cerr_ant = cerrados(df_anterior)
    cerr_act = cerrados(df_actual)

    # Prima neta from unique departamento values
    prima_ant = df_anterior.groupby("DEPARTAMENTO")["PRIMA_NETA_DPTO"].first().sum() if "PRIMA_NETA_DPTO" in df_anterior.columns else 0

    rows = [
        ("Avisos Reportados", f"{n_ant:,}", f"{n_act:,}", _delta(n_act, n_ant)),
        ("Avisos Cerrados/Ajustados", f"{cerr_ant:,}", f"{cerr_act:,}", _delta(cerr_act, cerr_ant)),
        ("Ha Indemnizadas", f"{ha_ant:,.0f}", f"{ha_act:,.0f}", _delta(ha_act, ha_ant)),
        ("Monto Indemnizado (S/)", f"{indemn_ant:,.0f}", f"{indemn_act:,.0f}", _delta(indemn_act, indemn_ant)),
        ("Monto Desembolsado (S/)", f"{desemb_ant:,.0f}", f"{desemb_act:,.0f}", _delta(desemb_act, desemb_ant)),
        ("Productores Beneficiados", f"{prod_ant:,.0f}", f"{prod_act:,.0f}", _delta(prod_act, prod_ant)),
        ("Siniestralidad", f"{(indemn_ant/prima_ant*100):.2f}%" if prima_ant > 0 else "—", "—", ""),
    ]

    return pd.DataFrame(rows, columns=["Indicador", "2024-2025", "2025-2026", "Variación"])


def _delta(actual, anterior):
    """Calcula porcentaje de variación."""
    if anterior == 0:
        return "—"
    pct = ((actual - anterior) / anterior) * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def get_monthly_detail_table(df_actual, df_anterior, metrica_key):
    """
    Genera tabla mes a mes con valores de ambas campañas.
    """
    meta = METRICAS_COMPARACION[metrica_key]
    if "special" in meta:
        return None

    series_ant = _build_monthly_series(df_anterior, meta, "2024-2025")
    series_act = _build_monthly_series(df_actual, meta, "2025-2026")

    # Build full month grid
    full = pd.DataFrame({"pos": range(12), "mes_label": MESES_CICLO})

    if series_ant is not None and len(series_ant) > 0:
        full = full.merge(series_ant[["pos", "valor"]].rename(columns={"valor": "2024-2025"}),
                          on="pos", how="left")
    else:
        full["2024-2025"] = np.nan

    if series_act is not None and len(series_act) > 0:
        full = full.merge(series_act[["pos", "valor"]].rename(columns={"valor": "2025-2026"}),
                          on="pos", how="left")
    else:
        full["2025-2026"] = np.nan

    full = full.rename(columns={"mes_label": "Mes"})
    full = full[["Mes", "2024-2025", "2025-2026"]]

    # Remove months where both are NaN
    full = full.dropna(subset=["2024-2025", "2025-2026"], how="all")

    return full
