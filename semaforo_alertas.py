"""
Semáforo de Alertas SAC — Motor de cálculo y UI Streamlit.
Sistema de control de plazos para las 6 etapas del flujo del
Seguro Agrícola Catastrófico (SAC).
"""

import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

# ═══════════════════════════════════════════════════════════════
#  CONSTANTES
# ═══════════════════════════════════════════════════════════════

COLS_MINIMAS = ["FECHA_AVISO", "FECHA_ATENCION"]

STAGES = [
    {"key": "atencion",        "label": "Atención",              "icon": "1", "emoji": "📋"},
    {"key": "programacion",    "label": "Programación",          "icon": "2", "emoji": "📅"},
    {"key": "ajuste",          "label": "Ajuste",                "icon": "3", "emoji": "🔍"},
    {"key": "reprogramacion",  "label": "Reprogramación",        "icon": "4", "emoji": "🔄"},
    {"key": "padron",          "label": "Padrón y Validación",   "icon": "5", "emoji": "📝"},
    {"key": "pago",            "label": "Pago SAC",              "icon": "6", "emoji": "💰"},
]

COLORS = {
    "verde":  {"hex": "#27ae60", "bg": "#d4edda", "label": "En plazo"},
    "ambar":  {"hex": "#f39c12", "bg": "#fff3cd", "label": "Riesgo"},
    "rojo":   {"hex": "#e74c3c", "bg": "#f8d7da", "label": "Vencido"},
}

# Mapeo precomputado (evita recrear dict en cada render)
_STAGE_KEY_TO_LABEL = {s["key"]: s["label"] for s in STAGES}


# ═══════════════════════════════════════════════════════════════
#  A) MOTOR DE CÁLCULO (vectorizado)
# ═══════════════════════════════════════════════════════════════

def check_semaforo_columns(df):
    """Verifica si el DataFrame tiene las columnas mínimas para el semáforo."""
    return all(c in df.columns for c in COLS_MINIMAS)


def _safe_col(df, col):
    """Retorna la columna como Series si existe, si no retorna NaT/NaN Series."""
    if col in df.columns:
        return df[col]
    return pd.Series(pd.NaT, index=df.index)


