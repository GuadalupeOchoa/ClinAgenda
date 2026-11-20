# Diagrama entidad-relación — ClinAgenda

Base de datos **PostgreSQL** `ClinAgenda`. Definición completa en [`sql/schema.sql`](../sql/schema.sql).

![Diagrama entidad-relación](diagrama_entidad_relacion.svg)

## Versión Mermaid

GitHub dibuja este bloque automáticamente.

```mermaid
erDiagram
    CLINICAS ||--o{ HORARIOS_MEDICO : "tiene"
    MEDICOS  ||--o{ HORARIOS_MEDICO : "tiene"
    CLINICAS ||--o{ CITAS : "se agenda en"
    MEDICOS  ||--o{ CITAS : "atiende"
    PACIENTES ||--o{ CITAS : "reserva"
    MEDICOS  |o--o| USUARIOS : "es usuario"
    USUARIOS ||--o{ CITAS : "crea / edita"
    USUARIOS ||--o{ PACIENTES : "registra"
    USUARIOS ||--o{ AUDITORIA : "genera"

    CLINICAS {
        serial id PK
        varchar nombre UK
        varchar direccion
        boolean activa
    }
    MEDICOS {
        serial id PK
        varchar nombres
        varchar especialidad
        boolean activo
    }
    HORARIOS_MEDICO {
        serial id PK
        int medico_id FK
        int clinica_id FK
        smallint dia_semana "0=lunes ... 6=domingo"
        time hora_inicio
        time hora_fin
    }
    PACIENTES {
        serial id PK
        varchar tipo_documento "CEDULA | PASAPORTE | NINGUNO"
        varchar documento UK "único por tipo"
        varchar nombres
        varchar apellidos
        varchar nombre_busqueda "sin tildes, minúsculas"
        date fecha_nacimiento
        varchar telefono
        varchar email
        varchar responsable
        varchar telefono_responsable
        int creado_por FK
        timestamp creado_en
    }
    CITAS {
        serial id PK
        int paciente_id FK
        int medico_id FK
        int clinica_id FK
        date fecha
        time hora
        varchar motivo
        varchar estado "AGENDADA | CANCELADA | ATENDIDA | NO_ASISTIO"
        varchar motivo_cancelacion
        int creado_por FK
        timestamp creado_en
        int actualizado_por FK
        timestamp actualizado_en
    }
    USUARIOS {
        serial id PK
        varchar usuario UK
        varchar nombre
        varchar clave_hash "hash, nunca la clave"
        varchar rol "ADMIN | RECEPCION | MEDICO"
        int medico_id FK
        boolean activo
        timestamp creado_en
    }
    AUDITORIA {
        bigserial id PK
        int usuario_id FK
        varchar accion
        varchar entidad
        int entidad_id
        text detalle
        timestamp fecha
    }
```

## Diccionario de datos

| Tabla | Para qué sirve | Reglas importantes |
|---|---|---|
| `clinicas` | Las 3 sedes: Centro, Norte y Sur. | Nombre único. Se puede desactivar sin borrar. |
| `medicos` | Los 12 médicos. | Se desactivan, no se borran (tienen citas históricas). |
| `horarios_medico` | Qué día y a qué hora atiende cada médico en cada clínica. | `hora_fin > hora_inicio`. La aplicación impide que un médico tenga horarios cruzados, aunque sea en clínicas distintas (caso Dr. Salazar). |
| `pacientes` | Datos de cada paciente. | Documento único por tipo (`CEDULA`/`PASAPORTE`). `NINGUNO` permite pacientes sin documento. `nombre_busqueda` guarda el nombre sin tildes y en minúsculas para encontrar duplicados. |
| `citas` | Cada cita agendada. | **Índice único `(medico_id, fecha, hora)` solo para citas `AGENDADA`**: la base de datos impide dar la misma hora dos veces al mismo médico, aunque dos recepcionistas guarden en el mismo segundo. Otro índice impide que un paciente tenga dos citas a la misma hora. Las citas **nunca se borran**: cambian de estado. |
| `usuarios` | Personal que entra al sistema. | Contraseña guardada como hash. Rol `MEDICO` enlazado a su médico (solo ve sus citas). |
| `auditoria` | Bitácora de quién hizo qué y cuándo. | Se escribe en la misma transacción que el cambio. La aplicación no ofrece forma de borrarla. |

## Relaciones

| Relación | Cardinalidad | Significado |
|---|---|---|
| clinicas → horarios_medico | 1 : N | Una clínica tiene muchos horarios de atención. |
| medicos → horarios_medico | 1 : N | Un médico puede atender varios días y en varias clínicas. |
| clinicas → citas | 1 : N | Una clínica recibe muchas citas. |
| medicos → citas | 1 : N | Un médico atiende muchas citas (nunca dos a la misma hora). |
| pacientes → citas | 1 : N | Un paciente puede tener muchas citas en el tiempo. |
| medicos → usuarios | 1 : 0..1 | Un médico puede tener (o no) un usuario para ver su agenda. |
| usuarios → citas / pacientes | 1 : N | Se guarda quién creó y quién modificó por última vez. |
| usuarios → auditoria | 1 : N | Cada acción queda registrada con su autor. |
