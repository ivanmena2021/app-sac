"""
gen_ppt_dinamico.py — Motor de generación de PPT dinámicas para SAC
===================================================================
Genera presentaciones PowerPoint con python-pptx (Python puro).
Incluye: métricas, pipeline SAC, gráficos, tablas, separadores.
Filtros: geográfico, tipo siniestro, empresa, rango de fechas.
"""

import io
import os
import json
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.chart.data import CategoryChartData
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn


# ══════════════════════════════════════════════════════════════════
# FUNCIONES DE FILTRADO Y CÁLCULO (usadas por app.py para preview)
# ══════════════════════════════════════════════════════════════════

def _safe_col(df, col):
    return col in df.columns


def _aplicar_filtros(df, filtros):
    """Aplica todos los filtros al DataFrame."""
    df = df.copy()
    empresa = filtros.get("empresa", "ambas")
    if empresa != "ambas" and _safe_col(df, "EMPRESA"):
        df = df[df["EMPRESA"].astype(str).str.upper().str.contains(empresa.upper())]
    tipos = filtros.get("tipos_siniestro", [])
    if tipos and _safe_col(df, "TIPO_SINIESTRO"):
        df = df[df["TIPO_SINIESTRO"].isin(tipos)]
    fecha_inicio = filtros.get("fecha_inicio")
    fecha_fin = filtros.get("fecha_fin")
    col_fecha = filtros.get("col_fecha", "FECHA_AVISO")
    if fecha_inicio and fecha_fin and _safe_col(df, col_fecha):
        df[col_fecha] = pd.to_datetime(df[col_fecha], errors="coerce")
        mask = (df[col_fecha] >= pd.Timestamp(fecha_inicio)) & (df[col_fecha] <= pd.Timestamp(fecha_fin))
        df = df[mask]
    deptos = filtros.get("departamentos", [])
    provs = filtros.get("provincias", [])
    dists = filtros.get("distritos", [])
    if deptos and _safe_col(df, "DEPARTAMENTO"):
        df = df[df["DEPARTAMENTO"].isin(deptos)]
    if provs and _safe_col(df, "PROVINCIA"):
        df = df[df["PROVINCIA"].isin(provs)]
    if dists and _safe_col(df, "DISTRITO"):
        df = df[df["DISTRITO"].isin(dists)]
    return df


def _calcular_metricas(df):
    """Calcula métricas principales del DataFrame."""
    n = len(df)
    cerrados = 0
    if _safe_col(df, "ESTADO_INSPECCION"):
        cerrados = int(len(df[df["ESTADO_INSPECCION"].astype(str).str.upper() == "CERRADO"]))
    pct_eval = (cerrados / n * 100) if n > 0 else 0
    indem = float(df["INDEMNIZACION"].sum()) if _safe_col(df, "INDEMNIZACION") else 0
    desemb = float(df["MONTO_DESEMBOLSADO"].sum()) if _safe_col(df, "MONTO_DESEMBOLSADO") else 0
    pct_desemb = (desemb / indem * 100) if indem > 0 else 0
    ha = float(df["SUP_INDEMNIZADA"].sum()) if _safe_col(df, "SUP_INDEMNIZADA") else 0
    if _safe_col(df, "N_PRODUCTORES") and _safe_col(df, "INDEMNIZACION"):
        _indemn = pd.to_numeric(df["INDEMNIZACION"], errors="coerce").fillna(0)
        _prods = pd.to_numeric(df["N_PRODUCTORES"], errors="coerce").fillna(0)
        productores = int(_prods[_indemn > 0].sum())
    elif _safe_col(df, "N_PRODUCTORES"):
        productores = int(df["N_PRODUCTORES"].sum())
    else:
        productores = 0
    return {
        "avisos": n, "cerrados": cerrados, "pct_eval": round(pct_eval, 1),
        "indemnizacion": indem, "desembolso": desemb,
        "pct_desembolso": round(pct_desemb, 1),
        "ha_indemnizadas": round(ha, 2), "productores": productores,
    }


def _calcular_pipeline(df):
    """Calcula pipeline del proceso SAC."""
    if not _safe_col(df, "ESTADO_INSPECCION"):
        return []
    raw = df["ESTADO_INSPECCION"].astype(str).str.upper().value_counts().to_dict()
    order = ["NOTIFICADO", "PROGRAMADO", "REPROGRAMADO", "CERRADO"]
    result = []
    for estado in order:
        val = raw.get(estado, 0)
        if val > 0:
            result.append({"label": estado.title(), "val": int(val)})
    for k, v in raw.items():
        if k not in order and v > 0:
            result.append({"label": k.title(), "val": int(v)})
    return result