def compute_semaforo(df, today=None):
    """
    Clasifica cada aviso en su etapa actual y nivel de alerta.
    Retorna DataFrame con columnas adicionales:
      SEM_ETAPA, SEM_ALERTA, SEM_DIAS, SEM_DETALLE
    """
    if today is None:
        today = pd.Timestamp.now().normalize()

    n = len(df)
    etapa   = pd.Series("completado", index=df.index)
    alerta  = pd.Series("", index=df.index)
    dias    = pd.Series(0, index=df.index, dtype="int64")
    detalle = pd.Series("", index=df.index)

    # Columnas seguras
    f_aviso   = pd.to_datetime(_safe_col(df, "FECHA_AVISO"), errors="coerce")
    f_atencion = pd.to_datetime(_safe_col(df, "FECHA_ATENCION"), errors="coerce")
    f_prog    = pd.to_datetime(_safe_col(df, "FECHA_PROGRAMACION_AJUSTE"), errors="coerce")
    f_acta1   = pd.to_datetime(_safe_col(df, "FECHA_AJUSTE_ACTA_1"), errors="coerce")
    f_acta_f  = pd.to_datetime(_safe_col(df, "FECHA_AJUSTE_ACTA_FINAL"), errors="coerce")
    f_reprg1  = pd.to_datetime(_safe_col(df, "FECHA_REPROGRAMACION_01"), errors="coerce")
    f_reprg2  = pd.to_datetime(_safe_col(df, "FECHA_REPROGRAMACION_02"), errors="coerce")
    f_reprg3  = pd.to_datetime(_safe_col(df, "FECHA_REPROGRAMACION_03"), errors="coerce")
    f_envio   = pd.to_datetime(_safe_col(df, "FECHA_ENVIO_DRAS"), errors="coerce")
    f_valid   = pd.to_datetime(_safe_col(df, "FECHA_VALIDACION"), errors="coerce")
    f_desemb  = pd.to_datetime(_safe_col(df, "FECHA_DESEMBOLSO"), errors="coerce")

    estado_sin = _safe_col(df, "ESTADO_SINIESTRO").astype(str).str.upper()
    dictamen   = _safe_col(df, "DICTAMEN").astype(str).str.upper()

    # ── Excluir avisos nulos (OBSERVACION contiene "AVISO NULO") ──
    observacion = _safe_col(df, "OBSERVACION").astype(str).str.upper()
    es_nulo = observacion.str.contains("AVISO NULO", na=False)

    # ── Etapa 6: PAGO ──
    m6 = f_valid.notna() & f_desemb.isna()
    d6 = (today - f_valid).dt.days.fillna(0).astype(int)
    etapa  = etapa.where(~m6, "pago")
    dias   = dias.where(~m6, d6)
    alerta = alerta.where(~m6, np.select(
        [m6 & (d6 <= 10), m6 & (d6 <= 14), m6 & (d6 >= 15)],
        ["verde", "ambar", "rojo"], default=""))
    detalle = detalle.where(~m6, np.where(m6, "Días sin desembolso: " + d6.astype(str), ""))

    # ── Etapa 5: PADRÓN Y VALIDACIÓN ──
    m5_base = f_acta_f.notna() & dictamen.str.contains("INDEMNIZABLE", na=False) & f_desemb.isna()
    m5_con_envio = m5_base & f_envio.notna() & f_valid.isna()
    m5_sin_envio = m5_base & f_envio.isna()
    m5 = m5_con_envio | m5_sin_envio
    d5 = np.where(m5_con_envio, (today - f_envio).dt.days.fillna(0), 999)
    d5 = pd.Series(d5, index=df.index).astype(int)
    a5 = np.select(
        [m5_sin_envio, m5_con_envio & (d5 <= 7), m5_con_envio & (d5 <= 14), m5_con_envio & (d5 >= 15)],
        ["rojo", "verde", "ambar", "rojo"], default="")
    det5 = np.where(m5_sin_envio, "Sin envío a DRAS",
           np.where(m5_con_envio, "Días sin validación: " + d5.astype(str), ""))
    etapa   = np.where(m5, "padron", etapa)
    alerta  = np.where(m5, a5, alerta)
    dias    = np.where(m5, d5, dias)
    detalle = np.where(m5, det5, detalle)

    # ── Etapa 4: REPROGRAMACIÓN ──
    m4 = (f_acta1.notna() & (estado_sin != "CONCRETADO") & f_acta_f.isna()
           & (f_reprg1.notna() | f_reprg2.notna() | f_reprg3.notna()))
    ciclo = np.where(f_reprg3.notna(), 3, np.where(f_reprg2.notna(), 2, 1))
    f_last_reprg = f_reprg3.fillna(f_reprg2).fillna(f_reprg1)
    d4 = (today - f_last_reprg).dt.days.fillna(0).astype(int)
    a4 = np.select(
        [m4 & (ciclo == 1) & (d4 <= 7), m4 & (ciclo == 1) & (d4 > 7), m4 & (ciclo >= 2)],
        ["ambar", "rojo", "rojo"], default="")
    det4 = np.where(m4, "Ciclo " + pd.Series(ciclo, index=df.index).astype(str) + " — " + d4.astype(str) + " días", "")
    etapa   = np.where(m4, "reprogramacion", etapa)
    alerta  = np.where(m4, a4, alerta)
    dias    = np.where(m4, d4, dias)
    detalle = np.where(m4, det4, detalle)

    # ── Etapa 3: AJUSTE ──
    m3 = f_prog.notna() & f_acta1.isna() & ~m4
    d3 = (today - f_prog).dt.days.fillna(0).astype(int)
    a3 = np.select(
        [m3 & (d3 <= 12), m3 & (d3 <= 15), m3 & (d3 >= 16)],
        ["verde", "ambar", "rojo"], default="")
    det3 = np.where(m3, "Días sin acta: " + d3.astype(str), "")
    etapa   = np.where(m3, "ajuste", etapa)
    alerta  = np.where(m3, a3, alerta)
    dias    = np.where(m3, d3, dias)
    detalle = np.where(m3, det3, detalle)

    # ── Etapa 2: PROGRAMACIÓN ──
    m2 = f_atencion.notna() & f_prog.isna() & ~m3 & ~m4
    d2 = (today - f_atencion).dt.days.fillna(0).astype(int)
    a2 = np.select(
        [m2 & (d2 <= 10), m2 & (d2 <= 14), m2 & (d2 >= 15)],
        ["verde", "ambar", "rojo"], default="")
    det2 = np.where(m2, "Días sin programación: " + d2.astype(str), "")
    etapa   = np.where(m2, "programacion", etapa)
    alerta  = np.where(m2, a2, alerta)
    dias    = np.where(m2, d2, dias)
    detalle = np.where(m2, det2, detalle)

    # ── Etapa 1: ATENCIÓN ──
    m1 = f_aviso.notna() & f_atencion.isna()
    deadline = f_aviso + pd.Timedelta(days=16)
    d1 = (deadline - today).dt.days.fillna(0).astype(int)
    a1 = np.select(
        [m1 & (d1 >= 8), m1 & (d1 >= 1) & (d1 <= 7), m1 & (d1 <= 0)],
        ["verde", "ambar", "rojo"], default="")
    det1 = np.where(m1 & (d1 > 0), "Faltan " + d1.astype(str) + " días",
           np.where(m1 & (d1 <= 0), "Vencido hace " + (-d1).astype(str) + " días", ""))
    etapa   = np.where(m1, "atencion", etapa)
    alerta  = np.where(m1, a1, alerta)
    dias    = np.where(m1, d1, dias)
    detalle = np.where(m1, det1, detalle)

    # ── Forzar avisos nulos como "completado" (excluirlos del semáforo) ──
    etapa   = np.where(es_nulo, "completado", etapa)
    alerta  = np.where(es_nulo, "", alerta)
    dias    = np.where(es_nulo, 0, dias)
    detalle = np.where(es_nulo, "Aviso nulo — excluido", detalle)

    # Asignar al DataFrame
    result = df.copy()
    result["SEM_ETAPA"]   = pd.Series(etapa, index=df.index)
    result["SEM_ALERTA"]  = pd.Series(alerta, index=df.index)
    result["SEM_DIAS"]    = pd.to_numeric(pd.Series(dias, index=df.index), errors="coerce").fillna(0).astype(int)
    result["SEM_DETALLE"] = pd.Series(detalle, index=df.index)

    return result


