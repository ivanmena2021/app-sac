"""Autenticación de la app SAC.

Gate central llamado desde app.py. Como la app usa st.navigation,
app.py corre en CADA carga de página — un solo gate protege las 12
páginas, incluidos los deep-links.

Credenciales (en orden de prioridad):
- Env var SAC_AUTH_USERS, o st.secrets["auth"]["users"]: JSON con
      {"usuario": {"name": "Nombre Apellido", "password": "<hash bcrypt>"}}
  Generar con:  python generar_credenciales.py
- Env var SAC_AUTH_COOKIE_KEY, o st.secrets["auth"]["cookie_key"]:
  clave de firma del cookie "recordarme". Si falta, se usa una clave
  aleatoria por proceso (la sesión sobrevive reruns, pero un redeploy
  obliga a re-loguear — seguro aunque menos cómodo).

Si SAC_AUTH_USERS no está configurada, la app corre SIN autenticación
(comportamiento previo a este feature) mostrando una advertencia en el
sidebar. Así el deploy no bloquea al equipo antes de configurar Railway.

Cada login exitoso deja una línea [AUTH] en los logs del servidor
(visible en Railway → Deployments → Logs): traza de acceso simple
para fines de auditoría.
"""
import json
import os
import secrets as _secrets
from datetime import datetime, timezone, timedelta

import streamlit as st

TZ_PERU = timezone(timedelta(hours=-5))

COOKIE_NAME = "sac_auth"
COOKIE_EXPIRY_DAYS = 7

# Fallback de clave de cookie: aleatoria por proceso. Estable entre
# reruns (vive a nivel módulo), se regenera en cada restart/redeploy.
_FALLBACK_COOKIE_KEY = _secrets.token_hex(32)


def _leer_config():
    """Lee usuarios y cookie_key de env vars o st.secrets.

    Returns: (users: dict | None, cookie_key: str)
    """
    users_raw = os.environ.get("SAC_AUTH_USERS", "")
    cookie_key = os.environ.get("SAC_AUTH_COOKIE_KEY", "")

    if not users_raw:
        try:
            users_raw = st.secrets["auth"]["users"]
        except Exception:
            users_raw = ""
    if not cookie_key:
        try:
            cookie_key = st.secrets["auth"]["cookie_key"]
        except Exception:
            cookie_key = ""

    users = None
    if users_raw:
        try:
            users = (json.loads(users_raw) if isinstance(users_raw, str)
                     else dict(users_raw))
            if not isinstance(users, dict) or not users:
                users = None
        except Exception:
            users = None  # JSON inválido → tratar como no configurado

    return users, (cookie_key or _FALLBACK_COOKIE_KEY)


def require_auth() -> None:
    """Gate de autenticación. Llamar en app.py antes de st.navigation.

    - Sin config → advertencia en sidebar y la app sigue (fail-open
      deliberado para el rollout; documentado arriba).
    - Con config → login form; si no está autenticado, st.stop().
    """
    users, cookie_key = _leer_config()

    if not users:
        with st.sidebar:
            st.caption("⚠ Acceso sin autenticación — configurar "
                       "`SAC_AUTH_USERS` en Railway (ver generar_credenciales.py).")
        return

    import streamlit_authenticator as stauth

    credentials = {"usernames": {}}
    for usuario, info in users.items():
        credentials["usernames"][str(usuario)] = {
            "name": info.get("name", str(usuario)),
            "password": info.get("password", ""),
            "email": info.get("email", f"{usuario}@sac.local"),
        }

    authenticator = stauth.Authenticate(
        credentials, COOKIE_NAME, cookie_key, COOKIE_EXPIRY_DAYS,
    )

    try:
        authenticator.login(
            location="main",
            fields={
                "Form name": "Acceso — SAC 2025-2026",
                "Username": "Usuario",
                "Password": "Contraseña",
                "Login": "Ingresar",
            },
        )
    except Exception as e:
        st.error(f"Error del módulo de autenticación: {e}")
        st.stop()

    status = st.session_state.get("authentication_status")

    if status is True:
        authenticator.logout("Cerrar sesión", "sidebar")
        # Traza de acceso: una línea por sesión de navegador (no por rerun)
        if not st.session_state.get("_auth_access_logged"):
            ahora = datetime.now(TZ_PERU).strftime("%Y-%m-%d %H:%M:%S")
            print(f"[AUTH] acceso OK: usuario={st.session_state.get('username')} "
                  f"hora={ahora} (Peru)")
            st.session_state["_auth_access_logged"] = True
        return

    if status is False:
        st.error("Usuario o contraseña incorrectos.")
    else:
        st.info("Ingrese sus credenciales para acceder al panel SAC.")
    st.stop()