def _top_breakdown(df, col, n=10):
    """Top N por columna geográfica."""
    if not _safe_col(df, col):
        return []
    agg = {"Avisos": (col, "count")}
    if _safe_col(df, "INDEMNIZACION"):
        agg["Indemnización"] = ("INDEMNIZACION", "sum")
    if _safe_col(df, "MONTO_DESEMBOLSADO"):
        agg["Desembolso"] = ("MONTO_DESEMBOLSADO", "sum")
    if _safe_col(df, "SUP_INDEMNIZADA"):
        agg["Ha"] = ("SUP_INDEMNIZADA", "sum")
    if _safe_col(df, "N_PRODUCTORES"):
        df = df.copy()
        df["_PROD_BENEF"] = pd.to_numeric(df["N_PRODUCTORES"], errors="coerce").fillna(0)
        if _safe_col(df, "INDEMNIZACION"):
            _ind = pd.to_numeric(df["INDEMNIZACION"], errors="coerce").fillna(0)
            df["_PROD_BENEF"] = df["_PROD_BENEF"].where(_ind > 0, 0)
        agg["Productores"] = ("_PROD_BENEF", "sum")
    result = df.groupby(col).agg(**agg).reset_index()
    result = result.sort_values("Avisos", ascending=False).head(n)
    rows = []
    for _, r in result.iterrows():
        row = {"name": str(r[col]), "avisos": int(r["Avisos"])}
        if "Indemnización" in r:
            row["indem"] = float(r["Indemnización"])
        if "Desembolso" in r:
            row["desemb"] = float(r["Desembolso"])
        if "Ha" in r:
            row["ha"] = round(float(r["Ha"]), 2)
        if "Productores" in r:
            row["prod"] = int(r["Productores"])
        rows.append(row)
    return rows


def _tipo_breakdown(df):
    """Distribución por tipo de siniestro."""
    if not _safe_col(df, "TIPO_SINIESTRO"):
        return []
    agg = {"Avisos": ("TIPO_SINIESTRO", "count")}
    if _safe_col(df, "INDEMNIZACION"):
        agg["Indemnización"] = ("INDEMNIZACION", "sum")
    result = df.groupby("TIPO_SINIESTRO").agg(**agg).reset_index()
    result = result.sort_values("Avisos", ascending=False)
    rows = []
    for _, r in result.iterrows():
        row = {"tipo": str(r["TIPO_SINIESTRO"]), "avisos": int(r["Avisos"])}
        if "Indemnización" in r:
            row["indem"] = float(r["Indemnización"])
        rows.append(row)
    return rows


def _empresa_breakdown(df):
    """Breakdown por empresa."""
    if not _safe_col(df, "EMPRESA"):
        return []
    results = []
    for emp in df["EMPRESA"].dropna().unique():
        df_emp = df[df["EMPRESA"] == emp]
        m = _calcular_metricas(df_emp)
        results.append({"empresa": str(emp), **m})
    return results


def _dictamen_breakdown(df):
    """Breakdown por resultado de dictamen."""
    for col in ["DICTAMEN", "RESULTADO_AJUSTE", "RESULTADO_INSPECCION"]:
        if _safe_col(df, col):
            counts = df[col].astype(str).str.upper().value_counts().to_dict()
            return {k: int(v) for k, v in counts.items() if k not in ("NAN", "NONE", "")}
    return {}


LLUVIA_TYPES = {"INUNDACION", "INUNDACIÓN", "HUAYCO", "HUAICO",
                "LLUVIAS EXCESIVAS", "DESLIZAMIENTO", "DESLIZAMIENTOS"}


