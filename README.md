# ClinAgenda

Sistema web sencillo para agendar citas en las tres clínicas de la Dra. Paredes
(Centro, Norte y Sur). Hecho con **Flask + HTML + CSS + PostgreSQL**.

## Qué hace

- **Agenda del día** por clínica, con botón de imprimir (respaldo en papel).
- **Pacientes**: búsqueda por nombre (sin importar tildes ni mayúsculas), cédula o teléfono.
  Registro con validación de cédula ecuatoriana (dígito verificador), pasaporte o
  "sin documento", teléfono, correo, fecha de nacimiento y representante para menores.
  Aviso de posible duplicado (mismo nombre y fecha de nacimiento).
- **Agendar cita** en 4 pasos: clínica → médico → día → hora (solo muestra horas libres).
- **Sin cruces**: la base de datos impide que un médico tenga dos citas a la misma hora,
  aunque sea en clínicas distintas o dos recepcionistas guarden en el mismo segundo.
- **Cancelar** con motivo; la cita no se borra y se puede **deshacer**.
- **Roles**: Administrador, Recepción y Médico (el médico solo ve su agenda).
- **Historial de cambios** (auditoría): quién creó, canceló o cambió qué y cuándo.
- **Respaldo** de la base con `respaldo.ps1`.
- Letra grande, alto contraste y diseño adaptable a celular.

## Estructura (arquitectura básica)

```
ClinAgenda/
├── app.py             # Rutas (pantallas) y reglas de negocio
├── db.py              # Conexión a PostgreSQL y bitácora
├── validaciones.py    # Validación de cédula, teléfono, correo, nombres...
├── init_db.py         # Crea la base, tablas, datos iniciales y el admin
├── sql/
│   ├── schema.sql           # Tablas e índices
│   └── datos_iniciales.sql  # 3 clínicas, 12 médicos y horarios (inventados)
├── templates/         # Pantallas HTML (Jinja2)
├── static/css/        # Estilos
├── instalar.ps1       # Instalador para un equipo Windows nuevo
├── iniciar.bat        # Abre el sistema con doble clic
├── respaldo.ps1       # Copia de seguridad de la base
├── .env.example       # Plantilla de configuración (el .env real NO se sube)
├── INSTALACION.md     # Instrucciones de uso e instalación (5 minutos)
└── DECISIONES.md      # Qué se decidió y por qué
```

## Inicio rápido

Ver [INSTALACION.md](INSTALACION.md).
