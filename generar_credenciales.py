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


def main():
    try:
        import bcrypt
    except ImportError:
        sys.exit("Falta bcrypt. Ejecuta primero:  pip install bcrypt")

    print("=" * 64)
    print("  Generador de credenciales — App SAC")
    print("=" * 64)
    print("Agrega un usuario por miembro del equipo.")
    print("Deja el usuario vacío (Enter) para terminar.\n")

    users = {}
    while True:
        usuario = input("Usuario (ej. imena): ").strip().lower()
        if not usuario:
            break
        if usuario in users:
            print("  Ese usuario ya fue agregado.\n")
            continue
        nombre = input("Nombre completo (ej. Ivan Mena): ").strip()
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
        print(f"  [OK] {usuario} agregado.\n")

    if not users:
        sys.exit("No se agregó ningún usuario. Nada que generar.")

    cookie_key = secrets.token_hex(32)

    print()
    print("=" * 64)
    print("  LISTO — configura estas 2 variables en Railway")
    print("  (proyecto app-sac → servicio → Settings → Variables)")
    print("=" * 64)
    print()
    print("SAC_AUTH_USERS")
    print(json.dumps(users, ensure_ascii=False, separators=(",", ":")))
    print()
    print("SAC_AUTH_COOKIE_KEY")
    print(cookie_key)
    print()
    print("Después de guardarlas, Railway redepliega solo y la app")
    print("pedirá login. El cookie 'recordarme' dura 7 días.")


if __name__ == "__main__":
    main()
