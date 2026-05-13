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

def descargar_lapositiva(usuario: str = None, password: str = None,
                         download_dir: str = None, headless: bool = True) -> pd.DataFrame:
    """
    Descarga el Excel MIDAGRI desde Agroevaluaciones (La Positiva).

    Flujo confirmado:
    1. GET catastrofico.agroevaluaciones.com/login
    2. Llenar input[type="text"] (usuario) + input[type="password"]
    3. Clic button "Iniciar sesión" → redirige a /
    4. Menú: Avisos → Todos (URL: /todos)
    5. Botón "Midagri" (sin FOGASA) → API /aviso/midagrid/export
    6. Descarga toma ~70 segundos (4000+ registros)
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

            # 5. Clic y polling robusto (hasta 5 min)
            # El portal LP no siempre dispara un download event tradicional —
            # a veces genera un blob via JS. Por eso usamos varias estrategias:
            #   A. Evento download capturado por _on_download
            #   B. Link <a download> con href blob: que apareció en el DOM
            # Si encontramos por A, listo. Si no, buscamos B y hacemos clic.

            midagri_btn.click()
            click_time = time.time()
            max_wait = 300  # 5 minutos
            check_interval = 3

            while (time.time() - click_time) < max_wait:
                page.wait_for_timeout(check_interval * 1000)

                # Estrategia A: ¿se disparó un evento download?
                if downloads_caught:
                    dl = downloads_caught[0]
                    file_path = os.path.join(
                        download_dir,
                        f"lp_midagri_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    )
                    dl.save_as(file_path)
                    break

                # Estrategia B: buscar link blob:/download en el DOM
                try:
                    blob_info = page.evaluate("""() => {
                        const links = document.querySelectorAll(
                            'a[href^="blob:"], a[download]'
                        );
                        return Array.from(links).map(a => ({
                            download: a.download || '',
                            href: a.href
                        })).filter(x => x.download || x.href.startsWith('blob:'));
                    }""")
                    if blob_info:
                        # Hay un link blob — hacer clic para forzar la descarga
                        for bl in blob_info:
                            try:
                                sel = (f'a[download="{bl["download"]}"]'
                                       if bl["download"]
                                       else 'a[href^="blob:"]')
                                link = page.query_selector(sel)
                                if not link:
                                    continue
                                with page.expect_download(timeout=60000) as info:
                                    link.click()
                                dl = info.value
                                file_path = os.path.join(
                                    download_dir,
                                    f"lp_midagri_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                                )
                                dl.save_as(file_path)
                                break
                            except Exception:
                                continue
                        if file_path:
                            break
                except Exception:
                    pass  # JS evaluation falla en algunas paginas, seguir

            if not file_path:
                raise TimeoutError(
                    "La Positiva: pasaron 5 min y no se disparo descarga "
                    "(ni evento download, ni link blob detectado). "
                    "Posible cambio en el portal."
                )

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