def get_pipeline_summary(df_sem):
    """Genera resumen por etapa: conteo de verde/ámbar/rojo."""
    df_active = df_sem[df_sem["SEM_ETAPA"] != "completado"]
    summary = {}
    for s in STAGES:
        k = s["key"]
        sub = df_active[df_active["SEM_ETAPA"] == k]
        summary[k] = {
            "verde": int((sub["SEM_ALERTA"] == "verde").sum()),
            "ambar": int((sub["SEM_ALERTA"] == "ambar").sum()),
            "rojo":  int((sub["SEM_ALERTA"] == "rojo").sum()),
            "total": len(sub),
        }
    return summary


def get_kpi_summary(df_sem):
    """KPIs globales."""
    active = df_sem[df_sem["SEM_ETAPA"] != "completado"]
    total = len(active)
    if total == 0:
        return {"total": 0, "verde": 0, "ambar": 0, "rojo": 0,
                "pct_verde": 0, "pct_ambar": 0, "pct_rojo": 0}
    v = int((active["SEM_ALERTA"] == "verde").sum())
    a = int((active["SEM_ALERTA"] == "ambar").sum())
    r = int((active["SEM_ALERTA"] == "rojo").sum())
    return {
        "total": total, "verde": v, "ambar": a, "rojo": r,
        "pct_verde": round(v / total * 100, 1),
        "pct_ambar": round(a / total * 100, 1),
        "pct_rojo":  round(r / total * 100, 1),
    }


def get_notification_banner_html(datos):
    """Genera HTML de banner de notificaciones con resumen de alertas.
    Retorna None si no hay columnas de semáforo."""
    df = datos.get("midagri")
    if df is None or df.empty:
        return None
    if not check_semaforo_columns(df):
        return None

    today = pd.Timestamp.now().normalize()
    df_sem = compute_semaforo(df, today)
    kpis = get_kpi_summary(df_sem)

    if kpis["total"] == 0:
        return None

    return (
        '<div style="background:linear-gradient(135deg,#fff8f0,#fef3e6);border:1px solid #f0c78a;'
        'border-radius:12px;padding:0.8rem 1.2rem;margin-bottom:1rem;display:flex;'
        'align-items:center;gap:1.5rem;flex-wrap:wrap;">'
        '<div style="font-weight:700;color:#0c2340;font-size:0.85rem;">Alertas SAC</div>'
        f'<div style="display:flex;gap:0.3rem;align-items:center;">'
        f'<span style="background:#e74c3c;color:white;border-radius:20px;padding:2px 10px;'
        f'font-size:0.78rem;font-weight:700;">{kpis["rojo"]}</span>'
        f'<span style="color:#64748b;font-size:0.75rem;">vencidos</span></div>'
        f'<div style="display:flex;gap:0.3rem;align-items:center;">'
        f'<span style="background:#f39c12;color:white;border-radius:20px;padding:2px 10px;'
        f'font-size:0.78rem;font-weight:700;">{kpis["ambar"]}</span>'
        f'<span style="color:#64748b;font-size:0.75rem;">en riesgo</span></div>'
        f'<div style="display:flex;gap:0.3rem;align-items:center;">'
        f'<span style="background:#27ae60;color:white;border-radius:20px;padding:2px 10px;'
        f'font-size:0.78rem;font-weight:700;">{kpis["verde"]}</span>'
        f'<span style="color:#64748b;font-size:0.75rem;">en plazo</span></div>'
        '</div>'
    )


