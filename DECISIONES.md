# DECISIONES — ClinAgenda

Este documento responde, una por una, las preocupaciones de la Dra. Paredes (sección 5 de las bases).
Para cada pregunta se indica:

- **Decisión:** qué hace el sistema.
- **En el código:** dónde está implementado (archivo y función), para que el jurado lo pueda verificar.
- **Prueba:** la prueba automática que lo demuestra, en [`tests/test_controles.py`](tests/test_controles.py).

Las 38 pruebas se ejecutan con un solo comando (usan una base de datos aparte y no tocan los datos reales):

```powershell
.\venv\Scripts\python.exe -m unittest -v tests.test_controles
```

Resultado de la última ejecución: **38 pruebas, 38 correctas.**

---

## 0. Supuestos que hicimos sobre la clienta

| Supuesto | Por qué |
|---|---|
| Las 3 clínicas están en Ecuador, misma zona horaria (`America/Guayaquil`), sin cambio de horario. | Así lo indica el contexto (cédula ecuatoriana). |
| Cada cita dura 30 minutos. | Es lo más común en consulta externa. Se cambia en `app.py` → `DURACION_CITA_MIN`. |
| "Cualquiera puede cancelar" = cualquier persona del **personal** con usuario. El paciente cancela llamando a recepción. | Un paciente cancelando solo, sin identificarse, contradice "no se pierden citas". |
| La Dra. Paredes es la administradora; las 5 recepcionistas tienen rol Recepción; cada médico puede tener su usuario. | Separar lo que ve cada uno (pregunta "¿quién puede ver qué?"). |
| El sistema se instala en una computadora de la red local de una clínica. | Es lo más simple y barato para empezar el lunes. Ver sección 6 (fallos). |

---

## 1. Sobre las citas

### 1.1 Dos recepcionistas dan la misma hora al mismo médico en el mismo segundo
- **Decisión:** se guarda **solo la primera**. A la segunda le aparece: *"Otra persona acaba de tomar ese horario hace un momento. Elija otro."* No se crea ninguna cita repetida.
- **En el código:** lo garantiza **la base de datos**, no solo la pantalla: índice único `ux_citas_medico_horario (medico_id, fecha, hora) WHERE estado='AGENDADA'` en `sql/schema.sql`. La aplicación atrapa el error en `app.py` → `cita_nueva()` (`except psycopg2.errors.UniqueViolation`) y muestra el mensaje.
- **Prueba:** `test_dos_recepcionistas_misma_hora_mismo_segundo` (lanza dos guardados **al mismo tiempo** con dos hilos) y `test_la_base_impide_doble_cita_aunque_se_salte_la_aplicacion`.

### 1.2 Agendar en una fecha que ya pasó
- **Decisión:** no se permite. Tampoco se muestran las horas de hoy que ya pasaron. Además, no se puede agendar a más de 180 días.
- **En el código:** `app.py` → `cita_nueva()` (valida `fecha < hoy()` y `DIAS_MAX_ADELANTO`) y `horarios_libres()` (descarta horas `<= ahora()`). El calendario de la pantalla tiene `min="hoy"`, pero **la validación real es en el servidor**.
- **Prueba:** `test_fecha_pasada_rechazada`, `test_mas_de_180_dias_rechazado`.

### 1.3 Una cita se cancela dos veces seguidas
- **Decisión:** la segunda vez no hace nada y avisa: *"Esta cita ya estaba cancelada. No se hizo ningún cambio."* En el historial queda una sola cancelación.
- **En el código:** `app.py` → `cita_cancelar()`: `UPDATE ... WHERE id=%s AND estado='AGENDADA'` y revisa `rowcount`.
- **Prueba:** `test_cancelar_dos_veces_no_hace_nada_la_segunda`.

### 1.4 ¿Qué pasa con la hora que quedó libre?
- **Decisión:** vuelve a aparecer **de inmediato** como disponible para otro paciente.
- **En el código:** el índice único solo cuenta citas `AGENDADA`; `horarios_libres()` solo descarta horas con citas `AGENDADA`.
- **Prueba:** `test_hora_cancelada_vuelve_a_estar_libre`.

### 1.5 ¿Puede un médico atender en dos clínicas a la misma hora?
- **Decisión:** no. Doble protección:
  1. Al **configurar horarios**, no se acepta un horario que se cruce con otro del mismo médico, aunque sea en otra clínica (caso Dr. Salazar: Centro en la mañana, Norte en la tarde).
  2. Al **agendar**, el índice único no incluye la clínica: un médico no puede tener dos citas a la misma hora en ninguna clínica.
