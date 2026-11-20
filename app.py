"""ClinAgenda - Sistema de agendamiento de citas para 3 clínicas.

Arquitectura simple:
  app.py          -> rutas (pantallas) y reglas de negocio
  db.py           -> conexión a PostgreSQL y bitácora
  validaciones.py -> validación y normalización de datos
  templates/      -> pantallas HTML
  static/         -> estilos CSS
"""
import os
import secrets
from datetime import date, datetime, timedelta
from functools import wraps
from zoneinfo import ZoneInfo

import psycopg2
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import validaciones as v
from db import conexion, consultar, registrar_auditoria

ZONA = ZoneInfo("America/Guayaquil")
DURACION_CITA_MIN = 30
DIAS_MAX_ADELANTO = 180
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
ESTADOS = {"AGENDADA": "Agendada", "CANCELADA": "Cancelada",
           "ATENDIDA": "Atendida", "NO_ASISTIO": "No asistió"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY") or secrets.token_hex(32),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


# ---------------------------------------------------------------- utilidades
def ahora():
    return datetime.now(ZONA).replace(tzinfo=None)


def hoy():
    return ahora().date()


@app.template_filter("fecha")
def filtro_fecha(valor):
    if not valor:
        return ""
    return f"{DIAS_SEMANA[valor.weekday()]} {valor.strftime('%d/%m/%Y')}"


@app.template_filter("hora")
def filtro_hora(valor):
    return valor.strftime("%H:%M") if valor else ""


@app.context_processor
def variables_globales():
    return dict(usuario=g.get("usuario"), csrf_token=session.get("csrf"),
                ESTADOS=ESTADOS, DIAS_SEMANA=DIAS_SEMANA, hoy=hoy())


# ------------------------------------------------------- sesión y seguridad
@app.before_request
def cargar_usuario_y_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST" and request.form.get("csrf") != session["csrf"]:
        flash("La página estaba abierta hace mucho tiempo. Intente de nuevo.", "error")
        return redirect(request.url)
    g.usuario = None
    if "usuario_id" in session:
        g.usuario = consultar(
            "SELECT id, usuario, nombre, rol, medico_id FROM usuarios WHERE id=%s AND activo",
            (session["usuario_id"],), uno=True)
        if g.usuario is None:
            session.clear()


def login_requerido(*roles):
    def decorador(f):
        @wraps(f)
        def envoltura(*args, **kwargs):
            if g.usuario is None:
                return redirect(url_for("login", siguiente=request.path))
            if roles and g.usuario["rol"] not in roles:
                flash("Usted no tiene permiso para entrar a esa pantalla.", "error")
                return redirect(url_for("agenda"))
            return f(*args, **kwargs)
        return envoltura
    return decorador


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.usuario:
        return redirect(url_for("agenda"))
    if request.method == "POST":
        nombre = v.limpiar_texto(request.form.get("usuario"), 40).lower()
        clave = request.form.get("clave", "")
        u = consultar("SELECT * FROM usuarios WHERE usuario=%s", (nombre,), uno=True)
        if u and u["activo"] and check_password_hash(u["clave_hash"], clave):
            session.clear()
            session.permanent = True
            session["usuario_id"] = u["id"]
            with conexion() as con, con.cursor() as cur:
                registrar_auditoria(cur, u["id"], "INICIO_SESION", "usuario", u["id"])
            siguiente = request.args.get("siguiente", "")
            return redirect(siguiente if siguiente.startswith("/") else url_for("agenda"))
        flash("Usuario o contraseña incorrectos.", "error")
        return render_template("login.html", usuario_escrito=nombre)
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "ok")
    return redirect(url_for("login"))


