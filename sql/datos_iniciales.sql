-- Datos iniciales INVENTADOS (no son personas reales).
-- Solo se insertan si las tablas están vacías.

INSERT INTO clinicas (nombre, direccion)
SELECT * FROM (VALUES
    ('Clínica Centro', 'Dirección por definir'),
    ('Clínica Norte',  'Dirección por definir'),
    ('Clínica Sur',    'Dirección por definir')
) AS v(nombre, direccion)
WHERE NOT EXISTS (SELECT 1 FROM clinicas);

INSERT INTO medicos (nombres, especialidad)
SELECT * FROM (VALUES
    ('Dra. Ana Paredes',     'Medicina general'),
    ('Dr. Luis Salazar',     'Pediatría'),
    ('Dra. Carmen Vega',     'Ginecología'),
    ('Dr. Jorge Andrade',    'Medicina interna'),
    ('Dra. Sofía Morales',   'Dermatología'),
    ('Dr. Pablo Cevallos',   'Traumatología'),
    ('Dra. Lucía Herrera',   'Medicina general'),
    ('Dr. Mario Ortiz',      'Cardiología'),
    ('Dra. Elena Ruiz',      'Pediatría'),
    ('Dr. Diego Torres',     'Medicina familiar'),
    ('Dra. Paula Jaramillo', 'Geriatría'),
    ('Dr. Andrés Castro',    'Medicina general')
) AS v(nombres, especialidad)
WHERE NOT EXISTS (SELECT 1 FROM medicos);

-- Horarios de ejemplo: lunes a viernes (0..4).
-- Médicos 1-4 Centro, 5-8 Norte, 9-12 Sur, de 08:00 a 13:00.
-- El Dr. Salazar (id 2) atiende mañanas en Centro y tardes en Norte.
INSERT INTO horarios_medico (medico_id, clinica_id, dia_semana, hora_inicio, hora_fin)
SELECT m.id,
       CASE WHEN m.id <= 4 THEN 1 WHEN m.id <= 8 THEN 2 ELSE 3 END,
       d.dia, '08:00', '13:00'
FROM medicos m CROSS JOIN generate_series(0, 4) AS d(dia)
WHERE NOT EXISTS (SELECT 1 FROM horarios_medico);

INSERT INTO horarios_medico (medico_id, clinica_id, dia_semana, hora_inicio, hora_fin)
SELECT 2, 2, d.dia, '14:00', '18:00'
FROM generate_series(0, 4) AS d(dia)
WHERE NOT EXISTS (SELECT 1 FROM horarios_medico WHERE medico_id = 2 AND clinica_id = 2);
