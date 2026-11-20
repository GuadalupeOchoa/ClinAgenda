"""Carga datos de DEMOSTRACIÓN (inventados) para probar o presentar el sistema.

Crea usuarios de prueba (admin, recepción y médico) con contraseñas aleatorias
que se guardan en demo_credenciales.txt (excluido de Git), algunos pacientes
y citas para la semana. Se puede ejecutar varias veces.

Uso:  python demo_datos.py
"""
import secrets
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

import validaciones as v
from db import conexion

USUARIOS = [("demo_admin", "Administrador Demo", "ADMIN", None),
            ("demo_rosa", "Rosa (Recepción Demo)", "RECEPCION", None),
            ("demo_salazar", "Dr. Salazar (Demo)", "MEDICO", 2)]

PACIENTES = [  # tipo, documento, nombres, apellidos, nacimiento, teléfono, responsable, tel. resp.
    ("CEDULA", "1710034065", "María", "López Andrade", "1980-05-10", "0991234567", None, None),
    ("CEDULA", "0102030400", "Juan", "Pérez Mora", "1955-11-02", "072345678", None, None),
    ("PASAPORTE", "AB123456", "Carlos", "Rivas", "1990-03-15", "0987654321", None, None),
    ("NINGUNO", None, "Sofía", "Pérez Vega", "2025-08-01", None, "Ana Vega", "0998877665"),
    ("CEDULA", "1712345675", "Rosa", "Guamán Tituaña", "1948-01-20", None, "Luis Guamán", "0977665544"),
]


def dia_habil(desde, n):
    """n-ésimo día de lunes a viernes a partir de 'desde' (0 = el mismo si es hábil)."""
    d = desde
    while d.weekday() > 4:
        d += timedelta(days=1)
    for _ in range(n):
        d += timedelta(days=1)
        while d.weekday() > 4:
            d += timedelta(days=1)
    return d


def main():
    lineas = ["Usuarios de DEMOSTRACIÓN de ClinAgenda (no usar en producción)", ""]
    with conexion() as con, con.cursor() as cur:
        for usuario, nombre, rol, medico_id in USUARIOS:
            clave = secrets.token_urlsafe(9)
            cur.execute("""INSERT INTO usuarios (usuario, nombre, clave_hash, rol, medico_id)
                           VALUES (%s,%s,%s,%s,%s)
                           ON CONFLICT (usuario) DO UPDATE SET clave_hash=EXCLUDED.clave_hash, activo=TRUE""",
                        (usuario, nombre, generate_password_hash(clave), rol, medico_id))
            lineas.append(f"{rol:10} usuario: {usuario:14} contraseña: {clave}")
        cur.execute("SELECT id FROM usuarios WHERE usuario='demo_rosa'")
        rosa = cur.fetchone()["id"]

        ids = []
        for t, doc, nom, ape, nac, tel, resp, tel_r in PACIENTES:
            cur.execute("SELECT id FROM pacientes WHERE nombre_busqueda=%s AND fecha_nacimiento=%s",
                        (v.clave_busqueda(f"{nom} {ape}"), nac))
            fila = cur.fetchone()
            if not fila:
                cur.execute("""INSERT INTO pacientes (tipo_documento, documento, nombres, apellidos, nombre_busqueda,
                               fecha_nacimiento, telefono, responsable, telefono_responsable, creado_por)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                            (t, doc, nom, ape, v.clave_busqueda(f"{nom} {ape}"), nac, tel, resp, tel_r, rosa))
                fila = cur.fetchone()
            ids.append(fila["id"])

        hoy = date.today()
        d0, d1, d2 = dia_habil(hoy, 0), dia_habil(hoy, 1), dia_habil(hoy, 2)
        citas = [  # paciente, médico, clínica, fecha, hora, motivo, estado
            (ids[0], 1, 1, d0, "08:00", "Control general", "ATENDIDA"),
            (ids[1], 4, 1, d0, "08:30", "Presión alta", "NO_ASISTIO"),
            (ids[3], 2, 1, d0, "09:00", "Control niño sano", "AGENDADA"),
            (ids[4], 11, 3, d0, "10:00", "Dolor de rodilla", "AGENDADA"),
            (ids[2], 5, 2, d0, "11:00", "Revisión de lunar", "AGENDADA"),
            (ids[0], 2, 2, d1, "15:00", "Consulta pediátrica para su hijo", "AGENDADA"),
            (ids[1], 4, 1, d1, "09:30", "Reagendada", "AGENDADA"),
            (ids[4], 11, 3, d2, "08:00", "Control", "CANCELADA"),
        ]
        for pac, med, cli, f, h, motivo, estado in citas:
            cur.execute("""SELECT 1 FROM citas WHERE paciente_id=%s AND fecha=%s AND hora=%s""", (pac, f, h))
            if cur.fetchone():
                continue
            cur.execute("""INSERT INTO citas (paciente_id, medico_id, clinica_id, fecha, hora, motivo, estado,
                           motivo_cancelacion, creado_por) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT DO NOTHING""",
                        (pac, med, cli, f, h, motivo, estado,
                         "El paciente llamó, viaja ese día" if estado == "CANCELADA" else None, rosa))

    with open("demo_credenciales.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    print("Datos de demostración cargados. Usuarios y contraseñas en demo_credenciales.txt")


if __name__ == "__main__":
    main()