- **En el código:** `app.py` → `admin_medicos()` (acción `nuevo_horario`, consulta de cruce) y el índice `ux_citas_medico_horario`.
- **Prueba:** `test_medico_no_puede_estar_en_dos_clinicas_a_la_misma_hora`.

### 1.6 ¿Y si un día llegan 500 citas? ¿Y si no llega ninguna?
- **Decisión:** 500 citas es poco para PostgreSQL (hay índices por fecha y médico). La agenda se puede filtrar por clínica. Si no hay citas, se muestra *"No hay citas para este día"* en lugar de una pantalla vacía.
- **En el código:** índice `ix_citas_fecha` en `sql/schema.sql`; mensaje vacío en `templates/agenda.html`.
- **Prueba:** `test_dia_sin_citas_muestra_mensaje`. *(No hicimos prueba de carga con 500 citas: queda pendiente.)*

### 1.7 Controles adicionales sobre citas
- Cancelar **exige escribir un motivo** → `test_cancelar_exige_motivo`.
- No se puede marcar como "Atendida" una cita futura → `app.py` → `cita_estado()` → `test_no_se_marca_atendida_una_cita_futura`.
- Un paciente no puede tener dos citas a la misma hora → índice `ux_citas_paciente_horario`.

---

## 2. Sobre las personas

### 2.1 ¿Es el mismo "Juan Pérez" de hace un mes? ¿Y si hay dos con el mismo nombre?
- **Decisión:**
  - Se busca por **nombre** (sin importar tildes ni mayúsculas), **cédula** o **teléfono**.
  - Si al registrar ya existe alguien con el **mismo nombre y fecha de nacimiento**, el sistema muestra quién es y **exige marcar "Confirmo que es otra persona"** para continuar.
  - El mismo **documento** no puede registrarse dos veces.
- **En el código:** `app.py` → `pacientes()` (búsqueda) y `paciente_form()` (aviso de duplicado y documento repetido); columna `nombre_busqueda` e índice único `ux_pacientes_documento` en `sql/schema.sql`.
- **Prueba:** `test_mismo_nombre_y_nacimiento_avisa_posible_duplicado`, `test_documento_repetido_rechazado`.

### 2.2 Paciente sin cédula, correo ni teléfono
- **Decisión:** se acepta sin documento (opción "No tiene", por ejemplo un recién nacido) y sin correo. Pero **se exige al menos un teléfono** (del paciente o de un familiar), porque sin ningún contacto no se le puede avisar si su cita cambia. Si es **menor de edad**, el representante es obligatorio.
- **En el código:** `app.py` → `leer_formulario_paciente()`.
- **Prueba:** `test_paciente_sin_cedula_ni_correo_pero_con_telefono_de_familiar`, `test_paciente_sin_ningun_telefono_rechazado`, `test_menor_de_edad_exige_representante`.

### 2.3 Número de teléfono mal escrito
- **Decisión:** se valida el formato ecuatoriano: celular `09XXXXXXXX` (10 dígitos) o fijo `0[2-7]XXXXXXX` (9 dígitos); se acepta `+593`. Se quitan espacios y guiones. **No podemos saber si el número existe**: se recomienda confirmarlo leyéndoselo al paciente.
- **En el código:** `validaciones.py` → `normalizar_telefono()`, `validar_telefono()`.
- **Prueba:** `test_telefonos`.

### 2.4 ¿Quién puede ver qué?
- **Decisión:**

  | Rol | Ve | No puede |
  |---|---|---|
  | Recepción | Agenda de las 3 clínicas, pacientes | Administración, usuarios, historial |
  | Médico | **Solo sus propias citas** | Cancelar, agendar, ver citas de otros médicos |
  | Administración | Todo | — |

  Además **no se guardan diagnósticos**: solo el motivo de la cita. Así una recepcionista nunca ve información clínica.
- **En el código:** `app.py` → decorador `login_requerido(*roles)`, filtro por `medico_id` en `agenda()` y en `obtener_cita()`.
- **Prueba:** `test_recepcion_no_entra_a_administracion`, `test_medico_solo_ve_sus_citas_y_no_cancela`.

---

## 3. Sobre los datos médicos

