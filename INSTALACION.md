# Instalación y uso de ClinAgenda

## A. Equipo nuevo (sin nada instalado) — instalación automática

1. Copie la carpeta `ClinAgenda` al equipo (por ejemplo en `C:\ClinAgenda`).
2. Abra **PowerShell como Administrador** (clic derecho en Inicio → *Terminal (Administrador)*).
3. Ejecute:

   ```powershell
   cd C:\ClinAgenda
   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
   ```

4. El script pedirá:
   - La **clave del usuario `postgres`** de la base de datos (se usa al instalar PostgreSQL y se guarda en `.env`).
   - El **usuario y contraseña del administrador** del sistema.
5. Al terminar, haga doble clic en **`iniciar.bat`**. Se abrirá `http://localhost:5000`.

El instalador usa `winget` (viene en Windows 10/11). Instala Python 3.12, PostgreSQL 17 y Git.

## B. Instalación manual (si el script falla)

1. Instale **Python 3.12** desde https://www.python.org/downloads/ — marque *"Add python.exe to PATH"*.
2. Instale **PostgreSQL 17** desde https://www.postgresql.org/download/windows/ — anote la clave del usuario `postgres`, puerto `5432`.
3. En la carpeta del proyecto:

   ```powershell
   python -m venv venv
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   copy .env.example .env
   notepad .env        # escriba la clave en DB_PASSWORD y una cadena larga en SECRET_KEY
   .\venv\Scripts\python.exe init_db.py
   .\venv\Scripts\python.exe app.py
   ```

4. Abra http://localhost:5000

## C. Probar el sistema en 5 minutos (para el jurado)

1. Cargue los datos de demostración (pacientes inventados, citas de la semana y el personal del caso):

   ```powershell
   .\venv\Scripts\python.exe demo_datos.py
   ```

   | Persona | Rol | Usuario | Contraseña (solo demo) |
   |---|---|---|---|
   | Dra. Ana Paredes | Administración | `paredes` | `paredes2026` |
   | Rosa Quishpe | Recepción | `rosa` | `rosa2026` |
   | Marcela, Diana, Patricia, Verónica | Recepción | `marcela`, `diana`, `patricia`, `veronica` | usuario + `2026` |
   | Dr. Luis Salazar | Médico | `salazar` | `salazar2026` |
   | Dra. Carmen Vega | Médico | `vega` | `vega2026` |

   Las contraseñas de demostración son sencillas a propósito. **En la clínica real**
   cada persona debe cambiarla (Usuarios → Cambiar contraseña).

2. Entre como `rosa` (recepción) y pruebe lo siguiente. Entre como `salazar` para ver que el médico solo ve su agenda.
3. **Pacientes** → *Registrar paciente nuevo*. Pruebe datos malos:
   cédula `0000000000` o `1234567890`, teléfono `12345`, correo `juan@@gmail`,
   nacimiento en 2090 → el sistema explica qué corregir **sin borrar lo escrito**.
   Una cédula válida de prueba: `1710034065`.
4. En la ficha del paciente → **Agendar cita** → Clínica Centro → Dr. Luis Salazar → un día de semana → elija la hora.
5. Intente agendar al **Dr. Salazar** en Clínica Norte el mismo día a la misma hora: esa hora ya no aparece.
6. En **Agenda** → *Cancelar* (pide motivo) → *Deshacer cancelación*.
7. **Historial de cambios** → se ve quién hizo cada acción.

8. Opcional: ejecute las pruebas automáticas de todos los controles (tarda menos de un minuto):

   ```powershell
   .\venv\Scripts\python.exe -m unittest -v tests.test_controles
   ```

## D. Usar desde otros equipos o celulares de la clínica

El sistema escucha en la red local. Desde otro equipo de la misma red abra
`http://<IP-del-equipo-servidor>:5000` (la IP se ve con `ipconfig`).
Puede ser necesario permitir el puerto 5000 en el Firewall de Windows.

## E. Respaldo

```powershell
powershell -ExecutionPolicy Bypass -File .\respaldo.ps1
```

Crea un archivo en `respaldos\`. Programe este comando a diario en el
*Programador de tareas* de Windows y copie la carpeta a un disco externo.