# ------------------------------------------------------------------- agenda
@app.route("/")
@login_requerido()
def agenda():
    try:
        fecha = date.fromisoformat(request.args.get("fecha", ""))
    except ValueError:
        fecha = hoy()
    clinica_id = request.args.get("clinica_id", type=int)

    sql = """SELECT c.*, p.nombres || ' ' || p.apellidos AS paciente,
                    COALESCE(p.telefono, p.telefono_responsable) AS telefono,
                    p.documento, m.nombres AS medico, cl.nombre AS clinica
             FROM citas c
             JOIN pacientes p ON p.id = c.paciente_id
             JOIN medicos m   ON m.id = c.medico_id
             JOIN clinicas cl ON cl.id = c.clinica_id
             WHERE c.fecha = %s"""
    params = [fecha]
    if g.usuario["rol"] == "MEDICO":
        sql += " AND c.medico_id = %s"
        params.append(g.usuario["medico_id"])
    if clinica_id:
        sql += " AND c.clinica_id = %s"
        params.append(clinica_id)
    sql += " ORDER BY c.hora, cl.nombre, m.nombres"

    return render_template(
        "agenda.html", citas=consultar(sql, params), fecha=fecha,
        clinica_id=clinica_id, clinicas=consultar("SELECT * FROM clinicas WHERE activa ORDER BY id"),
        dia_anterior=fecha - timedelta(days=1), dia_siguiente=fecha + timedelta(days=1))


# ---------------------------------------------------------------- pacientes
@app.route("/pacientes")
@login_requerido()
def pacientes():
    q = v.limpiar_texto(request.args.get("q"), 100)
    lista = consultar("SELECT * FROM pacientes ORDER BY creado_en DESC LIMIT 6")
    if q:
        clave = v.clave_busqueda(q)
        lista = consultar(
            """SELECT * FROM pacientes
               WHERE nombre_busqueda LIKE %s OR documento = %s OR telefono = %s
               ORDER BY apellidos, nombres LIMIT 50""",
            (f"%{clave}%", q.upper(), v.normalizar_telefono(q)))
    return render_template("pacientes.html", q=q, pacientes=lista, edad=v.edad)


def leer_formulario_paciente():
    f = request.form
    datos = {
        "tipo_documento": f.get("tipo_documento", "CEDULA"),
        "documento": v.limpiar_texto(f.get("documento"), 20).upper().replace(" ", ""),
        "nombres": v.normalizar_nombre(f.get("nombres")),
        "apellidos": v.normalizar_nombre(f.get("apellidos")),
        "fecha_nacimiento": f.get("fecha_nacimiento", ""),
        "telefono": v.normalizar_telefono(f.get("telefono")),
        "email": v.limpiar_texto(f.get("email"), 120).lower(),
        "responsable": v.normalizar_nombre(f.get("responsable")),
        "telefono_responsable": v.normalizar_telefono(f.get("telefono_responsable")),
    }
    errores = {}
    if datos["tipo_documento"] not in ("CEDULA", "PASAPORTE", "NINGUNO"):
        errores["tipo_documento"] = "Elija un tipo de documento."
    elif datos["tipo_documento"] == "CEDULA":
        e = v.validar_cedula_ecuador(datos["documento"]) if datos["documento"] else "Escriba la cédula."
        if e:
            errores["documento"] = e
    elif datos["tipo_documento"] == "PASAPORTE":
        e = v.validar_pasaporte(datos["documento"]) if datos["documento"] else "Escriba el pasaporte."
        if e:
            errores["documento"] = e
    else:
        datos["documento"] = ""

    for campo in ("nombres", "apellidos"):
        e = v.validar_nombre(datos[campo], campo)
        if e:
            errores[campo] = e
    fecha_nac, e = v.validar_fecha_nacimiento(datos["fecha_nacimiento"], hoy())
    if e:
        errores["fecha_nacimiento"] = e
    for campo in ("telefono", "telefono_responsable"):
        e = v.validar_telefono(datos[campo])
        if e:
            errores[campo] = e
    e = v.validar_email(datos["email"])
    if e:
        errores["email"] = e

    # Sin ningún contacto no se le puede avisar de cambios en su cita
    if not datos["telefono"] and not datos["telefono_responsable"]:
        errores["telefono"] = "Escriba al menos un teléfono (del paciente o de un familiar responsable)."
    # Menores de edad deben tener responsable
    if fecha_nac and v.edad(fecha_nac, hoy()) < 18 and not datos["responsable"]:
        errores["responsable"] = "El paciente es menor de edad: escriba el nombre de su representante."
    datos["fecha_nac_obj"] = fecha_nac
    return datos, errores