def _generar_insights(df, metricas, tipos, provincias_o_distritos=None,
                      col_geo="PROVINCIA", provs_seleccionadas=None):
    """Genera insights automáticos basados en los datos."""
    insights = []
    m = metricas
    n = m["avisos"]
    if n == 0:
        return insights

    if tipos and len(tipos) > 0:
        top = tipos[0]
        pct = (top["avisos"] / n * 100) if n > 0 else 0
        indem_txt = f" y {_fmt_money_py(top.get('indem', 0))} en indemnización" if top.get("indem") else ""
        insights.append({
            "title": f"{top['tipo']} es el siniestro predominante",
            "text": f"con {top['avisos']:,} avisos ({pct:.1f}% del total){indem_txt}.",
            "type": "predominance"
        })

    if tipos:
        lluvia = [t for t in tipos if t["tipo"].upper() in LLUVIA_TYPES]
        if lluvia:
            lluvia_avisos = sum(t["avisos"] for t in lluvia)
            lluvia_indem = sum(t.get("indem", 0) for t in lluvia)
            lluvia_nombres = ", ".join(t["tipo"].lower() for t in lluvia[:3])
            insights.append({
                "title": "Eventos asociados a lluvias",
                "text": f"({lluvia_nombres}) suman {lluvia_avisos:,} avisos y {_fmt_money_py(lluvia_indem)}.",
                "type": "lluvia"
            })

    if provincias_o_distritos:
        rezago = [p for p in provincias_o_distritos
                  if p["avisos"] >= 5 and p.get("indem", 0) == 0]
        if rezago:
            top_rez = rezago[0]
            insights.append({
                "title": f"{top_rez['name']} presenta rezago en evaluación",
                "text": f"con {top_rez['avisos']} avisos sin indemnización registrada.",
                "type": "rezago"
            })

    if m["pct_desembolso"] > 0:
        if m["pct_desembolso"] < 30:
            insights.append({
                "title": "Bajo nivel de desembolso",
                "text": f"Solo {m['pct_desembolso']:.1f}% de la indemnización ha sido desembolsada ({_fmt_money_py(m['desembolso'])}).",
                "type": "alert"
            })
        elif m["pct_desembolso"] >= 90:
            insights.append({
                "title": "Alto nivel de desembolso",
                "text": f"{m['pct_desembolso']:.1f}% de la indemnización ya fue desembolsada.",
                "type": "positive"
            })

    if provs_seleccionadas and provincias_o_distritos:
        sel = [p for p in provincias_o_distritos if p["name"] in provs_seleccionadas]
        if sel:
            combined_avisos = sum(p["avisos"] for p in sel)
            combined_indem = sum(p.get("indem", 0) for p in sel)
            combined_ha = sum(p.get("ha", 0) for p in sel)
            combined_prod = sum(p.get("prod", 0) for p in sel)
            nombres = " + ".join(p["name"] for p in sel)
            insights.append({
                "title": f"{nombres}: foco seleccionado",
                "text": f"{combined_avisos:,} avisos combinados, {_fmt_money_py(combined_indem)} indemnización, {combined_ha:,.1f} ha, {combined_prod:,} productores.",
                "type": "highlight"
            })

    return insights[:4]


def _empresa_composition(df):
    """Describe composición de empresa."""
    if not _safe_col(df, "EMPRESA"):
        return ""
    counts = df["EMPRESA"].value_counts()
    total = counts.sum()
    if len(counts) == 1:
        return f"Opera exclusivamente con {counts.index[0]}"
    parts = []
    for emp, cnt in counts.items():
        pct = cnt / total * 100
        parts.append(f"{emp}: {pct:.0f}%")
    return " · ".join(parts)


def _fmt_money_py(n):
    """Format money in Python."""
    if n is None or n == 0:
        return "S/ 0"
    if abs(n) >= 1_000_000:
        return f"S/ {n/1_000_000:,.2f} M"
    return f"S/ {n:,.0f}"


# ══════════════════════════════════════════════════════════════════
# PREPARAR DATA
# ══════════════════════════════════════════════════════════════════

