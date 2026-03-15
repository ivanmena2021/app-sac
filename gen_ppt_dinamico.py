"""
gen_ppt_dinamico.py — Motor de generación de PPT dinámicas para SAC
===================================================================
Genera presentaciones PowerPoint con PptxGenJS (Node.js) vía subprocess.
Incluye: métricas, pipeline SAC, gráficos, tablas, separadores.
Filtros: geográfico, tipo siniestro, empresa, rango de fechas.
"""

import io
import os
import json
import subprocess
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime


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
    # Productores beneficiados: solo registros con indemnización > 0
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
    # Add any remaining
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
        # Solo contar productores donde hay indemnización > 0
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

    # 1. Tipo siniestro predominante
    if tipos and len(tipos) > 0:
        top = tipos[0]
        pct = (top["avisos"] / n * 100) if n > 0 else 0
        indem_txt = f" y {_fmt_money_py(top.get('indem', 0))} en indemnización" if top.get("indem") else ""
        insights.append({
            "title": f"{top['tipo']} es el siniestro predominante",
            "text": f"con {top['avisos']:,} avisos ({pct:.1f}% del total){indem_txt}.",
            "type": "predominance"
        })

    # 2. Eventos de lluvia
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

    # 3. Rezago en evaluación (low evaluation rate)
    if provincias_o_distritos:
        rezago = [p for p in provincias_o_distritos
                  if p["avisos"] >= 5 and p.get("indem", 0) == 0]
        if not rezago:
            # Check for very low eval rates
            for p in provincias_o_distritos:
                if p["avisos"] >= 10:
                    # We can't calculate pct_eval from breakdown, but flag high-count low-indem
                    pass
        if rezago:
            top_rez = rezago[0]
            insights.append({
                "title": f"{top_rez['name']} presenta rezago en evaluación",
                "text": f"con {top_rez['avisos']} avisos sin indemnización registrada.",
                "type": "rezago"
            })

    # 4. Desembolso alert
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

    # 5. Highlight provincias seleccionadas
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

    return insights[:4]  # Max 4 insights per section


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
# PREPARAR DATA PARA NODE.JS
# ══════════════════════════════════════════════════════════════════

def _prepare_data(df, filtros, fecha_corte):
    """Prepara toda la data en un dict JSON-serializable para Node.
    Soporta modelo acumulativo: Nacional + Departamental + Provincial + Distrital
    se pueden combinar libremente.
    """
    scope = filtros.get("scope", "nacional")
    incluir_nacional = filtros.get("incluir_nacional", True)
    deptos = filtros.get("departamentos", [])
    provs = filtros.get("provincias", [])
    dists = filtros.get("distritos", [])

    # Aplicar filtros NO geográficos
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

    # ── Nacional (si está marcado o si no hay deptos seleccionados) ──
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

    # ── Departamentales (siempre que haya deptos seleccionados) ──
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

    # ── Provinciales (siempre que haya provs seleccionadas) ──
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

    # ── Distritales (siempre que haya dists seleccionados) ──
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
# JS TEMPLATE
# ══════════════════════════════════════════════════════════════════