def guardar_paciente(datos, paciente_id=None):
    valores = (datos["tipo_documento"], datos["documento"] or None, datos["nombres"],
               datos["apellidos"], v.clave_busqueda(f"{datos['nombres']} {datos['apellidos']}"),
               datos["fecha_nac_obj"], datos["telefono"] or None, datos["email"] or None,
               datos["responsable"] or None, datos["telefono_responsable"] or None)
    with conexion() as con, con.cursor() as cur:
        if paciente_id:
            cur.execute("""UPDATE pacientes SET tipo_documento=%s, documento=%s, nombres=%s,
                           apellidos=%s, nombre_busqueda=%s, fecha_nacimiento=%s, telefono=%s,
                           email=%s, responsable=%s, telefono_responsable=%s WHERE id=%s""",
                        valores + (paciente_id,))
            registrar_auditoria(cur, g.usuario["id"], "EDITAR", "paciente", paciente_id)
        else:
            cur.execute("""INSERT INTO pacientes (tipo_documento, documento, nombres, apellidos,
                           nombre_busqueda, fecha_nacimiento, telefono, email, responsable,
                           telefono_responsable, creado_por)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        valores + (g.usuario["id"],))
            paciente_id = cur.fetchone()["id"]
            registrar_auditoria(cur, g.usuario["id"], "CREAR", "paciente", paciente_id)
    return paciente_id


@app.route("/pacientes/nuevo", methods=["GET", "POST"])
@app.route("/pacientes/<int:paciente_id>/editar", methods=["GET", "POST"])
@login_requerido("ADMIN", "RECEPCION")
def paciente_form(paciente_id=None):
    if request.method == "GET":
        datos = {}
        if paciente_id:
            datos = consultar("SELECT * FROM pacientes WHERE id=%s", (paciente_id,), uno=True) or abort(404)
            datos = {k: ("" if val is None else val) for k, val in datos.items()}
        return render_template("paciente_form.html", datos=datos, errores={},
                               paciente_id=paciente_id, parecidos=[])

    datos, errores = leer_formulario_paciente()
    parecidos = []
    if not errores:
        # ¿Ya existe con el mismo documento?
        if datos["documento"]:
            otro = consultar("""SELECT id, nombres, apellidos FROM pacientes
                                WHERE tipo_documento=%s AND documento=%s AND id <> %s""",
                             (datos["tipo_documento"], datos["documento"], paciente_id or 0), uno=True)
            if otro:
                errores["documento"] = (f"Ya existe un paciente con este documento: "
                                        f"{otro['nombres']} {otro['apellidos']}. Búsquelo en Pacientes.")
        # ¿Mismo nombre y fecha de nacimiento? Puede ser la misma persona.
        if not errores and not request.form.get("confirmar_distinto"):
            parecidos = consultar(
                """SELECT * FROM pacientes WHERE nombre_busqueda=%s AND fecha_nacimiento=%s AND id <> %s""",
                (v.clave_busqueda(f"{datos['nombres']} {datos['apellidos']}"),
                 datos["fecha_nac_obj"], paciente_id or 0))
    if errores or parecidos:
        if errores:
            flash("Hay datos por corregir. Revise los campos marcados en rojo.", "error")
        return render_template("paciente_form.html", datos=datos, errores=errores,
                               paciente_id=paciente_id, parecidos=parecidos)
    try:
        nuevo_id = guardar_paciente(datos, paciente_id)
    except psycopg2.errors.UniqueViolation:
        errores["documento"] = "Otra persona acaba de registrar este documento. Búsquelo en Pacientes."
        return render_template("paciente_form.html", datos=datos, errores=errores,
                               paciente_id=paciente_id, parecidos=[])
    flash("Paciente guardado correctamente.", "ok")
    return redirect(url_for("paciente_ficha", paciente_id=nuevo_id))


@app.route("/pacientes/<int:paciente_id>")
@login_requerido()
def paciente_ficha(paciente_id):
    p = consultar("SELECT * FROM pacientes WHERE id=%s", (paciente_id,), uno=True) or abort(404)
    citas = consultar("""SELECT c.*, m.nombres AS medico, cl.nombre AS clinica FROM citas c
                         JOIN medicos m ON m.id=c.medico_id JOIN clinicas cl ON cl.id=c.clinica_id
                         WHERE c.paciente_id=%s ORDER BY c.fecha DESC, c.hora DESC""", (paciente_id,))
    return render_template("paciente_ficha.html", p=p, citas=citas, edad=v.edad(p["fecha_nacimiento"], hoy()))


# -------------------------------------------------------------------- citas
def horarios_libres(medico_id, clinica_id, fecha):
    """Devuelve la lista de horas libres del médico en esa clínica y fecha."""
    bloques = consultar("""SELECT hora_inicio, hora_fin FROM horarios_medico
                           WHERE medico_id=%s AND clinica_id=%s AND dia_semana=%s""",
                        (medico_id, clinica_id, fecha.weekday()))
    # Ocupadas en CUALQUIER clínica (un médico no puede estar en dos lugares)
    ocupadas = {r["hora"] for r in consultar(
        "SELECT hora FROM citas WHERE medico_id=%s AND fecha=%s AND estado='AGENDADA'",
        (medico_id, fecha))}
    libres = []
    paso = timedelta(minutes=DURACION_CITA_MIN)
    for b in bloques:
        t = datetime.combine(fecha, b["hora_inicio"])
        fin = datetime.combine(fecha, b["hora_fin"])
        while t + paso <= fin:
            if t.time() not in ocupadas and t > ahora():
                libres.append(t.time())
            t += paso
    return sorted(libres)


def describir_cita(cur, paciente_id, medico_id, clinica_id, fecha, hora):
    """Texto entendible para el historial: 'María López · Dr. Luis Salazar · Clínica Norte · 23/11/2026 14:00'."""
    cur.execute("""SELECT p.nombres || ' ' || p.apellidos AS paciente, m.nombres AS medico, cl.nombre AS clinica
                   FROM pacientes p, medicos m, clinicas cl WHERE p.id=%s AND m.id=%s AND cl.id=%s""",
                (paciente_id, medico_id, clinica_id))
    r = cur.fetchone()
    return f"{r['paciente']} · {r['medico']} · {r['clinica']} · {fecha:%d/%m/%Y} {hora:%H:%M}"


@app.route("/citas/nueva/<int:paciente_id>", methods=["GET", "POST"])
@login_requerido("ADMIN", "RECEPCION")
def cita_nueva(paciente_id):
    p = consultar("SELECT * FROM pacientes WHERE id=%s", (paciente_id,), uno=True) or abort(404)
    src = request.form if request.method == "POST" else request.args
    clinica_id = src.get("clinica_id", type=int)
    medico_id = src.get("medico_id", type=int)
    motivo = v.limpiar_texto(src.get("motivo"), 300)
    try:
        fecha = date.fromisoformat(src.get("fecha", ""))
    except ValueError:
        fecha = None

    error = None
    if fecha and fecha < hoy():
        error = "No se puede agendar en una fecha que ya pasó. Elija hoy o una fecha futura."
    elif fecha and fecha > hoy() + timedelta(days=DIAS_MAX_ADELANTO):
        error = f"Solo se puede agendar hasta {DIAS_MAX_ADELANTO} días adelante."

    if request.method == "POST" and not error:
        try:
            hora = datetime.strptime(request.form.get("hora", ""), "%H:%M").time()
        except ValueError:
            hora = None
        # Se vuelve a calcular en el servidor: nunca se confía en lo que manda el navegador
        if not (clinica_id and medico_id and fecha and hora) or hora not in horarios_libres(medico_id, clinica_id, fecha):
            error = "Ese horario ya no está disponible. Elija otro de la lista."
        else:
            try:
                with conexion() as con, con.cursor() as cur:
                    cur.execute("""INSERT INTO citas (paciente_id, medico_id, clinica_id, fecha, hora,
                                   motivo, creado_por) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                                (paciente_id, medico_id, clinica_id, fecha, hora, motivo or None, g.usuario["id"]))
                    cita_id = cur.fetchone()["id"]
                    registrar_auditoria(cur, g.usuario["id"], "CREAR", "cita", cita_id,
                                        describir_cita(cur, paciente_id, medico_id, clinica_id, fecha, hora))
                flash(f"Cita agendada para el {filtro_fecha(fecha)} a las {hora:%H:%M}.", "ok")
                return redirect(url_for("paciente_ficha", paciente_id=paciente_id))
            except psycopg2.errors.UniqueViolation as ex:
                if "paciente" in str(ex):
                    error = "Este paciente ya tiene otra cita a esa misma hora."
                else:
                    error = "Otra persona acaba de tomar ese horario hace un momento. Elija otro."

    clinicas = consultar("SELECT * FROM clinicas WHERE activa ORDER BY id")
    medicos = []
    if clinica_id:
        medicos = consultar("""SELECT DISTINCT m.id, m.nombres, m.especialidad FROM medicos m
                               JOIN horarios_medico h ON h.medico_id=m.id
                               WHERE h.clinica_id=%s AND m.activo ORDER BY m.nombres""", (clinica_id,))
    clinica_sel = next((cl for cl in clinicas if cl["id"] == clinica_id), None)
    medico_sel = next((m for m in medicos if m["id"] == medico_id), None)
    if medico_id and not medico_sel:
        medico_id = None  # el médico elegido no atiende en esta clínica

    # Próximos días en que el médico atiende en esa clínica (accesos rápidos)
    dias = []
    if clinica_sel and medico_sel:
        dias_semana = {r["dia_semana"] for r in consultar(
            "SELECT DISTINCT dia_semana FROM horarios_medico WHERE medico_id=%s AND clinica_id=%s",
            (medico_id, clinica_id))}
        d = hoy()
        while len(dias) < 8 and d <= hoy() + timedelta(days=DIAS_MAX_ADELANTO):
            if d.weekday() in dias_semana:
                dias.append(d)
            d += timedelta(days=1)

    libres = None
    if clinica_sel and medico_sel and fecha and not (error and request.method == "GET"):
        libres = horarios_libres(medico_id, clinica_id, fecha)
    if error:
        flash(error, "error")
    return render_template("cita_nueva.html", p=p, clinicas=clinicas, medicos=medicos,
                           clinica_id=clinica_id, medico_id=medico_id, fecha=fecha,
                           motivo=motivo, libres=libres, dias=dias,
                           clinica_sel=clinica_sel, medico_sel=medico_sel)


