"""Pruebas automáticas de los controles descritos en DECISIONES.md.

Cada prueba corresponde a una pregunta de la clienta. Se ejecutan sobre una base de datos
APARTE llamada "ClinAgenda_pruebas", que se crea desde cero en cada ejecución, así nunca
se tocan los datos reales ni los de demostración.

Uso (desde la carpeta del proyecto):
    .\\venv\\Scripts\\python.exe -m unittest -v tests.test_controles
"""
import builtins
import getpass
import os
import random
import re
import string
import sys
import threading
import unittest
from datetime import timedelta
from unittest import mock

os.environ["DB_NAME"] = "ClinAgenda_pruebas"          # antes de importar db/app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2                                         # noqa: E402
from psycopg2 import sql                                # noqa: E402
from werkzeug.security import generate_password_hash   # noqa: E402

import app as aplicacion                                # noqa: E402
import init_db                                          # noqa: E402
import validaciones as v                                # noqa: E402
from db import conexion, consultar, parametros_conexion  # noqa: E402

CLAVE = "prueba2026"
CENTRO, NORTE = 1, 2
SALAZAR, ANDRADE = 2, 4      # Salazar: Centro mañanas y Norte tardes. Andrade: Centro mañanas.


def proximo_lunes():
    h = aplicacion.hoy()
    return h + timedelta(days=7 - h.weekday())


def setUpModule():
    con = psycopg2.connect(**parametros_conexion("postgres"))
    con.autocommit = True
    with con.cursor() as cur:
        cur.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier("ClinAgenda_pruebas")))
    con.close()
    with mock.patch.object(builtins, "input", lambda *a: "admin"), \
            mock.patch.object(getpass, "getpass", lambda *a: CLAVE), \
            mock.patch("builtins.print"):
        init_db.crear_base()
        init_db.ejecutar_scripts()
    with conexion() as con, con.cursor() as cur:
        for usuario, rol, medico in [("rosa", "RECEPCION", None), ("marcela", "RECEPCION", None),
                                     ("salazar", "MEDICO", SALAZAR)]:
            cur.execute("INSERT INTO usuarios (usuario, nombre, clave_hash, rol, medico_id) VALUES (%s,%s,%s,%s,%s)",
                        (usuario, usuario.title(), generate_password_hash(CLAVE), rol, medico))


class Base(unittest.TestCase):
    def cliente(self, usuario="rosa"):
        c = aplicacion.app.test_client()
        c.get("/login")
        r = c.post("/login", data={"usuario": usuario, "clave": CLAVE, "csrf": self.csrf(c)})
        self.assertEqual(r.status_code, 302, f"no pudo entrar {usuario}")
        c.get("/")
        return c

    @staticmethod
    def csrf(c):
        with c.session_transaction() as s:
            return s.get("csrf", "")

    def nuevo_paciente(self, c, **extra):
        letras = "".join(random.choice(string.ascii_lowercase) for _ in range(8))   # nombres: solo letras
        datos = dict(tipo_documento="NINGUNO", nombres="Paciente", apellidos=f"Prueba {letras}",
                     fecha_nacimiento="1990-01-01", telefono="0991234567")
        datos.update(extra)
        nombres = datos["apellidos"]
        r = c.post("/pacientes/nuevo", data=dict(csrf=self.csrf(c), **datos))
        self.assertEqual(r.status_code, 302, r.data.decode()[:1500])
        return consultar("SELECT id FROM pacientes WHERE apellidos=%s", (v.normalizar_nombre(nombres),), uno=True)["id"]

    def agendar(self, c, paciente, medico, clinica, fecha, hora):
        return c.post(f"/citas/nueva/{paciente}", data=dict(csrf=self.csrf(c), medico_id=medico,
                                                             clinica_id=clinica, fecha=fecha, hora=hora))

    def horas_libres(self, c, paciente, medico, clinica, fecha):
        html = c.get(f"/citas/nueva/{paciente}?clinica_id={clinica}&medico_id={medico}&fecha={fecha}").data.decode()
        return re.findall(r'name="hora" value="(\d\d:\d\d)"', html)

    def cita(self, paciente, fecha, hora):
        return consultar("SELECT * FROM citas WHERE paciente_id=%s AND fecha=%s AND hora=%s",
                         (paciente, fecha, hora), uno=True)