def _prepare_data(df, filtros, fecha_corte):
    """Prepara toda la data en un dict para la generación de slides.
    Soporta modelo acumulativo: Nacional + Departamental + Provincial + Distrital.
    """
    scope = filtros.get("scope", "nacional")
    incluir_nacional = filtros.get("incluir_nacional", True)
    deptos = filtros.get("departamentos", [])
    provs = filtros.get("provincias", [])
    dists = filtros.get("distritos", [])

    filtros_base = {k: v for k, v in filtros.items()
                    if k not in ("departamentos", "provincias", "distritos", "scope", "incluir_nacional")}
    df_base = _aplicar_filtros(df, filtros_base)

    data = {
        "fecha_corte": fecha_corte,
        "scope": scope,
        "filtros": {
            "deptos": deptos, "provs": provs, "dists": dists,
            "tipos": filtros.get("tipos_siniestro", []),
            "empresa": filtros.get("empresa", "ambas"),
            "fecha_inicio": str(filtros.get("fecha_inicio", "")) if filtros.get("fecha_inicio") else "",
            "fecha_fin": str(filtros.get("fecha_fin", "")) if filtros.get("fecha_fin") else "",
        },
        "sections": [],
    }

    if incluir_nacional or not deptos:
        m = _calcular_metricas(df_base)
        tipos_nac = _tipo_breakdown(df_base)
        top_deptos_nac = _top_breakdown(df_base, "DEPARTAMENTO", 10)
        n_deptos = df_base["DEPARTAMENTO"].nunique() if _safe_col(df_base, "DEPARTAMENTO") else 0
        data["sections"].append({
            "type": "nacional",
            "metricas": m,
            "pipeline": _calcular_pipeline(df_base),
            "dictamen": _dictamen_breakdown(df_base),
            "empresas": _empresa_breakdown(df_base),
            "top_deptos": top_deptos_nac,
            "tipos": tipos_nac,
            "n_deptos": n_deptos,
            "insights": _generar_insights(df_base, m, tipos_nac, top_deptos_nac, "DEPARTAMENTO"),
        })

    if deptos:
        for depto in deptos:
            df_d = df_base[df_base["DEPARTAMENTO"] == depto] if _safe_col(df_base, "DEPARTAMENTO") else pd.DataFrame()
            if len(df_d) == 0:
                continue
            m = _calcular_metricas(df_d)
            tipos_d = _tipo_breakdown(df_d)
            provs_d = _top_breakdown(df_d, "PROVINCIA", 20)
            emp_comp = _empresa_composition(df_d)
            n_provs = df_d["PROVINCIA"].nunique() if _safe_col(df_d, "PROVINCIA") else 0
            data["sections"].append({
                "type": "departamental",
                "name": depto,
                "metricas": m,
                "pipeline": _calcular_pipeline(df_d),
                "dictamen": _dictamen_breakdown(df_d),
                "provincias": provs_d,
                "tipos": tipos_d,
                "empresa_comp": emp_comp,
                "n_provincias": n_provs,
                "insights": _generar_insights(df_d, m, tipos_d, provs_d, "PROVINCIA", provs),
                "provs_seleccionadas": provs,
            })

    if provs:
        for prov in provs:
            df_p = df_base[df_base["PROVINCIA"] == prov] if _safe_col(df_base, "PROVINCIA") else pd.DataFrame()
            if len(df_p) == 0:
                continue
            m = _calcular_metricas(df_p)
            depto_name = str(df_p["DEPARTAMENTO"].iloc[0]) if _safe_col(df_p, "DEPARTAMENTO") and len(df_p) > 0 else ""
            tipos_p = _tipo_breakdown(df_p)
            dists_p = _top_breakdown(df_p, "DISTRITO", 20)
            emp_comp = _empresa_composition(df_p)
            data["sections"].append({
                "type": "provincial",
                "name": prov,
                "depto": depto_name,
                "metricas": m,
                "pipeline": _calcular_pipeline(df_p),
                "dictamen": _dictamen_breakdown(df_p),
                "distritos": dists_p,
                "tipos": tipos_p,
                "empresa_comp": emp_comp,
                "insights": _generar_insights(df_p, m, tipos_p, dists_p, "DISTRITO"),
            })

    if dists:
        for dist in dists[:5]:
            df_dist = df_base[df_base["DISTRITO"] == dist] if _safe_col(df_base, "DISTRITO") else pd.DataFrame()
            if len(df_dist) == 0:
                continue
            m = _calcular_metricas(df_dist)
            prov_name = str(df_dist["PROVINCIA"].iloc[0]) if _safe_col(df_dist, "PROVINCIA") and len(df_dist) > 0 else ""
            depto_name = str(df_dist["DEPARTAMENTO"].iloc[0]) if _safe_col(df_dist, "DEPARTAMENTO") and len(df_dist) > 0 else ""
            data["sections"].append({
                "type": "distrital",
                "name": dist,
                "prov": prov_name,
                "depto": depto_name,
                "metricas": m,
                "pipeline": _calcular_pipeline(df_dist),
                "tipos": _tipo_breakdown(df_dist),
            })

    return data


# ══════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR PPT GENERATION (python-pptx)
# ══════════════════════════════════════════════════════════════════

# Color palette
C = {
    "forest": RGBColor(0x1B, 0x43, 0x32),
    "green": RGBColor(0x2D, 0x6A, 0x4F),
    "sage": RGBColor(0x52, 0xB7, 0x88),
    "mint": RGBColor(0x95, 0xD5, 0xB2),
    "cream": RGBColor(0xF5, 0xF1, 0xEB),
    "gold": RGBColor(0xD4, 0xA8, 0x43),
    "amber": RGBColor(0xC1, 0x78, 0x17),
    "navy": RGBColor(0x1A, 0x27, 0x44),
    "dark": RGBColor(0x21, 0x25, 0x29),
    "gray": RGBColor(0x6C, 0x75, 0x7D),
    "lightGray": RGBColor(0xE9, 0xEC, 0xEF),
    "white": RGBColor(0xFF, 0xFF, 0xFF),
    "red": RGBColor(0xC0, 0x39, 0x2B),
    "blue": RGBColor(0x21, 0x96, 0xF3),
}


def _fmt_num(n):
    """Format number with locale."""
    if n is None:
        return "0"
    return f"{int(n):,}"


def _fmt_money(n):
    """Format money (S/ X,XXX or S/ X.XX M)."""
    if n is None or n == 0:
        return "S/ 0"
    if abs(n) >= 1_000_000:
        return f"S/ {n/1_000_000:,.2f} M"
    return f"S/ {n:,.0f}"


def _fmt_pct(n):
    """Format percentage."""
    if n is None:
        return "0%"
    return f"{n:.1f}%"


def _add_shadow(shape):
    """Add shadow effect to shape via XML."""
    try:
        spPr = shape._element.spPr
        effectLst = spPr.makeelement(qn('a:effectLst'), {})
        outerShdw = effectLst.makeelement(qn('a:outerShdw'), {
            'blurRad': '50800',
            'dist': '25400',
            'dir': '8100000',
        })
        srgbClr = outerShdw.makeelement(qn('a:srgbClr'), {'val': '000000'})
        alpha = srgbClr.makeelement(qn('a:alpha'), {'val': '12000'})
        srgbClr.append(alpha)
        outerShdw.append(srgbClr)
        effectLst.append(outerShdw)
        spPr.append(effectLst)
    except Exception:
        pass