### 3.1 ¿Qué pasaría si alguien ajeno ve la información? ¿Cómo se evita?
- **Decisión:**
  - Sin usuario y contraseña **no se ve ninguna pantalla**.
  - Contraseñas guardadas **cifradas (hash)**, nunca en texto.
  - **Bloqueo**: tras 5 contraseñas incorrectas, el usuario se bloquea 15 minutos (se registra en el historial). La administradora lo desbloquea asignando una contraseña nueva.
  - La sesión expira a las 8 horas. Al cerrar sesión, el botón "Atrás" **no muestra** datos de pacientes (no se guardan en el navegador).
  - Protección contra formularios enviados desde otros sitios (token CSRF) y contra redirecciones a sitios externos después del login.
  - La clave de la base de datos está en `.env`, que **no se sube a GitHub**.
- **En el código:** `app.py` → `login()`, `login_requerido()`, `cargar_usuario_y_csrf()`, `encabezados_seguridad()`, `destino_seguro()`; `werkzeug.security.generate_password_hash`; `.gitignore`.
- **Prueba:** `test_sin_sesion_no_se_ve_nada`, `test_contrasenas_guardadas_como_hash`, `test_bloqueo_tras_5_intentos_fallidos`, `test_paginas_no_quedan_guardadas_en_el_navegador`, `test_formulario_sin_token_csrf_rechazado`, `test_no_redirige_a_sitios_externos`.
- **Pendiente:** si algún día se publica en internet, usar HTTPS (certificado). En la red local no aplica.

### 3.2 Si alguien cambia o borra una cita, ¿cómo se sabe quién y cuándo?
- **Decisión:** cada acción (crear, cancelar, deshacer, cambiar estado, crear pacientes, usuarios, horarios, inicios de sesión y contraseñas fallidas) se guarda en el **historial de cambios** con usuario, fecha y hora, y una descripción entendible (por ejemplo *"María López · Dr. Luis Salazar · Clínica Norte · 23/11/2026 14:00 — Motivo: viaje"*).
  El historial **no se puede modificar ni borrar, ni siquiera con SQL directo**: la base de datos lo rechaza.
- **En el código:** `db.py` → `registrar_auditoria()` (se escribe **en la misma transacción** que el cambio); disparadores `tr_auditoria_inmutable` y `tr_auditoria_sin_truncate` en `sql/schema.sql`; pantalla `admin_auditoria()`.
- **Prueba:** `test_cada_cambio_queda_registrado_con_quien_y_cuando`, `test_el_historial_no_se_puede_modificar_ni_borrar`.

### 3.3 ¿Qué pasa si se borra todo por accidente?
- **Decisión:**
  1. **Las citas no se pueden borrar**: la base de datos lo impide (`DELETE` y `TRUNCATE` dan error). Solo se cancelan.
  2. **Copias de seguridad** con `respaldo.ps1` (guarda las últimas 30). Se recomienda programarlo a diario en Windows y copiar la carpeta a un disco externo.
  3. Restaurar: `pg_restore -U postgres -d ClinAgenda --clean respaldos\<archivo>.dump`.
- **En el código:** disparadores `tr_citas_sin_borrado` y `tr_citas_sin_truncate` en `sql/schema.sql`; `respaldo.ps1`.
- **Prueba:** `test_las_citas_no_se_pueden_borrar`. El respaldo se probó a mano el 20/11/2026: se ejecutó `respaldo.ps1`, se restauró en una base aparte y coincidieron las cantidades de citas, pacientes e historial (no hay prueba automática de esto).

---

## 4. Sobre el uso real

### 4.1 ¿Podría doña Rosa usarlo sin ayuda?
- **Decisión de diseño:** letra grande (17 px), alto contraste, botones grandes, palabras simples, menú con íconos y texto, agendar en **4 pasos numerados** con un resumen siempre visible. Manual paso a paso con capturas en [`docs/MANUAL_USUARIO.md`](docs/MANUAL_USUARIO.md).
- **Pendiente honesto:** **todavía no lo probamos con una persona no técnica.** Cuando se haga, anotaremos aquí qué le costó y qué cambiamos.

### 4.2 Cuando algo sale mal, ¿el mensaje sirve a una persona normal?
- **Decisión:** todos los mensajes dicen **qué pasó y qué hacer**, sin palabras técnicas. Ejemplos:
  - Cédula mal: *"Esta cédula no es válida (el último dígito no coincide). Revise que esté bien escrita."*
  - Sin base de datos: *"No hay conexión con la base de datos… No se perdió nada de lo ya guardado. Espere un minuto… use la agenda impresa del día."* (nunca se muestra un error de programador).
