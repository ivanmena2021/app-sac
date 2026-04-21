"""Helpers de cache para recursos estáticos (JSON, archivos) compartidos
entre páginas, usando @st.cache_data para evitar relecturas en cada rerun.
"""
import json
import os

try:
    import streamlit as st
    _cache_data = st.cache_data
except Exception:  # pragma: no cover
    def _cache_data(*dargs, **dkwargs):
        def _dec(fn):
            return fn
        if dargs and callable(dargs[0]):
            return dargs[0]
        return _dec


@_cache_data(show_spinner=False, ttl=86400)
def load_json_cached(path):
    """Lee un JSON desde disco y cachea el resultado por 24h.

    Returns {} si el archivo no existe o falla el parse (para que las
    páginas no tengan que manejar excepciones de I/O en cada render).
    """
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
