"""CSS global del dashboard SAC — fuente única de estilos."""

import streamlit as st

GLOBAL_CSS = """
<style>
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
       PAGE HEADER
       ══════════════════════════════════════════ */
    .page-header {
        background: linear-gradient(135deg, #0c2340 0%, #1a5276 35%, #2980b9 100%);
        padding: 1.4rem 2rem;
        border-radius: 14px;
        margin-bottom: 1.2rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(12,35,64,0.2);
    }
    .page-header::before {
        content: '';
        position: absolute;
        top: -60%;
        right: -15%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%);
        border-radius: 50%;
    }
    .page-header h1 {
        color: #fff !important;
        font-size: 1.5rem;
        font-weight: 800;
        margin: 0 0 0.15rem 0;
        position: relative;
    }
    .page-header .page-desc {
        color: rgba(255,255,255,0.7);
        font-size: 0.85rem;
        margin: 0;
        position: relative;
    }
    .page-header .breadcrumb {
        color: rgba(255,255,255,0.5);
        font-size: 0.7rem;
        margin-bottom: 0.4rem;
        position: relative;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 500;
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
</style>
"""


def inject_css():
    """Inyecta el CSS global. Llamar una vez desde app.py."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
