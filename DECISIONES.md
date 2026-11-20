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

## Contradicciones detectadas

- *"Cualquiera pueda cancelar fácilmente"* vs. *"no soporta que se pierdan citas"* → se cancela en 2 clics, pero exige motivo, nunca se borra, queda registrado quién lo hizo y se puede deshacer.

## Lo que la clienta no dijo (y se agregó)

- Usuarios individuales y roles, historial de cambios, respaldos, representante para menores.

## Fuera de alcance (por ahora)

- Recordatorios por WhatsApp/SMS, lista de espera para horas liberadas, feriados/vacaciones de médicos, funcionamiento offline real en el navegador, importación de los datos de prueba (se hará cuando se entreguen el martes).