def resumen(c):
    return f"{c['paciente']} · {c['medico']} · {c['clinica']} · {c['fecha']:%d/%m/%Y} {c['hora']:%H:%M}"


def obtener_cita(cita_id):
    c = consultar("""SELECT c.*, p.nombres || ' ' || p.apellidos AS paciente,
                     m.nombres AS medico, cl.nombre AS clinica FROM citas c
                     JOIN pacientes p ON p.id=c.paciente_id JOIN medicos m ON m.id=c.medico_id
                     JOIN clinicas cl ON cl.id=c.clinica_id WHERE c.id=%s""", (cita_id,), uno=True)
    if c is None:
        abort(404)
    if g.usuario["rol"] == "MEDICO" and c["medico_id"] != g.usuario["medico_id"]:
        abort(404)
    return c


@app.route("/citas/<int:cita_id>/cancelar", methods=["GET", "POST"])
@login_requerido("ADMIN", "RECEPCION")
def cita_cancelar(cita_id):
    c = obtener_cita(cita_id)
    if request.method == "POST":
        motivo = v.limpiar_texto(request.form.get("motivo_cancelacion"), 300)
        if not motivo:
            flash("Escriba por qué se cancela la cita.", "error")
            return render_template("cita_cancelar.html", c=c)
        with conexion() as con, con.cursor() as cur:
            # Solo cancela si sigue AGENDADA: cancelar dos veces no hace nada
            cur.execute("""UPDATE citas SET estado='CANCELADA', motivo_cancelacion=%s,
                           actualizado_por=%s, actualizado_en=NOW()
                           WHERE id=%s AND estado='AGENDADA'""", (motivo, g.usuario["id"], cita_id))
            if cur.rowcount == 0:
                flash("Esta cita ya estaba cancelada o cerrada. No se hizo ningún cambio.", "aviso")
            else:
                registrar_auditoria(cur, g.usuario["id"], "CANCELAR", "cita", cita_id,
                                    f"{resumen(c)} — Motivo: {motivo}")
                flash("Cita cancelada. El horario quedó libre para otro paciente. "
                      "Si fue un error, presione «Deshacer cancelación».", "ok")
        return redirect(request.form.get("volver") or url_for("agenda", fecha=c["fecha"]))
    if c["estado"] != "AGENDADA":
        flash("Esta cita ya no se puede cancelar.", "aviso")
        return redirect(url_for("agenda", fecha=c["fecha"]))
    return render_template("cita_cancelar.html", c=c)


