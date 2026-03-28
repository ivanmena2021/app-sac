"""
gen_pdf_resumen.py — Generador de PDF ejecutivo para el Seguro Agrícola Catastrófico
Produce un resumen de 1-2 páginas con KPIs, tablas y gráficos embebidos.
Requiere: fpdf2, matplotlib
"""

import io
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from fpdf import FPDF


# ─── Colores corporativos ───
NAVY = (12, 35, 64)        # #0c2340
TEAL = (26, 82, 118)       # #1a5276
LIGHT_BG = (248, 249, 250)  # #f8f9fa
WHITE = (255, 255, 255)
DARK_TEXT = (51, 51, 51)
GRAY_TEXT = (120, 120, 120)

# ─── Colores para pie chart ───
PIE_COLORS = [
    "#0c2340", "#1a5276", "#2980b9", "#3498db", "#27ae60",
    "#e67e22", "#e74c3c", "#8e44ad", "#1abc9c", "#f39c12",
]


def _safe_val(datos, key, default=0):
    """Safely retrieve a value from datos, returning default if missing or NaN."""
    val = datos.get(key, default)
    if val is None:
        return default
    if isinstance(val, (int, float)):
        if np.isnan(val) if isinstance(val, float) else False:
            return default
        return val
    return default


def _safe_str(datos, key, default="N/D"):
    """Safely retrieve a string value from datos."""
    val = datos.get(key, default)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return str(val)


def _fmt_number(value, prefix="", suffix="", decimals=0):
    """Format a number with thousands separator."""
    try:
        if decimals > 0:
            formatted = f"{float(value):,.{decimals}f}"
        else:
            formatted = f"{int(round(float(value))):,}"
        return f"{prefix}{formatted}{suffix}"
    except (ValueError, TypeError):
        return "N/D"


def _create_pie_chart_png(siniestros_por_tipo):
    """Create a pie chart PNG in memory from siniestros_por_tipo Series.

    Returns bytes of the PNG image, or None if no data.
    """
    if siniestros_por_tipo is None or len(siniestros_por_tipo) == 0:
        return None

    # Take top 8, group rest as "Otros"
    if len(siniestros_por_tipo) > 8:
        top = siniestros_por_tipo.head(8)
        otros = siniestros_por_tipo.iloc[8:].sum()
        top["OTROS"] = otros
        data = top
    else:
        data = siniestros_por_tipo

    labels = [str(l).title() for l in data.index]
    sizes = data.values.astype(float)
    colors = PIE_COLORS[:len(labels)]

    fig, ax = plt.subplots(figsize=(5, 3.5), dpi=150)
    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        autopct="%1.1f%%",
        colors=colors,
        startangle=140,
        pctdistance=0.75,
        textprops={"fontsize": 7, "color": "white", "fontweight": "bold"},
    )

    # Legend
    ax.legend(
        wedges, labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=6.5,
        frameon=False,
    )

    ax.set_title(
        "Distribución de Siniestros por Tipo",
        fontsize=9,
        fontweight="bold",
        color="#0c2340",
        pad=12,
    )

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def _generate_observations(datos):
    """Auto-generate key observations text from datos."""
    lines = []

    total_avisos = _safe_val(datos, "total_avisos")
    siniestralidad = _safe_val(datos, "indice_siniestralidad")
    pct_desembolso = _safe_val(datos, "pct_desembolso")
    monto_indemn = _safe_val(datos, "monto_indemnizado")
    monto_desemb = _safe_val(datos, "monto_desembolsado")
    productores = _safe_val(datos, "productores_desembolso")

    if total_avisos > 0:
        lines.append(
            f"Se han registrado {int(total_avisos):,} avisos de siniestro a nivel nacional."
        )

    if siniestralidad > 0:
        if siniestralidad > 100:
            lines.append(
                f"El indice de siniestralidad alcanza {siniestralidad:.1f}%, "
                f"superando la prima neta recaudada."
            )
        elif siniestralidad > 70:
            lines.append(
                f"El indice de siniestralidad es elevado ({siniestralidad:.1f}%), "
                f"acercandose al total de la prima neta."
            )
        else:
            lines.append(
                f"El indice de siniestralidad se encuentra en {siniestralidad:.1f}%."
            )

    if pct_desembolso > 0:
        pendiente = monto_indemn - monto_desemb
        if pendiente > 0:
            lines.append(
                f"El {pct_desembolso:.1f}% de las indemnizaciones han sido desembolsadas. "
                f"Quedan S/ {pendiente:,.0f} pendientes de desembolso."
            )
        else:
            lines.append(
                f"Se ha desembolsado el {pct_desembolso:.1f}% de las indemnizaciones reconocidas."
            )

    if productores > 0:
        lines.append(
            f"Un total de {int(productores):,} productores han sido beneficiados con desembolsos."
        )

    # Top siniestros
    top3 = datos.get("top3_siniestros", None)
    if top3 is not None and len(top3) > 0:
        tipos = [f"{str(t).title()} ({int(c):,})" for t, c in top3.items()]
        lines.append(
            f"Los principales tipos de siniestro son: {', '.join(tipos)}."
        )

    if not lines:
        lines.append("No se dispone de datos suficientes para generar observaciones automaticas.")

    return lines