# ================================================================ SOBRE LAS CITAS
class SobreLasCitas(Base):
    def test_dos_recepcionistas_misma_hora_mismo_segundo(self):
        """Solo una de las dos citas se guarda; la otra recibe un aviso claro."""
        rosa, marcela = self.cliente("rosa"), self.cliente("marcela")
        p1, p2 = self.nuevo_paciente(rosa), self.nuevo_paciente(rosa)
        fecha = proximo_lunes() + timedelta(days=7)
        barrera, respuestas = threading.Barrier(2), {}

        def intentar(nombre, c, p):
            barrera.wait()
            respuestas[nombre] = self.agendar(c, p, ANDRADE, CENTRO, fecha, "09:00")

        hilos = [threading.Thread(target=intentar, args=a) for a in (("rosa", rosa, p1), ("marcela", marcela, p2))]
        [h.start() for h in hilos]
        [h.join() for h in hilos]
        n = consultar("""SELECT COUNT(*) n FROM citas WHERE medico_id=%s AND fecha=%s AND hora='09:00'
                         AND estado='AGENDADA'""", (ANDRADE, fecha), uno=True)["n"]
        self.assertEqual(n, 1)
        perdedora = [r for r in respuestas.values() if r.status_code == 200]
        self.assertEqual(len(perdedora), 1)
        self.assertRegex(perdedora[0].data.decode(), "acaba de tomar ese horario|ya no está disponible")

    def test_la_base_impide_doble_cita_aunque_se_salte_la_aplicacion(self):
        c = self.cliente()
        p1, p2 = self.nuevo_paciente(c), self.nuevo_paciente(c)
        fecha = proximo_lunes()
        self.agendar(c, p1, ANDRADE, CENTRO, fecha, "10:00")
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            with conexion() as con, con.cursor() as cur:
                cur.execute("INSERT INTO citas (paciente_id, medico_id, clinica_id, fecha, hora) VALUES (%s,%s,%s,%s,'10:00')",
                            (p2, ANDRADE, CENTRO, fecha))

    def test_fecha_pasada_rechazada(self):
        c = self.cliente()
        p = self.nuevo_paciente(c)
        r = self.agendar(c, p, ANDRADE, CENTRO, "2020-01-06", "09:00")
        self.assertIn("ya pasó", r.data.decode())
        self.assertIsNone(self.cita(p, "2020-01-06", "09:00"))

    def test_mas_de_180_dias_rechazado(self):
        c = self.cliente()
        p = self.nuevo_paciente(c)
        lejos = aplicacion.hoy() + timedelta(days=400)
        self.assertIn("180 días", self.agendar(c, p, ANDRADE, CENTRO, lejos, "09:00").data.decode())

    def test_cancelar_dos_veces_no_hace_nada_la_segunda(self):
        c = self.cliente()
        p = self.nuevo_paciente(c)
        fecha = proximo_lunes()
        self.agendar(c, p, ANDRADE, CENTRO, fecha, "11:00")
        cid = self.cita(p, fecha, "11:00")["id"]
        r1 = c.post(f"/citas/{cid}/cancelar", data={"csrf": self.csrf(c), "motivo_cancelacion": "llamó"}, follow_redirects=True)
        r2 = c.post(f"/citas/{cid}/cancelar", data={"csrf": self.csrf(c), "motivo_cancelacion": "otra"}, follow_redirects=True)
        self.assertIn("Cita cancelada", r1.data.decode())
        self.assertIn("ya estaba cancelada", r2.data.decode())
        self.assertEqual(consultar("SELECT COUNT(*) n FROM auditoria WHERE accion='CANCELAR' AND entidad_id=%s",
                                   (cid,), uno=True)["n"], 1)

    def test_cancelar_exige_motivo(self):
        c = self.cliente()
        p = self.nuevo_paciente(c)
        fecha = proximo_lunes()
        self.agendar(c, p, ANDRADE, CENTRO, fecha, "11:30")
        cid = self.cita(p, fecha, "11:30")["id"]
        r = c.post(f"/citas/{cid}/cancelar", data={"csrf": self.csrf(c), "motivo_cancelacion": "  "})
        self.assertIn("por qué se cancela", r.data.decode())
        self.assertEqual(self.cita(p, fecha, "11:30")["estado"], "AGENDADA")

    def test_hora_cancelada_vuelve_a_estar_libre(self):
        c = self.cliente()
        p = self.nuevo_paciente(c)
        fecha = proximo_lunes()
        self.agendar(c, p, ANDRADE, CENTRO, fecha, "12:00")
        self.assertNotIn("12:00", self.horas_libres(c, p, ANDRADE, CENTRO, fecha))
        cid = self.cita(p, fecha, "12:00")["id"]
        c.post(f"/citas/{cid}/cancelar", data={"csrf": self.csrf(c), "motivo_cancelacion": "x"})
        self.assertIn("12:00", self.horas_libres(c, p, ANDRADE, CENTRO, fecha))

    def test_deshacer_cancelacion_y_no_si_otro_tomo_la_hora(self):
        c = self.cliente()
        p1, p2 = self.nuevo_paciente(c), self.nuevo_paciente(c)
        fecha = proximo_lunes() + timedelta(days=1)
        self.agendar(c, p1, ANDRADE, CENTRO, fecha, "08:00")
        cid = self.cita(p1, fecha, "08:00")["id"]
        c.post(f"/citas/{cid}/cancelar", data={"csrf": self.csrf(c), "motivo_cancelacion": "x"})
        self.assertIn("deshecha", c.post(f"/citas/{cid}/reactivar", data={"csrf": self.csrf(c)},
                                         follow_redirects=True).data.decode())
        c.post(f"/citas/{cid}/cancelar", data={"csrf": self.csrf(c), "motivo_cancelacion": "x"})
        self.agendar(c, p2, ANDRADE, CENTRO, fecha, "08:00")
        r = c.post(f"/citas/{cid}/reactivar", data={"csrf": self.csrf(c)}, follow_redirects=True)
        self.assertIn("ya fue dado a otro paciente", r.data.decode())

    def test_medico_no_puede_estar_en_dos_clinicas_a_la_misma_hora(self):
        c = self.cliente()
        p1, p2 = self.nuevo_paciente(c), self.nuevo_paciente(c)
        fecha = proximo_lunes()
        self.agendar(c, p1, SALAZAR, CENTRO, fecha, "09:30")
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            with conexion() as con, con.cursor() as cur:
                cur.execute("INSERT INTO citas (paciente_id, medico_id, clinica_id, fecha, hora) VALUES (%s,%s,%s,%s,'09:30')",
                            (p2, SALAZAR, NORTE, fecha))
        admin = self.cliente("admin")
        r = admin.post("/admin/medicos", data=dict(csrf=self.csrf(admin), accion="nuevo_horario", medico_id=SALAZAR,
                                                    clinica_id=NORTE, dia_semana=0, hora_inicio="10:00",
                                                    hora_fin="12:00"), follow_redirects=True)
        self.assertIn("se cruza", r.data.decode())

    def test_no_se_marca_atendida_una_cita_futura(self):
        c = self.cliente()
        p = self.nuevo_paciente(c)
        fecha = proximo_lunes()
        self.agendar(c, p, ANDRADE, CENTRO, fecha, "12:30")
        cid = self.cita(p, fecha, "12:30")["id"]
        c.post(f"/citas/{cid}/estado", data={"csrf": self.csrf(c), "estado": "ATENDIDA"})
        self.assertEqual(self.cita(p, fecha, "12:30")["estado"], "AGENDADA")

    def test_filtro_de_agenda_por_medico(self):
        c = self.cliente()
        p1 = self.nuevo_paciente(c, nombres="Paciente", apellidos="De Salazar")
        p2 = self.nuevo_paciente(c, nombres="Paciente", apellidos="De Andrade")
        fecha = proximo_lunes() + timedelta(days=14)
        self.agendar(c, p1, SALAZAR, CENTRO, fecha, "08:00")
        self.agendar(c, p2, ANDRADE, CENTRO, fecha, "08:00")
        html = c.get(f"/?fecha={fecha}&medico_id={SALAZAR}").data.decode()
        self.assertIn("De Salazar", html)
        self.assertNotIn("De Andrade", html)
        html = c.get(f"/?fecha={fecha}&clinica_id={CENTRO}&medico_id={ANDRADE}").data.decode()
        self.assertIn("De Andrade", html)
        self.assertNotIn("De Salazar", html)
        # Un médico que no atiende en la clínica elegida no filtra (se muestran todas las de esa clínica)
        SUR = 3
        html = c.get(f"/?fecha={fecha}&clinica_id={SUR}&medico_id={SALAZAR}").data.decode()
        self.assertIn("con estos filtros", html)
        self.assertNotIn("Solo citas de", html)

    def test_dia_sin_citas_muestra_mensaje(self):
        c = self.cliente()
        self.assertIn("No hay citas para este día", c.get("/?fecha=2030-01-01").data.decode())