JS_TEMPLATE = r'''
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const {
  FaChartBar, FaSearchDollar, FaCheckCircle, FaUsers, FaSeedling,
  FaHandHoldingUsd, FaMapMarkerAlt, FaExclamationTriangle, FaClipboardList,
  FaBuilding, FaLeaf, FaMountain, FaArrowRight, FaIndustry
} = require("react-icons/fa");

function renderIconSvg(Icon, color = "#000", size = 256) {
  return ReactDOMServer.renderToStaticMarkup(
    React.createElement(Icon, { color, size: String(size) })
  );
}
async function iconPng(Icon, color, size = 256) {
  const svg = renderIconSvg(Icon, color, size);
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

const C = {
  forest: "1B4332", green: "2D6A4F", sage: "52B788", mint: "95D5B2",
  cream: "F5F1EB", gold: "D4A843", amber: "C17817", navy: "1A2744",
  dark: "212529", gray: "6C757D", lightGray: "E9ECEF", white: "FFFFFF",
  red: "C0392B", blue: "2196F3"
};

const makeShadow = () => ({ type: "outer", blur: 4, offset: 2, angle: 135, color: "000000", opacity: 0.12 });
const fmtNum = (n) => n == null ? "0" : Number(n).toLocaleString("es-PE", {maximumFractionDigits: 0});
const fmtMoney = (n) => {
  if (n == null || n === 0) return "S/ 0";
  if (Math.abs(n) >= 1000000) return `S/ ${(n/1000000).toFixed(2).replace(".", ",")} M`;
  return `S/ ${fmtNum(n)}`;
};
const fmtPct = (n) => n == null ? "0%" : `${Number(n).toFixed(1)}%`;

const DATA = %%DATA_JSON%%;

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "DSFFA — MIDAGRI";
  pres.title = "SAC 2025-2026 — Presentación Dinámica";

  const icons = {
    chart: await iconPng(FaChartBar, "#" + C.white),
    search: await iconPng(FaSearchDollar, "#" + C.white),
    check: await iconPng(FaCheckCircle, "#" + C.white),
    users: await iconPng(FaUsers, "#" + C.white),
    seed: await iconPng(FaSeedling, "#" + C.white),
    hand: await iconPng(FaHandHoldingUsd, "#" + C.white),
    map: await iconPng(FaMapMarkerAlt, "#" + C.white),
    warn: await iconPng(FaExclamationTriangle, "#" + C.white),
    clip: await iconPng(FaClipboardList, "#" + C.white),
    build: await iconPng(FaBuilding, "#" + C.white),
    leaf: await iconPng(FaLeaf, "#" + C.white),
    mtn: await iconPng(FaMountain, "#" + C.white),
    chartD: await iconPng(FaChartBar, "#" + C.forest),
    searchD: await iconPng(FaSearchDollar, "#" + C.forest),
    checkD: await iconPng(FaCheckCircle, "#" + C.forest),
    usersD: await iconPng(FaUsers, "#" + C.forest),
    handD: await iconPng(FaHandHoldingUsd, "#" + C.forest),
    mapD: await iconPng(FaMapMarkerAlt, "#" + C.forest),
    seedD: await iconPng(FaSeedling, "#" + C.forest),
    warnD: await iconPng(FaExclamationTriangle, "#" + C.amber),
    leafD: await iconPng(FaLeaf, "#" + C.green),
    buildD: await iconPng(FaBuilding, "#" + C.navy),
    industryD: await iconPng(FaIndustry, "#" + C.navy),
  };

  // ════════════════════════════════════════════════════════════════
  //  HELPER: Add metric cards (2x4 or 2x3 grid)
  // ════════════════════════════════════════════════════════════════
  function addMetricCards(slide, cards, opts = {}) {
    const cols = opts.cols || (cards.length > 6 ? 4 : 3);
    const cardW = opts.cardW || (cols === 4 ? 2.12 : 2.8);
    const cardH = opts.cardH || 1.5;
    const gapX = 0.16, gapY = 0.18;
    const startX = opts.startX || (10 - cols * cardW - (cols - 1) * gapX) / 2;
    const startY = opts.startY || 1.1;
    const accentColor = opts.accentColor || C.sage;
    const valColor = opts.valColor || C.forest;

    cards.forEach((c, i) => {
      const col = i % cols, row = Math.floor(i / cols);
      const cx = startX + col * (cardW + gapX);
      const cy = startY + row * (cardH + gapY);
      slide.addShape(pres.shapes.RECTANGLE, {
        x: cx, y: cy, w: cardW, h: cardH,
        fill: { color: C.white }, shadow: makeShadow()
      });
      slide.addShape(pres.shapes.RECTANGLE, {
        x: cx, y: cy, w: 0.06, h: cardH, fill: { color: accentColor }
      });
      if (c.icon) {
        slide.addImage({ data: c.icon, x: cx + 0.15, y: cy + 0.12, w: 0.3, h: 0.3 });
      }
      slide.addText(c.label, {
        x: cx + (c.icon ? 0.52 : 0.18), y: cy + 0.1, w: cardW - (c.icon ? 0.62 : 0.3), h: 0.3,
        fontSize: 9, fontFace: "Calibri", color: C.gray, margin: 0
      });
      slide.addText(String(c.val), {
        x: cx + 0.15, y: cy + 0.55, w: cardW - 0.3, h: 0.45,
        fontSize: cols === 4 ? 18 : 20, fontFace: "Georgia", color: valColor, bold: true, margin: 0
      });
      if (c.sub) {
        slide.addText(c.sub, {
          x: cx + 0.15, y: cy + 1.0, w: cardW - 0.3, h: 0.3,
          fontSize: 8.5, fontFace: "Calibri", color: C.gray, italic: true, margin: 0
        });
      }
    });
  }

  // ════════════════════════════════════════════════════════════════
  //  HELPER: Add pipeline row
  // ════════════════════════════════════════════════════════════════
  function addPipeline(slide, pipeline, dictamen, y) {
    if (!pipeline || pipeline.length === 0) return;
    slide.addText("Pipeline del Proceso SAC", {
      x: 0.6, y: y - 0.32, w: 5, h: 0.25,
      fontSize: 10, fontFace: "Calibri", color: C.dark, bold: true, margin: 0
    });
    const pColors = {
      "Notificado": { bg: C.lightGray, txt: C.dark },
      "Programado": { bg: C.sage, txt: C.forest },
      "Reprogramado": { bg: C.gold, txt: C.dark },
      "Cerrado": { bg: C.green, txt: C.white },
    };
    // Always show all 4 standard stages
    const stdStages = ["Notificado", "Programado", "Reprogramado", "Cerrado"];
    const pipeMap = {};
    pipeline.forEach(p => { pipeMap[p.label] = p.val; });
    const fullPipeline = stdStages.map(label => ({
      label, val: pipeMap[label] || 0
    }));
    const maxItems = fullPipeline.length;
    const pW = (9 - (maxItems - 1) * 0.18) / maxItems;
    const pGap = 0.18;
    fullPipeline.forEach((p, i) => {
      const px = 0.6 + i * (pW + pGap);
      const colors = pColors[p.label] || { bg: C.lightGray, txt: C.dark };
      slide.addShape(pres.shapes.RECTANGLE, {
        x: px, y: y, w: pW, h: 0.6, fill: { color: colors.bg }
      });
      slide.addText(p.label, {
        x: px, y: y + 0.03, w: pW, h: 0.22,
        fontSize: 9, fontFace: "Calibri", color: colors.txt, align: "center", margin: 0
      });
      slide.addText(fmtNum(p.val), {
        x: px, y: y + 0.23, w: pW, h: 0.32,
        fontSize: 16, fontFace: "Georgia", color: colors.txt, bold: true, align: "center", margin: 0
      });
      if (i < maxItems - 1) {
        slide.addText("\u25B6", {
          x: px + pW, y: y + 0.1, w: pGap, h: 0.35,
          fontSize: 12, color: C.gray, align: "center", margin: 0
        });
      }
    });

    // Dictamen line
    if (dictamen && Object.keys(dictamen).length > 0) {
      const dictParts = Object.entries(dictamen).map(([k, v]) => `${v} ${k.toLowerCase()}`);
      slide.addText("Dictamen: " + dictParts.join(" \u00B7 "), {
        x: 0.6, y: y + 0.68, w: 8.8, h: 0.2,
        fontSize: 9, fontFace: "Calibri", color: C.dark, italic: true, margin: 0
      });
    }
  }

  // ════════════════════════════════════════════════════════════════
  //  HELPER: Add header bar
  // ════════════════════════════════════════════════════════════════
  function addHeaderBar(slide, title, color) {
    const barColor = color || C.forest;
    slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: barColor } });
    slide.addText(title, {
      x: 0.5, y: 0.12, w: 9, h: 0.65, fontSize: 20, fontFace: "Georgia",
      color: C.white, bold: true, margin: 0
    });
  }

  // ════════════════════════════════════════════════════════════════
  //  HELPER: Add table
  // ════════════════════════════════════════════════════════════════
  function addDataTable(slide, headers, rows, opts = {}) {
    const x = opts.x || 0.25, y = opts.y || 1.1, w = opts.w || 9.5;
    const hdrColor = opts.hdrColor || C.forest;
    const hdrOpts = { fill: { color: hdrColor }, color: C.white, bold: true, fontSize: 9, fontFace: "Calibri", align: "center" };
    let tblData = [headers.map(h => ({ text: h, options: hdrOpts }))];
    rows.forEach((r, i) => {
      const bg = i % 2 === 0 ? C.white : C.lightGray;
      tblData.push(r.map((cell, j) => {
        const isNum = j > 0;
        return { text: String(cell), options: { fontSize: 8.5, fontFace: "Calibri", color: C.dark, fill: { color: bg }, align: isNum ? "right" : "left" } };
      }));
    });
    const colW = opts.colW || headers.map(() => w / headers.length);
    slide.addTable(tblData, { x, y, w, colW, border: { pt: 0.3, color: C.lightGray } });
  }

  // ════════════════════════════════════════════════════════════════
  //  HELPER: Add insight box with dynamic insights
  // ════════════════════════════════════════════════════════════════
  function addInsightBox(slide, insights, x, y, w, h) {
    if (!insights || insights.length === 0) return;
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y, w, h, fill: { color: C.white }, shadow: makeShadow()
    });
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y, w, h: 0.06, fill: { color: C.gold }
    });
    slide.addText("Observaciones", {
      x: x + 0.2, y: y + 0.15, w: w - 0.4, h: 0.35,
      fontSize: 13, fontFace: "Georgia", color: C.navy, bold: true, margin: 0
    });

    const textRuns = [];
    insights.forEach((ins, i) => {
      if (i > 0) textRuns.push({ text: "\n", options: { breakLine: true, fontSize: 5 } });
      textRuns.push({ text: ins.title, options: { bold: true, breakLine: true, fontSize: 10, color: C.dark } });
      textRuns.push({ text: ins.text, options: { breakLine: true, fontSize: 10, color: C.gray } });
    });
    slide.addText(textRuns, { x: x + 0.2, y: y + 0.55, w: w - 0.4, h: h - 0.7, valign: "top", margin: 0 });
  }

  // ════════════════════════════════════════════════════════════════
  //  HELPER: Add highlight box for selected items
  // ════════════════════════════════════════════════════════════════
  function addHighlightBox(slide, text, x, y, w) {
    slide.addShape(pres.shapes.RECTANGLE, {
      x, y, w, h: 0.65,
      fill: { color: C.mint, transparency: 60 },
      line: { color: C.green, width: 1.5 }
    });
    slide.addText(text, {
      x: x + 0.2, y: y + 0.08, w: w - 0.4, h: 0.45,
      fontSize: 11, fontFace: "Calibri", color: C.forest, bold: true, margin: 0
    });
  }

  // ════════════════════════════════════════════════════════════════
  //  PORTADA
  // ════════════════════════════════════════════════════════════════
  const s1 = pres.addSlide();
  s1.background = { color: C.forest };
  s1.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.gold } });
  s1.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0.06, w: 0.12, h: 5.565, fill: { color: C.sage } });

  s1.addText("SEGURO AGRI\u0301COLA CATASTRO\u0301FICO", {
    x: 0.7, y: 1.0, w: 8.6, h: 0.7, fontSize: 32, fontFace: "Georgia",
    color: C.gold, bold: true, charSpacing: 3, margin: 0
  });
  s1.addText("SAC 2025\u20132026", {
    x: 0.7, y: 1.7, w: 8.6, h: 0.6, fontSize: 26, fontFace: "Georgia",
    color: C.white, margin: 0
  });
  s1.addShape(pres.shapes.LINE, { x: 0.7, y: 2.5, w: 3.5, h: 0, line: { color: C.gold, width: 2 } });

  // Dynamic subtitle
  const scopeLabels = { nacional: "Resumen Nacional", departamental: "Resumen Departamental",
    provincial: "Resumen Provincial", distrital: "Resumen Distrital" };
  let geoLine = scopeLabels[DATA.scope] || "Resumen";
  if (DATA.filtros.deptos.length > 0) geoLine += " \u00B7 " + DATA.filtros.deptos.join(", ");
  if (DATA.filtros.provs.length > 0) geoLine += "\n" + DATA.filtros.provs.join(", ");
  if (DATA.filtros.dists.length > 0) geoLine += "\n" + DATA.filtros.dists.slice(0, 5).join(", ");

  s1.addText(geoLine, {
    x: 0.7, y: 2.8, w: 8.6, h: 0.8, fontSize: 16, fontFace: "Calibri",
    color: C.mint, italic: true, margin: 0
  });

  let infoLine = `Corte: ${DATA.fecha_corte}`;
  if (DATA.filtros.tipos.length > 0) infoLine += ` \u00B7 ${DATA.filtros.tipos.join(", ")}`;
  if (DATA.filtros.empresa !== "ambas") infoLine += ` \u00B7 ${DATA.filtros.empresa}`;
  if (DATA.filtros.fecha_inicio) infoLine += ` \u00B7 ${DATA.filtros.fecha_inicio} a ${DATA.filtros.fecha_fin}`;

  s1.addText(infoLine, {
    x: 0.7, y: 3.7, w: 8.6, h: 0.4, fontSize: 12, fontFace: "Calibri", color: C.cream, margin: 0
  });
  s1.addText("Direcci\u00F3n de Seguro y Fomento del Financiamiento Agrario \u2014 MIDAGRI", {
    x: 0.7, y: 4.8, w: 8.6, h: 0.35, fontSize: 11, fontFace: "Calibri", color: C.sage, margin: 0
  });
  s1.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.565, w: 10, h: 0.06, fill: { color: C.gold } });

  // ════════════════════════════════════════════════════════════════
  //  PROCESS EACH SECTION
  // ════════════════════════════════════════════════════════════════
  for (const section of DATA.sections) {

    if (section.type === "nacional") {
      // ── Nacional: Métricas ──
      const s = pres.addSlide();
      s.background = { color: C.cream };
      addHeaderBar(s, "RESUMEN NACIONAL SAC 2025\u20132026");

      const m = section.metricas;
      const empData = section.empresas || [];
      const cards = [
        { icon: icons.chartD, label: "Avisos de Siniestro", val: fmtNum(m.avisos), sub: "Total campaña" },
        { icon: icons.checkD, label: "Evaluados (Cerrados)", val: fmtNum(m.cerrados), sub: `${fmtPct(m.pct_eval)} del total` },
        { icon: icons.searchD, label: "Indemnización", val: fmtMoney(m.indemnizacion), sub: "Reconocida" },
        { icon: icons.handD, label: "Desembolso", val: fmtMoney(m.desembolso), sub: `${fmtPct(m.pct_desembolso)} de indemnización` },
        { icon: icons.seedD, label: "Ha Indemnizadas", val: fmtNum(m.ha_indemnizadas), sub: "Con evaluación cerrada" },
        { icon: icons.usersD, label: "Productores", val: fmtNum(m.productores), sub: "Beneficiados" },
      ];
      // Add empresa cards if available
      empData.forEach(e => {
        cards.push({
          icon: icons.buildD, label: e.empresa,
          val: `${fmtNum(e.avisos)} avisos`,
          sub: `${fmtPct(e.pct_eval)} cerrados \u00B7 ${fmtMoney(e.indemnizacion)}`
        });
      });

      addMetricCards(s, cards, { cols: cards.length > 6 ? 4 : 3 });

      // Pipeline
      if (section.pipeline.length > 0) {
        const pipeY = cards.length > 6 ? 4.6 : 4.35;
        addPipeline(s, section.pipeline, section.dictamen, pipeY);
      }

      // ── Nacional: Top Departamentos chart ──
      if (section.top_deptos && section.top_deptos.length > 0) {
        const sc = pres.addSlide();
        sc.background = { color: C.cream };
        addHeaderBar(sc, "TOP DEPARTAMENTOS POR INDEMNIZACIÓN");

        const labels = section.top_deptos.map(d => d.name);
        const values = section.top_deptos.map(d => d.indem || 0);
        sc.addChart(pres.charts.BAR, [{
          name: "Indemnización (S/)", labels, values
        }], {
          x: 0.3, y: 1.1, w: 9.4, h: 4.2, barDir: "bar",
          chartColors: [C.green],
          chartArea: { fill: { color: C.white }, roundedCorners: true },
          catAxisLabelColor: C.dark, catAxisLabelFontSize: 9,
          valAxisLabelColor: C.gray, valAxisLabelFontSize: 8,
          valGridLine: { color: C.lightGray, size: 0.5 },
          catGridLine: { style: "none" },
          showValue: true, dataLabelPosition: "outEnd",
          dataLabelColor: C.dark, dataLabelFontSize: 8,
          valAxisNumFmt: "#,##0", showLegend: false
        });
        sc.addText(`Fuente: DSFFA — MIDAGRI. Corte: ${DATA.fecha_corte}.`, {
          x: 0.5, y: 5.2, w: 9, h: 0.25, fontSize: 8, fontFace: "Calibri", color: C.gray, italic: true, margin: 0
        });
      }

      // ── Nacional: Tipo siniestro (pie + table) ──
      if (section.tipos && section.tipos.length > 0) {
        const st = pres.addSlide();
        st.background = { color: C.cream };
        addHeaderBar(st, "DISTRIBUCIÓN POR TIPO DE SINIESTRO");

        const tipoLabels = section.tipos.map(t => t.tipo);
        const tipoValues = section.tipos.map(t => t.avisos);
        const pieColors = [C.forest, C.green, C.sage, C.blue, C.amber, C.gold, C.mint, C.red, C.lightGray, C.navy];
        st.addChart(pres.charts.PIE, [{
          name: "Avisos", labels: tipoLabels, values: tipoValues
        }], {
          x: 0.2, y: 1.1, w: 4.5, h: 4.0,
          showPercent: true, showLegend: true, legendPos: "b", legendFontSize: 8,
          chartColors: pieColors, dataLabelFontSize: 8
        });

        // Table right
        const tipoHeaders = ["Tipo", "Avisos", "Indemnización"];
        const tipoRows = section.tipos.slice(0, 10).map(t => [t.tipo, fmtNum(t.avisos), fmtMoney(t.indem || 0)]);
        addDataTable(st, tipoHeaders, tipoRows, { x: 5.0, y: 1.2, w: 4.6, colW: [1.8, 1.1, 1.7] });

        // Nacional insights box below table
        addInsightBox(st, section.insights || [], 5.0, 1.2 + (Math.min(section.tipos.length, 10) + 1) * 0.35 + 0.25, 4.6, 1.8);
      }
    }

    if (section.type === "departamental") {
      // ── Separador ──
      const sep = pres.addSlide();
      sep.background = { color: C.navy };
      sep.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.gold } });
      sep.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.565, w: 10, h: 0.06, fill: { color: C.gold } });
      sep.addImage({ data: icons.mtn, x: 4.5, y: 1.3, w: 1, h: 1 });
      sep.addText(section.name, {
        x: 1, y: 2.5, w: 8, h: 0.8, fontSize: 36, fontFace: "Georgia",
        color: C.gold, bold: true, align: "center", charSpacing: 5, margin: 0
      });
      sep.addText("Resumen Departamental SAC 2025\u20132026", {
        x: 1, y: 3.3, w: 8, h: 0.5, fontSize: 16, fontFace: "Calibri",
        color: C.cream, align: "center", margin: 0
      });
      const sepInfo = [`${fmtNum(section.metricas.avisos)} avisos`, `${section.n_provincias || ""} provincias`];
      if (section.empresa_comp) sepInfo.push(section.empresa_comp);
      sep.addText(sepInfo.filter(Boolean).join(" \u00B7 "), {
        x: 1, y: 3.9, w: 8, h: 0.4, fontSize: 13, fontFace: "Calibri",
        color: C.sage, align: "center", italic: true, margin: 0
      });

      // ── Métricas ──
      const sm = pres.addSlide();
      sm.background = { color: C.cream };
      addHeaderBar(sm, `${section.name} — INDICADORES CLAVE`, C.navy);

      const m = section.metricas;
      const cards = [
        { icon: icons.chartD, label: "Total Avisos", val: fmtNum(m.avisos), sub: "Campaña completa" },
        { icon: icons.checkD, label: "Evaluados (Cerrados)", val: fmtNum(m.cerrados), sub: `${fmtPct(m.pct_eval)} del total` },
        { icon: icons.searchD, label: "Indemnización", val: fmtMoney(m.indemnizacion), sub: "Reconocida" },
        { icon: icons.handD, label: "Desembolso", val: fmtMoney(m.desembolso), sub: `${fmtPct(m.pct_desembolso)} de indemnización` },
        { icon: icons.seedD, label: "Ha Indemnizadas", val: fmtNum(m.ha_indemnizadas), sub: "Con evaluación cerrada" },
        { icon: icons.usersD, label: "Productores", val: fmtNum(m.productores), sub: "Beneficiados" },
      ];
      addMetricCards(sm, cards, { accentColor: C.gold, valColor: C.navy });
      addPipeline(sm, section.pipeline, section.dictamen, 4.5);

      // ── Tabla de provincias ──
      if (section.provincias && section.provincias.length > 0) {
        const sp = pres.addSlide();
        sp.background = { color: C.cream };
        addHeaderBar(sp, `${section.name} — AVANCE POR PROVINCIA`, C.navy);

        const headers = ["Provincia", "Avisos", "Cerrados", "% Eval.", "Indemnización", "Desembolso", "Ha", "Productores"];
        const rows = section.provincias.map(p => {
          const pctE = p.avisos > 0 ? ((p.indem > 0 ? p.avisos : 0) / p.avisos * 100) : 0;
          return [p.name, fmtNum(p.avisos), "—", "—",
            p.indem ? fmtMoney(p.indem) : "—", p.desemb ? fmtMoney(p.desemb) : "—",
            p.ha ? String(p.ha) : "—", p.prod ? fmtNum(p.prod) : "—"];
        });
        addDataTable(sp, headers, rows, { colW: [1.4, 0.7, 0.8, 0.7, 1.2, 1.2, 0.7, 0.7] });

        // Highlight box for selected provinces
        if (section.provs_seleccionadas && section.provs_seleccionadas.length > 0) {
          const selProvs = section.provincias.filter(p => section.provs_seleccionadas.includes(p.name));
          if (selProvs.length > 0) {
            const combined = selProvs.map(p => p.name).join(" y ");
            const combAvisos = selProvs.reduce((s, p) => s + p.avisos, 0);
            const combIndem = selProvs.reduce((s, p) => s + (p.indem || 0), 0);
            const hlText = `Foco: ${combined} — ${fmtNum(combAvisos)} avisos, ${fmtMoney(combIndem)} indemnización`;
            const hlY = 1.1 + (Math.min(rows.length, 15) + 1) * 0.35 + 0.25;
            addHighlightBox(sp, hlText, 0.25, Math.min(hlY, 4.8), 9.5);
          }
        }
      }

      // ── Tipo siniestro chart ──
      if (section.tipos && section.tipos.length > 0) {
        const stc = pres.addSlide();
        stc.background = { color: C.cream };
        addHeaderBar(stc, `${section.name} — SINIESTROS POR TIPO`, C.navy);

        stc.addChart(pres.charts.BAR, [{
          name: "Avisos",
          labels: section.tipos.map(t => t.tipo),
          values: section.tipos.map(t => t.avisos)
        }], {
          x: 0.3, y: 1.1, w: 5.5, h: 4.2, barDir: "bar",
          chartColors: [C.navy],
          chartArea: { fill: { color: C.white }, roundedCorners: true },
          catAxisLabelColor: C.dark, catAxisLabelFontSize: 9,
          valAxisLabelColor: C.gray, valAxisLabelFontSize: 8,
          valGridLine: { color: C.lightGray, size: 0.5 },
          catGridLine: { style: "none" },
          showValue: true, dataLabelPosition: "outEnd",
          dataLabelColor: C.dark, dataLabelFontSize: 9,
          showLegend: false
        });

        // Insight box from dynamic insights
        addInsightBox(stc, section.insights || [], 6.1, 1.3, 3.6, 3.5);
      }
    }

    if (section.type === "provincial") {
      // ── Separador provincial ──
      const sep = pres.addSlide();
      sep.background = { color: C.forest };
      sep.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.gold } });
      sep.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.565, w: 10, h: 0.06, fill: { color: C.gold } });
      sep.addImage({ data: icons.leaf, x: 4.5, y: 1.3, w: 1, h: 1 });
      sep.addText(section.name, {
        x: 1, y: 2.5, w: 8, h: 0.8, fontSize: 34, fontFace: "Georgia",
        color: C.gold, bold: true, align: "center", charSpacing: 4, margin: 0
      });
      sep.addText(`${section.depto} — SAC 2025\u20132026`, {
        x: 1, y: 3.3, w: 8, h: 0.5, fontSize: 16, fontFace: "Calibri",
        color: C.cream, align: "center", margin: 0
      });
      const provSepInfo = [`${fmtNum(section.metricas.avisos)} avisos`, fmtMoney(section.metricas.indemnizacion)];
      if (section.empresa_comp) provSepInfo.push(section.empresa_comp);
      sep.addText(provSepInfo.join(" \u00B7 "), {
        x: 1, y: 3.9, w: 8, h: 0.4, fontSize: 13, fontFace: "Calibri",
        color: C.mint, align: "center", italic: true, margin: 0
      });

      // ── Detalle provincial: cards left + tables right ──
      const sp = pres.addSlide();
      sp.background = { color: C.cream };
      addHeaderBar(sp, `PROVINCIA DE ${section.name}`);

      const m = section.metricas;
      const provCards = [
        { icon: icons.chartD, label: "Total Avisos", val: fmtNum(m.avisos), sub: `${fmtPct(m.pct_eval)} evaluados` },
        { icon: icons.searchD, label: "Indemnización", val: fmtMoney(m.indemnizacion), sub: `Desembolso: ${fmtMoney(m.desembolso)} (${fmtPct(m.pct_desembolso)})` },
        { icon: icons.seedD, label: "Ha / Productores", val: `${fmtNum(m.ha_indemnizadas)} ha \u00B7 ${fmtNum(m.productores)}`, sub: "Con evaluación cerrada" },
      ];
      const jcW = 4.2, jcH = 1.15, jcGap = 0.2;
      provCards.forEach((c, i) => {
        const cy = 1.15 + i * (jcH + jcGap);
        sp.addShape(pres.shapes.RECTANGLE, {
          x: 0.5, y: cy, w: jcW, h: jcH,
          fill: { color: C.white }, shadow: makeShadow()
        });
        sp.addShape(pres.shapes.RECTANGLE, {
          x: 0.5, y: cy, w: 0.06, h: jcH, fill: { color: C.sage }
        });
        if (c.icon) sp.addImage({ data: c.icon, x: 0.68, y: cy + 0.1, w: 0.28, h: 0.28 });
        sp.addText(c.label, {
          x: 1.05, y: cy + 0.08, w: jcW - 0.7, h: 0.28,
          fontSize: 9, fontFace: "Calibri", color: C.gray, margin: 0
        });
        sp.addText(String(c.val), {
          x: 0.68, y: cy + 0.42, w: jcW - 0.35, h: 0.35,
          fontSize: 18, fontFace: "Georgia", color: C.forest, bold: true, margin: 0
        });
        if (c.sub) sp.addText(c.sub, {
          x: 0.68, y: cy + 0.82, w: jcW - 0.35, h: 0.25,
          fontSize: 8.5, fontFace: "Calibri", color: C.gray, italic: true, margin: 0
        });
      });

      // District table right
      if (section.distritos && section.distritos.length > 0) {
        const dHeaders = ["Distrito", "Avisos", "Indemniz.", "Ha"];
        const dRows = section.distritos.map(d => [d.name, fmtNum(d.avisos), d.indem ? fmtMoney(d.indem) : "\u2014", d.ha ? String(d.ha) : "\u2014"]);
        addDataTable(sp, dHeaders, dRows, { x: 5.2, y: 1.15, w: 4.4, colW: [1.7, 0.7, 1.0, 1.0] });
      }

      // Tipo table right below
      if (section.tipos && section.tipos.length > 0) {
        const tHeaders = ["Tipo Siniestro", "Avisos", "Indemniz."];
        const tRows = section.tipos.slice(0, 6).map(t => [t.tipo, fmtNum(t.avisos), t.indem ? fmtMoney(t.indem) : "\u2014"]);
        const tY = section.distritos && section.distritos.length > 0 ?
          1.15 + (Math.min(section.distritos.length, 8) + 1) * 0.35 + 0.3 : 1.15;
        addDataTable(sp, tHeaders, tRows, { x: 5.2, y: Math.min(tY, 3.5), w: 4.4, colW: [1.8, 0.8, 1.8] });
      }

      // Pipeline on this slide
      // Pipeline goes on its own slide for provincial
      const sPipe = pres.addSlide();
      sPipe.background = { color: C.cream };
      addHeaderBar(sPipe, `${section.name} — PROCESO SAC`);
      addPipeline(sPipe, section.pipeline, section.dictamen, 1.5);

      // Add summary metrics below pipeline
      const mp = section.metricas;
      sPipe.addShape(pres.shapes.RECTANGLE, {
        x: 0.5, y: 3.0, w: 9, h: 1.6,
        fill: { color: C.white }, shadow: makeShadow()
      });
      sPipe.addShape(pres.shapes.RECTANGLE, {
        x: 0.5, y: 3.0, w: 9, h: 0.06, fill: { color: C.sage }
      });
      sPipe.addText("Resumen del proceso", {
        x: 0.7, y: 3.15, w: 3, h: 0.3,
        fontSize: 12, fontFace: "Georgia", color: C.forest, bold: true, margin: 0
      });
      sPipe.addText([
        { text: `${fmtNum(mp.avisos)} avisos totales`, options: { bold: true, breakLine: true, fontSize: 11, color: C.dark } },
        { text: `${fmtNum(mp.cerrados)} evaluaciones cerradas (${fmtPct(mp.pct_eval)})`, options: { breakLine: true, fontSize: 11, color: C.gray } },
        { text: `${fmtMoney(mp.indemnizacion)} indemnizaci\u00F3n reconocida`, options: { breakLine: true, fontSize: 11, color: C.gray } },
        { text: `${fmtMoney(mp.desembolso)} desembolsado (${fmtPct(mp.pct_desembolso)})`, options: { fontSize: 11, color: C.gray } },
      ], { x: 0.7, y: 3.5, w: 4.3, h: 1.0, valign: "top", margin: 0 });

      // Provincial insights box
      addInsightBox(sPipe, section.insights || [], 5.2, 3.0, 4.3, 1.6);
    }

    if (section.type === "distrital") {
      // ── Separador distrital ──
      const sep = pres.addSlide();
      sep.background = { color: C.navy };
      sep.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.gold } });
      sep.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.565, w: 10, h: 0.06, fill: { color: C.gold } });
      sep.addImage({ data: icons.map, x: 4.5, y: 1.5, w: 0.8, h: 0.8 });
      sep.addText(`DISTRITO: ${section.name}`, {
        x: 1, y: 2.5, w: 8, h: 0.7, fontSize: 30, fontFace: "Georgia",
        color: C.gold, bold: true, align: "center", margin: 0
      });
      sep.addText(`${section.depto} / ${section.prov}`, {
        x: 1, y: 3.2, w: 8, h: 0.5, fontSize: 14, fontFace: "Calibri",
        color: C.cream, align: "center", margin: 0
      });

      // ── Métricas distrito ──
      const sd = pres.addSlide();
      sd.background = { color: C.cream };
      addHeaderBar(sd, `DISTRITO: ${section.name}`);

      const m = section.metricas;
      const dCards = [
        { icon: icons.chartD, label: "Avisos", val: fmtNum(m.avisos), sub: `${fmtPct(m.pct_eval)} evaluados` },
        { icon: icons.checkD, label: "Cerrados", val: fmtNum(m.cerrados), sub: "Evaluaciones cerradas" },
        { icon: icons.searchD, label: "Indemnización", val: fmtMoney(m.indemnizacion), sub: "Reconocida" },
        { icon: icons.handD, label: "Desembolso", val: fmtMoney(m.desembolso), sub: `${fmtPct(m.pct_desembolso)} desembolsado` },
        { icon: icons.seedD, label: "Ha Indemnizadas", val: fmtNum(m.ha_indemnizadas), sub: "" },
        { icon: icons.usersD, label: "Productores", val: fmtNum(m.productores), sub: "Beneficiados" },
      ];
      addMetricCards(sd, dCards);
      addPipeline(sd, section.pipeline, null, 4.5);
    }
  }

  // ════════════════════════════════════════════════════════════════
  //  CIERRE
  // ════════════════════════════════════════════════════════════════
  const sEnd = pres.addSlide();
  sEnd.background = { color: C.forest };
  sEnd.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.55, w: 10, h: 0.075, fill: { color: C.gold } });
  sEnd.addText("Gracias", {
    x: 1, y: 1.5, w: 8, h: 1, fontSize: 36, fontFace: "Georgia",
    color: C.white, bold: true, align: "center", margin: 0
  });
  sEnd.addText([
    { text: "Seguro Agr\u00EDcola Catastr\u00F3fico \u2014 Campa\u00F1a 2025\u20132026", options: { breakLine: true, fontSize: 13 } },
    { text: "Direcci\u00F3n de Seguro y Fomento del Financiamiento Agrario", options: { breakLine: true, fontSize: 12 } },
    { text: "Ministerio de Desarrollo Agrario y Riego \u2014 MIDAGRI", options: { fontSize: 12 } },
  ], {
    x: 1.5, y: 2.8, w: 7, h: 1.2, fontFace: "Calibri",
    color: C.mint, align: "center", margin: 0
  });
  sEnd.addText(`Datos al ${DATA.fecha_corte}`, {
    x: 1, y: 4.3, w: 8, h: 0.4, fontSize: 10, fontFace: "Calibri",
    color: C.gold, align: "center", margin: 0
  });

  // ════════════════════════════════════════════════════════════════
  //  SAVE
  // ════════════════════════════════════════════════════════════════
  await pres.writeFile({ fileName: "%%OUTPUT_PATH%%" });
  console.log("OK");
})();
'''


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def _find_node():
    """Busca el ejecutable de Node.js y el NODE_PATH adecuado."""
    import shutil
    node_exe = shutil.which("node")
    if not node_exe:
        # Intenta rutas comunes en Windows y Linux
        common = [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
        ]
        # Agregar rutas de usuario en Windows (nvm-windows, Chocolatey, etc.)
        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
        if appdata:
            common.append(os.path.join(appdata, "nvm", "current", "node.exe"))
            common.append(os.path.join(appdata, "npm", "node.exe"))
        if localappdata:
            common.append(os.path.join(localappdata, "Programs", "node", "node.exe"))
        if userprofile:
            # nvm-windows instala en %APPDATA%\nvm\<version>\node.exe
            nvm_dir = os.path.join(appdata or userprofile, "nvm")
            if os.path.isdir(nvm_dir):
                # Buscar la versión más reciente
                versions = [d for d in os.listdir(nvm_dir) if d.startswith("v")]
                if versions:
                    versions.sort(reverse=True)
                    common.append(os.path.join(nvm_dir, versions[0], "node.exe"))
        # Linux/Mac
        common.extend([
            os.path.expanduser("~/.nvm/current/bin/node"),
            "/usr/local/bin/node",
            "/usr/bin/node",
        ])

        for p in common:
            if os.path.isfile(p):
                node_exe = p
                break

    if not node_exe:
        raise FileNotFoundError(
            "Node.js no encontrado. Instálalo desde https://nodejs.org/ "
            "y asegúrate de que 'node' esté en el PATH del sistema. "
            "Después de instalar, REINICIA la terminal y Streamlit."
        )

    # Detectar node_modules: priorizar local, luego global
    node_paths = []
    # 1. node_modules junto al script (donde hicimos npm install)
    local_nm = os.path.join(os.path.dirname(os.path.abspath(__file__)), "node_modules")
    if os.path.isdir(local_nm):
        node_paths.append(local_nm)
    # 2. Global npm paths (usando os.pathsep para Windows compatibilidad)
    try:
        sep = os.pathsep  # ';' en Windows, ':' en Linux/Mac
        res = subprocess.run(
            [node_exe, "-e", f"console.log(require('module').globalPaths.join('{sep}'))"],
            capture_output=True, text=True, timeout=10
        )
        if res.returncode == 0 and res.stdout.strip():
            node_paths.extend(res.stdout.strip().split(sep))
    except Exception:
        pass
    # 3. Fallback conocidos
    fallbacks = []
    if appdata:
        fallbacks.append(os.path.join(appdata, "npm", "node_modules"))
    if userprofile:
        fallbacks.append(os.path.join(userprofile, "node_modules"))
    fallbacks.extend([
        "/sessions/serene-nice-archimedes/.npm-global/lib/node_modules",
        os.path.expanduser("~/.npm-global/lib/node_modules"),
        "/usr/local/lib/node_modules",
        "/usr/lib/node_modules",
    ])
    for p in fallbacks:
        if os.path.isdir(p) and p not in node_paths:
            node_paths.append(p)

    return node_exe, os.pathsep.join(node_paths)