class _SacPDF(FPDF):
    """Custom FPDF subclass with SAC header/footer styling."""

    def header(self):
        """Minimal header — main header is drawn manually on page 1."""
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*GRAY_TEXT)
        self.cell(0, 10, f"SAC 2025-2026 | Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="L")
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="R")


def generate_executive_pdf(datos):
    """Generate a 1-2 page PDF executive summary.

    Page 1:
    - Header: "SEGURO AGRICOLA CATASTROFICO - Resumen Ejecutivo"
    - Subtitle with fecha_corte
    - 8 KPI boxes in 2 rows of 4
    - Top 10 departments table

    Page 2:
    - Pie chart of siniestros por tipo
    - Auto-generated observations

    Parameters
    ----------
    datos : dict
        Output from process_dynamic_data.

    Returns
    -------
    bytes
        PDF file content.
    """
    pdf = _SacPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ═══════════════════════════════════════════════════════════════
    # PAGE 1
    # ═══════════════════════════════════════════════════════════════
    pdf.add_page()
    page_w = pdf.w - 20  # effective width (10mm margins each side)

    # ─── Header band ───
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 32, "F")
    pdf.set_xy(10, 6)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*WHITE)
    pdf.cell(page_w, 8, "SEGURO AGRICOLA CATASTROFICO", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(200, 220, 240)
    fecha_corte = _safe_str(datos, "fecha_corte", datetime.now().strftime("%d/%m/%Y"))
    pdf.cell(page_w, 6, f"Resumen Ejecutivo  |  SAC 2025-2026  |  Corte al {fecha_corte}", align="C")

    pdf.set_y(38)

    # ─── KPI boxes: 2 rows of 4 ───
    kpis = [
        # Row 1
        ("Total Avisos", _fmt_number(_safe_val(datos, "total_avisos"))),
        ("Ha Indemnizadas", _fmt_number(_safe_val(datos, "ha_indemnizadas"), decimals=2)),
        ("Monto Indemnizado", _fmt_number(_safe_val(datos, "monto_indemnizado"), prefix="S/ ")),
        ("Monto Desembolsado", _fmt_number(_safe_val(datos, "monto_desembolsado"), prefix="S/ ")),
        # Row 2
        ("Productores", _fmt_number(_safe_val(datos, "productores_desembolso"))),
        ("Siniestralidad", _fmt_number(_safe_val(datos, "indice_siniestralidad"), suffix="%", decimals=1)),
        ("% Desembolso", _fmt_number(_safe_val(datos, "pct_desembolso"), suffix="%", decimals=1)),
        ("Prima Total", _fmt_number(_safe_val(datos, "prima_total"), prefix="S/ ")),
    ]

    box_w = page_w / 4
    box_h = 18
    x_start = 10

    for row in range(2):
        y = pdf.get_y() + 2
        for col in range(4):
            idx = row * 4 + col
            label, value = kpis[idx]
            x = x_start + col * box_w

            # Background
            pdf.set_fill_color(*LIGHT_BG)
            pdf.rect(x + 1, y, box_w - 2, box_h, "F")

            # Accent line
            pdf.set_fill_color(*TEAL)
            pdf.rect(x + 1, y, 1.5, box_h, "F")

            # Label
            pdf.set_xy(x + 5, y + 2)
            pdf.set_font("Helvetica", "", 6.5)
            pdf.set_text_color(*GRAY_TEXT)
            pdf.cell(box_w - 8, 4, label, align="L")

            # Value
            pdf.set_xy(x + 5, y + 7)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*NAVY)
            pdf.cell(box_w - 8, 6, value, align="L")

        pdf.set_y(y + box_h + 1)

    # ─── Top 10 departments table ───
    pdf.set_y(pdf.get_y() + 6)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(page_w, 7, "Top 10 Departamentos por Avisos de Siniestro", new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(pdf.get_y() + 2)

    cuadro2 = datos.get("cuadro2", pd.DataFrame())
    if cuadro2 is not None and not cuadro2.empty:
        # Exclude TOTAL row, sort by avisos or first numeric col
        df_table = cuadro2.copy()
        if "Departamento" in df_table.columns:
            df_table = df_table[df_table["Departamento"] != "TOTAL"]

        # Determine sort column
        sort_col = None
        for c in ["Hectareas Indemnizadas", "Monto Indemnizado (S/)"]:
            if c in df_table.columns:
                sort_col = c
                break
        if sort_col:
            df_table = df_table.sort_values(sort_col, ascending=False)

        df_table = df_table.head(10).reset_index(drop=True)

        # Table headers
        col_widths = [40, 30, 38, 38, 38]
        headers = ["Departamento", "Ha Indemn.", "Monto Indemn.", "Monto Desemb.", "Productores"]

        # Map actual columns
        col_keys = []
        for h in ["Departamento", "Hectareas Indemnizadas", "Monto Indemnizado (S/)",
                   "Monto Desembolsado (S/)", "Productores con Desembolso"]:
            # Try exact match first, then partial
            if h in df_table.columns:
                col_keys.append(h)
            else:
                found = False
                for c in df_table.columns:
                    if h.split()[0].lower() in str(c).lower():
                        col_keys.append(c)
                        found = True
                        break
                if not found:
                    col_keys.append(None)

        # Header row
        pdf.set_fill_color(*TEAL)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 7)
        for i, hdr in enumerate(headers):
            w = col_widths[i] if i < len(col_widths) else 35
            pdf.cell(w, 6, hdr, border=0, fill=True, align="C" if i > 0 else "L")
        pdf.ln()

        # Data rows
        pdf.set_font("Helvetica", "", 7)
        for row_idx in range(len(df_table)):
            if row_idx % 2 == 0:
                pdf.set_fill_color(245, 247, 250)
            else:
                pdf.set_fill_color(*WHITE)

            pdf.set_text_color(*DARK_TEXT)
            for i, key in enumerate(col_keys):
                w = col_widths[i] if i < len(col_widths) else 35
                if key and key in df_table.columns:
                    val = df_table.iloc[row_idx][key]
                    if i == 0:
                        cell_text = str(val) if pd.notna(val) else "N/D"
                        align = "L"
                    else:
                        try:
                            cell_text = f"{float(val):,.0f}" if pd.notna(val) else "0"
                        except (ValueError, TypeError):
                            cell_text = str(val) if pd.notna(val) else "0"
                        align = "R"
                else:
                    cell_text = "N/D"
                    align = "C"
                pdf.cell(w, 5, cell_text, border=0, fill=True, align=align)
            pdf.ln()
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(page_w, 8, "No hay datos disponibles para la tabla departamental.", align="C")

    # ═══════════════════════════════════════════════════════════════
    # PAGE 2
    # ═══════════════════════════════════════════════════════════════
    pdf.add_page()

    # ─── Section header ───
    pdf.set_fill_color(*NAVY)
    pdf.rect(10, pdf.get_y(), page_w, 8, "F")
    pdf.set_xy(12, pdf.get_y() + 1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*WHITE)
    pdf.cell(page_w - 4, 6, "Analisis de Siniestros por Tipo", align="L")
    pdf.set_y(pdf.get_y() + 12)

    # ─── Pie chart ───
    siniestros_por_tipo = datos.get("siniestros_por_tipo", None)
    pie_png = _create_pie_chart_png(siniestros_por_tipo)

    if pie_png:
        img_stream = io.BytesIO(pie_png)
        pdf.image(img_stream, x=25, w=160)
        pdf.set_y(pdf.get_y() + 5)
    else:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*GRAY_TEXT)
        pdf.cell(page_w, 10, "No se dispone de datos de siniestros por tipo.", align="C")
        pdf.ln(12)

    # ─── Observations ───
    pdf.set_y(pdf.get_y() + 6)
    pdf.set_fill_color(*NAVY)
    pdf.rect(10, pdf.get_y(), page_w, 8, "F")
    pdf.set_xy(12, pdf.get_y() + 1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*WHITE)
    pdf.cell(page_w - 4, 6, "Observaciones Clave", align="L")
    pdf.set_y(pdf.get_y() + 12)

    observations = _generate_observations(datos)

    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*DARK_TEXT)

    for idx, obs in enumerate(observations, 1):
        bullet_y = pdf.get_y()
        pdf.set_xy(14, bullet_y)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(*TEAL)
        pdf.cell(5, 5, str(idx) + ".")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*DARK_TEXT)
        pdf.multi_cell(page_w - 12, 5, obs)
        pdf.set_y(pdf.get_y() + 1)

    # ─── Disclaimer ───
    pdf.set_y(max(pdf.get_y() + 10, 260))
    pdf.set_font("Helvetica", "I", 6.5)
    pdf.set_text_color(*GRAY_TEXT)
    pdf.cell(
        page_w, 4,
        "Documento generado automaticamente. Los datos corresponden al corte indicado y pueden variar.",
        align="C",
    )

    # ─── Output ───
    return bytes(pdf.output())