def _add_header_bar(slide, title, color, y_pos=Inches(0.3)):
    """Add colored rectangle header bar with title."""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), y_pos,
        Inches(10), Inches(0.7)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.color.rgb = color

    text_frame = shape.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = title
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = C["white"]
    p.alignment = PP_ALIGN.LEFT
    text_frame.margin_left = Inches(0.3)
    text_frame.margin_top = Inches(0.1)
    text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE


def _add_metric_card(slide, left, top, width, height, label, value, sublabel="", accent_color=None):
    """Add a single metric card with shadow."""
    if accent_color is None:
        accent_color = C["sage"]

    bg = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        left, top, width, height
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = C["white"]
    bg.line.color.rgb = C["lightGray"]
    _add_shadow(bg)

    accent = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        left, top, Inches(0.05), height
    )
    accent.fill.solid()
    accent.fill.fore_color.rgb = accent_color
    accent.line.fill.background()

    tf = slide.shapes.add_textbox(
        left + Inches(0.15), top + Inches(0.1),
        width - Inches(0.3), height - Inches(0.2)
    )
    text_frame = tf.text_frame
    text_frame.word_wrap = True

    p = text_frame.paragraphs[0]
    p.text = str(value)
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = C["forest"]
    p.alignment = PP_ALIGN.CENTER

    p2 = text_frame.add_paragraph()
    p2.text = str(label)
    p2.font.size = Pt(11)
    p2.font.color.rgb = C["gray"]
    p2.alignment = PP_ALIGN.CENTER
    p2.space_before = Pt(4)

    if sublabel:
        p3 = text_frame.add_paragraph()
        p3.text = str(sublabel)
        p3.font.size = Pt(9)
        p3.font.color.rgb = C["gray"]
        p3.alignment = PP_ALIGN.CENTER
        p3.space_before = Pt(2)


def _add_pipeline(slide, pipeline, dictamen, top_y):
    """Add pipeline flow visualization."""
    if not pipeline:
        return

    total = sum(p["val"] for p in pipeline)
    x_start = Inches(0.5)
    y_base = top_y

    for i, stage in enumerate(pipeline):
        x_pos = x_start + Inches(i * 2.2)

        rect = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            x_pos, y_base,
            Inches(1.8), Inches(0.6)
        )
        rect.fill.solid()
        rect.fill.fore_color.rgb = C["sage"]
        rect.line.color.rgb = C["green"]

        tf = slide.shapes.add_textbox(
            x_pos + Inches(0.1), y_base + Inches(0.05),
            Inches(1.6), Inches(0.5)
        )
        text_frame = tf.text_frame
        text_frame.word_wrap = True

        p = text_frame.paragraphs[0]
        p.text = stage["label"]
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = C["white"]
        p.alignment = PP_ALIGN.CENTER

        p2 = text_frame.add_paragraph()
        p2.text = f"{stage['val']:,}"
        p2.font.size = Pt(11)
        p2.font.bold = True
        p2.font.color.rgb = C["white"]
        p2.alignment = PP_ALIGN.CENTER

        if i < len(pipeline) - 1:
            arrow = slide.shapes.add_shape(
                MSO_SHAPE.RIGHT_ARROW,
                x_pos + Inches(1.95), y_base + Inches(0.15),
                Inches(0.25), Inches(0.3)
            )
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = C["gold"]
            arrow.line.fill.background()

    if dictamen:
        y_dict = y_base + Inches(1.0)
        tf = slide.shapes.add_textbox(
            Inches(0.5), y_dict,
            Inches(9), Inches(0.4)
        )
        text_frame = tf.text_frame
        text_frame.word_wrap = True

        dictamen_str = " | ".join([f"{k}: {v}" for k, v in list(dictamen.items())[:3]])
        p = text_frame.paragraphs[0]
        p.text = f"Dictamen: {dictamen_str}"
        p.font.size = Pt(10)
        p.font.color.rgb = C["gray"]


