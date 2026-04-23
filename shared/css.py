"""CSS global del dashboard SAC — fuente única de estilos."""

import streamlit as st

GLOBAL_CSS = """
<style>
    /* ══════════════════════════════════════════
       DESIGN TOKENS — single source of truth
       (se pueden usar como var(--name) en reglas
        futuras sin romper el CSS existente)
       ══════════════════════════════════════════ */
    :root {
        /* Colores institucionales (espejados en shared/charts.PALETTE) */
        --color-primary: #0c2340;
        --color-primary-mid: #1a5276;
        --color-accent: #2980b9;
        --color-midagri: #408B14;
        --color-midagri-soft: #5FAE2E;
        --color-success: #27ae60;
        --color-warning: #f39c12;
        --color-danger: #e74c3c;
        --color-info: #3498db;
        --color-neutral: #64748b;
        --color-text: #1e293b;
        --color-text-soft: #475569;
        --color-bg: #ffffff;
        --color-surface: #f8fafc;
        --color-surface-2: #f4f7fa;
        --color-border: #e2e8f0;
        --color-grid-soft: #f1f5f9;

        /* Espaciado (progresión 4-8-12-16-24-32-48) */
        --space-1: 0.25rem;
        --space-2: 0.5rem;
        --space-3: 0.75rem;
        --space-4: 1rem;
        --space-5: 1.5rem;
        --space-6: 2rem;
        --space-7: 3rem;

        /* Radios */
        --radius-xs: 6px;
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 16px;
        --radius-xl: 20px;
        --radius-pill: 999px;

        /* Sombras */
        --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
        --shadow-sm: 0 2px 8px rgba(15, 23, 42, 0.05);
        --shadow-md: 0 4px 16px rgba(15, 23, 42, 0.07);
        --shadow-lg: 0 8px 32px rgba(12, 35, 64, 0.15);

        /* Transiciones */
        --trans-fast: 120ms ease;
        --trans-med: 220ms ease;
    }

    /* Utility classes para reemplazar <div style="height:Xrem"></div> */
    .spacer-xs { height: var(--space-2); }
    .spacer-sm { height: var(--space-3); }
    .spacer-md { height: var(--space-4); }
    .spacer-lg { height: var(--space-5); }
    .spacer-xl { height: var(--space-6); }

    /* Divider más sutil y consistente (aplicado a st.divider) */
    [data-testid="stDivider"] hr,
    hr {
        border: none;
        border-top: 1px solid var(--color-border);
        margin: var(--space-5) 0;
        opacity: 1;
    }

    /* ══════════════════════════════════════════
       GLOBAL RESET & BASE
       ══════════════════════════════════════════ */
    .block-container { padding-top: 0.8rem; max-width: 1200px; }
    [data-testid="stAppViewBlockContainer"] { background: #f4f7fa; }

    /* Sidebar profesional */
    [data-testid="stSidebar"] {
        background: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        font-size: 0.85rem;
    }

    /* Sidebar branding */
    .sidebar-brand {
        background: linear-gradient(135deg, #0c2340 0%, #1a5276 100%);
        padding: 1.2rem 1rem;
        border-radius: 12px;
        margin: 0 0 1rem 0;
        text-align: center;
    }
    .sidebar-brand h2 {
        color: #fff;
        font-size: 1.1rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.3px;
    }
    .sidebar-brand p {
        color: rgba(255,255,255,0.7);
        font-size: 0.75rem;
        margin: 0.2rem 0 0;
    }
    .sidebar-brand .badge-sb {
        display: inline-block;
        background: rgba(255,255,255,0.12);
        color: rgba(255,255,255,0.9);
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        font-size: 0.65rem;
        font-weight: 500;
        margin-top: 0.5rem;
        border: 1px solid rgba(255,255,255,0.1);
    }

    /* ══════════════════════════════════════════
       PAGE HEADER — compacto y profesional
       ══════════════════════════════════════════ */
    .page-header {
        background: linear-gradient(135deg, #0c2340 0%, #1a5276 50%, #2980b9 100%);
        padding: 1rem 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        position: relative;
        overflow: hidden;
    }
    .page-header .ph-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: relative;
    }
    .page-header h1 {
        color: #fff !important;
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.3;
    }
    .page-header .page-desc {
        color: rgba(255,255,255,0.65);
        font-size: 0.78rem;
        margin: 0.15rem 0 0;
    }
    .page-header .ph-badge {
        background: rgba(255,255,255,0.1);
        color: rgba(255,255,255,0.85);
        padding: 0.25rem 0.8rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 500;
        white-space: nowrap;
        border: 1px solid rgba(255,255,255,0.1);
        flex-shrink: 0;
    }

    /* ══════════════════════════════════════════
       HERO HEADER — Landing page
       ══════════════════════════════════════════ */
    .hero {
        background: linear-gradient(135deg, #0c2340 0%, #1a5276 35%, #2980b9 70%, #3498db 100%);
        padding: 1.8rem 2.5rem;
        border-radius: 18px;
        margin-bottom: 1.2rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 8px 32px rgba(12,35,64,0.25);
    }
    .hero::before {
        content: '';
        position: absolute;
        top: -60%;
        right: -15%;
        width: 500px;
        height: 500px;
        background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
        border-radius: 50%;
    }
    .hero h1 {
        color: #fff !important;
        font-size: 1.8rem;
        font-weight: 800;
        margin: 0 0 0.2rem 0;
        position: relative;
    }
    .hero .subtitle {
        color: rgba(255,255,255,0.75);
        font-size: 0.9rem;
        margin: 0;
        position: relative;
    }
    .hero .hero-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        position: relative;
    }
    .hero .badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(255,255,255,0.12);
        color: rgba(255,255,255,0.9);
        padding: 0.3rem 0.9rem;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 500;
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.1);
    }

    /* ══════════════════════════════════════════
       ACTION CARD — Pantalla inicial
       ══════════════════════════════════════════ */
    .action-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        padding: 2.5rem 2rem;
        text-align: center;
        box-shadow: 0 4px 24px rgba(0,0,0,0.04);
        transition: all 0.3s ease;
    }
    .action-card:hover {
        box-shadow: 0 8px 40px rgba(0,0,0,0.08);
        transform: translateY(-3px);
    }
    .action-card h2 { color: #0c2340; margin: 0.8rem 0 0.4rem; font-size: 1.5rem; font-weight: 700; }
    .action-card p { color: #64748b; font-size: 0.9rem; margin: 0; max-width: 500px; margin-left: auto; margin-right: auto; line-height: 1.6; }

    /* ══════════════════════════════════════════
       STEPPER — Progreso de descarga
       ══════════════════════════════════════════ */
    .stepper { display: flex; justify-content: center; gap: 0; margin: 1.5rem 0; padding: 0 1rem; }
    .step { display: flex; align-items: center; gap: 0.5rem; }
    .step-circle { width: 38px; height: 38px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem; flex-shrink: 0; transition: all 0.3s ease; }
    .step-pending .step-circle { background: #e8ecf1; color: #94a3b8; }
    .step-active .step-circle { background: #2980b9; color: #fff; animation: pulse 1.5s infinite; }
    .step-done .step-circle { background: #27ae60; color: #fff; }
    .step-error .step-circle { background: #e74c3c; color: #fff; }
    .step-label { font-size: 0.82rem; font-weight: 500; }
    .step-pending .step-label { color: #94a3b8; }
    .step-active .step-label { color: #2980b9; font-weight: 600; }
    .step-done .step-label { color: #27ae60; }
    .step-error .step-label { color: #e74c3c; }
    .step-connector { width: 40px; height: 2px; background: #e2e8f0; margin: 0 0.3rem; align-self: center; }
    .step-connector.done { background: #27ae60; }
    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(41,128,185,0.4); }
        50% { box-shadow: 0 0 0 10px rgba(41,128,185,0); }
    }

    /* ══════════════════════════════════════════
       METRIC CARDS — Dashboard
       ══════════════════════════════════════════ */
    .metric-card-v2 {
        background: white;
        border-radius: 14px;
        padding: 1.2rem 1.3rem;
        border: 1px solid #e8ecf1;
        box-shadow: 0 2px 12px rgba(0,0,0,0.03);
        transition: all 0.25s ease;
    }
    .metric-card-v2:hover { box-shadow: 0 6px 24px rgba(0,0,0,0.07); transform: translateY(-2px); }
    .metric-card-v2 .label { color: #64748b; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.6px; font-weight: 700; margin-bottom: 0.5rem; }
    .metric-card-v2 .value { color: #0c2340; font-size: 1.4rem; font-weight: 800; line-height: 1.2; }
    .metric-card-v2 .delta { font-size: 0.78rem; margin-top: 0.3rem; font-weight: 500; }
    .delta-positive { color: #27ae60; }
    .delta-neutral { color: #64748b; }
    .delta-warning { color: #f39c12; }
    .accent-blue { border-left: 4px solid #2980b9; }
    .accent-green { border-left: 4px solid #27ae60; }
    .accent-amber { border-left: 4px solid #f39c12; }
    .accent-purple { border-left: 4px solid #8e44ad; }
    .accent-red { border-left: 4px solid #e74c3c; }

    /* ══════════════════════════════════════════
       REPORT CARDS — Pantalla inicial
       ══════════════════════════════════════════ */
    .report-card {
        background: white; border: 1px solid #e8ecf1; border-radius: 16px;
        padding: 1.6rem; height: 100%; box-shadow: 0 2px 12px rgba(0,0,0,0.03);
        transition: all 0.25s ease;
    }
    .report-card:hover { box-shadow: 0 6px 24px rgba(0,0,0,0.07); transform: translateY(-2px); }
    .report-card .icon { font-size: 2rem; margin-bottom: 0.6rem; display: inline-block; width: 52px; height: 52px; line-height: 52px; text-align: center; background: #f0f7ff; border-radius: 14px; }
    .report-card h3 { color: #0c2340; margin: 0.5rem 0; font-size: 1.05rem; font-weight: 700; }
    .report-card p { color: #64748b; font-size: 0.83rem; margin: 0.3rem 0 0; line-height: 1.6; }

    /* ══════════════════════════════════════════
       STATUS BANNER
       ══════════════════════════════════════════ */
    .status-banner {
        background: linear-gradient(90deg, #e8f8ee 0%, #d4f1de 100%);
        border: 1px solid #b8e6c8; border-radius: 12px;
        padding: 0.7rem 1.2rem; display: flex; align-items: center; gap: 0.6rem; margin: 0.5rem 0;
    }
    .status-banner .dot { width: 8px; height: 8px; background: #27ae60; border-radius: 50%; animation: blink 2s infinite; flex-shrink: 0; }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
    .status-banner span { color: #155724; font-size: 0.82rem; font-weight: 500; }

    /* ══════════════════════════════════════════
       SECTION HEADERS
       ══════════════════════════════════════════ */
    .section-header { display: flex; align-items: center; gap: 0.6rem; margin: 1rem 0 0.8rem; }
    .section-header .icon-box { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; flex-shrink: 0; }
    .section-header h3 { color: #0c2340; font-size: 1.15rem; font-weight: 700; margin: 0; }

    /* ══════════════════════════════════════════
       TABS — Para reportes (dentro de páginas)
       ══════════════════════════════════════════ */
    .stTabs [data-baseweb="tab-list"] {
        background: #edf2f7; border-radius: 10px; padding: 3px; gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px; padding: 8px 16px; font-weight: 500; font-size: 0.84rem; color: #64748b;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover { background: rgba(255,255,255,0.6); color: #1a5276; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: white !important; box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        color: #1a5276 !important; font-weight: 600;
    }
    .stTabs [data-baseweb="tab-highlight"] { display: none; }
    .stTabs [data-baseweb="tab-border"] { display: none; }

    /* ══════════════════════════════════════════
       TAB CONTENT CARDS
       ══════════════════════════════════════════ */
    .tab-intro {
        background: linear-gradient(135deg, #f8fafc, #edf2f7);
        padding: 1.2rem 1.5rem; border-radius: 14px;
        border-left: 4px solid #2980b9; margin-bottom: 1rem;
    }
    .tab-intro .title { font-size: 1rem; font-weight: 700; color: #0c2340; margin-bottom: 0.3rem; }
    .tab-intro .desc { color: #64748b; font-size: 0.85rem; line-height: 1.6; }

    /* ══════════════════════════════════════════
       CHAT — Consulta
       ══════════════════════════════════════════ */
    .chat-header {
        background: linear-gradient(135deg, #f0f7ff 0%, #e8f4f8 100%);
        padding: 1.3rem 1.5rem; border-radius: 14px;
        border-left: 4px solid #2980b9; margin-bottom: 1rem;
    }
    .chat-header .title { font-size: 1.05rem; font-weight: 700; color: #0c2340; }
    .chat-header .subtitle { color: #64748b; font-size: 0.83rem; margin-top: 0.2rem; }
    .engine-badge {
        display: inline-flex; align-items: center; gap: 5px;
        padding: 0.3rem 0.9rem; border-radius: 20px;
        font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
    }
    .sug-btn {
        display: inline-block; background: white; border: 1px solid #dce4ec;
        border-radius: 10px; padding: 0.5rem 0.8rem; font-size: 0.8rem; color: #475569;
        cursor: pointer; transition: all 0.2s ease;
    }
    .sug-btn:hover { border-color: #2980b9; color: #2980b9; background: #f0f7ff; }
    .query-result-box {
        background: white; padding: 1.5rem; border-radius: 14px;
        border: 1px solid #e2e8f0; font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 0.92rem; line-height: 1.75; color: #1a1a1a;
        white-space: pre-wrap; box-shadow: 0 2px 12px rgba(0,0,0,0.03);
    }
    .query-context {
        background: #f0f7ff; padding: 0.6rem 1rem; border-radius: 10px;
        margin-bottom: 0.8rem; color: #1a5276; font-size: 0.83rem;
        display: flex; justify-content: space-between; align-items: center;
    }

    /* ══════════════════════════════════════════
       FOOTER
       ══════════════════════════════════════════ */
    .footer {
        text-align: center; color: #94a3b8; font-size: 0.72rem;
        padding: 1.5rem 0 1rem 0; border-top: 1px solid #e2e8f0; margin-top: 2rem;
    }

    /* ══════════════════════════════════════════
       BUTTONS & MISC
       ══════════════════════════════════════════ */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0c2340, #1a5276, #2980b9) !important;
        border: none !important; border-radius: 12px !important;
        padding: 0.65rem 1.8rem !important; font-weight: 700 !important;
        letter-spacing: 0.3px !important;
        box-shadow: 0 4px 14px rgba(41,128,185,0.25) !important;
        transition: all 0.25s ease !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 22px rgba(41,128,185,0.35) !important;
        transform: translateY(-2px) !important;
    }
    .streamlit-expanderHeader { background: #f8fafc; border-radius: 10px; font-weight: 600; font-size: 0.9rem; }
    .stDownloadButton > button { border-radius: 10px !important; font-weight: 600 !important; border: 1px solid #d1d9e0 !important; transition: all 0.2s ease !important; }
    .stDownloadButton > button:hover { border-color: #2980b9 !important; color: #2980b9 !important; background: #f0f7ff !important; }
    .stDataFrame { border-radius: 10px; overflow: hidden; }

    /* ══════════════════════════════════════════
       DARK MODE — activado por preferencia del
       SO (prefers-color-scheme) y también por el
       toggle de Streamlit (Settings → Theme:
       Dark, que aplica [data-theme="dark"] al
       root del DOM).
       ══════════════════════════════════════════ */
    @media (prefers-color-scheme: dark) {
        :root:not([data-theme="light"]) {
            --color-bg: #0b1220;
            --color-surface: #111827;
            --color-surface-2: #0f1729;
            --color-border: #1f2a3d;
            --color-grid-soft: #1e293b;
            --color-text: #e2e8f0;
            --color-text-soft: #94a3b8;
        }
        [data-testid="stAppViewBlockContainer"] { background: #0b1220; }
        .block-container { color: #e2e8f0; }
        [data-testid="stSidebar"] {
            background: #0f1729;
            border-right: 1px solid #1f2a3d;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label { color: #cbd5e1; }

        /* Cards y contenedores */
        .metric-card-v2,
        .action-card,
        .report-card,
        .hero-left,
        .hero-right,
        .status-banner,
        .tab-intro,
        .query-result-box,
        .chat-header,
        .sem-drilldown-title {
            background: #111827 !important;
            color: #e2e8f0 !important;
            border-color: #1f2a3d !important;
        }
        .metric-card-v2 .label { color: #94a3b8 !important; }
        .metric-card-v2 .value { color: #e2e8f0 !important; }

        /* Expanders */
        .streamlit-expanderHeader,
        [data-testid="stExpander"] summary,
        [data-testid="stExpander"] details {
            background: #111827 !important;
            color: #e2e8f0 !important;
        }

        /* Hr/divider */
        [data-testid="stDivider"] hr, hr {
            border-top-color: #1f2a3d !important;
        }

        /* Inputs y selects */
        .stTextInput input, .stTextArea textarea,
        [data-baseweb="select"] > div,
        .stDateInput input {
            background: #0f1729 !important;
            color: #e2e8f0 !important;
            border-color: #1f2a3d !important;
        }

        /* Tablas */
        [data-testid="stDataFrame"] { color: #e2e8f0; }
        [data-testid="stDataFrame"] [role="columnheader"] {
            background: #1e293b !important;
            color: #e2e8f0 !important;
        }

        /* Download button */
        .stDownloadButton > button {
            background: #111827 !important;
            color: #e2e8f0 !important;
            border-color: #1f2a3d !important;
        }
        .stDownloadButton > button:hover {
            background: #1a2234 !important;
            color: #60a5fa !important;
            border-color: #2980b9 !important;
        }

        /* Captions */
        [data-testid="stCaptionContainer"],
        .stCaption { color: #94a3b8 !important; }

        /* Tabs (el Streamlit nativo) */
        [data-baseweb="tab"] { color: #cbd5e1 !important; }
        [data-baseweb="tab-list"] { border-bottom-color: #1f2a3d !important; }
    }

    /* Toggle explicito: si el usuario elige Dark en Streamlit
       (y el SO esta en light), Streamlit pone data-theme="dark"
       en el root. Espejamos las reglas. */
    [data-theme="dark"] [data-testid="stAppViewBlockContainer"] { background: #0b1220; }
    [data-theme="dark"] .block-container { color: #e2e8f0; }
    [data-theme="dark"] [data-testid="stSidebar"] {
        background: #0f1729;
        border-right: 1px solid #1f2a3d;
    }
    [data-theme="dark"] .metric-card-v2,
    [data-theme="dark"] .action-card,
    [data-theme="dark"] .report-card,
    [data-theme="dark"] .hero-left,
    [data-theme="dark"] .hero-right,
    [data-theme="dark"] .status-banner,
    [data-theme="dark"] .tab-intro,
    [data-theme="dark"] .query-result-box,
    [data-theme="dark"] .chat-header,
    [data-theme="dark"] .sem-drilldown-title {
        background: #111827 !important;
        color: #e2e8f0 !important;
        border-color: #1f2a3d !important;
    }
    [data-theme="dark"] .metric-card-v2 .label { color: #94a3b8 !important; }
    [data-theme="dark"] .metric-card-v2 .value { color: #e2e8f0 !important; }
    [data-theme="dark"] .streamlit-expanderHeader,
    [data-theme="dark"] [data-testid="stExpander"] summary {
        background: #111827 !important;
        color: #e2e8f0 !important;
    }
    [data-theme="dark"] [data-testid="stDivider"] hr,
    [data-theme="dark"] hr {
        border-top-color: #1f2a3d !important;
    }
    [data-theme="dark"] [data-testid="stDataFrame"] [role="columnheader"] {
        background: #1e293b !important;
        color: #e2e8f0 !important;
    }
</style>
"""


def inject_css():
    """Inyecta el CSS global. Guarda un flag en session_state para no
    re-inyectar (el <style> ya vive en el DOM del cliente tras el primer
    render). Esto ahorra enviar ~20 KB por cada rerun.
    """
    if st.session_state.get("_css_injected"):
        return
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.session_state["_css_injected"] = True
