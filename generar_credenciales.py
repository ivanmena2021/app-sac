# -*- coding: utf-8 -*-
"""Generador de credenciales para la autenticación de la app SAC.

Uso (en tu máquina, NO en el servidor):
    python generar_credenciales.py

Te pide usuario/nombre/contraseña para cada miembro del equipo y al
final imprime los valores de las DOS variables que hay que configurar
en Railway (Settings → Variables del servicio):

    SAC_AUTH_USERS        ← el JSON con los usuarios (hashes bcrypt)
    SAC_AUTH_COOKIE_KEY   ← clave de firma del cookie "recordarme"

Las contraseñas NUNCA se guardan en texto plano: solo el hash bcrypt
(irreversible). Si alguien olvida su clave, se vuelve a correr este
script y se reemplaza la variable en Railway.

Requiere: pip install bcrypt
"""
import getpass
import json
import secrets
import sys


def _cargar_existentes():
    """Modo 'agregar': pega el SAC_AUTH_USERS actual para partir de él.

    Devuelve (users: dict, es_existente: bool). Si el usuario no pega
    nada, arranca de cero.
    """
    print("¿Vas a AGREGAR usuarios a los que ya tienes, o empezar de cero?")
    print("  - Para AGREGAR: copia el valor actual de SAC_AUTH_USERS desde")
    print("    Railway (Variables) y pégalo abajo, luego Enter.")
    print("  - Para EMPEZAR DE CERO: solo presiona Enter.\n")
    raw = input("Pega SAC_AUTH_USERS actual (o Enter): ").strip()
    if not raw:
        return {}, False
    try:
        users = json.loads(raw)
        if not isinstance(users, dict):
            print("  El valor pegado no es un objeto JSON de usuarios. "
                  "Empezando de cero.\n")
            return {}, False
        print(f"  [OK] {len(users)} usuario(s) existente(s) cargado(s): "
              f"{', '.join(users.keys())}\n")
        return users, True
    except Exception:
        print("  No pude leer ese JSON (¿pegado incompleto?). "
              "Empezando de cero.\n")
        return {}, False


def main():
    try:
        import bcrypt
    except ImportError:
        sys.exit("Falta bcrypt. Ejecuta primero:  pip install bcrypt")

    print("=" * 64)
    print("  Generador de credenciales — App SAC")
    print("=" * 64)

    users, es_existente = _cargar_existentes()

    print("Agrega un usuario por persona. Si el usuario ya existe, podrás")
    print("reemplazar su contraseña. Deja el usuario vacío (Enter) para terminar.\n")

    cambios = 0
    while True:
        usuario = input("Usuario (ej. imena): ").strip().lower()
        if not usuario:
            break
        if usuario in users:
            resp = input(f"  '{usuario}' ya existe. ¿Reemplazar su contraseña? (s/N): ").strip().lower()
            if resp != "s":
                print("  Saltado.\n")
                continue
        nombre_default = users.get(usuario, {}).get("name", "")
        prompt_nombre = (f"Nombre completo [{nombre_default}]: " if nombre_default
                         else "Nombre completo (ej. Ivan Mena): ")
        nombre = input(prompt_nombre).strip() or nombre_default
        pwd = getpass.getpass("Contraseña: ")
        pwd2 = getpass.getpass("Repetir contraseña: ")
        if pwd != pwd2:
            print("  Las contraseñas no coinciden. Intenta de nuevo.\n")
            continue
        if len(pwd) < 8:
            print("  Mínimo 8 caracteres. Intenta de nuevo.\n")
            continue
        h = bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
        users[usuario] = {"name": nombre or usuario, "password": h}
        cambios += 1
        print(f"  [OK] {usuario} guardado.\n")

    if not users:
        sys.exit("No hay usuarios. Nada que generar.")
    if cambios == 0 and es_existente:
        print("\nNo hiciste cambios. El SAC_AUTH_USERS actual sigue válido; "
              "no hace falta tocar Railway.")
        return

    print()
    print("=" * 64)
    if es_existente:
        print("  LISTO — reemplaza SOLO esta variable en Railway:")
    else:
        print("  LISTO — configura estas 2 variables en Railway")
        print("  (proyecto app-sac → servicio → Variables)")
    print("=" * 64)
    print()
    print("SAC_AUTH_USERS")
    print(json.dumps(users, ensure_ascii=False, separators=(",", ":")))
    print()

    if es_existente:
        print("IMPORTANTE: NO cambies SAC_AUTH_COOKIE_KEY — si la cambias, todos")
        print("los usuarios actuales tendrán que volver a loguearse. Déjala como está.")
    else:
        cookie_key = secrets.token_hex(32)
        print("SAC_AUTH_COOKIE_KEY")
        print(cookie_key)
        print()
        print("Después de guardarlas, Railway redepliega solo y la app pedirá")
        print("login. El cookie 'recordarme' dura 7 días.")


if __name__ == "__main__":
    main()