def generate_sankey_figure(df_sem):
    """Genera diagrama Sankey mostrando flujo de avisos por las 6 etapas."""
    active = df_sem[df_sem["SEM_ETAPA"] != "completado"]
    if active.empty:
        return None

    stage_keys = [s["key"] for s in STAGES]
    stage_labels = [s["label"] for s in STAGES] + ["Completado"]
    node_colors = ["#3498db", "#2980b9", "#1a5276", "#f39c12", "#e67e22", "#27ae60", "#95a5a6"]

    # Contar avisos por etapa y alerta
    sources, targets, values, link_colors = [], [], [], []
    color_map = {"verde": "rgba(39,174,96,0.4)", "ambar": "rgba(243,156,18,0.4)", "rojo": "rgba(231,76,60,0.4)"}

    for i, key in enumerate(stage_keys):
        sub = active[active["SEM_ETAPA"] == key]
        for alert_level in ["verde", "ambar", "rojo"]:
            cnt = int((sub["SEM_ALERTA"] == alert_level).sum())
            if cnt > 0:
                # Flujo de esta etapa hacia "Completado" (último nodo)
                sources.append(i)
                targets.append(len(stage_keys))  # Completado
                values.append(cnt)
                link_colors.append(color_map.get(alert_level, "rgba(150,150,150,0.3)"))

    if not values:
        return None

    fig = go.Figure(go.Sankey(
        node=dict(
            pad=20, thickness=25,
            label=stage_labels,
            color=node_colors,
        ),
        link=dict(source=sources, target=targets, value=values, color=link_colors),
    ))
    fig.update_layout(
        title_text="Flujo de Avisos por Etapas",
        font_size=12, height=350,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    return fig


def export_semaforo_excel(df_sem, pipeline, kpis):
    """Genera Excel con formato condicional verde/ámbar/rojo."""
    wb = Workbook()

    # ── Hoja 1: Resumen Pipeline ──
    ws1 = wb.active
    ws1.title = "Resumen Pipeline"

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="2C3E50")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"))

    headers = ["Etapa", "Verde", "Ámbar", "Rojo", "Total"]
    for col_idx, h in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    fill_v = PatternFill("solid", fgColor="27AE60")
    fill_a = PatternFill("solid", fgColor="F39C12")
    fill_r = PatternFill("solid", fgColor="E74C3C")

    for row_idx, s in enumerate(STAGES, 2):
        k = s["key"]
        data = pipeline.get(k, {"verde": 0, "ambar": 0, "rojo": 0, "total": 0})
        ws1.cell(row=row_idx, column=1, value=s["label"]).border = thin_border
        c_v = ws1.cell(row=row_idx, column=2, value=data["verde"])
        c_v.fill = fill_v if data["verde"] > 0 else PatternFill()
        c_v.font = Font(color="FFFFFF", bold=True) if data["verde"] > 0 else Font()
        c_v.border = thin_border
        c_v.alignment = Alignment(horizontal="center")
        c_a = ws1.cell(row=row_idx, column=3, value=data["ambar"])
        c_a.fill = fill_a if data["ambar"] > 0 else PatternFill()
        c_a.font = Font(color="FFFFFF", bold=True) if data["ambar"] > 0 else Font()
        c_a.border = thin_border
        c_a.alignment = Alignment(horizontal="center")
        c_r = ws1.cell(row=row_idx, column=4, value=data["rojo"])
        c_r.fill = fill_r if data["rojo"] > 0 else PatternFill()
        c_r.font = Font(color="FFFFFF", bold=True) if data["rojo"] > 0 else Font()
        c_r.border = thin_border
        c_r.alignment = Alignment(horizontal="center")
        ws1.cell(row=row_idx, column=5, value=data["total"]).border = thin_border

    # KPIs resumen
    row_k = len(STAGES) + 3
    ws1.cell(row=row_k, column=1, value="RESUMEN GLOBAL").font = Font(bold=True, size=12)
    ws1.cell(row=row_k+1, column=1, value="Total alertas activas")
    ws1.cell(row=row_k+1, column=2, value=kpis["total"])
    ws1.cell(row=row_k+2, column=1, value="% Verde")
    ws1.cell(row=row_k+2, column=2, value=f"{kpis['pct_verde']}%")
    ws1.cell(row=row_k+3, column=1, value="% Ámbar")
    ws1.cell(row=row_k+3, column=2, value=f"{kpis['pct_ambar']}%")
    ws1.cell(row=row_k+4, column=1, value="% Rojo")
    ws1.cell(row=row_k+4, column=2, value=f"{kpis['pct_rojo']}%")

    for c in range(1, 6):
        ws1.column_dimensions[chr(64 + c)].width = 18

    # ── Hoja 2: Detalle Alertas ──
    ws2 = wb.create_sheet("Detalle Alertas")

    display_cols = ["CODIGO_AVISO", "DEPARTAMENTO", "PROVINCIA", "DISTRITO",
                    "SECTOR_ESTADISTICO", "TIPO_CULTIVO", "EMPRESA",
                    "TIPO_SINIESTRO", "SEM_ETAPA", "SEM_ALERTA",
                    "SEM_DIAS", "SEM_DETALLE"]
    available = [c for c in display_cols if c in df_sem.columns]
    df_export = df_sem[df_sem["SEM_ETAPA"] != "completado"][available].copy()

    col_labels = {
        "CODIGO_AVISO": "Código Aviso", "DEPARTAMENTO": "Departamento",
        "PROVINCIA": "Provincia", "DISTRITO": "Distrito",
        "SECTOR_ESTADISTICO": "Sector", "TIPO_CULTIVO": "Cultivo",
        "EMPRESA": "Empresa",
        "TIPO_SINIESTRO": "Tipo Siniestro", "SEM_ETAPA": "Etapa",
        "SEM_ALERTA": "Alerta", "SEM_DIAS": "Días", "SEM_DETALLE": "Detalle"
    }

    for col_idx, col in enumerate(available, 1):
        cell = ws2.cell(row=1, column=col_idx, value=col_labels.get(col, col))
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    fill_map = {"verde": fill_v, "ambar": fill_a, "rojo": fill_r}
    font_white = Font(color="FFFFFF", bold=True)
    center_align = Alignment(horizontal="center")

    # Batch write: usar .values en vez de iterrows (5-10x más rápido)
    alerta_col_idx = available.index("SEM_ALERTA") + 1 if "SEM_ALERTA" in available else -1
    data_matrix = df_export[available].values
    for row_idx, row_data in enumerate(data_matrix, 2):
        for col_idx, val in enumerate(row_data, 1):
            cell = ws2.cell(row=row_idx, column=col_idx, value=val)
            cell.border = thin_border
            if col_idx == alerta_col_idx and val in fill_map:
                cell.fill = fill_map[val]
                cell.font = font_white
                cell.alignment = center_align

    from openpyxl.utils import get_column_letter
    for i in range(1, len(available) + 1):
        ws2.column_dimensions[get_column_letter(i)].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════
