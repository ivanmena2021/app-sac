"""
Choropleth map of Peru departments for SAC agricultural insurance metrics.
Renders an interactive Plotly map and optional Streamlit UI tab.
"""

import json
import os
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


# ── Metric definitions ─────────────────────────────────────────────────────
METRIC_OPTIONS = {
    "avisos": {
        "label": "Total de Avisos",
        "format": ",d",
        "color_scale": "YlOrRd",
        "agg_col": None,  # count-based
    },
    "indemnizacion": {
        "label": "Monto Indemnizado (S/)",
        "format": ",.0f",
        "color_scale": "Reds",
        "agg_col": None,
    },
    "siniestralidad": {
        "label": "Indice de Siniestralidad (%)",
        "format": ".1f",
        "color_scale": "RdYlGn_r",
        "agg_col": None,
    },
    "desembolso": {
        "label": "Monto Desembolsado (S/)",
        "format": ",.0f",
        "color_scale": "Blues",
        "agg_col": None,
    },
}

# ── Department name normalization map ──────────────────────────────────────
_DEPT_NORMALIZE = {
    "MADRE DE DIOS": "MADRE DE DIOS",
    "SAN MARTIN": "SAN MARTIN",
    "SAN MARTÍN": "SAN MARTIN",
    "JUNÍN": "JUNIN",
    "HUÁNUCO": "HUANUCO",
    "ÁNCASH": "ANCASH",
    "APURÍMAC": "APURIMAC",
    "AYACUCHO": "AYACUCHO",
}


def _normalize_dept(name):
    """Normalize department names: uppercase, strip accents for matching."""
    if not isinstance(name, str):
        return name
    name = name.strip().upper()
    # Remove common accents
    replacements = {
        "\u00c1": "A", "\u00c9": "E", "\u00cd": "I", "\u00d3": "O", "\u00da": "U",
        "\u00e1": "a", "\u00e9": "e", "\u00ed": "i", "\u00f3": "o", "\u00fa": "u",
        "\u00d1": "N", "\u00f1": "n",
    }
    for accent, plain in replacements.items():
        name = name.replace(accent, plain.upper())
    return _DEPT_NORMALIZE.get(name, name)


def _load_geojson():
    """Load Peru department boundaries GeoJSON."""
    path = os.path.join(os.path.dirname(__file__), "static_data", "peru_departamentos.geojson")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_column(df, candidates):
    """Find first column matching any candidate (case-insensitive)."""
    cols_upper = {c.upper(): c for c in df.columns}
    for cand in candidates:
        if cand.upper() in cols_upper:
            return cols_upper[cand.upper()]
    return None


def _build_dept_metrics(datos):
    """Aggregate metrics by department from midagri DataFrame.

    Returns DataFrame with columns:
        DEPARTAMENTO, avisos, indemnizacion, siniestralidad, desembolso
    """
    midagri = datos.get("midagri")
    if midagri is None or midagri.empty:
        return pd.DataFrame()

    dept_col = _find_column(midagri, ["DEPARTAMENTO", "DEPTO", "DEPT", "DEPARMENT"])
    if dept_col is None:
        return pd.DataFrame()

    df = midagri.copy()
    df["_dept_norm"] = df[dept_col].apply(_normalize_dept)

    # Find relevant columns
    indem_col = _find_column(df, ["INDEMNIZACION", "MONTO_INDEMNIZADO",
                                   "MONTO INDEMNIZADO", "INDEMNIZACIÓN"])
    desemb_col = _find_column(df, ["DESEMBOLSO", "MONTO_DESEMBOLSADO",
                                    "MONTO DESEMBOLSADO", "MONTO_DESEMBOLSO"])
    prima_col = _find_column(df, ["PRIMA_NETA", "PRIMA NETA", "PRIMA_TOTAL", "PRIMA"])

    agg_dict = {"_dept_norm": "count"}  # avisos = row count
    rename_map = {"_dept_norm": "avisos"}

    if indem_col:
        df[indem_col] = pd.to_numeric(df[indem_col], errors="coerce").fillna(0)
        agg_dict[indem_col] = "sum"
        rename_map[indem_col] = "indemnizacion"

    if desemb_col:
        df[desemb_col] = pd.to_numeric(df[desemb_col], errors="coerce").fillna(0)
        agg_dict[desemb_col] = "sum"
        rename_map[desemb_col] = "desembolso"

    if prima_col:
        df[prima_col] = pd.to_numeric(df[prima_col], errors="coerce").fillna(0)
        agg_dict[prima_col] = "sum"
        rename_map[prima_col] = "prima"

    grouped = df.groupby("_dept_norm").agg(agg_dict).reset_index()
    grouped.rename(columns={"_dept_norm": "DEPARTAMENTO"}, inplace=True)
    grouped.rename(columns=rename_map, inplace=True)

    # Calculate siniestralidad
    if "indemnizacion" in grouped.columns and "prima" in grouped.columns:
        grouped["siniestralidad"] = np.where(
            grouped["prima"] > 0,
            (grouped["indemnizacion"] / grouped["prima"]) * 100,
            0.0,
        )
    else:
        grouped["siniestralidad"] = 0.0

    # Ensure desembolso column exists
    if "desembolso" not in grouped.columns:
        grouped["desembolso"] = 0.0

    return grouped