# ============================================================== SOBRE LAS PERSONAS
class SobreLasPersonas(Base):
    def test_mismo_nombre_y_nacimiento_avisa_posible_duplicado(self):
        c = self.cliente()
        datos = dict(tipo_documento="NINGUNO", nombres="Juan", apellidos="Pérez Duplicado",
                     fecha_nacimiento="1970-03-03", telefono="0991111111")
        c.post("/pacientes/nuevo", data=dict(csrf=self.csrf(c), **datos))
        datos.update(nombres="  JUAN ", apellidos="perez   duplicado")
        r = c.post("/pacientes/nuevo", data=dict(csrf=self.csrf(c), **datos))
        self.assertIn("Es la misma persona", r.data.decode())
        r = c.post("/pacientes/nuevo", data=dict(csrf=self.csrf(c), confirmar_distinto="1", **datos))
        self.assertEqual(r.status_code, 302)

    def test_documento_repetido_rechazado(self):
        c = self.cliente()
        self.nuevo_paciente(c, tipo_documento="CEDULA", documento="1710034065")
        r = c.post("/pacientes/nuevo", data=dict(csrf=self.csrf(c), tipo_documento="CEDULA", documento="1710034065",
                                                 nombres="Otra", apellidos="Persona", fecha_nacimiento="1990-01-01",
                                                 telefono="0991234567"))
        self.assertIn("Ya existe un paciente con este documento", r.data.decode())

    def test_paciente_sin_ningun_telefono_rechazado(self):
        c = self.cliente()
        r = c.post("/pacientes/nuevo", data=dict(csrf=self.csrf(c), tipo_documento="NINGUNO", nombres="Sin",
                                                 apellidos="Contacto", fecha_nacimiento="1990-01-01"))
        self.assertIn("al menos un teléfono", r.data.decode())

    def test_paciente_sin_cedula_ni_correo_pero_con_telefono_de_familiar(self):
        c = self.cliente()
        self.nuevo_paciente(c, telefono="", responsable="Ana Vega", telefono_responsable="0998877665",
                            fecha_nacimiento=str(aplicacion.hoy() - timedelta(days=30)))

    def test_menor_de_edad_exige_representante(self):
        c = self.cliente()
        r = c.post("/pacientes/nuevo", data=dict(csrf=self.csrf(c), tipo_documento="NINGUNO", nombres="Niño",
                                                 apellidos="Sin Representante", telefono="0991234567",
                                                 fecha_nacimiento=str(aplicacion.hoy() - timedelta(days=400))))
        self.assertIn("menor de edad", r.data.decode())

    def test_recepcion_no_entra_a_administracion(self):
        c = self.cliente("rosa")
        for url in ("/admin/usuarios", "/admin/medicos", "/admin/auditoria"):
            self.assertEqual(c.get(url).status_code, 302, url)

    def test_medico_solo_ve_sus_citas_y_no_cancela(self):
        rosa = self.cliente("rosa")
        p = self.nuevo_paciente(rosa)
        fecha = proximo_lunes() + timedelta(days=2)
        self.agendar(rosa, p, ANDRADE, CENTRO, fecha, "09:00")
        cid = self.cita(p, fecha, "09:00")["id"]
        medico = self.cliente("salazar")
        self.assertNotIn("Andrade", medico.get(f"/?fecha={fecha}").data.decode())
        self.assertEqual(medico.get(f"/citas/{cid}/cancelar").status_code, 302)   # sin permiso
        self.assertEqual(medico.post(f"/citas/{cid}/estado",
                                     data={"csrf": self.csrf(medico), "estado": "NO_ASISTIO"}).status_code, 404)