def _add_data_table(slide, headers, rows, left=Inches(0.3), top=Inches(1.2), max_rows=12):
    """Add formatted table."""
    rows_to_add = min(len(rows), max_rows)
    cols = len(headers)

    table_shape = slide.shapes.add_table(rows_to_add + 1, cols, left, top,
                                          Inches(9.4), Inches(0.35 * (rows_to_add + 1)))
    table = table_shape.table

    for i, header in enumerate(headers):
        cell = table.cell(0, i)
        cell.fill.solid()
        cell.fill.fore_color.rgb = C["forest"]
        p = cell.text_frame.paragraphs[0]
        p.text = header
        p.font.size = Pt(10)
        p.font.bold = True
        p.font.color.rgb = C["white"]
        p.alignment = PP_ALIGN.CENTER

    for row_idx, row_data in enumerate(rows[:max_rows], 1):
        for col_idx, value in enumerate(row_data):
            cell = table.cell(row_idx, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = C["white"] if row_idx % 2 == 0 else C["cream"]

            p = cell.text_frame.paragraphs[0]
            p.text = str(value) if value is not None else ""
            p.font.size = Pt(9)
            p.font.color.rgb = C["dark"]
            p.alignment = PP_ALIGN.CENTER


def _add_insight_box(slide, insights, left, top, width, height):
    """Add insight box with text."""
    if not insights:
        return

    insight = insights[0]

    bg = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        left, top, width, height
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = C["mint"]
    bg.line.color.rgb = C["sage"]
    bg.line.width = Pt(1.5)

    tf = slide.shapes.add_textbox(
        left + Inches(0.15), top + Inches(0.1),
        width - Inches(0.3), height - Inches(0.2)
    )
    text_frame = tf.text_frame
    text_frame.word_wrap = True

    p = text_frame.paragraphs[0]
    p.text = insight.get("title", "")
    p.font.size = Pt(11)
    p.font.bold = True
    p.font.color.rgb = C["forest"]

    p2 = text_frame.add_paragraph()
    p2.text = insight.get("text", "")
    p2.font.size = Pt(9)
    p2.font.color.rgb = C["dark"]
    p2.space_before = Pt(4)


def _add_highlight_box(slide, text, left, top, width):
    """Add highlight/info box."""
    bg = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        left, top, width, Inches(0.5)
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = C["gold"]
    bg.line.fill.background()

    tf = slide.shapes.add_textbox(
        left + Inches(0.1), top + Inches(0.05),
        width - Inches(0.2), Inches(0.4)
    )
    text_frame = tf.text_frame
    text_frame.word_wrap = True

    p = text_frame.paragraphs[0]
    p.text = text
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = C["white"]
    p.alignment = PP_ALIGN.CENTER


# ══════════════════════════════════════════════════════════════════
# SLIDE GENERATION FUNCTIONS
# ══════════════════════════════════════════════════════════════════

def _add_portada(prs, data):
    """Add cover slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        prs.slide_width, prs.slide_height
    )
    background.fill.solid()
    background.fill.fore_color.rgb = C["forest"]
    background.line.fill.background()

    line_top = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0.2),
        prs.slide_width, Inches(0.08)
    )
    line_top.fill.solid()
    line_top.fill.fore_color.rgb = C["gold"]
    line_top.line.fill.background()

    line_bottom = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(5.3),
        prs.slide_width, Inches(0.08)
    )
    line_bottom.fill.solid()
    line_bottom.fill.fore_color.rgb = C["gold"]
    line_bottom.line.fill.background()

    accent_bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0.8),
        Inches(0.15), Inches(4.0)
    )
    accent_bar.fill.solid()
    accent_bar.fill.fore_color.rgb = C["sage"]
    accent_bar.line.fill.background()

    tf_title = slide.shapes.add_textbox(
        Inches(0.5), Inches(1.5),
        Inches(9), Inches(1.0)
    )
    text_frame = tf_title.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = "SEGURO AGRÍCOLA CATASTRÓFICO"
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = C["gold"]
    p.font.name = "Georgia"
    p.alignment = PP_ALIGN.CENTER

    tf_subtitle = slide.shapes.add_textbox(
        Inches(0.5), Inches(2.7),
        Inches(9), Inches(0.8)
    )
    text_frame = tf_subtitle.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = "SAC 2025–2026"
    p.font.size = Pt(26)
    p.font.color.rgb = C["white"]
    p.font.name = "Georgia"
    p.alignment = PP_ALIGN.CENTER

    sep_line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(3.5), Inches(3.6),
        Inches(3), Inches(0.04)
    )
    sep_line.fill.solid()
    sep_line.fill.fore_color.rgb = C["gold"]
    sep_line.line.fill.background()

    geo_info = data.get("filtros", {})
    deptos = ", ".join(geo_info.get("deptos", [])[:3]) or "Nacional"

    tf_geo = slide.shapes.add_textbox(
        Inches(0.5), Inches(4.1),
        Inches(9), Inches(0.4)
    )
    text_frame = tf_geo.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = f"Ámbito: {deptos}"
    p.font.size = Pt(12)
    p.font.color.rgb = C["mint"]
    p.alignment = PP_ALIGN.CENTER

    corte_info = f"Corte: {data.get('fecha_corte', 'S.F.')}"
    tf_footer = slide.shapes.add_textbox(
        Inches(0.5), Inches(4.8),
        Inches(9), Inches(0.5)
    )
    text_frame = tf_footer.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = "Dirección de Seguro y Fomento del Financiamiento Agrario — MIDAGRI"
    p.font.size = Pt(10)
    p.font.color.rgb = C["lightGray"]
    p.alignment = PP_ALIGN.CENTER

    p2 = text_frame.add_paragraph()
    p2.text = corte_info
    p2.font.size = Pt(9)
    p2.font.color.rgb = C["lightGray"]
    p2.alignment = PP_ALIGN.CENTER


def _add_cierre(prs):
    """Add closing slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        prs.slide_width, prs.slide_height
    )
    background.fill.solid()
    background.fill.fore_color.rgb = C["forest"]
    background.line.fill.background()

    line_top = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0.2),
        prs.slide_width, Inches(0.08)
    )
    line_top.fill.solid()
    line_top.fill.fore_color.rgb = C["gold"]
    line_top.line.fill.background()

    tf_title = slide.shapes.add_textbox(
        Inches(1), Inches(1.8),
        Inches(8), Inches(1.5)
    )
    text_frame = tf_title.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = "Gracias"
    p.font.size = Pt(48)
    p.font.bold = True
    p.font.color.rgb = C["white"]
    p.alignment = PP_ALIGN.CENTER

    tf_footer = slide.shapes.add_textbox(
        Inches(1), Inches(4.2),
        Inches(8), Inches(0.8)
    )
    text_frame = tf_footer.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = "Dirección de Seguro y Fomento del Financiamiento Agrario"
    p.font.size = Pt(11)
    p.font.color.rgb = C["lightGray"]
    p.alignment = PP_ALIGN.CENTER

    p2 = text_frame.add_paragraph()
    p2.text = "Ministerio de Desarrollo Agrario y Riego"
    p2.font.size = Pt(10)
    p2.font.color.rgb = C["lightGray"]
    p2.alignment = PP_ALIGN.CENTER


