-- =========================================================
-- ClinAgenda - Esquema de base de datos (PostgreSQL)
-- Se puede ejecutar varias veces: usa IF NOT EXISTS.
-- =========================================================

CREATE TABLE IF NOT EXISTS clinicas (
    id          SERIAL PRIMARY KEY,
    nombre      VARCHAR(80)  NOT NULL UNIQUE,
    direccion   VARCHAR(200),
    activa      BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS medicos (
    id           SERIAL PRIMARY KEY,
    nombres      VARCHAR(120) NOT NULL,
    especialidad VARCHAR(80),
    activo       BOOLEAN      NOT NULL DEFAULT TRUE
);

-- En qué clínica, qué día y en qué horario atiende cada médico.
-- Un médico puede tener horarios en varias clínicas (ej. Dr. Salazar).
CREATE TABLE IF NOT EXISTS horarios_medico (
    id           SERIAL PRIMARY KEY,
    medico_id    INT      NOT NULL REFERENCES medicos(id),
    clinica_id   INT      NOT NULL REFERENCES clinicas(id),
    dia_semana   SMALLINT NOT NULL CHECK (dia_semana BETWEEN 0 AND 6), -- 0=lunes ... 6=domingo
    hora_inicio  TIME     NOT NULL,
    hora_fin     TIME     NOT NULL,
    CHECK (hora_fin > hora_inicio)
);

CREATE TABLE IF NOT EXISTS usuarios (
    id             SERIAL PRIMARY KEY,
    usuario        VARCHAR(40)  NOT NULL UNIQUE,
    nombre         VARCHAR(120) NOT NULL,
    clave_hash     VARCHAR(255) NOT NULL,
    rol            VARCHAR(20)  NOT NULL CHECK (rol IN ('ADMIN', 'RECEPCION', 'MEDICO')),
    medico_id      INT REFERENCES medicos(id),       -- solo si rol = MEDICO
    activo         BOOLEAN      NOT NULL DEFAULT TRUE,
    creado_en      TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pacientes (
    id                SERIAL PRIMARY KEY,
    tipo_documento    VARCHAR(12)  NOT NULL CHECK (tipo_documento IN ('CEDULA', 'PASAPORTE', 'NINGUNO')),
    documento         VARCHAR(20),
    nombres           VARCHAR(100) NOT NULL,
    apellidos         VARCHAR(100) NOT NULL,
    nombre_busqueda   VARCHAR(220) NOT NULL,  -- minúsculas, sin tildes ni espacios extra
    fecha_nacimiento  DATE         NOT NULL,
    telefono          VARCHAR(15),
    email             VARCHAR(120),
    responsable       VARCHAR(150),           -- para niños o adultos mayores
    telefono_responsable VARCHAR(15),
    creado_por        INT REFERENCES usuarios(id),
    creado_en         TIMESTAMP    NOT NULL DEFAULT NOW(),
    CHECK (tipo_documento = 'NINGUNO' OR documento IS NOT NULL)
);
-- El mismo documento no puede registrarse dos veces
CREATE UNIQUE INDEX IF NOT EXISTS ux_pacientes_documento
    ON pacientes (tipo_documento, documento) WHERE documento IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_pacientes_busqueda ON pacientes (nombre_busqueda);

CREATE TABLE IF NOT EXISTS citas (
    id              SERIAL PRIMARY KEY,
    paciente_id     INT         NOT NULL REFERENCES pacientes(id),
    medico_id       INT         NOT NULL REFERENCES medicos(id),
    clinica_id      INT         NOT NULL REFERENCES clinicas(id),
    fecha           DATE        NOT NULL,
    hora            TIME        NOT NULL,
    motivo          VARCHAR(300),
    estado          VARCHAR(12) NOT NULL DEFAULT 'AGENDADA'
                    CHECK (estado IN ('AGENDADA', 'CANCELADA', 'ATENDIDA', 'NO_ASISTIO')),
    motivo_cancelacion VARCHAR(300),
    creado_por      INT         REFERENCES usuarios(id),
    creado_en       TIMESTAMP   NOT NULL DEFAULT NOW(),
    actualizado_por INT         REFERENCES usuarios(id),
    actualizado_en  TIMESTAMP
);
-- CLAVE: un médico no puede tener dos citas activas a la misma hora,
-- sin importar la clínica. Lo garantiza la base de datos, aunque dos
-- recepcionistas presionen "Guardar" en el mismo segundo.
CREATE UNIQUE INDEX IF NOT EXISTS ux_citas_medico_horario
    ON citas (medico_id, fecha, hora) WHERE estado = 'AGENDADA';
-- Un paciente no puede tener dos citas activas a la misma hora
CREATE UNIQUE INDEX IF NOT EXISTS ux_citas_paciente_horario
    ON citas (paciente_id, fecha, hora) WHERE estado = 'AGENDADA';
CREATE INDEX IF NOT EXISTS ix_citas_fecha ON citas (fecha, clinica_id);

-- Bitácora: quién hizo qué y cuándo. Nunca se borra.
CREATE TABLE IF NOT EXISTS auditoria (
    id          BIGSERIAL PRIMARY KEY,
    usuario_id  INT REFERENCES usuarios(id),
    accion      VARCHAR(40)  NOT NULL,
    entidad     VARCHAR(40)  NOT NULL,
    entidad_id  INT,
    detalle     TEXT,
    fecha       TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_auditoria_fecha ON auditoria (fecha DESC);
