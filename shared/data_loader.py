"""Funciones de carga de datos del dashboard SAC."""
import os
import io
import streamlit as st
from datetime import datetime


def check_auto_download():
    """Verifica si la descarga automática está disponible."""
    try:
        from auto_download import descargar_rimac, descargar_lapositiva, descargar_ambos
        return True
    except ImportError:
        return False


def check_credentials():
    """Verifica si hay credenciales configuradas."""
    has_rimac = False
    has_lp = False
    try:
        has_rimac = bool(st.secrets.get("rimac", {}).get("email"))
        has_lp = bool(st.secrets.get("lapositiva", {}).get("usuario"))
    except Exception:
        pass
    if not has_rimac:
        has_rimac = bool(os.environ.get("RIMAC_EMAIL"))
    if not has_lp:
        has_lp = bool(os.environ.get("LP_USUARIO"))
    return has_rimac, has_lp


def run_auto_download(stepper_placeholder):
    """Ejecuta la descarga automática de ambas aseguradoras y procesa los datos.

    Args:
        stepper_placeholder: st.empty() para actualizar el stepper visual

    Returns:
        True si exitoso, False si falló
    """
    from shared.components import render_stepper
    from auto_download import descargar_ambos
    from data_processor import process_dynamic_data

    try:
        # Step 1-2: Descargar
        with stepper_placeholder:
            st.markdown(render_stepper([
                ("Rímac", "active"), ("La Positiva", "pending"),
                ("Procesando", "pending"), ("Listo", "pending"),
            ]), unsafe_allow_html=True)

        result = descargar_ambos()
        if not result or not result.get("rimac") or not result.get("lapositiva"):
            return False

        with stepper_placeholder:
            st.markdown(render_stepper([
                ("Rímac", "done"), ("La Positiva", "done"),
                ("Procesando", "active"), ("Listo", "pending"),
            ]), unsafe_allow_html=True)

        # Step 3: Procesar
        buf_rimac = io.BytesIO(result["rimac"])
        buf_lp = io.BytesIO(result["lapositiva"])
        datos = process_dynamic_data(buf_lp, buf_rimac)

        # Step 4: Guardar en session state
        st.session_state["datos"] = datos
        st.session_state["processed"] = True
        st.session_state["update_timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        st.session_state["source"] = "auto"
        st.session_state["rimac_rows"] = result.get("rimac_rows", 0)
        st.session_state["lp_rows"] = result.get("lp_rows", 0)

        with stepper_placeholder:
            st.markdown(render_stepper([
                ("Rímac", "done"), ("La Positiva", "done"),
                ("Procesando", "done"), ("Listo", "done"),
            ]), unsafe_allow_html=True)

        return True

    except Exception as e:
        st.error(f"Error al procesar datos: {e}")
        return False


def process_manual_upload(midagri_file, siniestros_file):
    """Procesa archivos subidos manualmente.

    Returns:
        True si exitoso, False si falló
    """
    from data_processor import process_dynamic_data

    try:
        datos = process_dynamic_data(midagri_file, siniestros_file)
        st.session_state["datos"] = datos
        st.session_state["processed"] = True
        st.session_state["update_timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        st.session_state["source"] = "manual"
        return True
    except Exception as e:
        st.error(f"Error al procesar datos: {e}")
        return False


def build_consolidated_excel(midagri_df):
    """Construye Excel consolidado para descarga."""
    buf = io.BytesIO()
    cols = [c for c in midagri_df.columns if not c.startswith("_")]
    df_clean = midagri_df[cols]
    df_clean.to_excel(buf, index=False, sheet_name="Consolidado SAC")
    buf.seek(0)
    return buf.getvalue()