#  B) UI STREAMLIT
# ═══════════════════════════════════════════════════════════════

def _css_semaforo():
    """CSS para el pipeline visual y badges."""
    return """
    <style>
    .sem-pipeline {
        display: flex; align-items: center; justify-content: center;
        gap: 0; padding: 15px 0; overflow-x: auto;
    }
    .sem-stage {
        background: #fff; border: 2px solid #e2e8f0; border-radius: 12px;
        padding: 12px 14px; min-width: 130px; text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }
    .sem-stage-label {
        font-size: 12px; font-weight: 700; color: #2C3E50;
        margin-bottom: 6px; text-transform: uppercase; letter-spacing: 0.5px;
    }
    .sem-stage-num { font-size: 10px; color: #95a5a6; margin-bottom: 4px; }
    .sem-badges { display: flex; gap: 4px; justify-content: center; }
    .sem-badge {
        display: inline-flex; align-items: center; justify-content: center;
        min-width: 28px; height: 22px; border-radius: 11px;
        font-size: 11px; font-weight: 700; color: #fff; padding: 0 6px;
    }
    .sem-badge-v { background: #27ae60; }
    .sem-badge-a { background: #f39c12; }
    .sem-badge-r { background: #e74c3c; }
    .sem-arrow {
        font-size: 18px; color: #bdc3c7; margin: 0 2px;
        display: flex; align-items: center;
    }
    .sem-kpi-row {
        display: flex; gap: 16px; margin: 16px 0;
        justify-content: center; flex-wrap: wrap;
    }
    .sem-kpi {
        background: #fff; border-radius: 10px; padding: 16px 24px;
        text-align: center; min-width: 140px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07); border-left: 4px solid #408B14;
    }
    .sem-kpi-val { font-size: 28px; font-weight: 800; color: #2C3E50; }
    .sem-kpi-label { font-size: 11px; color: #7f8c8d; text-transform: uppercase; letter-spacing: 0.5px; }
    .sem-kpi.verde  { border-left-color: #27ae60; }
    .sem-kpi.ambar  { border-left-color: #f39c12; }
    .sem-kpi.rojo   { border-left-color: #e74c3c; }
    .sem-kpi.total  { border-left-color: #408B14; }
    .sem-drilldown-title {
        font-size: 13px; font-weight: 700; color: #2C3E50;
        margin: 8px 0 4px 0; padding: 6px 10px;
        background: #f8f9fa; border-radius: 6px; border-left: 3px solid #408B14;
    }
    </style>
    """


