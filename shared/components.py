"""Componentes UI reutilizables del dashboard SAC."""
import streamlit as st


def render_metric(label, value, delta=None, accent="blue"):
    """Renderiza una tarjeta de métrica KPI."""
    delta_html = ""
    if delta:
        delta_html = f'<div class="delta delta-positive">{delta}</div>'
    return (
        f'<div class="metric-card-v2 accent-{accent}">'
        f'  <div class="label">{label}</div>'
        f'  <div class="value">{value}</div>'
        f'  {delta_html}'
        f'</div>'
    )


def render_stepper(steps):
    """Renderiza indicador de progreso por pasos."""
    html = '<div class="stepper">'
    for i, (label, status) in enumerate(steps):
        icon = {"done": "&#10003;", "active": "&#9679;", "error": "&#10007;"}.get(status, str(i + 1))
        html += f'<div class="step step-{status}"><div class="step-circle">{icon}</div><div class="step-label">{label}</div></div>'
        if i < len(steps) - 1:
            conn_cls = "done" if status == "done" else ""
            html += f'<div class="step-connector {conn_cls}"></div>'
    html += '</div>'
    return html


def page_header(title, description="", badge="🌾 SAC 2025-2026"):
    """Renderiza el header compacto de cada página.

    Args:
        title: Título H1 de la página.
        description: Línea descriptiva opcional (aparece bajo el título).
        badge: Texto del pill a la derecha. Default mantiene identidad SAC
               (🌾 SAC 2025-2026); páginas específicas pueden pasar un
               badge diferenciado para romper la monotonía visual.
    """
    desc_html = f'<p class="page-desc">{description}</p>' if description else ""
    st.markdown(f"""
    <div class="page-header">
        <div class="ph-row">
            <div>
                <h1>{title}</h1>
                {desc_html}
            </div>
            <div class="ph-badge">{badge}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def footer():
    """Renderiza el footer estándar MIDAGRI."""
    st.markdown("""
    <div class="footer">
        SAC 2025-2026 · Dirección de Seguro y Fomento del Financiamiento Agrario · MIDAGRI<br>
        Sistema automatizado para la gestión de reportes del Seguro Agrícola Catastrófico
    </div>
    """, unsafe_allow_html=True)
