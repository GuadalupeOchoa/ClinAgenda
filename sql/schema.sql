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

-- Bloqueo tras varios intentos fallidos de contraseña
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS intentos_fallidos INT NOT NULL DEFAULT 0;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS bloqueado_hasta TIMESTAMP;

-- "No soporta que se pierdan citas": la base de datos no permite borrar citas.
-- Una cita se CANCELA (cambia de estado), nunca desaparece.
CREATE OR REPLACE FUNCTION impedir_borrado_citas() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Las citas no se borran: cámbiela a estado CANCELADA';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS tr_citas_sin_borrado ON citas;
CREATE TRIGGER tr_citas_sin_borrado BEFORE DELETE ON citas
    FOR EACH ROW EXECUTE FUNCTION impedir_borrado_citas();
DROP TRIGGER IF EXISTS tr_citas_sin_truncate ON citas;
CREATE TRIGGER tr_citas_sin_truncate BEFORE TRUNCATE ON citas
    FOR EACH STATEMENT EXECUTE FUNCTION impedir_borrado_citas();

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

-- La bitácora es de solo agregar: nadie puede modificarla ni borrarla (ni siquiera con SQL directo
-- desde la aplicación). Así el historial de "quién hizo qué" es confiable.
CREATE OR REPLACE FUNCTION auditoria_inmutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'El historial de cambios no se puede modificar ni borrar';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS tr_auditoria_inmutable ON auditoria;
CREATE TRIGGER tr_auditoria_inmutable BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION auditoria_inmutable();
DROP TRIGGER IF EXISTS tr_auditoria_sin_truncate ON auditoria;
CREATE TRIGGER tr_auditoria_sin_truncate BEFORE TRUNCATE ON auditoria
    FOR EACH STATEMENT EXECUTE FUNCTION auditoria_inmutable();
