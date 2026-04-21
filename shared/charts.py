"""Tema institucional y helpers de descarga para todos los charts SAC.

Uso básico:
    from shared.charts import apply_theme, render_chart, PALETTE

    fig = go.Figure(...)
    apply_theme(fig, title="Avisos por Mes", height=420)
    render_chart(fig, key="avisos_mes", filename="avisos_por_mes")
"""
import io
import streamlit as st


# ═══════════════════════════════════════════════════════════════
#   PALETA INSTITUCIONAL SAC / MIDAGRI
# ═══════════════════════════════════════════════════════════════

PALETTE = {
    # Institucional MIDAGRI
    "primary": "#0c2340",       # Navy corporate
    "primary_mid": "#1a5276",   # Mid blue
    "accent": "#2980b9",        # Blue accent
    "midagri": "#408B14",       # Verde MIDAGRI
    "midagri_soft": "#5FAE2E",  # Verde claro
    # Semánticos
    "success": "#27ae60",
    "warning": "#f39c12",
    "danger": "#e74c3c",
    "info": "#3498db",
    "neutral": "#64748b",
    # Superficies
    "bg": "#ffffff",
    "surface": "#f8fafc",
    "grid_soft": "#f1f5f9",
    "grid": "#e2e8f0",
    "border": "#cbd5e1",
    "text": "#0c2340",
    "text_soft": "#334155",
    "muted": "#64748b",
}

# Secuencia de colores para series categóricas (múltiples campañas, tipos, etc.)
SEQUENCE = [
    "#1a5276",  # Dark blue
    "#e67e22",  # Orange
    "#16a085",  # Teal
    "#8e44ad",  # Purple
    "#c0392b",  # Red
    "#408B14",  # Verde MIDAGRI (reservado p/ campaña actual)
    "#d4af37",  # Gold
    "#6c5ce7",  # Violet
]

# Escalas continuas recomendadas
SCALE = {
    "sequential": "Blues",
    "diverging": "RdYlGn",
    "warm": "YlOrRd",
    "cool": "Blues",
}

FONT_FAMILY = "Segoe UI, Inter, Arial, sans-serif"


# ═══════════════════════════════════════════════════════════════
#   TEMA GENERAL
# ═══════════════════════════════════════════════════════════════

def apply_theme(fig, title=None, subtitle=None, height=420, show_legend=None,
                xaxis_title=None, yaxis_title=None, y_is_currency=False):
    """Aplica el tema institucional SAC a un figure Plotly.

    Args:
        fig: plotly.graph_objects.Figure
        title: Título principal (en negrita)
        subtitle: Subtítulo opcional debajo del título
        height: alto en px (default 420)
        show_legend: True/False, o None para dejar el default del figure
        xaxis_title / yaxis_title: sobrescribir títulos de ejes
        y_is_currency: si True, formatea ticks del eje Y como S/
    Returns:
        fig (mutado in-place + retornado por conveniencia)
    """
    # Título compuesto
    title_html = None
    if title:
        if subtitle:
            title_html = (
                f"<b>{title}</b>"
                f"<br><span style='font-size:11px;color:{PALETTE['muted']};"
                f"font-weight:400'>{subtitle}</span>"
            )
        else:
            title_html = f"<b>{title}</b>"

    layout_updates = dict(
        template="simple_white",
        font=dict(family=FONT_FAMILY, size=12, color=PALETTE["text_soft"]),
        plot_bgcolor=PALETTE["bg"],
        paper_bgcolor=PALETTE["bg"],
        colorway=SEQUENCE,
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor=PALETTE["border"],
            font=dict(size=12, color=PALETTE["text"], family=FONT_FAMILY),
        ),
        margin=dict(l=60, r=30, t=70 if title else 30, b=55),
        height=height,
    )

    if title_html:
        layout_updates["title"] = dict(
            text=title_html,
            font=dict(size=16, color=PALETTE["text"], family=FONT_FAMILY),
            x=0.0, xanchor="left", y=0.96, yanchor="top",
        )

    if show_legend is not None:
        layout_updates["showlegend"] = show_legend

    fig.update_layout(**layout_updates)

    # Ejes estilo uniforme
    fig.update_xaxes(
        showgrid=False,
        showline=True, linewidth=1, linecolor=PALETTE["grid"],
        tickfont=dict(size=11, color=PALETTE["muted"]),
        title_font=dict(size=12, color=PALETTE["text_soft"]),
        title_text=xaxis_title if xaxis_title is not None else None,
        zeroline=False,
    )
    fig.update_yaxes(
        showgrid=True, gridcolor=PALETTE["grid_soft"], gridwidth=1,
        showline=False,
        tickfont=dict(size=11, color=PALETTE["muted"]),
        title_font=dict(size=12, color=PALETTE["text_soft"]),
        title_text=yaxis_title if yaxis_title is not None else None,
        zeroline=True, zerolinecolor=PALETTE["grid"],
    )
    if y_is_currency:
        fig.update_yaxes(tickprefix="S/ ", tickformat=",.0f")

    return fig


