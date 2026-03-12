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
    productores = int(df["N_PRODUCTORES"].sum()) if _safe_col(df, "N_PRODUCTORES") else 0
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
        agg["Productores"] = ("N_PRODUCTORES", "sum")
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


# ══════════════════════════════════════════════════════════════════
# PREPARAR DATA PARA NODE.JS
# ══════════════════════════════════════════════════════════════════

def _prepare_data(df, filtros, fecha_corte):
    """Prepara toda la data en un dict JSON-serializable para Node."""
    scope = filtros.get("scope", "nacional")
    deptos = filtros.get("departamentos", [])
    provs = filtros.get("provincias", [])
    dists = filtros.get("distritos", [])

    # Aplicar filtros NO geográficos
    filtros_base = {k: v for k, v in filtros.items()
                    if k not in ("departamentos", "provincias", "distritos", "scope")}
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

    # ── Nacional ──
    if scope == "nacional" or not deptos:
        m = _calcular_metricas(df_base)
        data["sections"].append({
            "type": "nacional",
            "metricas": m,
            "pipeline": _calcular_pipeline(df_base),
            "dictamen": _dictamen_breakdown(df_base),
            "empresas": _empresa_breakdown(df_base),
            "top_deptos": _top_breakdown(df_base, "DEPARTAMENTO", 10),
            "tipos": _tipo_breakdown(df_base),
        })

    # ── Departamentales ──
    if scope in ("departamental", "provincial", "distrital") and deptos:
        for depto in deptos:
            df_d = df_base[df_base["DEPARTAMENTO"] == depto] if _safe_col(df_base, "DEPARTAMENTO") else pd.DataFrame()
            if len(df_d) == 0:
                continue
            m = _calcular_metricas(df_d)
            data["sections"].append({
                "type": "departamental",
                "name": depto,
                "metricas": m,
                "pipeline": _calcular_pipeline(df_d),
                "dictamen": _dictamen_breakdown(df_d),
                "provincias": _top_breakdown(df_d, "PROVINCIA", 20),
                "tipos": _tipo_breakdown(df_d),
            })

    # ── Provinciales ──
    if scope in ("provincial", "distrital") and provs:
        for prov in provs:
            df_p = df_base[df_base["PROVINCIA"] == prov] if _safe_col(df_base, "PROVINCIA") else pd.DataFrame()
            if len(df_p) == 0:
                continue
            m = _calcular_metricas(df_p)
            depto_name = str(df_p["DEPARTAMENTO"].iloc[0]) if _safe_col(df_p, "DEPARTAMENTO") and len(df_p) > 0 else ""
            data["sections"].append({
                "type": "provincial",
                "name": prov,
                "depto": depto_name,
                "metricas": m,
                "pipeline": _calcular_pipeline(df_p),
                "dictamen": _dictamen_breakdown(df_p),
                "distritos": _top_breakdown(df_p, "DISTRITO", 20),
                "tipos": _tipo_breakdown(df_p),
            })

    # ── Distritales ──
    if scope == "distrital" and dists:
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
      sep.addText(`${fmtNum(section.metricas.avisos)} avisos \u00B7 ${fmtMoney(section.metricas.indemnizacion)} indemnización`, {
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

        // Insight box
        const topTipo = section.tipos[0];
        stc.addShape(pres.shapes.RECTANGLE, {
          x: 6.1, y: 1.3, w: 3.6, h: 2.8,
          fill: { color: C.white }, shadow: makeShadow()
        });
        stc.addShape(pres.shapes.RECTANGLE, {
          x: 6.1, y: 1.3, w: 3.6, h: 0.06, fill: { color: C.gold }
        });
        stc.addText("Observaciones", {
          x: 6.3, y: 1.5, w: 3.2, h: 0.35,
          fontSize: 13, fontFace: "Georgia", color: C.navy, bold: true, margin: 0
        });

        const totalAvisos = section.metricas.avisos;
        const topPct = totalAvisos > 0 ? ((topTipo.avisos / totalAvisos) * 100).toFixed(1) : 0;
        stc.addText([
          { text: `${topTipo.tipo} es el siniestro predominante`, options: { bold: true, breakLine: true, fontSize: 10, color: C.dark } },
          { text: `con ${fmtNum(topTipo.avisos)} avisos (${topPct}% del total) y ${fmtMoney(topTipo.indem || 0)} en indemnización.`, options: { breakLine: true, fontSize: 10, color: C.gray } },
          { text: "\n", options: { breakLine: true, fontSize: 6 } },
          { text: `Total de tipos: ${section.tipos.length}`, options: { bold: true, breakLine: true, fontSize: 10, color: C.dark } },
          { text: `con ${fmtNum(totalAvisos)} avisos en total para ${section.name}.`, options: { fontSize: 10, color: C.gray } },
        ], { x: 6.3, y: 1.95, w: 3.2, h: 2.0, valign: "top", margin: 0 });
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
      sep.addText(`${fmtNum(section.metricas.avisos)} avisos \u00B7 ${fmtMoney(section.metricas.indemnizacion)}`, {
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
      ], { x: 0.7, y: 3.5, w: 8.5, h: 1.0, valign: "top", margin: 0 });
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

NODE_PATH = "/sessions/serene-nice-archimedes/.npm-global/lib/node_modules"


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
    env["NODE_PATH"] = NODE_PATH

    result = subprocess.run(
        ["node", js_path],
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
    except:
        pass

    return ppt_bytes