def _render_pipeline_html(pipeline):
    """Genera el HTML del pipeline visual."""
    html = '<div class="sem-pipeline">'
    for i, s in enumerate(STAGES):
        k = s["key"]
        data = pipeline.get(k, {"verde": 0, "ambar": 0, "rojo": 0, "total": 0})
        if i > 0:
            html += '<div class="sem-arrow">&#10132;</div>'
        html += f'''
        <div class="sem-stage">
            <div class="sem-stage-num">{s["emoji"]} Etapa {s["icon"]}</div>
            <div class="sem-stage-label">{s["label"]}</div>
            <div class="sem-badges">
                <span class="sem-badge sem-badge-v">{data["verde"]}</span>
                <span class="sem-badge sem-badge-a">{data["ambar"]}</span>
                <span class="sem-badge sem-badge-r">{data["rojo"]}</span>
            </div>
        </div>'''
    html += '</div>'
    return html


def _render_kpis_html(kpis):
    """Genera KPIs como HTML."""
    return f'''
    <div class="sem-kpi-row">
        <div class="sem-kpi total">
            <div class="sem-kpi-val">{kpis["total"]:,}</div>
            <div class="sem-kpi-label">Alertas Activas</div>
        </div>
        <div class="sem-kpi verde">
            <div class="sem-kpi-val">{kpis["pct_verde"]}%</div>
            <div class="sem-kpi-label">En Plazo ({kpis["verde"]:,})</div>
        </div>
        <div class="sem-kpi ambar">
            <div class="sem-kpi-val">{kpis["pct_ambar"]}%</div>
            <div class="sem-kpi-label">En Riesgo ({kpis["ambar"]:,})</div>
        </div>
        <div class="sem-kpi rojo">
            <div class="sem-kpi-val">{kpis["pct_rojo"]}%</div>
            <div class="sem-kpi-label">Vencidos ({kpis["rojo"]:,})</div>
        </div>
    </div>
    '''


def _stage_label(key):
    """Devuelve el label legible de una etapa."""
    for s in STAGES:
        if s["key"] == key:
            return f'{s["emoji"]} {s["label"]}'
    return key