@app.route("/citas/<int:cita_id>/reactivar", methods=["POST"])
@login_requerido("ADMIN", "RECEPCION")
def cita_reactivar(cita_id):
    c = obtener_cita(cita_id)
    if c["estado"] != "CANCELADA":
        flash("Solo se puede deshacer una cita cancelada.", "aviso")
    elif datetime.combine(c["fecha"], c["hora"]) <= ahora():
        flash("No se puede reactivar: la hora de la cita ya pasó.", "error")
    else:
        try:
            with conexion() as con, con.cursor() as cur:
                cur.execute("""UPDATE citas SET estado='AGENDADA', motivo_cancelacion=NULL,
                               actualizado_por=%s, actualizado_en=NOW() WHERE id=%s AND estado='CANCELADA'""",
                            (g.usuario["id"], cita_id))
                registrar_auditoria(cur, g.usuario["id"], "REACTIVAR", "cita", cita_id, resumen(c))
            flash("Cancelación deshecha. La cita vuelve a estar agendada.", "ok")
        except psycopg2.errors.UniqueViolation:
            flash("No se puede deshacer: ese horario ya fue dado a otro paciente.", "error")
    return redirect(request.form.get("volver") or url_for("agenda", fecha=c["fecha"]))


@app.route("/citas/<int:cita_id>/estado", methods=["POST"])
@login_requerido()
def cita_estado(cita_id):
    c = obtener_cita(cita_id)
    nuevo = request.form.get("estado")
    if nuevo not in ("ATENDIDA", "NO_ASISTIO", "AGENDADA"):
        abort(400)
    if c["estado"] == "CANCELADA":
        flash("La cita está cancelada.", "aviso")
    elif nuevo != "AGENDADA" and c["fecha"] > hoy():
        flash("No se puede marcar una cita futura como atendida o no asistida.", "error")
    else:
        with conexion() as con, con.cursor() as cur:
            cur.execute("""UPDATE citas SET estado=%s, actualizado_por=%s, actualizado_en=NOW()
                           WHERE id=%s""", (nuevo, g.usuario["id"], cita_id))
            registrar_auditoria(cur, g.usuario["id"], "ESTADO", "cita", cita_id,
                                f"{resumen(c)} — {ESTADOS[c['estado']]} → {ESTADOS[nuevo]}")
        flash(f"Cita marcada como «{ESTADOS[nuevo]}».", "ok")
    return redirect(url_for("agenda", fecha=c["fecha"]))


