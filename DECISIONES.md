# DECISIONES — ClinAgenda

> Borrador inicial. El equipo debe revisarlo, completarlo con lo que pregunte a la
> clienta y con lo que pase al probar con alguien no técnico.

## Supuestos sobre la clienta

- Las 3 clínicas están en Ecuador (misma zona horaria, sin cambio de horario).
- Las citas duran 30 minutos (configurable en `app.py`, `DURACION_CITA_MIN`).
- "Cualquiera" que cancela = cualquier persona del personal con usuario, no el paciente
  directamente (el paciente llama y la recepción cancela).
- La doctora es la administradora; las 5 recepcionistas tienen rol Recepción.

## Sobre las citas

| Pregunta | Decisión |
|---|---|
| Dos recepcionistas, misma hora, mismo médico, mismo segundo | Índice único en PostgreSQL `(medico_id, fecha, hora)` solo para citas activas. La primera se guarda; la segunda recibe: *"Otra persona acaba de tomar ese horario. Elija otro."* |
| Fecha que ya pasó | Rechazada en el servidor (y el calendario no permite elegirla). Horas ya pasadas del día de hoy no se muestran. |
| Cancelar dos veces | El `UPDATE` solo afecta citas `AGENDADA`. La segunda vez muestra *"ya estaba cancelada, no se hizo ningún cambio"*. |
| Hora liberada por cancelación | Vuelve a aparecer como disponible de inmediato. |
| Médico en dos clínicas a la misma hora | Imposible: el índice único no incluye la clínica. Además, al crear horarios se impide que se crucen entre clínicas. |
| 500 citas en un día / ninguna | 500 filas es poco para PostgreSQL; la agenda se filtra por clínica. Sin citas se muestra "No hay citas para este día". |
| Agendar a 2 años | Límite de 180 días adelante. |

## Sobre las personas

| Pregunta | Decisión |
|---|---|
| ¿Es el mismo "Juan Pérez"? | Se busca por documento, teléfono o nombre. Si al registrar coincide nombre + fecha de nacimiento, se avisa y se exige confirmar que es otra persona. |
| Sin cédula, correo ni teléfono | Se permite "sin documento" (bebés, extranjeros sin papeles), pero se exige **al menos un teléfono** (propio o del representante) para poder avisar cambios. |
| Teléfono mal escrito | Se valida formato ecuatoriano (celular 09XXXXXXXX, fijo 0XXXXXXXX). No se puede verificar que exista: pendiente confirmar por llamada. |
| ¿Quién ve qué? | Recepción: agenda de todas las clínicas y pacientes. Médico: solo su agenda. Admin: todo + historial de cambios + usuarios. **No se guardan diagnósticos**, solo el motivo de la cita. |

## Sobre los datos médicos

- Acceso solo con usuario y contraseña (guardada con hash, nunca en texto plano).
- Sesión expira a las 8 horas. Protección CSRF en todos los formularios.
- Claves fuera del código: archivo `.env` excluido de Git.
- Contraseñas de demostración (`usuario2026`): son sencillas a propósito para que el jurado
  pruebe rápido y solo las crea `demo_datos.py`. En producción el administrador real se crea con
  `init_db.py` y cada persona cambia su contraseña. Decisión consciente, no un descuido.
- **Nada se borra**: las citas se cancelan; el historial (`auditoria`) registra usuario, acción y fecha.
- **Borrado accidental**: `respaldo.ps1` genera copias diarias (programar en Windows). Restauración documentada.
- Pendiente: HTTPS si se publica fuera de la red local; bloqueo tras varios intentos fallidos de login.

## Sobre el uso real

- Letra de 18 px, botones grandes, alto contraste, textos sin tecnicismos, flujo guiado en pasos numerados.
- Mensajes de error dicen **qué está mal y cómo corregirlo**; el formulario conserva lo escrito.
- Confirmación antes de agendar y cancelar; la cancelación se puede deshacer; marcar "Atendida" se puede corregir.
- Diseño adaptable a celular (las tablas se vuelven tarjetas).
- **Pendiente**: prueba con una persona no técnica (anotar aquí qué pasó).