- **En el código:** `validaciones.py` (mensajes), `app.py` → manejadores `sin_base_datos()`, `no_encontrado()`, `error_interno()`.
- **Prueba:** `test_error_explica_y_conserva_lo_escrito`, `test_sin_base_de_datos_mensaje_para_personas`, `test_pagina_inexistente_mensaje_amable`.

### 4.3 Si alguien presiona el botón equivocado, ¿se puede deshacer?
- **Decisión:** sí.
  - Antes de agendar, marcar "No vino", desactivar usuarios o quitar horarios aparece una **ventana de confirmación**.
  - Cancelar → **"Deshacer cancelación"** (si nadie tomó la hora).
  - Marcar Atendida / No vino → **"Corregir"**.
- **En el código:** `templates/base.html` (confirmación `data-confirmar`), `app.py` → `cita_reactivar()`, `cita_estado()`.
- **Prueba:** `test_deshacer_cancelacion_y_no_si_otro_tomo_la_hora`.

### 4.4 ¿Se puede usar desde un celular? ¿Con letra pequeña o poca luz?
- **Decisión:** sí; el diseño se adapta (las listas pasan a tarjetas, el menú se abre con ☰). Colores con buen contraste y estados con **texto además de color** (no se depende solo del color). Funciona en la red local de la clínica.
- **En el código:** `static/css/estilos.css` (secciones "Responsivo").

---

## 5. Sobre la calidad de los datos

| Pregunta | Decisión | En el código | Prueba |
|---|---|---|---|
| Cédula de 9 dígitos, con letras o `0000000000`. ¿Cómo saber si es real? | Rechazada. Se validan 10 dígitos, provincia (01–24 o 30), tercer dígito < 6 y **dígito verificador módulo 10**. Esto prueba que el número es *válido*; saber si *existe* requeriría consultar al Registro Civil (fuera de alcance). | `validaciones.py` → `validar_cedula_ecuador()` | `test_cedulas` |
| Extranjero con pasaporte o paciente sin documento | Tipo `PASAPORTE` (5–20 letras/números) o `NINGUNO`. | `validar_pasaporte()`, `leer_formulario_paciente()` | `test_pasaporte` |
| Teléfono `12345` o correo `juan@@gmail` | Rechazados con el formato correcto y un ejemplo. | `validar_telefono()`, `validar_email()` | `test_telefonos`, `test_correos` |
| Nacido en 2090 o con 300 años | Rechazado: fecha futura o más de 120 años. | `validar_fecha_nacimiento()` | `test_fechas_de_nacimiento_imposibles` |
| "MARÍA lópez" vs "Maria Lopez" | Se guarda ordenado ("María López") y se compara sin tildes ni mayúsculas, para la búsqueda y el aviso de duplicado. | `normalizar_nombre()`, `clave_busqueda()` | `test_mismo_nombre_escrito_distinto` |
| Al rechazar un dato, ¿dice qué está mal sin borrar lo escrito? | Sí: mensaje en rojo junto al campo y el formulario conserva todo. | `paciente_form()` + `templates/paciente_form.html` | `test_error_explica_y_conserva_lo_escrito` |
| Texto raro: emojis, comillas, código | Se quitan emojis y caracteres invisibles; tabuladores y saltos se vuelven espacios; se limita el largo. Los nombres solo aceptan letras. El código pegado **se muestra como texto** (no se ejecuta) y las consultas usan parámetros (sin inyección SQL). | `limpiar_texto()`, `validar_nombre()`; Jinja escapa el HTML; `psycopg2` con `%s` | `test_texto_raro_emojis_y_codigo`, `test_codigo_pegado_se_muestra_como_texto` |

> Al escribir las pruebas encontramos un error real: un tabulador pegado unía palabras ("de cabeza" quedaba "decabeza"). Se corrigió en `limpiar_texto()`.

---

## 6. Sobre los fallos

### 6.1 Se cae el internet en la Clínica Sur a mitad de agendar
- **Decisión:** el sistema no depende de internet: no usa servicios ni fuentes externas. Si está instalado **en una computadora de la Clínica Sur**, sigue funcionando ahí aunque no haya internet. Si el servidor está en otra clínica, la Sur perdería acceso: para eso se recomienda (a) **imprimir la agenda cada mañana** (botón Imprimir) y anotar en papel las citas nuevas para registrarlas al volver la conexión, o (b) a futuro, un servidor en la nube o una VPN.
  Si la conexión se corta justo al guardar, **no queda nada a medias**: cada guardado es una transacción completa (o se guarda todo, o nada) y la pantalla avisa que no se pudo guardar.
