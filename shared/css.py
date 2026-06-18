"""CSS global del dashboard SAC — fuente única de estilos.

REDISEÑO 2026 · Identidad institucional MIDAGRI 2024
====================================================
Dirección: institucional limpio / data product.
- Paleta VERDE oficial MIDAGRI (Pantone P 142-15 / 368 / 7738 C) + acentos
  teal (3145/306) y cálidos (7569/1235/7577). Sin gradientes decorativos.
- Tipografía Raleway (institucional) en toda la interfaz.
- Superficies blancas planas, fondo gris-verdoso muy claro, bordes hairline.
- Cifras tabulares, jerarquía por escala/peso (no por color de relleno).

Conserva TODOS los selectores que ya usa la app (sidebar-brand, page-header,
hero, action-card, stepper, metric-card-v2, report-card, status-banner,
section-header, stTabs, tab-intro, chat-header, engine-badge, sug-btn,
query-result-box, footer, etc.) — es drop-in, no rompe el markup existente.
"""

import streamlit as st

GLOBAL_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Raleway:wght@400;500;600;700;800&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=swap');

    /* Ícono de línea Material (reemplazo de emojis). Uso:
       <span class="ms">description</span>  ·  ver lista en fonts.google.com/icons */
    .ms {
        font-family: 'Material Symbols Rounded'; font-weight: 400; font-style: normal;
        font-size: 1.25rem; line-height: 1; letter-spacing: normal; text-transform: none;
        display: inline-flex; vertical-align: middle; white-space: nowrap; direction: ltr;
        -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga';
        -webkit-font-smoothing: antialiased; color: var(--color-brand);
    }

    /* ══════════════════════════════════════════
       DESIGN TOKENS — MIDAGRI 2024 (single source)
       Espejados en shared/charts.PALETTE
       ══════════════════════════════════════════ */
    :root {
        /* Verde institucional MIDAGRI */
        --color-primary: #1f3d2b;        /* verde forest: títulos, cifras, rellenos primarios */
        --color-primary-mid: #00758d;    /* teal PANTONE 3145 C — datos secundarios */
        --color-brand: #008f49;          /* PANTONE P 142-15 C — acción primaria */
        --color-brand-bright: #76bc21;   /* PANTONE 368 C */
        --color-midagri: #45a041;        /* PANTONE 7738 C */
        --color-midagri-soft: #76bc21;
        --color-accent: #0a7a43;         /* verde legible para acentos/links/activo */
        /* Semánticos (alineados a la paleta) */
        --color-success: #45a041;
        --color-warning: #b06e16;        /* texto ámbar legible (fill: #DA8824) */
        --color-gold: #ffb71b;           /* PANTONE 1235 C */
        --color-orange: #e47e3d;         /* PANTONE 7577 C */
        --color-danger: #c0392b;
        --color-info: #00b2e3;           /* PANTONE 306 C */
        --color-teal: #00758d;
        /* Neutros */
        --color-neutral: #8a938f;
        --color-text: #23292b;
        --color-text-soft: #586066;
        --color-bg: #ffffff;
        --color-surface: #ffffff;
        --color-surface-2: #f5f7f4;
        --color-border: #e6eae6;
        --color-grid-soft: #eef2ee;
        --color-green-soft: #eaf4ec;
        --color-green-line: #cde5d4;

        /* Espaciado (4-8-12-16-24-32-48) */
        --space-1: 0.25rem; --space-2: 0.5rem; --space-3: 0.75rem;
        --space-4: 1rem; --space-5: 1.5rem; --space-6: 2rem; --space-7: 3rem;

        /* Radios — más sobrios que el set anterior */
        --radius-xs: 7px; --radius-sm: 9px; --radius-md: 11px;
        --radius-lg: 13px; --radius-xl: 16px; --radius-pill: 999px;

        /* Sombras — sutiles, planas */
        --shadow-xs: 0 1px 2px rgba(31,61,43,0.04);
        --shadow-sm: 0 1px 3px rgba(31,61,43,0.06);
        --shadow-md: 0 4px 14px rgba(31,61,43,0.06);
        --shadow-lg: 0 8px 28px rgba(31,61,43,0.10);

        --trans-fast: 120ms ease;
        --trans-med: 200ms ease;
    }

    /* ══════════════════════════════════════════
       TIPOGRAFÍA — Raleway en toda la UI
       (NO se toca la fuente de los íconos Material:
        se excluye stIconMaterial para no romperlos)
       ══════════════════════════════════════════ */
    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stSidebar"],
    [data-testid="stMarkdownContainer"],
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5,
    .stApp p, .stApp label, .stApp li,
    .stButton > button, .stDownloadButton > button,
    .stTextInput input, .stTextArea textarea, .stDateInput input,
    [data-baseweb="tab"], [data-baseweb="select"] {
        font-family: 'Raleway', system-ui, -apple-system, sans-serif;
    }
    /* Salvaguarda: los íconos Material conservan su tipografía de ligaduras */
    [data-testid="stIconMaterial"], .material-icons, .material-symbols-outlined, .ms {
        font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    }

    .spacer-xs { height: var(--space-2); }
    .spacer-sm { height: var(--space-3); }
    .spacer-md { height: var(--space-4); }
    .spacer-lg { height: var(--space-5); }
    .spacer-xl { height: var(--space-6); }

    /* Ritmo vertical de títulos de sección */
    .stMarkdown h3 { margin: 1.4rem 0 0.5rem; font-weight: 700; color: var(--color-primary); letter-spacing: -0.01em; }
    .stMarkdown h4 { margin: 1.1rem 0 0.45rem; font-weight: 700; color: var(--color-primary); }

    [data-testid="stDivider"] hr, hr {
        border: none; border-top: 1px solid var(--color-border);
        margin: var(--space-5) 0; opacity: 1;
    }

    /* ══════════════════════════════════════════
       GLOBAL RESET & BASE
       ══════════════════════════════════════════ */
    .block-container { padding-top: 0.9rem; max-width: 1200px; }
    [data-testid="stAppViewBlockContainer"],
    [data-testid="stAppViewContainer"] { background: var(--color-surface-2); }

    /* Sidebar limpio */
    [data-testid="stSidebar"] {
        background: var(--color-surface);
        border-right: 1px solid var(--color-border);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { font-size: 0.85rem; }

    /* ── Sidebar branding ──
       app.py debe renderizar el logo oficial con st.image("assets/midagri_logo.png").
       Este bloque estiliza el contenedor + el sub-rótulo SAC (sin gradiente navy). */
    .sidebar-brand {
        background: transparent;
        padding: 0.2rem 0.2rem 1rem;
        border-bottom: 1px solid var(--color-grid-soft);
        margin: 0 0 1rem 0;
        text-align: left;
    }
    .sidebar-brand img { width: 100%; max-width: 210px; height: auto; display: block; }
    .sidebar-brand h2 {
        color: var(--color-primary); font-size: 0.82rem; font-weight: 700;
        margin: 0.85rem 0 0; letter-spacing: 0.01em; display: flex; align-items: center; gap: 7px;
    }
    .sidebar-brand h2::before {
        content: ''; width: 7px; height: 7px; border-radius: 2px;
        background: var(--color-brand); flex-shrink: 0;
    }
    .sidebar-brand p {
        color: var(--color-neutral); font-size: 0.62rem; font-weight: 600;
        letter-spacing: 0.14em; text-transform: uppercase; margin: 0.25rem 0 0 1rem;
    }
    .sidebar-brand .badge-sb {
        display: inline-block; background: var(--color-green-soft);
        color: var(--color-accent); padding: 0.2rem 0.7rem; border-radius: var(--radius-pill);
        font-size: 0.62rem; font-weight: 600; margin-top: 0.6rem;
        border: 1px solid var(--color-green-line); letter-spacing: 0.04em;
    }

    /* ══════════════════════════════════════════
       PAGE HEADER — PLANO (sin gradiente)
       Título + descripción + badge sobre línea hairline
       ══════════════════════════════════════════ */
    .page-header {
        background: transparent; padding: 0.2rem 0 1rem; border-radius: 0;
        border-bottom: 1px solid var(--color-border);
        margin-bottom: 1.4rem; position: relative; overflow: visible;
    }
    .page-header .ph-row {
        display: flex; justify-content: space-between; align-items: flex-end;
        gap: 1.4rem; position: relative;
    }
    .page-header h1 {
        color: var(--color-primary) !important; font-size: 1.55rem; font-weight: 700;
        margin: 0; line-height: 1.18; letter-spacing: -0.015em;
    }
    .page-header .page-desc {
        color: var(--color-text-soft); font-size: 0.85rem; margin: 0.45rem 0 0; font-weight: 400;
    }
    .page-header .ph-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: var(--color-surface); color: var(--color-text-soft);
        padding: 0.32rem 0.85rem; border-radius: var(--radius-pill);
        font-size: 0.72rem; font-weight: 600; white-space: nowrap;
        border: 1px solid var(--color-border); flex-shrink: 0;
    }

    /* ══════════════════════════════════════════
       HERO — Landing (plano, no gradiente)
       ══════════════════════════════════════════ */
    .hero {
        background: var(--color-surface); padding: 0.2rem 0 1.1rem;
        border-radius: 0; border-bottom: 1px solid var(--color-border);
        margin-bottom: 1.6rem; position: relative; overflow: visible; box-shadow: none;
    }
    .hero::before { display: none; }
    .hero h1 {
        color: var(--color-primary) !important; font-size: 1.7rem; font-weight: 800;
        margin: 0 0 0.25rem 0; letter-spacing: -0.02em;
    }
    .hero .subtitle { color: var(--color-text-soft); font-size: 0.9rem; margin: 0; }
    .hero .hero-row { display: flex; justify-content: space-between; align-items: flex-end; }
    .hero .badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: var(--color-green-soft); color: var(--color-accent);
        padding: 0.32rem 0.9rem; border-radius: var(--radius-pill);
        font-size: 0.72rem; font-weight: 600; border: 1px solid var(--color-green-line);
        backdrop-filter: none;
    }

    /* ══════════════════════════════════════════
       ACTION CARD — Pantalla inicial
       ══════════════════════════════════════════ */
    .action-card {
        background: var(--color-surface); border: 1px solid var(--color-border);
        border-radius: var(--radius-xl); padding: 2.5rem 2rem; text-align: center;
        box-shadow: var(--shadow-sm); transition: all var(--trans-med);
    }
    .action-card:hover { box-shadow: var(--shadow-md); border-color: var(--color-green-line); }
    .action-card h2 { color: var(--color-primary); margin: 0.8rem 0 0.4rem; font-size: 1.35rem; font-weight: 700; }
    .action-card p { color: var(--color-text-soft); font-size: 0.9rem; margin: 0 auto; max-width: 500px; line-height: 1.65; }

    /* ══════════════════════════════════════════
       STEPPER — Progreso de descarga (verde)
       ══════════════════════════════════════════ */
    .stepper { display: flex; justify-content: center; gap: 0; margin: 1.6rem 0; padding: 0 1rem; }
    .step { display: flex; align-items: center; gap: 0.5rem; }
    .step-circle {
        width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center;
        justify-content: center; font-weight: 700; font-size: 0.85rem; flex-shrink: 0;
        transition: all var(--trans-med);
    }
    .step-pending .step-circle { background: var(--color-grid-soft); color: var(--color-neutral); }
    .step-active .step-circle { background: var(--color-brand); color: #fff; animation: pulse 1.5s infinite; }
    .step-done .step-circle { background: var(--color-midagri); color: #fff; }
    .step-error .step-circle { background: var(--color-danger); color: #fff; }
    .step-label { font-size: 0.82rem; font-weight: 600; }
    .step-pending .step-label { color: var(--color-neutral); }
    .step-active .step-label { color: var(--color-brand); }
    .step-done .step-label { color: var(--color-midagri); }
    .step-error .step-label { color: var(--color-danger); }
    .step-connector { width: 42px; height: 2px; background: var(--color-border); margin: 0 0.3rem; align-self: center; }
    .step-connector.done { background: var(--color-midagri); }
    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(0,143,73,0.35); }
        50% { box-shadow: 0 0 0 9px rgba(0,143,73,0); }
    }

    /* ══════════════════════════════════════════
       METRIC CARDS — KPIs (sin barras de color arcoíris)
       Jerarquía por escala/peso; acentos solo en delta.
       ══════════════════════════════════════════ */
    .metric-card-v2 {
        background: var(--color-surface); border-radius: var(--radius-md);
        padding: 1.1rem 1.2rem; border: 1px solid var(--color-border);
        box-shadow: var(--shadow-xs); transition: all var(--trans-med);
    }
    .metric-card-v2:hover { box-shadow: var(--shadow-md); border-color: var(--color-green-line); }
    .metric-card-v2 .label {
        color: var(--color-neutral); font-size: 0.68rem; text-transform: uppercase;
        letter-spacing: 0.07em; font-weight: 700; margin-bottom: 0.55rem;
    }
    .metric-card-v2 .value {
        color: var(--color-primary); font-size: 1.7rem; font-weight: 700; line-height: 1.15;
        letter-spacing: -0.01em; font-variant-numeric: tabular-nums;
    }
    .metric-card-v2 .delta { font-size: 0.78rem; margin-top: 0.35rem; font-weight: 600; }
    .delta-positive { color: var(--color-accent); }
    .delta-neutral { color: var(--color-neutral); }
    .delta-warning { color: var(--color-warning); }
    /* Acentos neutralizados: ya NO pintan una barra lateral de color.
       Se conservan las clases para no romper render_metric(). */
    .accent-blue, .accent-green, .accent-amber, .accent-purple, .accent-red {
        border-left: 1px solid var(--color-border);
    }

    /* ══════════════════════════════════════════
       REPORT CARDS — Pantalla inicial
       ══════════════════════════════════════════ */
    .report-card {
        background: var(--color-surface); border: 1px solid var(--color-border);
        border-radius: var(--radius-lg); padding: 1.5rem; height: 100%;
        box-shadow: var(--shadow-xs); transition: all var(--trans-med);
    }
    .report-card:hover { box-shadow: var(--shadow-md); border-color: var(--color-green-line); }
    .report-card .icon {
        font-size: 1.4rem; margin-bottom: 0.6rem; display: inline-flex; align-items: center;
        justify-content: center; width: 46px; height: 46px; background: var(--color-green-soft);
        color: var(--color-brand); border-radius: var(--radius-md);
    }
    .report-card h3 { color: var(--color-primary); margin: 0.5rem 0; font-size: 1rem; font-weight: 700; }
    .report-card p { color: var(--color-text-soft); font-size: 0.83rem; margin: 0.3rem 0 0; line-height: 1.6; }

    /* ══════════════════════════════════════════
       STATUS BANNER (verde, plano)
       ══════════════════════════════════════════ */
    .status-banner {
        background: var(--color-surface); border: 1px solid var(--color-border);
        border-radius: var(--radius-md); padding: 0.7rem 1.1rem;
        display: flex; align-items: center; gap: 0.6rem; margin: 0.5rem 0;
    }
    .status-banner .dot {
        width: 8px; height: 8px; background: var(--color-midagri); border-radius: 50%;
        animation: blink 2s infinite; flex-shrink: 0;
    }
    @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
    .status-banner span { color: var(--color-text-soft); font-size: 0.82rem; font-weight: 500; }
    .status-banner span b { color: var(--color-text); }

    /* ══════════════════════════════════════════
       SECTION HEADERS
       ══════════════════════════════════════════ */
    .section-header { display: flex; align-items: center; gap: 0.55rem; margin: 1rem 0 0.85rem; }
    .section-header .icon-box {
        width: 32px; height: 32px; border-radius: var(--radius-sm); display: flex;
        align-items: center; justify-content: center; font-size: 1rem; flex-shrink: 0;
        background: var(--color-green-soft) !important; color: var(--color-brand);
    }
    .section-header h3 { color: var(--color-primary); font-size: 1.1rem; font-weight: 700; margin: 0; }

    /* ══════════════════════════════════════════
       TABS
       ══════════════════════════════════════════ */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--color-surface-2); border-radius: var(--radius-md);
        padding: 4px; gap: 2px; border: 1px solid var(--color-border);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-sm); padding: 8px 16px; font-weight: 500;
        font-size: 0.84rem; color: var(--color-text-soft); transition: all var(--trans-fast);
    }
    .stTabs [data-baseweb="tab"]:hover { background: rgba(255,255,255,0.7); color: var(--color-primary); }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #fff !important; box-shadow: var(--shadow-sm);
        color: var(--color-primary) !important; font-weight: 700;
    }
    .stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display: none; }

    /* ══════════════════════════════════════════
       TAB INTRO / CHAT (acento verde)
       ══════════════════════════════════════════ */
    .tab-intro {
        background: var(--color-surface-2); padding: 1.1rem 1.4rem; border-radius: var(--radius-md);
        border: 1px solid var(--color-border); border-left: 3px solid var(--color-brand); margin-bottom: 1rem;
    }
    .tab-intro .title { font-size: 0.98rem; font-weight: 700; color: var(--color-primary); margin-bottom: 0.3rem; }
    .tab-intro .desc { color: var(--color-text-soft); font-size: 0.85rem; line-height: 1.6; }

    .chat-header {
        background: var(--color-green-soft); padding: 1.25rem 1.4rem; border-radius: var(--radius-md);
        border: 1px solid var(--color-green-line); border-left: 3px solid var(--color-brand); margin-bottom: 1rem;
    }
    .chat-header .title { font-size: 1.02rem; font-weight: 700; color: var(--color-primary); }
    .chat-header .subtitle { color: var(--color-text-soft); font-size: 0.83rem; margin-top: 0.2rem; }
    .engine-badge {
        display: inline-flex; align-items: center; gap: 5px; padding: 0.3rem 0.9rem;
        border-radius: var(--radius-pill); font-size: 0.72rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.5px;
    }
    .sug-btn {
        display: inline-block; background: var(--color-surface); border: 1px solid var(--color-border);
        border-radius: var(--radius-sm); padding: 0.5rem 0.8rem; font-size: 0.8rem;
        color: var(--color-text-soft); cursor: pointer; transition: all var(--trans-fast);
    }
    .sug-btn:hover { border-color: var(--color-brand); color: var(--color-brand); background: var(--color-green-soft); }
    .query-result-box {
        background: var(--color-surface); padding: 1.5rem; border-radius: var(--radius-md);
        border: 1px solid var(--color-border); font-family: 'Raleway', sans-serif;
        font-size: 0.92rem; line-height: 1.75; color: var(--color-text);
        white-space: pre-wrap; box-shadow: var(--shadow-xs);
    }
    .query-context {
        background: var(--color-green-soft); padding: 0.6rem 1rem; border-radius: var(--radius-sm);
        margin-bottom: 0.8rem; color: var(--color-accent); font-size: 0.83rem;
        display: flex; justify-content: space-between; align-items: center;
    }

    /* ══════════════════════════════════════════
       FOOTER
       ══════════════════════════════════════════ */
    .footer {
        text-align: center; color: var(--color-neutral); font-size: 0.72rem;
        padding: 1.5rem 0 1rem; border-top: 1px solid var(--color-border); margin-top: 2rem; line-height: 1.7;
    }

    /* ══════════════════════════════════════════
       BUTTONS & MISC
       ══════════════════════════════════════════ */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    .stButton > button[kind="primary"] {
        background: var(--color-brand) !important; border: 1px solid var(--color-brand) !important;
        border-radius: var(--radius-sm) !important; padding: 0.62rem 1.6rem !important;
        font-weight: 700 !important; letter-spacing: 0.2px !important; color: #fff !important;
        box-shadow: none !important; transition: all var(--trans-med) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: #007a3e !important; border-color: #007a3e !important;
        box-shadow: 0 4px 14px rgba(0,143,73,0.22) !important; transform: translateY(-1px) !important;
    }
    .stButton > button[kind="secondary"] {
        border-radius: var(--radius-sm) !important; border: 1px solid var(--color-border) !important;
        color: var(--color-primary) !important; font-weight: 600 !important; background: var(--color-surface) !important;
        transition: all var(--trans-fast) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: var(--color-brand) !important; color: var(--color-brand) !important; background: var(--color-green-soft) !important;
    }
    .streamlit-expanderHeader { background: var(--color-surface-2); border-radius: var(--radius-sm); font-weight: 600; font-size: 0.9rem; }
    .stDownloadButton > button {
        border-radius: var(--radius-sm) !important; font-weight: 600 !important;
        border: 1px solid var(--color-border) !important; transition: all var(--trans-fast) !important;
    }
    .stDownloadButton > button:hover {
        border-color: var(--color-brand) !important; color: var(--color-brand) !important; background: var(--color-green-soft) !important;
    }
    .stDataFrame { border-radius: var(--radius-sm); overflow: hidden; }

    /* ══════════════════════════════════════════
       SIDEBAR — Indicador de página activa (verde)
       ══════════════════════════════════════════ */
    [data-testid="stSidebarNav"] a[aria-current="page"],
    [data-testid="stSidebarNav"] li[aria-current="page"] > a,
    [data-testid="stSidebarNav"] [role="link"][aria-current="page"] {
        background: var(--color-green-soft) !important;
        border-left: 2px solid var(--color-brand) !important;
        font-weight: 700 !important; border-radius: 8px !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] span,
    [data-testid="stSidebarNav"] li[aria-current="page"] > a span { color: var(--color-primary) !important; }

    /* ══════════════════════════════════════════
       SCROLLBARS
       ══════════════════════════════════════════ */
    [data-testid="stDataFrame"] ::-webkit-scrollbar,
    .stDataFrame ::-webkit-scrollbar { width: 10px; height: 10px; }
    [data-testid="stDataFrame"] ::-webkit-scrollbar-track,
    .stDataFrame ::-webkit-scrollbar-track { background: var(--color-grid-soft); border-radius: 6px; }
    [data-testid="stDataFrame"] ::-webkit-scrollbar-thumb,
    .stDataFrame ::-webkit-scrollbar-thumb { background: #c4d0c6; border-radius: 6px; border: 2px solid var(--color-grid-soft); }
    [data-testid="stDataFrame"] ::-webkit-scrollbar-thumb:hover,
    .stDataFrame ::-webkit-scrollbar-thumb:hover { background: var(--color-neutral); }

    /* ══════════════════════════════════════════
       FOCUS VISIBLE (verde)
       ══════════════════════════════════════════ */
    button:focus-visible, [role="button"]:focus-visible, a:focus-visible, [data-baseweb="tab"]:focus-visible {
        outline: 2px solid var(--color-brand) !important; outline-offset: 2px !important; border-radius: 6px;
    }

    /* ══════════════════════════════════════════
       DARK MODE (recoloreado a la identidad verde)
       ══════════════════════════════════════════ */
    @media (prefers-color-scheme: dark) {
        :root:not([data-theme="light"]) {
            --color-bg: #0c1410; --color-surface: #121a15; --color-surface-2: #0e1611;
            --color-border: #20312a; --color-grid-soft: #1a2820;
            --color-text: #e6efe8; --color-text-soft: #9fb0a6; --color-neutral: #7e8f85;
            --color-primary: #d6ecdd;
        }
        [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] { background: #0c1410; }
        .block-container { color: #e6efe8; }
        [data-testid="stSidebar"] { background: #0e1611; border-right: 1px solid #20312a; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] label { color: #c4d4ca; }
        .metric-card-v2, .action-card, .report-card, .status-banner,
        .tab-intro, .query-result-box, .chat-header {
            background: #121a15 !important; color: #e6efe8 !important; border-color: #20312a !important;
        }
        .metric-card-v2 .label { color: #9fb0a6 !important; }
        .metric-card-v2 .value, .page-header h1, .hero h1, .section-header h3 { color: #d6ecdd !important; }
        .streamlit-expanderHeader, [data-testid="stExpander"] summary {
            background: #121a15 !important; color: #e6efe8 !important;
        }
        [data-testid="stDivider"] hr, hr { border-top-color: #20312a !important; }
        .stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div, .stDateInput input {
            background: #0e1611 !important; color: #e6efe8 !important; border-color: #20312a !important;
        }
        [data-testid="stDataFrame"] [role="columnheader"] { background: #1a2820 !important; color: #e6efe8 !important; }
        .stDownloadButton > button { background: #121a15 !important; color: #e6efe8 !important; border-color: #20312a !important; }
    }
    [data-theme="dark"] [data-testid="stAppViewContainer"] { background: #0c1410; }
    [data-theme="dark"] [data-testid="stSidebar"] { background: #0e1611; border-right: 1px solid #20312a; }
    [data-theme="dark"] .metric-card-v2, [data-theme="dark"] .action-card, [data-theme="dark"] .report-card,
    [data-theme="dark"] .status-banner, [data-theme="dark"] .tab-intro, [data-theme="dark"] .query-result-box,
    [data-theme="dark"] .chat-header {
        background: #121a15 !important; color: #e6efe8 !important; border-color: #20312a !important;
    }
    [data-theme="dark"] .metric-card-v2 .value,
    [data-theme="dark"] .page-header h1, [data-theme="dark"] .hero h1, [data-theme="dark"] .section-header h3 { color: #d6ecdd !important; }
    [data-theme="dark"] [data-testid="stDivider"] hr, [data-theme="dark"] hr { border-top-color: #20312a !important; }
    [data-theme="dark"] [data-testid="stDataFrame"] [role="columnheader"] { background: #1a2820 !important; color: #e6efe8 !important; }
</style>
"""


def inject_css():
    """Inyecta el CSS global una sola vez por sesión."""
    if st.session_state.get("_css_injected"):
        return
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.session_state["_css_injected"] = True