## Sobre los fallos

- **Internet en Clínica Sur**: el sistema se instala en un servidor de la red local, por lo que funciona sin internet dentro de la clínica donde está el servidor. Para las otras clínicas haría falta un servidor accesible por internet o una VPN. Plan B: imprimir la agenda del día cada mañana (botón Imprimir) y registrar luego lo agendado en papel. Sin conexión, el sistema muestra un mensaje claro y no guarda datos a medias (todo es transaccional).
- **Caída un lunes 8 a.m.**: agenda impresa + reiniciar con `iniciar.bat` + restaurar respaldo si hace falta.
- **Horarios distintos por clínica**: cada médico tiene horarios por clínica y día de la semana. Ecuador no tiene cambio de horario; se usa la zona `America/Guayaquil`.

## Sobre la calidad de los datos

| Pregunta | Decisión |
|---|---|
| Cédula con 9 dígitos, letras o `0000000000` | Rechazada. Se validan 10 dígitos, código de provincia (01–24 o 30), tercer dígito < 6 y **dígito verificador (módulo 10)**. Así se sabe que el número *es válido*; no se puede saber si *existe* sin consultar al Registro Civil (fuera de alcance). |
| Extranjero con pasaporte / paciente sin documento | Tipo `PASAPORTE` (5–20 letras/números) o `NINGUNO`. El documento es único por tipo. |
| Teléfono `12345`, correo `juan@@gmail` | Rechazados con un mensaje que explica el formato correcto y da un ejemplo. |
| Nacido en 2090 o con 300 años | Rechazado: fecha futura o edad mayor a 120 años. |
| "MARÍA lópez" vs "Maria Lopez" | Se guarda ordenado ("María López") y se compara una versión sin tildes ni mayúsculas (`nombre_busqueda`), así la búsqueda y el aviso de duplicado los reconocen como iguales. |
| El sistema rechaza un dato | Muestra el error junto al campo, en rojo y en palabras simples, **sin borrar lo ya escrito**. |
| Texto raro (emojis, comillas, código) | Se eliminan emojis y caracteres de control, se recortan espacios y largo máximo. Las consultas usan parámetros (sin inyección SQL) y las plantillas escapan el HTML (sin inyección de código). |

## Contradicciones detectadas

- *"Cualquiera pueda cancelar fácilmente"* vs. *"no soporta que se pierdan citas"* → se cancela en 2 clics, pero exige motivo, nunca se borra, queda registrado quién lo hizo y se puede deshacer.

## Lo que la clienta no dijo (y se agregó)

- Usuarios individuales y roles, historial de cambios, respaldos, representante para menores.

## Documentación entregada

- [README.md](README.md): qué es y cómo está organizado.
- [INSTALACION.md](INSTALACION.md): instalación en un equipo nuevo y prueba en 5 minutos para el jurado.
- [docs/MANUAL_USUARIO.md](docs/MANUAL_USUARIO.md): manual paso a paso con capturas, pensado para doña Rosa.
- [docs/DIAGRAMA_ENTIDAD_RELACION.md](docs/DIAGRAMA_ENTIDAD_RELACION.md): modelo de datos y diccionario.

## Pendientes según el cronograma del concurso

- **Datos de prueba (martes):** cuando se reciba el archivo, se hará un importador que valide cada fila
  con las mismas reglas de `validaciones.py` y genere un reporte de filas rechazadas y por qué,
  en lugar de cargar datos malos en silencio.
- **Cambio de planes (miércoles/jueves):** se trabajará en una rama propia para que se vea en el historial.
- **Etiqueta `entrega-final`:** se crea el viernes por la noche sobre el último commit revisado.
- **Prueba con una persona no técnica:** pendiente; anotar aquí qué pasó y qué se cambió.

## Fuera de alcance (por ahora)

- Recordatorios por WhatsApp/SMS, lista de espera para horas liberadas, feriados/vacaciones de médicos, funcionamiento offline real en el navegador, importación de los datos de prueba (se hará cuando se entreguen el martes).