def _check_node_deps(node_exe, node_path_env):
    """Verifica que las dependencias npm estén instaladas, si no, instala."""
    required = ["pptxgenjs", "react", "react-dom", "sharp", "react-icons"]
    env = os.environ.copy()
    env["NODE_PATH"] = node_path_env

    missing = []
    for pkg in required:
        res = subprocess.run(
            [node_exe, "-e", f"require('{pkg}')"],
            capture_output=True, text=True, timeout=10, env=env
        )
        if res.returncode != 0:
            missing.append(pkg)

    if missing:
        # Intentar instalar globalmente
        install_dir = os.path.dirname(os.path.abspath(__file__))
        npm_exe = os.path.join(os.path.dirname(node_exe), "npm")
        if os.name == "nt":
            npm_exe = os.path.join(os.path.dirname(node_exe), "npm.cmd")
        if not os.path.isfile(npm_exe):
            import shutil
            npm_exe = shutil.which("npm") or shutil.which("npm.cmd") or "npm"

        try:
            subprocess.run(
                [npm_exe, "install", "--save"] + missing,
                cwd=install_dir, capture_output=True, text=True, timeout=120
            )
        except Exception as e:
            raise RuntimeError(
                f"Faltan dependencias npm: {', '.join(missing)}. "
                f"Ejecuta: cd {install_dir} && npm install {' '.join(missing)}"
            ) from e