# ---------------------------------------------------------- administración
@app.route("/admin/medicos", methods=["GET", "POST"])
@login_requerido("ADMIN")
def admin_medicos():
    if request.method == "POST":
        accion = request.form.get("accion")
        with conexion() as con, con.cursor() as cur:
            if accion == "nuevo_medico":
                nombres = v.limpiar_texto(request.form.get("nombres"), 120)
                esp = v.limpiar_texto(request.form.get("especialidad"), 80)
                if len(nombres) < 3:
                    flash("Escriba el nombre del médico.", "error")
                else:
                    cur.execute("INSERT INTO medicos (nombres, especialidad) VALUES (%s,%s) RETURNING id",
                                (nombres, esp or None))
                    registrar_auditoria(cur, g.usuario["id"], "CREAR", "medico", cur.fetchone()["id"], nombres)
                    flash("Médico creado. Ahora agréguele horarios.", "ok")
            elif accion == "nuevo_horario":
                f = request.form
                try:
                    medico_id, clinica_id, dia = int(f["medico_id"]), int(f["clinica_id"]), int(f["dia_semana"])
                    inicio = datetime.strptime(f["hora_inicio"], "%H:%M").time()
                    fin = datetime.strptime(f["hora_fin"], "%H:%M").time()
                except (KeyError, ValueError):
                    flash("Complete todos los datos del horario.", "error")
                    return redirect(url_for("admin_medicos"))
                cur.execute("""SELECT 1 FROM horarios_medico WHERE medico_id=%s AND dia_semana=%s
                               AND hora_inicio < %s AND hora_fin > %s""", (medico_id, dia, fin, inicio))
                if fin <= inicio:
                    flash("La hora de fin debe ser después de la hora de inicio.", "error")
                elif cur.fetchone():
                    flash("Ese médico ya tiene un horario que se cruza ese día (en esta u otra clínica).", "error")
                else:
                    cur.execute("""INSERT INTO horarios_medico (medico_id, clinica_id, dia_semana, hora_inicio, hora_fin)
                                   VALUES (%s,%s,%s,%s,%s) RETURNING id""", (medico_id, clinica_id, dia, inicio, fin))
                    registrar_auditoria(cur, g.usuario["id"], "CREAR", "horario", cur.fetchone()["id"],
                                        f"medico={medico_id} clinica={clinica_id} dia={dia} {inicio}-{fin}")
                    flash("Horario agregado.", "ok")
            elif accion == "borrar_horario":
                hid = request.form.get("horario_id", type=int)
                cur.execute("DELETE FROM horarios_medico WHERE id=%s RETURNING medico_id", (hid,))
                if cur.fetchone():
                    registrar_auditoria(cur, g.usuario["id"], "BORRAR", "horario", hid)
                    flash("Horario quitado. Las citas ya agendadas no se borran.", "ok")
        return redirect(url_for("admin_medicos"))

    medicos = consultar("SELECT * FROM medicos ORDER BY nombres")
    horarios = consultar("""SELECT h.*, cl.nombre AS clinica FROM horarios_medico h
                            JOIN clinicas cl ON cl.id=h.clinica_id
                            ORDER BY h.medico_id, h.dia_semana, h.hora_inicio""")
    por_medico = {}
    for h in horarios:
        por_medico.setdefault(h["medico_id"], []).append(h)
    return render_template("admin_medicos.html", medicos=medicos, por_medico=por_medico,
                           clinicas=consultar("SELECT * FROM clinicas ORDER BY id"))


