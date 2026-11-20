"""Crea la base de datos ClinAgenda, sus tablas, datos iniciales y el usuario
administrador. Se puede ejecutar varias veces sin dañar lo existente.

Uso:  python init_db.py
"""
import getpass
import os
import sys

import psycopg2
from psycopg2 import sql
from werkzeug.security import generate_password_hash

from db import parametros_conexion

BASE = os.path.dirname(os.path.abspath(__file__))


def crear_base():
    params = parametros_conexion("postgres")
    nombre = parametros_conexion()["dbname"]
    con = psycopg2.connect(**params)
    con.autocommit = True
    with con.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (nombre,))
        if cur.fetchone():
            print(f"- La base de datos «{nombre}» ya existe.")
        else:
            cur.execute(sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0")
                        .format(sql.Identifier(nombre)))
            print(f"+ Base de datos «{nombre}» creada.")
    con.close()


def ejecutar_scripts():
    con = psycopg2.connect(**parametros_conexion())
    with con, con.cursor() as cur:
        for archivo in ("schema.sql", "datos_iniciales.sql"):
            with open(os.path.join(BASE, "sql", archivo), encoding="utf-8") as f:
                cur.execute(f.read())
            print(f"+ Ejecutado sql/{archivo}")
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE rol='ADMIN'")
        if cur.fetchone()[0] == 0:
            print("\nCree el usuario ADMINISTRADOR (la doctora o quien administre el sistema).")
            usuario = (input("Usuario [admin]: ").strip().lower() or "admin")
            while True:
                clave = getpass.getpass("Contraseña (mínimo 8 caracteres, no se ve al escribir): ")
                if len(clave) >= 8 and clave == getpass.getpass("Repita la contraseña: "):
                    break
                print("  Las contraseñas no coinciden o son muy cortas. Intente de nuevo.")
            cur.execute("""INSERT INTO usuarios (usuario, nombre, clave_hash, rol)
                           VALUES (%s, %s, %s, 'ADMIN')""",
                        (usuario, "Administrador", generate_password_hash(clave)))
            print(f"+ Usuario administrador «{usuario}» creado.")
        else:
            print("- Ya existe un usuario administrador.")
    con.close()


if __name__ == "__main__":
    try:
        crear_base()
        ejecutar_scripts()
    except psycopg2.OperationalError as e:
        print("\nNo se pudo conectar a PostgreSQL. Revise que el servicio esté encendido y que")
        print("la clave en el archivo .env sea correcta.\nDetalle:", e)
        sys.exit(1)
    print("\nListo. Ahora ejecute:  python app.py   y abra http://localhost:5000")