- **En el código:** `db.py` → `conexion()` (COMMIT/ROLLBACK); `@media print` en `estilos.css`.
- **Pendiente honesto:** no implementamos funcionamiento sin conexión dentro del navegador (modo offline). Es complejo y arriesga citas duplicadas al sincronizar; preferimos el plan en papel, que es simple y seguro.

### 6.2 El sistema se cae un lunes a las 8 de la mañana
- **Decisión:** 1) usar la agenda impresa; 2) reiniciar con doble clic en `iniciar.bat`; 3) si la base se dañó, restaurar el último respaldo. Ningún dato guardado se pierde por un reinicio.

### 6.3 Clínicas con horarios distintos o cambio de hora
- **Decisión:** cada médico tiene horarios **por clínica y por día**, así cada clínica puede tener su propio horario. Ecuador no usa cambio de horario; aun así la hora se calcula con la zona `America/Guayaquil` (no con la hora de la computadora).
- **En el código:** tabla `horarios_medico`; `app.py` → `ZONA`, `ahora()`.

---

## 7. Sobre lo que la clienta no dijo

### 7.1 Cosas que necesita y no mencionó (las agregamos)
- Usuarios individuales y roles (para saber quién hizo qué).
- Historial de cambios que no se puede borrar.
- Copias de seguridad.
- Representante para menores de edad.
- Bloqueo por contraseñas fallidas.
- Manual de usuario.

### 7.2 Contradicción: "cualquiera puede cancelar fácilmente" vs "no soporto que se pierdan citas"
- **Decisión:** cancelar es fácil (2 clics), pero:
  - exige escribir el motivo,
  - **la cita nunca se borra** (la base lo impide),
  - queda registrado quién la canceló y cuándo,
  - se puede **deshacer**,
  - "cualquiera" = cualquier persona del personal con usuario, no cualquier persona anónima.

---

## 8. Lo que quedó fuera y por qué

| Tema | Por qué no se hizo | Cómo lo haríamos |
|---|---|---|
| Recordatorios por WhatsApp/SMS | Requiere servicios pagados y datos de contacto confirmados. | Integrar un proveedor de SMS/WhatsApp Business un día antes de cada cita. |
| Lista de espera para horas liberadas | Falta de tiempo. | Al cancelar, sugerir pacientes en espera para esa hora. |
| Feriados y vacaciones de médicos | Falta de tiempo. | Tabla de "días bloqueados" que `horarios_libres()` descuente. |
| Modo sin conexión en el navegador | Riesgo de citas duplicadas al sincronizar. | Ver 6.1: se prefirió el plan en papel. |
| Prueba de carga (500 citas en un día) | Falta de tiempo. | Script que cree 500 citas y mida tiempos de la agenda. |
| HTTPS | En red local no aplica. | Certificado si se publica en internet. |

---

## 9. Pendientes según el cronograma del concurso

- **Datos de prueba (martes):** al recibirlos haremos un importador que valide cada fila con las **mismas reglas** de `validaciones.py` y entregue un **reporte de filas rechazadas y por qué**, en lugar de cargar datos malos en silencio.
- **Cambio de planes (miércoles/jueves):** se trabajará en una rama propia para que se vea en el historial de Git.
- **Etiqueta `entrega-final`:** el viernes por la noche, sobre el último commit revisado.
- **Prueba con una persona no técnica:** anotar aquí qué pasó.

---

## 10. Datos de demostración y seguridad del repositorio

- Todos los pacientes, médicos y usuarios de ejemplo son **inventados**.
- `.env` (clave de la base), respaldos y `demo_credenciales.txt` están en `.gitignore`.
- Las contraseñas de demostración (`usuario` + `2026`) son sencillas **a propósito** para que el jurado pruebe rápido; solo las crea `demo_datos.py`. En la clínica real el administrador se crea con `init_db.py` y cada persona cambia su contraseña.

## Documentación relacionada

- [README.md](README.md) · [INSTALACION.md](INSTALACION.md) · [docs/MANUAL_USUARIO.md](docs/MANUAL_USUARIO.md) · [docs/DIAGRAMA_ENTIDAD_RELACION.md](docs/DIAGRAMA_ENTIDAD_RELACION.md)
- Versiones Word: carpeta [`docs/word/`](docs/word/)
