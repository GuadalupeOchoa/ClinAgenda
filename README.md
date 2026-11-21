# ClinAgenda

Sistema web sencillo para agendar citas en las tres clínicas de la Dra. Paredes
(Centro, Norte y Sur). Hecho con **Flask + HTML + CSS + PostgreSQL**, pensado para que
lo use personal sin experiencia con computadoras.

Repositorio: https://github.com/GuadalupeOchoa/ClinAgenda

wwwwww
![Agenda del día](docs/img/02_agenda.jpg)

## Documentación

| Documento | Para quién |
|---|---|


| [DECISIONES.md](DECISIONES.md) | Qué se decidió ante cada pregunta de la clienta, dónde está en el código y qué prueba lo demuestra. |


## Pruebas automáticas

38 pruebas verifican cada control descrito en DECISIONES (citas cruzadas, fechas pasadas, roles,
historial imborrable, validación de datos, bloqueo por contraseñas fallidas, etc.).
Usan una base de datos aparte (`ClinAgenda_pruebas`) y no tocan los datos reales:




## Qué hace

- **Agenda del día** por clínica, con contadores y botón de imprimir (respaldo en papel).
- **Pacientes**: búsqueda por nombre (sin importar tildes ni mayúsculas), cédula o teléfono.
  Validación de cédula ecuatoriana (dígito verificador), pasaporte o "sin documento",
  teléfono, correo, fecha de nacimiento y representante para menores. Aviso de posible duplicado.
- **Agendar cita** en 4 pasos guiados: clínica → médico → día → hora (solo muestra horas libres).
- **Sin cruces**: la base de datos impide que un médico tenga dos citas a la misma hora,
  aunque sea en clínicas distintas o dos recepcionistas guarden en el mismo segundo.
- **Cancelar** con motivo; la cita no se borra y se puede **deshacer**.
- **Roles**: Administración, Recepción y Médico (el médico solo ve su agenda).
- **Historial de cambios**: quién creó, canceló o cambió qué y cuándo.
- **Respaldo** de la base con `respaldo.ps1`.
- Diseño de letra grande y alto contraste, adaptable a celular y **sin dependencias de internet**.



## Estructura

```
ClinAgenda/
├── app.py             # Rutas (pantallas) y reglas de negocio
├── db.py              # Conexión a PostgreSQL y bitácora
├── validaciones.py    # Validación de cédula, teléfono, correo, nombres...
├── init_db.py         # Crea la base, tablas, datos iniciales y el administrador
├── sql/               # schema.sql (tablas e índices) y datos_iniciales.sql
├── templates/         # Pantallas HTML (Jinja2)
├── static/css/        # Estilos
├── herramientas/      # Generador de los documentos Word (Node.js)
├── iniciar.bat        # Abre el sistema con doble clic
└── DECISIONES.md
```

## Datos y seguridad

- No se suben datos reales ni credenciales: `.env` y los respaldos están en `.gitignore`.
- Todos los pacientes, médicos y usuarios de ejemplo son **inventados**.