# ========================================================== SOBRE LOS DATOS MÉDICOS
class SobreLosDatosMedicos(Base):
    def test_sin_sesion_no_se_ve_nada(self):
        c = aplicacion.app.test_client()
        for url in ("/", "/pacientes", "/pacientes/1", "/admin/auditoria"):
            r = c.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/login", r.headers["Location"])

    def test_contrasenas_guardadas_como_hash(self):
        fila = consultar("SELECT clave_hash FROM usuarios WHERE usuario='rosa'", uno=True)
        self.assertNotIn(CLAVE, fila["clave_hash"])
        self.assertTrue(fila["clave_hash"].startswith(("scrypt:", "pbkdf2:")))

    def test_cada_cambio_queda_registrado_con_quien_y_cuando(self):
        c = self.cliente("rosa")
        p = self.nuevo_paciente(c)
        fecha = proximo_lunes() + timedelta(days=3)
        self.agendar(c, p, ANDRADE, CENTRO, fecha, "10:30")
        cid = self.cita(p, fecha, "10:30")["id"]
        c.post(f"/citas/{cid}/cancelar", data={"csrf": self.csrf(c), "motivo_cancelacion": "viaje"})
        filas = consultar("""SELECT a.accion, u.usuario, a.fecha, a.detalle FROM auditoria a
                             JOIN usuarios u ON u.id=a.usuario_id WHERE entidad='cita' AND entidad_id=%s
                             ORDER BY a.id""", (cid,))
        self.assertEqual([f["accion"] for f in filas], ["CREAR", "CANCELAR"])
        self.assertTrue(all(f["usuario"] == "rosa" and f["fecha"] for f in filas))
        self.assertIn("viaje", filas[1]["detalle"])

    def test_el_historial_no_se_puede_modificar_ni_borrar(self):
        for orden in ("UPDATE auditoria SET detalle='x'", "DELETE FROM auditoria", "TRUNCATE auditoria"):
            with self.assertRaises(psycopg2.errors.RaiseException, msg=orden):
                with conexion() as con, con.cursor() as cur:
                    cur.execute(orden)

    def test_las_citas_no_se_pueden_borrar(self):
        for orden in ("DELETE FROM citas", "TRUNCATE citas CASCADE"):
            with self.assertRaises(psycopg2.errors.RaiseException, msg=orden):
                with conexion() as con, con.cursor() as cur:
                    cur.execute(orden)

    def test_paginas_no_quedan_guardadas_en_el_navegador(self):
        r = self.cliente().get("/pacientes")
        self.assertEqual(r.headers.get("Cache-Control"), "no-store")
        self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")