def generate_choropleth(datos, metric_key="avisos"):
    """Generate a Plotly choropleth figure for Peru departments.

    Parameters
    ----------
    datos : dict
        App data dictionary containing at least 'midagri' DataFrame.
    metric_key : str
        One of the keys in METRIC_OPTIONS.

    Returns
    -------
    plotly.graph_objects.Figure or None
        None if GeoJSON is not available.
    """
    geojson = _load_geojson()
    if geojson is None:
        return None

    dept_df = _build_dept_metrics(datos)
    if dept_df.empty:
        return None

    metric_info = METRIC_OPTIONS.get(metric_key, METRIC_OPTIONS["avisos"])

    # Ensure metric column exists
    if metric_key not in dept_df.columns:
        return None

    # Detect GeoJSON property for department name
    feat_props = geojson["features"][0]["properties"] if geojson["features"] else {}
    dept_prop = None
    for key in ["DEPARTAMEN", "NOMBDEP", "DEPARTAMENTO", "NAME_1", "name"]:
        if key in feat_props:
            dept_prop = key
            break
    if dept_prop is None:
        dept_prop = list(feat_props.keys())[0] if feat_props else "DEPARTAMEN"

    # Normalize GeoJSON names for matching
    for feat in geojson["features"]:
        original = feat["properties"].get(dept_prop, "")
        feat["properties"]["_dept_match"] = _normalize_dept(original)

    fig = px.choropleth(
        dept_df,
        geojson=geojson,
        locations="DEPARTAMENTO",
        featureidkey="properties._dept_match",
        color=metric_key,
        color_continuous_scale=metric_info["color_scale"],
        hover_name="DEPARTAMENTO",
        hover_data={
            metric_key: f":{metric_info['format']}",
            "DEPARTAMENTO": False,
        },
        labels={metric_key: metric_info["label"]},
        title=f"{metric_info['label']} por Departamento",
    )

    fig.update_geos(
        fitbounds="locations",
        visible=False,
        bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        height=600,
        coloraxis_colorbar=dict(
            title=metric_info["label"],
            thickness=15,
            len=0.7,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    return fig


def render_choropleth_tab(datos):
    """Render Streamlit UI for the choropleth map tab.

    Shows a metric selector, the choropleth map, and a ranking table below.
    """
    st.subheader("Mapa Coropleta por Departamento")

    col_sel, col_spacer = st.columns([2, 3])
    with col_sel:
        metric_labels = {k: v["label"] for k, v in METRIC_OPTIONS.items()}
        selected_label = st.selectbox(
            "Seleccionar metrica:",
            options=list(metric_labels.values()),
            index=0,
        )
        # Reverse-lookup key from label
        metric_key = next(k for k, v in METRIC_OPTIONS.items() if v["label"] == selected_label)

    fig = generate_choropleth(datos, metric_key=metric_key)

    if fig is None:
        geojson_path = os.path.join(os.path.dirname(__file__),
                                    "static_data", "peru_departamentos.geojson")
        st.warning(
            f"No se pudo generar el mapa. Verifique que el archivo GeoJSON exista en:\n"
            f"`{geojson_path}`\n\n"
            "Puede descargar los limites departamentales de Peru en formato GeoJSON "
            "y colocarlos en la carpeta `static_data/`."
        )
        return

    st.plotly_chart(fig, use_container_width=True)

    # Ranking table below
    st.subheader("Ranking Departamental")
    dept_df = _build_dept_metrics(datos)
    if not dept_df.empty:
        display_df = dept_df.sort_values(metric_key, ascending=False).reset_index(drop=True)
        display_df.index = display_df.index + 1
        display_df.index.name = "Rank"

        # Format columns for display
        fmt_df = display_df.copy()
        for col in ["indemnizacion", "desembolso"]:
            if col in fmt_df.columns:
                fmt_df[col] = fmt_df[col].apply(lambda x: f"S/ {x:,.0f}" if pd.notna(x) else "")
        if "siniestralidad" in fmt_df.columns:
            fmt_df["siniestralidad"] = fmt_df["siniestralidad"].apply(
                lambda x: f"{x:.1f}%" if pd.notna(x) else ""
            )
        if "avisos" in fmt_df.columns:
            fmt_df["avisos"] = fmt_df["avisos"].apply(
                lambda x: f"{int(x):,}" if pd.notna(x) else ""
            )

        # Drop internal columns
        drop_cols = [c for c in fmt_df.columns if c.startswith("prima")]
        fmt_df = fmt_df.drop(columns=drop_cols, errors="ignore")

        st.dataframe(fmt_df, use_container_width=True)