@app.route("/admin/usuarios", methods=["GET", "POST"])
@login_requerido("ADMIN")
def admin_usuarios():
    if request.method == "POST":
        accion = request.form.get("accion")
        with conexion() as con, con.cursor() as cur:
            if accion == "nuevo":
                usuario = v.limpiar_texto(request.form.get("usuario"), 40).lower()
                nombre = v.limpiar_texto(request.form.get("nombre"), 120)
                rol = request.form.get("rol")
                clave = request.form.get("clave", "")
                medico_id = request.form.get("medico_id", type=int) if rol == "MEDICO" else None
                if not usuario.isalnum() or len(usuario) < 3:
                    flash("El usuario debe tener al menos 3 letras o números, sin espacios.", "error")
                elif rol not in ("ADMIN", "RECEPCION", "MEDICO") or not nombre:
                    flash("Complete el nombre y el rol.", "error")
                elif rol == "MEDICO" and not medico_id:
                    flash("Elija qué médico es este usuario.", "error")
                elif len(clave) < 8:
                    flash("La contraseña debe tener al menos 8 caracteres.", "error")
                else:
                    try:
                        cur.execute("""INSERT INTO usuarios (usuario, nombre, clave_hash, rol, medico_id)
                                       VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                                    (usuario, nombre, generate_password_hash(clave), rol, medico_id))
                        registrar_auditoria(cur, g.usuario["id"], "CREAR", "usuario", cur.fetchone()["id"], usuario)
                        flash(f"Usuario «{usuario}» creado.", "ok")
                    except psycopg2.errors.UniqueViolation:
                        flash("Ya existe un usuario con ese nombre.", "error")
            elif accion in ("activar", "desactivar"):
                uid = request.form.get("usuario_id", type=int)
                if uid == g.usuario["id"]:
                    flash("No puede desactivarse a sí mismo.", "error")
                else:
                    cur.execute("UPDATE usuarios SET activo=%s WHERE id=%s", (accion == "activar", uid))
                    registrar_auditoria(cur, g.usuario["id"], accion.upper(), "usuario", uid)
                    flash("Usuario actualizado.", "ok")
            elif accion == "clave":
                uid = request.form.get("usuario_id", type=int)
                clave = request.form.get("clave", "")
                if len(clave) < 8:
                    flash("La contraseña debe tener al menos 8 caracteres.", "error")
                else:
                    cur.execute("UPDATE usuarios SET clave_hash=%s WHERE id=%s", (generate_password_hash(clave), uid))
                    registrar_auditoria(cur, g.usuario["id"], "CAMBIAR_CLAVE", "usuario", uid)
                    flash("Contraseña cambiada.", "ok")
        return redirect(url_for("admin_usuarios"))
    usuarios = consultar("""SELECT u.*, m.nombres AS medico FROM usuarios u
                            LEFT JOIN medicos m ON m.id=u.medico_id
                            ORDER BY u.activo DESC, CASE u.rol WHEN 'ADMIN' THEN 0 WHEN 'RECEPCION' THEN 1 ELSE 2 END, u.nombre""")
    return render_template("admin_usuarios.html", usuarios=usuarios,
                           medicos=consultar("SELECT * FROM medicos WHERE activo ORDER BY nombres"))


@app.route("/admin/auditoria")
@login_requerido("ADMIN")
def admin_auditoria():
    registros = consultar("""SELECT a.*, u.usuario, u.nombre FROM auditoria a
                             LEFT JOIN usuarios u ON u.id=a.usuario_id
                             ORDER BY a.fecha DESC LIMIT 300""")
    return render_template("admin_auditoria.html", registros=registros)


# ------------------------------------------------------- errores amigables
@app.errorhandler(404)
def no_encontrado(e):
    return render_template("error.html", titulo="No encontramos esa página",
                           mensaje="Puede que el enlace esté mal o que el registro no exista."), 404


@app.errorhandler(psycopg2.OperationalError)
def sin_base_datos(e):
    app.logger.error("Error de base de datos: %s", e)
    return render_template("error.html", titulo="No hay conexión con la base de datos",
                           mensaje="El sistema no puede guardar ni leer información en este momento. "
                                   "No se perdió nada de lo ya guardado. Espere un minuto y vuelva a intentar. "
                                   "Si continúa, llame al soporte técnico y use la agenda impresa del día."), 503


@app.errorhandler(500)
def error_interno(e):
    return render_template("error.html", titulo="Algo salió mal",
                           mensaje="Ocurrió un problema inesperado. Lo que ya estaba guardado no se perdió. "
                                   "Vuelva a la pantalla anterior e intente de nuevo."), 500


if __name__ == "__main__":
    # host 0.0.0.0 permite entrar desde otros equipos/celulares de la misma red
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