# ================================================================== SOBRE EL USO REAL
class SobreElUsoReal(Base):
    def test_error_explica_y_conserva_lo_escrito(self):
        c = self.cliente()
        r = c.post("/pacientes/nuevo", data=dict(csrf=self.csrf(c), tipo_documento="CEDULA", documento="1234567890",
                                                 nombres="Ana Lucía", apellidos="Torres", fecha_nacimiento="1990-01-01",
                                                 telefono="0991234567", email="ana@gmail.com"))
        html = r.data.decode()
        self.assertIn("Esta cédula no es válida", html)
        for valor in ('value="Ana Lucía"', 'value="Torres"', 'value="0991234567"', 'value="ana@gmail.com"'):
            self.assertIn(valor, html)

    def test_sin_base_de_datos_mensaje_para_personas(self):
        c = self.cliente()
        with mock.patch.object(aplicacion, "consultar", side_effect=psycopg2.OperationalError("caída")):
            r = c.get("/")
        self.assertEqual(r.status_code, 503)
        self.assertIn("No hay conexión con la base de datos", r.data.decode())
        self.assertNotIn("Traceback", r.data.decode())

    def test_pagina_inexistente_mensaje_amable(self):
        r = self.cliente().get("/no-existe")
        self.assertEqual(r.status_code, 404)
        self.assertIn("No encontramos esa página", r.data.decode())