def _add_nacional_section(prs, section):
    """Add nacional section slides."""
    m = section["metricas"]
    tipos = section.get("tipos", [])
    top_deptos = section.get("top_deptos", [])
    pipeline = section.get("pipeline", [])
    dictamen = section.get("dictamen", {})
    insights = section.get("insights", [])

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        prs.slide_width, prs.slide_height
    )
    background.fill.solid()
    background.fill.fore_color.rgb = C["cream"]
    background.line.fill.background()

    _add_header_bar(slide, "RESUMEN NACIONAL SAC 2025–2026", C["forest"])

    cards = [
        ("Avisos", _fmt_num(m["avisos"]), "Notificados"),
        ("Evaluados", _fmt_num(m["cerrados"]), f"{_fmt_pct(m['pct_eval'])}"),
        ("Indemnización", _fmt_money(m["indemnizacion"]), "Total"),
        ("Desembolso", _fmt_money(m["desembolso"]), f"{_fmt_pct(m['pct_desembolso'])}"),
        ("Ha Indemnizadas", f"{m['ha_indemnizadas']:,.1f}", "Hectáreas"),
        ("Productores", _fmt_num(m["productores"]), "Beneficiados"),
    ]

    for i, (label, value, sublabel) in enumerate(cards):
        col = i % 3
        row = i // 3
        left = Inches(0.5 + col * 3.15)
        top = Inches(1.3 + row * 1.75)
        _add_metric_card(slide, left, top, Inches(2.9), Inches(1.5), label, value, sublabel)

    _add_pipeline(slide, pipeline, dictamen, Inches(4.2))

    if insights:
        _add_insight_box(slide, insights, Inches(7.0), Inches(4.5), Inches(2.7), Inches(0.8))