def generar_ppt_dinamico(df, filtros, fecha_corte):
    """
    Genera una presentación PPT dinámica con PptxGenJS.

    Args:
        df: DataFrame consolidado (datos["midagri"])
        filtros: dict con selecciones del usuario
        fecha_corte: string con fecha de corte

    Returns:
        bytes del archivo .pptx
    """
    # 0. Find Node.js
    node_exe, node_path_env = _find_node()
    _check_node_deps(node_exe, node_path_env)

    # 1. Prepare data
    data = _prepare_data(df, filtros, fecha_corte)

    # 2. Create temp files
    tmp_dir = tempfile.mkdtemp()
    js_path = os.path.join(tmp_dir, "gen_ppt.js")
    out_path = os.path.join(tmp_dir, "output.pptx")

    # 3. Generate JS
    data_json = json.dumps(data, ensure_ascii=False, default=str)
    js_code = JS_TEMPLATE.replace("%%DATA_JSON%%", data_json)
    js_code = js_code.replace("%%OUTPUT_PATH%%", out_path.replace("\\", "/"))

    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_code)

    # 4. Run Node.js
    env = os.environ.copy()
    env["NODE_PATH"] = node_path_env

    result = subprocess.run(
        [node_exe, js_path],
        capture_output=True, text=True, timeout=60, env=env
    )

    if result.returncode != 0:
        raise RuntimeError(f"PptxGenJS error: {result.stderr[:500]}")

    # 5. Read output
    with open(out_path, "rb") as f:
        ppt_bytes = f.read()

    # 6. Cleanup
    try:
        os.remove(js_path)
        os.remove(out_path)
        os.rmdir(tmp_dir)
    except Exception:
        pass

    return ppt_bytes