# ============================================================ SEGURIDAD DEL ACCESO
class SeguridadDelAcceso(Base):
    def test_bloqueo_tras_5_intentos_fallidos(self):
        with conexion() as con, con.cursor() as cur:
            cur.execute("INSERT INTO usuarios (usuario, nombre, clave_hash, rol) VALUES ('victima','V',%s,'RECEPCION')",
                        (generate_password_hash(CLAVE),))
        c = aplicacion.app.test_client()
        c.get("/login")
        for _ in range(aplicacion.MAX_INTENTOS):
            r = c.post("/login", data={"usuario": "victima", "clave": "mala", "csrf": self.csrf(c)})
        self.assertIn("bloqueado", r.data.decode())
        r = c.post("/login", data={"usuario": "victima", "clave": CLAVE, "csrf": self.csrf(c)})
        self.assertEqual(r.status_code, 200)            # ni con la clave correcta mientras dure el bloqueo
        self.assertIn("bloqueado", r.data.decode())
        self.assertEqual(consultar("SELECT COUNT(*) n FROM auditoria a JOIN usuarios u ON u.id=a.entidad_id "
                                   "WHERE u.usuario='victima' AND a.accion='BLOQUEO'", uno=True)["n"], 1)

    def test_formulario_sin_token_csrf_rechazado(self):
        c = self.cliente()
        p = self.nuevo_paciente(c)
        r = c.post(f"/citas/nueva/{p}", data={"csrf": "falso", "medico_id": ANDRADE, "clinica_id": CENTRO,
                                              "fecha": proximo_lunes(), "hora": "08:30"})
        self.assertEqual(r.status_code, 302)
        self.assertIsNone(self.cita(p, proximo_lunes(), "08:30"))

    def test_no_redirige_a_sitios_externos(self):
        c = aplicacion.app.test_client()
        c.get("/login")
        r = c.post("/login?siguiente=//sitio-malo.com", data={"usuario": "rosa", "clave": CLAVE, "csrf": self.csrf(c)})
        self.assertNotIn("sitio-malo", r.headers["Location"])


# ======================================================= SOBRE LA CALIDAD DE LOS DATOS
class SobreLaCalidadDeLosDatos(unittest.TestCase):
    def test_cedulas(self):
        self.assertIsNone(v.validar_cedula_ecuador("1710034065"))
        for mala, razon in [("171003406", "10 números"), ("17100340AB", "solo debe tener números"),
                            ("0000000000", "provincia"), ("1234567890", "último dígito"),
                            ("1790034065", "tercer número")]:
            self.assertIn(razon, v.validar_cedula_ecuador(mala) or "", mala)

    def test_pasaporte(self):
        self.assertIsNone(v.validar_pasaporte("AB123456"))
        self.assertIsNotNone(v.validar_pasaporte("AB 12"))

    def test_telefonos(self):
        for bueno in ("0991234567", "022345678", "+593991234567"):
            self.assertIsNone(v.validar_telefono(v.normalizar_telefono(bueno)), bueno)
        for malo in ("12345", "0891234567", "09912345678", "abc"):
            self.assertIsNotNone(v.validar_telefono(v.normalizar_telefono(malo)), malo)

    def test_correos(self):
        self.assertIsNone(v.validar_email("juan@gmail.com"))
        for malo in ("juan@@gmail", "juan@gmail", "juan.gmail.com"):
            self.assertIsNotNone(v.validar_email(malo), malo)

    def test_fechas_de_nacimiento_imposibles(self):
        hoy = aplicacion.hoy()
        self.assertIn("futuro", v.validar_fecha_nacimiento("2090-01-01", hoy)[1])
        self.assertIn("120", v.validar_fecha_nacimiento("1726-01-01", hoy)[1])
        self.assertIsNone(v.validar_fecha_nacimiento("1950-06-15", hoy)[1])

    def test_mismo_nombre_escrito_distinto(self):
        self.assertEqual(v.normalizar_nombre("  MARÍA   lópez "), "María López")
        self.assertEqual(v.clave_busqueda("MARÍA lópez"), v.clave_busqueda("Maria  Lopez"))

    def test_texto_raro_emojis_y_codigo(self):
        self.assertEqual(v.limpiar_texto("Dolor 😷 de\tcabeza\x00"), "Dolor de cabeza")
        self.assertIsNotNone(v.validar_nombre("<script>", "nombres"))

    def test_codigo_pegado_se_muestra_como_texto(self):
        c = Base.cliente(Base(), "rosa")
        p = Base.nuevo_paciente(Base(), c)
        fecha = proximo_lunes() + timedelta(days=4)
        c.post(f"/citas/nueva/{p}", data=dict(csrf=Base.csrf(c), medico_id=ANDRADE, clinica_id=CENTRO,
                                              fecha=fecha, hora="11:00", motivo="<script>alert(1)</script>"))
        html = c.get(f"/?fecha={fecha}").data.decode()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