# ═══════════════════════════════════════════════════════════════
#   RENDER + DESCARGA
# ═══════════════════════════════════════════════════════════════

def _modebar_config(filename="chart"):
    """Config del modebar de Plotly con descarga de PNG al clic."""
    return {
        "displayModeBar": True,
        "displaylogo": False,
        "modeBarButtonsToRemove": [
            "select2d", "lasso2d", "autoScale2d", "hoverClosestCartesian",
            "hoverCompareCartesian",
        ],
        "toImageButtonOptions": {
            "format": "png",
            "filename": filename,
            "height": 720,
            "width": 1280,
            "scale": 2,
        },
        "responsive": True,
    }


def render_chart(fig, key, filename=None, show_downloads=True,
                 download_label="Descargar"):
    """Renderiza un Plotly chart con barra de herramientas limpia + botones
    de descarga HTML y PNG para compartir.

    Args:
        fig: Figure ya estilizado (llamar apply_theme antes)
        key: clave única de Streamlit
        filename: nombre base de archivo (sin extensión). Default = key.
        show_downloads: si True, agrega botones HTML/PNG debajo del chart.
        download_label: texto de la columna de descargas (vacío = sin label).
    """
    fname = filename or key

    st.plotly_chart(
        fig, use_container_width=True, key=key,
        config=_modebar_config(fname),
    )

    if not show_downloads:
        return

    # Botones de descarga (HTML interactivo + PNG estático)
    with st.container():
        cols = st.columns([5, 1.1, 1.1])
        if download_label:
            cols[0].markdown(
                f"<div style='color:{PALETTE['muted']};font-size:0.78rem;"
                f"padding-top:0.35rem'>💾 {download_label}</div>",
                unsafe_allow_html=True,
            )

        # HTML interactivo (no requiere dependencias extra)
        try:
            html_str = fig.to_html(include_plotlyjs="cdn", full_html=True)
            cols[1].download_button(
                "HTML", data=html_str.encode("utf-8"),
                file_name=f"{fname}.html", mime="text/html",
                key=f"{key}__dl_html", use_container_width=True,
            )
        except Exception:
            pass

        # PNG estático (requiere kaleido). Si no está, mostramos tip.
        try:
            png_bytes = fig.to_image(format="png", width=1280, height=720, scale=2)
            cols[2].download_button(
                "PNG", data=png_bytes,
                file_name=f"{fname}.png", mime="image/png",
                key=f"{key}__dl_png", use_container_width=True,
            )
        except Exception:
            # Fallback: botón deshabilitado con tooltip sobre el modebar
            cols[2].markdown(
                f"<div title='Usa el ícono 📷 del chart para descargar PNG' "
                f"style='background:{PALETTE['surface']};color:{PALETTE['muted']};"
                f"border:1px solid {PALETTE['grid']};border-radius:6px;"
                f"padding:0.35rem 0;text-align:center;font-size:0.78rem;'>"
                f"PNG 📷</div>",
                unsafe_allow_html=True,
            )


# ═══════════════════════════════════════════════════════════════
#   ANOTACIONES / HELPERS DE COMPOSICIÓN
# ═══════════════════════════════════════════════════════════════

def add_reference_line(fig, y, label=None, color=None, dash="dash"):
    """Añade una línea horizontal de referencia estilizada."""
    color = color or PALETTE["danger"]
    kwargs = dict(
        y=y, line_dash=dash, line_color=color, line_width=1.5, opacity=0.85,
    )
    if label:
        kwargs.update(
            annotation_text=label,
            annotation_position="top right",
            annotation_font=dict(color=color, size=10, family=FONT_FAMILY),
        )
    fig.add_hline(**kwargs)
    return fig


def style_bar(fig, gradient=False, corner_radius=4):
    """Mejora el estilo visual de un gráfico de barras existente."""
    fig.update_traces(
        marker=dict(
            line=dict(width=0),
            cornerradius=corner_radius,
        ),
        selector=dict(type="bar"),
    )
    return fig


def style_line(fig, marker_size=6, line_width=2.2):
    """Mejora el estilo visual de un gráfico de líneas existente."""
    fig.update_traces(
        line=dict(width=line_width),
        marker=dict(size=marker_size, line=dict(width=0)),
        selector=dict(type="scatter"),
    )
    return fig
