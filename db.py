"""Conexión a PostgreSQL. Todo el acceso a datos pasa por aquí."""
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


def parametros_conexion(dbname=None):
    return dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=dbname or os.getenv("DB_NAME", "ClinAgenda"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=5,
    )


@contextmanager
def conexion():
    """Abre una conexión, hace COMMIT si todo sale bien y ROLLBACK si hay error."""
    con = psycopg2.connect(**parametros_conexion(),
                           cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def consultar(sql, params=None, uno=False):
    with conexion() as con, con.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone() if uno else cur.fetchall()


def registrar_auditoria(cur, usuario_id, accion, entidad, entidad_id=None, detalle=None):
    """Se llama dentro de la misma transacción que el cambio auditado."""
    cur.execute(
        "INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id, detalle) "
        "VALUES (%s, %s, %s, %s, %s)",
        (usuario_id, accion, entidad, entidad_id, detalle),
    )