def render_semaforo_tab(datos):
    """Punto de entrada: renderiza la pestaña Semáforo de Alertas."""
    st.markdown(_css_semaforo(), unsafe_allow_html=True)

    st.markdown("""
    <div style="background:linear-gradient(135deg,#408B14 0%,#2C5F2D 100%);
         padding:18px 24px;border-radius:10px;margin-bottom:18px;">
        <span style="color:#fff;font-size:22px;font-weight:700;">
        🚦 Semáforo de Alertas — Control de Plazos SAC</span><br>
        <span style="color:#d4edda;font-size:13px;">
        Monitoreo en tiempo real de los 6 procesos del Seguro Agrícola Catastrófico</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Explicación de criterios ──
    with st.expander("ℹ️ ¿Cómo funciona el Semáforo? — Criterios y plazos por etapa", expanded=False):
        st.markdown("""
**El semáforo clasifica cada aviso de siniestro según la etapa en la que se encuentra dentro del flujo SAC.** Cada etapa tiene plazos regulados; al superarlos, el aviso cambia de verde → ámbar → rojo.

**Columna de referencia:** Se evalúan las fechas de cada proceso (`FECHA_AVISO`, `FECHA_ATENCION`, `FECHA_PROGRAMACION_AJUSTE`, etc.).
**Avisos excluidos:** Los que tienen observación "AVISO NULO" no se evalúan.

| # | Etapa | Columnas evaluadas | 🟢 Verde | 🟡 Ámbar | 🔴 Rojo |
|---|-------|-------------------|----------|----------|---------|
| 1 | **Atención** | `FECHA_AVISO` → `FECHA_ATENCION` | Faltan ≥8 días para el plazo (16 días) | Faltan 1-7 días | Plazo vencido (>16 días sin atención) |
| 2 | **Programación** | `FECHA_ATENCION` → `FECHA_PROGRAMACION_AJUSTE` | ≤10 días desde atención | 11-14 días | ≥15 días sin programar ajuste |
| 3 | **Ajuste** | `FECHA_PROGRAMACION_AJUSTE` → `FECHA_AJUSTE_ACTA_1` | ≤12 días desde programación | 13-15 días | ≥16 días sin acta de ajuste |
| 4 | **Reprogramación** | `FECHA_REPROGRAMACION_01/02/03` | 1er ciclo ≤7 días | 1er ciclo >7 días | 2do o 3er ciclo de reprogramación |
| 5 | **Padrón y Validación** | `FECHA_ENVIO_DRAS` → `FECHA_VALIDACION` | ≤7 días desde envío | 8-14 días | ≥15 días o sin envío a DRAS |
| 6 | **Pago SAC** | `FECHA_VALIDACION` → `FECHA_DESEMBOLSO` | ≤10 días desde validación | 11-14 días | ≥15 días sin desembolso |

**Nota:** Cada aviso aparece en **una sola etapa** (la primera incompleta en el flujo). Si todas las etapas están completas, el aviso se marca como "completado" y no aparece en el semáforo.
        """)

    df = datos.get("midagri")
    if df is None or df.empty:
        st.warning("No hay datos cargados.")
        return

    if not check_semaforo_columns(df):
        st.error(
            "⚠️ **Datos insuficientes para el Semáforo de Alertas**\n\n"
            "Los datos cargados no contienen las columnas necesarias para el control de plazos. "
            "Para habilitar esta funcionalidad, suba el archivo Excel expandido que incluye:\n"
            "- Fecha de Atención\n"
            "- Fecha de Programación de Ajuste\n"
            "- Fecha Ajuste Acta\n"
            "- Fechas de Reprogramación\n"
            "- Fecha Envío DRAS\n"
            "- Fecha Validación/Conformidad\n"
            "- Fecha Desembolso"
        )
        return

    # ── Cálculo ──
    today = pd.Timestamp.now().normalize()
    df_sem = compute_semaforo(df, today)
    pipeline = get_pipeline_summary(df_sem)
    kpis = get_kpi_summary(df_sem)

    # ── KPIs ──
    st.markdown(_render_kpis_html(kpis), unsafe_allow_html=True)

    # ── Pipeline visual ──
    st.markdown("#### Pipeline de Procesos")
    st.markdown(_render_pipeline_html(pipeline), unsafe_allow_html=True)

    # ── Diagrama Sankey ──
    try:
        fig_sankey = generate_sankey_figure(df_sem)
        if fig_sankey:
            with st.expander("📊 Diagrama de Flujo (Sankey)", expanded=False):
                st.plotly_chart(fig_sankey, use_container_width=True)
    except Exception:
        pass

    st.markdown("---")

    # ── Filtros ──
    st.markdown("#### 🔎 Filtros")
    c1, c2, c3, c4 = st.columns(4)

    deptos_list = sorted(df_sem["DEPARTAMENTO"].dropna().unique().tolist()) if "DEPARTAMENTO" in df_sem.columns else []
    empresas_list = sorted(df_sem["EMPRESA"].dropna().unique().tolist()) if "EMPRESA" in df_sem.columns else []
    etapas_opts = ["Todas"] + [s["label"] for s in STAGES]
    alertas_opts = ["verde", "ambar", "rojo"]

    with c1:
        fil_depto = st.multiselect("Departamento", deptos_list, key="sem_fil_depto")
    with c2:
        fil_empresa = st.multiselect("Empresa", empresas_list, key="sem_fil_empresa")
    with c3:
        fil_etapa = st.selectbox("Etapa", etapas_opts, key="sem_fil_etapa")
    with c4:
        fil_alerta = st.multiselect("Nivel de Alerta", alertas_opts,
                                     default=alertas_opts, key="sem_fil_alerta",
                                     format_func=lambda x: {"verde": "🟢 Verde", "ambar": "🟡 Ámbar", "rojo": "🔴 Rojo"}[x])

    # Aplicar filtros (sin .copy() innecesario — solo lectura)
    df_fil = df_sem[df_sem["SEM_ETAPA"] != "completado"]
    if fil_depto:
        df_fil = df_fil[df_fil["DEPARTAMENTO"].isin(fil_depto)]
    if fil_empresa:
        df_fil = df_fil[df_fil["EMPRESA"].isin(fil_empresa)]
    if fil_etapa != "Todas":
        stage_key = next((s["key"] for s in STAGES if s["label"] == fil_etapa), None)
        if stage_key:
            df_fil = df_fil[df_fil["SEM_ETAPA"] == stage_key]
    if fil_alerta:
        df_fil = df_fil[df_fil["SEM_ALERTA"].isin(fil_alerta)]

    st.markdown(f"**{len(df_fil):,} avisos** con alertas activas "
                f"(de {kpis['total']:,} totales)")

    # ── Tabla detalle ──
    st.markdown("#### 📋 Detalle de Alertas")

    display_cols = ["CODIGO_AVISO", "DEPARTAMENTO", "PROVINCIA", "DISTRITO",
                    "SECTOR_ESTADISTICO", "TIPO_CULTIVO", "EMPRESA",
                    "TIPO_SINIESTRO", "SEM_ETAPA", "SEM_ALERTA", "SEM_DIAS", "SEM_DETALLE"]
    available = [c for c in display_cols if c in df_fil.columns]

    df_display = df_fil[available].copy()
    df_display["SEM_ETAPA"] = df_display["SEM_ETAPA"].map(
        _STAGE_KEY_TO_LABEL).fillna(df_display["SEM_ETAPA"])

    rename_map = {
        "CODIGO_AVISO": "Código Aviso", "DEPARTAMENTO": "Departamento",
        "PROVINCIA": "Provincia", "DISTRITO": "Distrito",
        "SECTOR_ESTADISTICO": "Sector", "TIPO_CULTIVO": "Cultivo",
        "EMPRESA": "Empresa",
        "TIPO_SINIESTRO": "Tipo Siniestro", "SEM_ETAPA": "Etapa",
        "SEM_ALERTA": "Alerta", "SEM_DIAS": "Días", "SEM_DETALLE": "Detalle"
    }
    df_display = df_display.rename(columns={k: v for k, v in rename_map.items() if k in df_display.columns})

    st.dataframe(
        df_display,
        use_container_width=True,
        height=450,
        column_config={
            "Alerta": st.column_config.TextColumn(
                "Alerta", help="🟢 Verde: en plazo | 🟡 Ámbar: riesgo | 🔴 Rojo: vencido"),
            "Días": st.column_config.NumberColumn("Días", format="%d"),
        }
    )

    # ── Drill-down por etapa ──
    st.markdown("#### 📊 Análisis por Etapa")

    for s in STAGES:
        k = s["key"]
        p = pipeline.get(k, {"verde": 0, "ambar": 0, "rojo": 0, "total": 0})
        if p["total"] == 0:
            continue

        with st.expander(f'{s["emoji"]} {s["label"]} — {p["total"]} alertas '
                         f'(🟢{p["verde"]} 🟡{p["ambar"]} 🔴{p["rojo"]})'):
            sub = df_sem[df_sem["SEM_ETAPA"] == k]

            if "DEPARTAMENTO" in sub.columns:
                top_rojo = (sub[sub["SEM_ALERTA"] == "rojo"]
                            .groupby("DEPARTAMENTO").size()
                            .sort_values(ascending=False).head(5))
                if not top_rojo.empty:
                    st.markdown('<div class="sem-drilldown-title">🔴 Top 5 departamentos con más alertas rojas</div>',
                                unsafe_allow_html=True)
                    for depto, cnt in top_rojo.items():
                        st.markdown(f"&nbsp;&nbsp;&nbsp;**{depto}**: {cnt} avisos")

                top_total = (sub.groupby("DEPARTAMENTO").size()
                             .sort_values(ascending=False).head(5))
                if not top_total.empty:
                    st.markdown('<div class="sem-drilldown-title">📊 Top 5 departamentos por volumen</div>',
                                unsafe_allow_html=True)
                    for depto, cnt in top_total.items():
                        st.markdown(f"&nbsp;&nbsp;&nbsp;**{depto}**: {cnt} avisos")

            avg_days = sub["SEM_DIAS"].mean()
            st.markdown(f"**Promedio de días en esta etapa:** {avg_days:.1f} días")

    # ── Exportar ──
    st.markdown("---")
    col_exp1, col_exp2 = st.columns([1, 3])
    with col_exp1:
        if st.button("📥 Generar Excel Semáforo", key="sem_gen_excel", type="primary"):
            excel_bytes = export_semaforo_excel(df_fil, pipeline, kpis)
            st.session_state["sem_excel"] = excel_bytes
            st.session_state["sem_excel_name"] = f"semaforo_alertas_{today.strftime('%d%m%Y')}.xlsx"

    with col_exp2:
        if st.session_state.get("sem_excel"):
            st.download_button(
                "⬇️ Descargar Excel Semáforo",
                data=st.session_state["sem_excel"],
                file_name=st.session_state["sem_excel_name"],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="sem_download_excel"
            )
