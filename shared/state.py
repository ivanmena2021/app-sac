"""Gestión de session_state del dashboard SAC."""
import streamlit as st


def init_session_state():
    """Inicializa claves por defecto en session_state."""
    defaults = {
        "processed": False,
        "datos": None,
        "datos_filtered": None,
        "update_timestamp": None,
        "source": None,
        "rimac_rows": 0,
        "lp_rows": 0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def is_data_loaded():
    """Verifica si los datos están cargados."""
    return st.session_state.get("processed", False)


def get_datos():
    """Retorna datos filtrados si existen, sino los datos base."""
    return st.session_state.get("datos_filtered") or st.session_state.get("datos")


def require_data():
    """Guard: redirige a Inicio si no hay datos cargados."""
    if not is_data_loaded():
        st.warning("No hay datos cargados. Redirigiendo a la página de inicio...")
        st.switch_page("pages/inicio.py")
        st.stop()
