"""
Módulo de descarga automática de datos SAC (Playwright)
=======================================================
Descarga los Excel de ambos portales usando navegador headless:
- SISGAQSAC (Rímac): www.sisgaqsac.pe  (~5MB, descarga inmediata)
- Agroevaluaciones (La Positiva): catastrofico.agroevaluaciones.com (~800KB, ~70s)

Instalación:
    pip install playwright pandas openpyxl
    python -m playwright install chromium
"""

import os
import glob
import time
import pandas as pd
from datetime import datetime


def _get_credentials(portal: str):
    """
    Obtiene credenciales desde Streamlit secrets o variables de entorno.

    Streamlit Cloud secrets (Settings > Secrets):
        [rimac]
        email = "correo@ejemplo.com"
        password = "contraseña"

        [lapositiva]
        usuario = "USUARIO"
        password = "contraseña"
    """
    try:
        import streamlit as st
        if portal == "rimac":
            return st.secrets["rimac"]["email"], st.secrets["rimac"]["password"]
        elif portal == "lapositiva":
            return st.secrets["lapositiva"]["usuario"], st.secrets["lapositiva"]["password"]
    except Exception:
        pass

    if portal == "rimac":
        return (
            os.environ.get("RIMAC_EMAIL", ""),
            os.environ.get("RIMAC_PASSWORD", "")
        )
    elif portal == "lapositiva":
        return (
            os.environ.get("LP_USUARIO", ""),
            os.environ.get("LP_PASSWORD", "")
        )
    return ("", "")


# ============================================================
#  SISGAQSAC — Rímac
# ============================================================

