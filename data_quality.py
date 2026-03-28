"""
Modulo de Calidad de Datos -- Dashboard SAC
Analiza completitud, duplicados, fechas invalidas y anomalias
en los datasets de siniestros del seguro agricola catastrofico.
"""

import numpy as np
import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Columnas de fecha esperadas en midagri
# ---------------------------------------------------------------------------
_DATE_COLS = [
    "FECHA_AVISO", "FECHA_ATENCION", "FECHA_SINIESTRO",
    "FECHA_PROGRAMACION_AJUSTE", "FECHA_AJUSTE_ACTA_1",
    "FECHA_AJUSTE_ACTA_FINAL", "FECHA_REPROGRAMACION_01",
    "FECHA_REPROGRAMACION_02", "FECHA_REPROGRAMACION_03",
    "FECHA_ENVIO_DRAS", "FECHA_VALIDACION", "FECHA_DESEMBOLSO",
]


def compute_quality_report(df: pd.DataFrame, label: str = "Dataset") -> dict:
    """Genera un reporte de calidad sobre *df*.

    Devuelve un dict con:
      row_count, col_count, missing_summary (DataFrame),
      duplicate_rows, duplicate_codigos, date_issues, anomalies.
    """
    report: dict = {"label": label}

    # --- Dimensiones ---
    report["row_count"] = len(df)
    report["col_count"] = len(df.columns)

    # --- Valores faltantes ---
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    pct = (missing / len(df) * 100).round(2)
    report["missing_summary"] = pd.DataFrame({
        "Columna": missing.index,
        "Faltantes": missing.values,
        "Porcentaje": pct.values,
    }).reset_index(drop=True)

    # --- Duplicados ---
    report["duplicate_rows"] = int(df.duplicated().sum())
    if "CODIGO_AVISO" in df.columns:
        report["duplicate_codigos"] = int(
            df["CODIGO_AVISO"].dropna().duplicated().sum()
        )
    else:
        report["duplicate_codigos"] = 0

    # --- Fechas invalidas ---
    date_issues: list[dict] = []
    for col in _DATE_COLS:
        if col not in df.columns:
            continue
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            continue
        converted = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
        n_invalid = int(df[col].notna().sum() - converted.notna().sum())
        if n_invalid > 0:
            pct_inv = round(n_invalid / max(len(df), 1) * 100, 2)
            date_issues.append(
                {"column": col, "invalid_count": n_invalid, "pct": pct_inv}
            )
    report["date_issues"] = date_issues

    # --- Anomalias ---
    anomalies: list[str] = []

    if "INDEMNIZACION" in df.columns:
        neg = (pd.to_numeric(df["INDEMNIZACION"], errors="coerce") < 0).sum()
        if neg:
            anomalies.append(f"{neg} avisos con indemnizacion negativa")

    if {"FECHA_DESEMBOLSO", "FECHA_AVISO"}.issubset(df.columns):
        fd = pd.to_datetime(df["FECHA_DESEMBOLSO"], errors="coerce", dayfirst=True)
        fa = pd.to_datetime(df["FECHA_AVISO"], errors="coerce", dayfirst=True)
        bad = ((fd < fa) & fd.notna() & fa.notna()).sum()
        if bad:
            anomalies.append(
                f"{bad} avisos con FECHA_DESEMBOLSO antes de FECHA_AVISO"
            )

    if {"INDEMNIZACION", "DICTAMEN"}.issubset(df.columns):
        ind = pd.to_numeric(df["INDEMNIZACION"], errors="coerce")
        mask = (ind > 0) & (df["DICTAMEN"].str.upper() != "INDEMNIZABLE")
        n = mask.sum()
        if n:
            anomalies.append(
                f"{n} avisos con INDEMNIZACION > 0 pero DICTAMEN != INDEMNIZABLE"
            )

    report["anomalies"] = anomalies
    return report


# ---------------------------------------------------------------------------
# Helpers de renderizado
# ---------------------------------------------------------------------------

def _metric_card(label: str, value, color: str = "blue") -> str:
    return (
        f'<div class="metric-card-v2 accent-{color}">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f"</div>"
    )


def _section(title: str):
    st.markdown(
        f'<div class="section-header">{title}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------

def render_quality_dashboard(datos: dict):
    """Muestra el dashboard de calidad de datos en Streamlit."""

    df = datos.get("midagri")
    if df is None or df.empty:
        st.warning("No hay datos cargados para analizar.")
        return

    rpt = compute_quality_report(df, label="MIDAGRI consolidado")

    # --- Fila de metricas ---
    total_anomalies = len(rpt["anomalies"])
    cols = st.columns(4)
    cards = [
        ("Total registros", f"{rpt['row_count']:,}", "blue"),
        ("Columnas", rpt["col_count"], "green"),
        ("Filas duplicadas", f"{rpt['duplicate_rows']:,}", "amber"),
        ("Anomalias encontradas", total_anomalies, "red"),
    ]
    for col, (lbl, val, clr) in zip(cols, cards):
        col.markdown(_metric_card(lbl, val, clr), unsafe_allow_html=True)

    st.markdown("---")

    # --- Valores faltantes ---
    _section("Valores Faltantes")
    ms = rpt["missing_summary"]
    if ms.empty:
        st.success("No se encontraron valores faltantes.")
    else:
        ms_display = ms.copy()
        ms_display["Barra"] = ms_display["Porcentaje"].apply(
            lambda p: f'<div style="background:#e74c3c;width:{min(p, 100):.0f}%;'
                      f'height:10px;border-radius:4px"></div>'
        )
        st.dataframe(
            ms[["Columna", "Faltantes", "Porcentaje"]],
            use_container_width=True,
            hide_index=True,
        )

    # --- Fechas invalidas ---
    _section("Fechas Invalidas")
    if not rpt["date_issues"]:
        st.success("Todas las columnas de fecha son validas.")
    else:
        di_df = pd.DataFrame(rpt["date_issues"])
        di_df.columns = ["Columna", "Invalidos", "% Invalidos"]
        st.dataframe(di_df, use_container_width=True, hide_index=True)

    # --- Anomalias ---
    _section("Anomalias Detectadas")
    if not rpt["anomalies"]:
        st.success("No se detectaron anomalias.")
    else:
        for a in rpt["anomalies"]:
            st.markdown(f":warning: {a}")

    # --- Distribucion por empresa ---
    _section("Distribucion por Empresa")
    if "EMPRESA" in df.columns:
        counts = df["EMPRESA"].value_counts()
        chart_df = pd.DataFrame({"Empresa": counts.index, "Registros": counts.values})
        st.bar_chart(chart_df, x="Empresa", y="Registros", color="#2980b9")
    else:
        st.info("Columna EMPRESA no disponible en el dataset.")

    # --- Codigos duplicados ---
    if rpt["duplicate_codigos"] > 0:
        st.markdown(
            f":information_source: **{rpt['duplicate_codigos']:,}** "
            f"codigos de aviso duplicados (CODIGO_AVISO)."
        )