def _add_departamental_section(prs, section):
    """Add departamental section slides."""
    name = section.get("name", "Departamento")
    m = section["metricas"]
    provs = section.get("provincias", [])
    tipos = section.get("tipos", [])
    pipeline = section.get("pipeline", [])
    insights = section.get("insights", [])

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        prs.slide_width, prs.slide_height
    )
    background.fill.solid()
    background.fill.fore_color.rgb = C["navy"]
    background.line.fill.background()

    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(1.0),
        prs.slide_width, Inches(0.06)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = C["gold"]
    line.line.fill.background()

    tf = slide.shapes.add_textbox(
        Inches(0.5), Inches(2.0),
        Inches(9), Inches(1.5)
    )
    text_frame = tf.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = name.upper()
    p.font.size = Pt(48)
    p.font.bold = True
    p.font.color.rgb = C["gold"]
    p.alignment = PP_ALIGN.CENTER

    p2 = text_frame.add_paragraph()
    p2.text = f"{m['avisos']:,} avisos | {_fmt_money(m['indemnizacion'])} indemnización"
    p2.font.size = Pt(12)
    p2.font.color.rgb = C["white"]
    p2.alignment = PP_ALIGN.CENTER
    p2.space_before = Pt(6)

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        prs.slide_width, prs.slide_height
    )
    background.fill.solid()
    background.fill.fore_color.rgb = C["cream"]
    background.line.fill.background()

    _add_header_bar(slide, f"MÉTRICAS — {name}", C["navy"])

    cards = [
        ("Avisos", _fmt_num(m["avisos"]), ""),
        ("Evaluados", _fmt_num(m["cerrados"]), f"{_fmt_pct(m['pct_eval'])}"),
        ("Indemnización", _fmt_money(m["indemnizacion"]), ""),
        ("Desembolso", _fmt_money(m["desembolso"]), f"{_fmt_pct(m['pct_desembolso'])}"),
    ]

    for i, (label, value, sublabel) in enumerate(cards):
        col = i % 2
        row = i // 2
        left = Inches(1.0 + col * 4.0)
        top = Inches(1.3 + row * 1.65)
        _add_metric_card(slide, left, top, Inches(3.8), Inches(1.5), label, value, sublabel, C["navy"])

    _add_pipeline(slide, section.get("pipeline", []), section.get("dictamen", {}), Inches(3.2))

    if provs:
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        background = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0), Inches(0),
            prs.slide_width, prs.slide_height
        )
        background.fill.solid()
        background.fill.fore_color.rgb = C["cream"]
        background.line.fill.background()

        _add_header_bar(slide, f"PROVINCIAS — {name}", C["forest"])

        headers = ["Provincia", "Avisos", "Indemnización", "Desembolso", "Ha"]
        rows = []
        for p in provs[:12]:
            rows.append([
                p["name"],
                _fmt_num(p["avisos"]),
                _fmt_money(p.get("indem", 0)),
                _fmt_money(p.get("desemb", 0)),
                f"{p.get('ha', 0):.1f}"
            ])

        _add_data_table(slide, headers, rows, top=Inches(1.2))


def _add_provincial_section(prs, section):
    """Add provincial section slides."""
    name = section.get("name", "Provincia")
    depto = section.get("depto", "")
    m = section["metricas"]
    dists = section.get("distritos", [])
    tipos = section.get("tipos", [])
    pipeline = section.get("pipeline", [])

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        prs.slide_width, prs.slide_height
    )
    background.fill.solid()
    background.fill.fore_color.rgb = C["forest"]
    background.line.fill.background()

    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(1.0),
        prs.slide_width, Inches(0.06)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = C["gold"]
    line.line.fill.background()

    tf = slide.shapes.add_textbox(
        Inches(0.5), Inches(2.0),
        Inches(9), Inches(1.5)
    )
    text_frame = tf.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = name.upper()
    p.font.size = Pt(48)
    p.font.bold = True
    p.font.color.rgb = C["gold"]
    p.alignment = PP_ALIGN.CENTER

    p2 = text_frame.add_paragraph()
    p2.text = f"{depto}"
    p2.font.size = Pt(14)
    p2.font.color.rgb = C["mint"]
    p2.alignment = PP_ALIGN.CENTER


def _add_distrital_section(prs, section):
    """Add distrital section slides."""
    name = section.get("name", "Distrito")

    slide = prs.slides.add_slide(prs.slide_layouts[6])
    background = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0),
        prs.slide_width, prs.slide_height
    )
    background.fill.solid()
    background.fill.fore_color.rgb = C["navy"]
    background.line.fill.background()

    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(1.0),
        prs.slide_width, Inches(0.06)
    )
    line.fill.solid()
    line.fill.fore_color.rgb = C["gold"]
    line.line.fill.background()

    tf = slide.shapes.add_textbox(
        Inches(0.5), Inches(2.0),
        Inches(9), Inches(1.5)
    )
    text_frame = tf.text_frame
    text_frame.word_wrap = True
    p = text_frame.paragraphs[0]
    p.text = name.upper()
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = C["gold"]
    p.alignment = PP_ALIGN.CENTER


# ══════════════════════════════════════════════════════════════════
# MAIN GENERATION FUNCTION
# ══════════════════════════════════════════════════════════════════

def generar_ppt_dinamico(df, filtros, fecha_corte):
    """
    Genera una presentación PPT dinámica con python-pptx.

    Args:
        df: DataFrame consolidado (datos["midagri"])
        filtros: dict con selecciones del usuario
        fecha_corte: string con fecha de corte

    Returns:
        bytes del archivo .pptx
    """
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625)
    prs.author = "DSFFA — MIDAGRI"
    prs.title = "SAC 2025-2026 — Presentación Dinámica"

    data = _prepare_data(df, filtros, fecha_corte)

    _add_portada(prs, data)

    for section in data.get("sections", []):
        section_type = section.get("type", "")

        if section_type == "nacional":
            _add_nacional_section(prs, section)
        elif section_type == "departamental":
            _add_departamental_section(prs, section)
        elif section_type == "provincial":
            _add_provincial_section(prs, section)
        elif section_type == "distrital":
            _add_distrital_section(prs, section)

    _add_cierre(prs)

    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output.getvalue()