def descargar_rimac(email: str = None, password: str = None,
                    download_dir: str = None, headless: bool = True) -> pd.DataFrame:
    """
    Descarga el Excel de siniestros desde SISGAQSAC (Rímac).

    Flujo confirmado:
    1. GET sisgaqsac.pe → redirige a /Identity/Account/Login
    2. Llenar input[type="email"] + input[type="password"]
    3. Clic button "Acceder" → redirige a /UsuarioSeguimiento/registros
    4. Tabla con DataTables → botón "Excel" descarga inmediatamente
    """
    from playwright.sync_api import sync_playwright

    if not email or not password:
        email, password = _get_credentials("rimac")
    if not email or not password:
        raise ValueError("Credenciales de Rímac (SISGAQSAC) no configuradas")

    if not download_dir:
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "sac_auto")
    os.makedirs(download_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()

        try:
            # 1. Ir al portal
            page.goto("https://www.sisgaqsac.pe",
                      wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)

            # 2. Login
            page.wait_for_selector('input[type="email"]', timeout=10000).fill(email)
            page.wait_for_selector('input[type="password"]', timeout=5000).fill(password)
            page.wait_for_selector('button:has-text("Acceder")', timeout=5000).click()

            # 3. Esperar tabla de siniestros
            page.wait_for_timeout(5000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # Verificar login
            if not page.query_selector('text="Salir"'):
                raise ConnectionError("Login en SISGAQSAC falló")

            # 4. Clic en botón Excel (descarga inmediata)
            with page.expect_download(timeout=120000) as download_info:
                page.wait_for_selector('button:has-text("Excel")', timeout=10000).click()

            # 5. Guardar archivo
            download = download_info.value
            file_path = os.path.join(
                download_dir,
                f"rimac_siniestros_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            )
            download.save_as(file_path)

        finally:
            browser.close()

    # 6. Leer como DataFrame
    try:
        df = pd.read_excel(file_path)
    except Exception:
        df = pd.read_excel(file_path, engine='xlrd')

    return df


# ============================================================
#  Agroevaluaciones — La Positiva
# ============================================================

# Selectores reales de Agroevaluaciones (Tailwind/Vue, no Angular Material).
# Verificados con test_lp_bell_inspect.py el 2026-05-15:
#
#   Campanita:   <button class="relative p-1 ..."><svg>...<g id="icon/notification">...</svg></button>
#   Descarga:    <button class="text-xs text-green-600 ... underline"> Descargar ahora </button>
#
_BELL_SELECTORS = [
    # Primario: SVG con id explicito "icon/notification"
    'button:has(svg g[id="icon/notification"])',
    # Alternativos defensivos por si renombran el id
    'button:has(svg[viewBox="0 0 24 24"]) >> nth=0',
    'button.relative.p-1:has(svg)',
    # Fallback Material/otros frameworks (por si cambian de stack)
    'button:has(mat-icon:has-text("notifications"))',
    'button[aria-label*="notif" i]',
]

_DESCARGAR_SELECTOR = 'button:has-text("Descargar ahora")'


def _find_bell_button(page):
    """Encuentra el botón de la campanita de notificaciones en el header."""
    for sel in _BELL_SELECTORS:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el
        except Exception:
            continue

    # Fallback final: cualquier button en zona top-right con badge numerico
    try:
        candidates = page.evaluate(r"""() => {
            const all = document.querySelectorAll('button, a, [role="button"]');
            const results = [];
            for (const el of all) {
                const txt = (el.textContent || '').trim();
                const rect = el.getBoundingClientRect();
                if (/\d/.test(txt) && rect.top < 200 &&
                    rect.right > window.innerWidth * 0.5 &&
                    rect.width < 100) {
                    results.push(el.outerHTML.substring(0, 200));
                }
            }
            return results;
        }""")
        if candidates:
            # Volver a querar via Playwright usando el primer match
            buttons = page.query_selector_all('button, a, [role="button"]')
            for btn in buttons:
                try:
                    if btn.evaluate("e => e.outerHTML.substring(0, 200)") == candidates[0]:
                        return btn
                except Exception:
                    continue
    except Exception:
        pass

    return None


def _count_descargar_links(page, bell_button):
    """Abre la campanita, cuenta los botones 'Descargar ahora' y la cierra.

    Devuelve 0 si algo falla (mejor que crashear el flujo entero).
    """
    try:
        bell_button.click()
        page.wait_for_timeout(1200)
        links = page.query_selector_all(_DESCARGAR_SELECTOR)
        count = len(links)
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(400)
        return count
    except Exception:
        return 0


def descargar_lapositiva(usuario: str = None, password: str = None,
                         download_dir: str = None, headless: bool = True) -> pd.DataFrame:
    """
    Descarga el Excel MIDAGRI desde Agroevaluaciones (La Positiva).

    Flujo actualizado (2026-05+) — el portal ahora usa cola asincrónica con
    notificaciones en una "campanita" (top-right del header):

    1. Login en catastrofico.agroevaluaciones.com/login
    2. Menú: Avisos > Todos
    3. Clic en botón "Midagri" → server inicia generación async
    4. Aparece notificación "Estamos preparando tu archivo..." en la campanita
    5. ~60s después se convierte en "Tu archivo está listo para descargar"
       con un link "Descargar ahora"
    6. Clic en "Descargar ahora" → dispara la descarga real

    Tiempo total: ~70-120 segundos según carga del portal.
    """
    from playwright.sync_api import sync_playwright

    if not usuario or not password:
        usuario, password = _get_credentials("lapositiva")
    if not usuario or not password:
        raise ValueError("Credenciales de La Positiva (Agroevaluaciones) no configuradas")

    if not download_dir:
        download_dir = os.path.join(os.path.expanduser("~"), "Downloads", "sac_auto")
    os.makedirs(download_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            accept_downloads=True,
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        # Listener de descargas: el portal LP a veces dispara el evento
        # como blob/JS y `expect_download` lo pierde. `page.on("download")`
        # captura el evento en cualquier momento, no solo dentro de un with.
        downloads_caught = []

        def _on_download(dl):
            downloads_caught.append(dl)

        page.on("download", _on_download)

        # Listener de la respuesta del POST /export — clave para diagnosticar
        # si el servidor LP acepta el click de Midagri o lo rechaza.
        export_response = {
            "status": None,
            "body": "",
            "headers": "",
            "url": "",
            "request_seen": False,
        }

        def _on_request(req):
            if "midagri" in req.url.lower() and "export" in req.url.lower():
                export_response["request_seen"] = True

        def _on_response(resp):
            if "midagri" in resp.url.lower() and "export" in resp.url.lower():
                try:
                    export_response["status"] = resp.status
                    export_response["url"] = resp.url
                    # Headers compactos
                    h = resp.headers or {}
                    export_response["headers"] = (
                        f"content-type={h.get('content-type', '?')}, "
                        f"content-length={h.get('content-length', '?')}"
                    )
                    # Body (best-effort, max 1500 chars)
                    try:
                        body = resp.text()
                        export_response["body"] = body[:1500] if body else "(empty)"
                    except Exception as e:
                        export_response["body"] = f"(error leyendo body: {e})"
                except Exception:
                    pass

        page.on("request", _on_request)
        page.on("response", _on_response)

        file_path = None

        try:
            # 1. Ir al login
            page.goto("https://catastrofico.agroevaluaciones.com/login",
                      wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)

            # 2. Login
            page.wait_for_selector('input[type="text"]', timeout=5000).fill(usuario)
            page.wait_for_selector('input[type="password"]', timeout=5000).fill(password)
            page.wait_for_selector('button:has-text("Iniciar")', timeout=5000).click()

            page.wait_for_timeout(5000)
            page.wait_for_load_state("networkidle")

            # 3. Navegar a Avisos > Todos
            page.wait_for_selector('text="Avisos"', timeout=10000).click()
            page.wait_for_timeout(2000)
            page.wait_for_selector('text="Todos"', timeout=5000).click()
            page.wait_for_timeout(5000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # 4. Encontrar botón Midagri CORRECTO (no el username "MIDAGRI FOGASA")
            all_midagri = page.query_selector_all('button:has-text("Midagri")')
            midagri_btn = None
            for el in all_midagri:
                txt = el.inner_text().strip()
                if "FOGASA" not in txt.upper():
                    midagri_btn = el
                    break

            if not midagri_btn:
                raise ConnectionError(
                    "No se encontró el botón Midagri de descarga en Agroevaluaciones"
                )

            # 5. Localizar la campanita de notificaciones (top-right del header)
            bell_button = _find_bell_button(page)
            if not bell_button:
                raise ConnectionError(
                    "No se encontro la campanita de notificaciones en el portal "
                    "(selectores cambiaron o pagina en estado inesperado)."
                )

            # 6. Snapshot pre-click: contar cuantos 'Descargar ahora' ya hay
            #    Esto permite detectar el nuevo despues del clic en Midagri.
            initial_count = _count_descargar_links(page, bell_button)

            # 7. Click en Midagri y polling de la campanita hasta que aparezca
            #    una nueva entrada 'Descargar ahora' (~60s segun la app).
            midagri_btn.click()
            click_time = time.time()
            max_wait = 360  # 6 minutos (margen extra por carga del portal)
            poll_every = 10

            new_link = None
            iter_count = 0
            counts_history = []  # para diagnostico
            saw_preparando = False

            while (time.time() - click_time) < max_wait:
                iter_count += 1
                page.wait_for_timeout(poll_every * 1000)
                elapsed = int(time.time() - click_time)

                # Estrategia de respaldo: si por algun motivo el server vuelve
                # a disparar download directo (sin pasar por campanita), lo
                # captamos via el listener persistente.
                if downloads_caught:
                    dl = downloads_caught[0]
                    file_path = os.path.join(
                        download_dir,
                        f"lp_midagri_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    )
                    dl.save_as(file_path)
                    break

                # Asegurar que la campanita este ABIERTA antes de contar.
                # Detectamos estado por el header "Notificaciones" visible.
                panel_abierto = False
                try:
                    notif_header = page.query_selector('text="Notificaciones"')
                    panel_abierto = notif_header is not None and notif_header.is_visible()
                except Exception:
                    panel_abierto = False

                if not panel_abierto:
                    try:
                        bell_button.click()
                        page.wait_for_timeout(1500)
                    except Exception:
                        try:
                            page.keyboard.press("Escape")
                        except Exception:
                            pass
                        continue

                # Diagnostico: detectar "Estamos preparando" (confirma que el
                # click en Midagri si dispato una notificacion nueva)
                try:
                    prep_el = page.query_selector('text=/Estamos preparando/i')
                    if prep_el is not None and prep_el.is_visible():
                        saw_preparando = True
                except Exception:
                    pass

                links = page.query_selector_all(_DESCARGAR_SELECTOR)
                counts_history.append(len(links))

                if len(links) > initial_count:
                    new_link = links[0]
                    break

                # Cerrar dropdown para que la proxima iteracion lo abra fresco
                try:
                    page.keyboard.press("Escape")
                    page.wait_for_timeout(400)
                except Exception:
                    pass

            if file_path is None and new_link is None:
                # Capturar screenshot en BYTES (no path) para mostrarlo en Streamlit.
                # El path en Railway es efimero y no accesible desde la UI.
                screenshot_bytes = None
                page_url = ""
                page_html_snippet = ""
                try:
                    screenshot_bytes = page.screenshot(full_page=False)
                    page_url = page.url
                    # Snippet del HTML para ver estado del DOM
                    body_text = page.evaluate("() => document.body.innerText.substring(0, 1500)")
                    page_html_snippet = body_text or ""
                except Exception:
                    pass

                diag = (
                    f"iteraciones={iter_count}, "
                    f"counts_por_iter={counts_history[-10:]}, "
                    f"initial_count={initial_count}, "
                    f"preparando_visto={saw_preparando}, "
                    f"url={page_url}"
                )
                # Info clave: que respondió el server al POST /export
                export_diag = (
                    f"POST_request_seen={export_response['request_seen']}, "
                    f"POST_status={export_response['status']}, "
                    f"POST_url={export_response['url']!r}, "
                    f"POST_headers={export_response['headers']!r}, "
                    f"POST_body={export_response['body']!r}"
                )
                err = TimeoutError(
                    f"La Positiva: pasaron {max_wait}s sin notificacion 'archivo listo'. "
                    f"Diag: {diag}. "
                    f"Export: {export_diag}"
                )
                # Adjuntar info para que inicio.py pueda mostrarla
                err.lp_screenshot = screenshot_bytes
                err.lp_page_text = page_html_snippet
                err.lp_page_url = page_url
                err.lp_export_response = export_response
                raise err

            # 8. Si el flujo fue por campanita, clic en 'Descargar ahora'
            if new_link is not None and file_path is None:
                with page.expect_download(timeout=120000) as info:
                    new_link.click()
                dl = info.value
                file_path = os.path.join(
                    download_dir,
                    f"lp_midagri_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                )
                dl.save_as(file_path)

        finally:
            browser.close()

    # 7. Leer como DataFrame
    try:
        df = pd.read_excel(file_path)
    except Exception:
        df = pd.read_excel(file_path, engine='xlrd')

    return df


# ============================================================
#  Función principal: descargar ambos
# ============================================================

def descargar_ambos(rimac_email=None, rimac_password=None,
                    lp_usuario=None, lp_password=None,
                    download_dir=None, headless=True):
    """
    Descarga datos de ambos portales.

    Returns:
        dict con keys "siniestros" (Rímac) y "midagri" (La Positiva)
    """
    resultados = {}

    try:
        df_rimac = descargar_rimac(rimac_email, rimac_password, download_dir, headless)
        resultados["siniestros"] = {
            "success": True, "data": df_rimac, "rows": len(df_rimac),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        resultados["siniestros"] = {
            "success": False, "error": str(e),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    try:
        df_lp = descargar_lapositiva(lp_usuario, lp_password, download_dir, headless)
        resultados["midagri"] = {
            "success": True, "data": df_lp, "rows": len(df_lp),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        resultados["midagri"] = {
            "success": False, "error": str(e),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    return resultados
