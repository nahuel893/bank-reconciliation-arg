# Guía de Instalación Completa - Bank Reconciliation ARG

Esta guía te ayuda a instalar el sistema desde cero en una PC nueva.

---

## Requisitos Previos

### Software necesario:
- ✅ **Python 3.8+** - [Descargar](https://www.python.org/downloads/)
- ✅ **Node.js 16+** - [Descargar](https://nodejs.org/)
- ✅ **PostgreSQL 12+** - [Descargar](https://www.postgresql.org/download/)
- ✅ **Git** (opcional) - Para clonar el repositorio

---

## Instalación Paso a Paso

### PASO 1: Instalar PostgreSQL

#### En Ubuntu/Debian:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### En Windows:
1. Descargar instalador desde [postgresql.org](https://www.postgresql.org/download/windows/)
2. Ejecutar instalador (recordar la contraseña del usuario `postgres`)
3. Verificar que el servicio esté corriendo

#### En macOS:
```bash
brew install postgresql
brew services start postgresql
```

---

### PASO 2: Crear la Base de Datos

```bash
# Conectar a PostgreSQL
sudo -u postgres psql

# Dentro de psql:
CREATE DATABASE comprobantes_badie;
CREATE USER badie_user WITH PASSWORD 'tu_password_aqui';
GRANT ALL PRIVILEGES ON DATABASE comprobantes_badie TO badie_user;

# Salir
\q
```

**IMPORTANTE:** Anota estos datos:
- Base de datos: `comprobantes_badie`
- Usuario: `badie_user`
- Contraseña: `tu_password_aqui`

---

### PASO 3: Clonar/Copiar el Código

#### Opción A - Con Git:
```bash
git clone <URL_DEL_REPOSITORIO>
cd bank-reconciliation-arg
```

#### Opción B - Copiando archivos:
1. Copia toda la carpeta del proyecto a la nueva PC
2. Navega a la carpeta en terminal

---

### PASO 4: Configurar Variables de Entorno

#### Opción A - Crear archivo `.env` (RECOMENDADO):

Crea un archivo `.env` en la raíz del proyecto:

```bash
# .env
GEMINI_API_KEY=tu_api_key_de_google_gemini
DATABASE_URL=postgresql://badie_user:tu_password_aqui@localhost:5432/comprobantes_badie
POSTGRES_USER=badie_user
POSTGRES_PASSWORD=tu_password_aqui
DATABASE=comprobantes_badie
```

#### Opción B - Editar `src/config.py`:

Si no usas `.env`, edita directamente `src/config.py`:

```python
POSTGRES_USER = "badie_user"
POSTGRES_PASSWORD = "tu_password_aqui"
DATABASE = "comprobantes_badie"
GEMINI_API_KEY = "tu_api_key_de_google_gemini"
```

**⚠️ IMPORTANTE:** Agrega `.env` a `.gitignore` para no subir credenciales al repositorio.

---

### PASO 5: Instalar Dependencias Python

```bash
# Crear entorno virtual (RECOMENDADO)
python -m venv venv

# Activar entorno virtual
# En Linux/macOS:
source venv/bin/activate

# En Windows:
venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

**Verificar instalación:**
```bash
pip list | grep -E "flask|pandas|sqlalchemy|psycopg2"
```

Deberías ver:
- Flask
- pandas
- SQLAlchemy
- psycopg2-binary
- openpyxl
- google-generativeai

---

### PASO 6: Inicializar la Base de Datos

```bash
python main.py init-db
```

**Salida esperada:**
```
Inicializando la base de datos...
¡Base de datos inicializada con éxito!
```

**❌ Si hay error:**
- Verifica que PostgreSQL esté corriendo: `sudo systemctl status postgresql`
- Verifica credenciales en `.env` o `config.py`
- Verifica que la base de datos exista: `psql -U postgres -c "\l"`

**✅ Verificar que las tablas se crearon:**
```bash
psql -U badie_user -d comprobantes_badie -c "\dt"
```

Deberías ver:
```
 Schema |    Name     | Type  |   Owner
--------+-------------+-------+-----------
 public | comprobantes| table | badie_user
 public | mensajes    | table | badie_user
```

**✅ Verificar columnas de conciliación:**
```bash
psql -U badie_user -d comprobantes_badie -c "\d comprobantes"
```

Deberías ver las columnas:
- `conciliado`
- `fecha_conciliacion`
- `observaciones_conciliacion`

**Si NO ves estas columnas**, significa que el modelo no se sincronizó. Ejecuta:
```bash
python migrate_conciliacion.py
```

---

### PASO 7: Instalar Dependencias Node.js

```bash
cd whatsapp-bot
npm install
cd ..
```

**Verificar instalación:**
```bash
cd whatsapp-bot
npm list whatsapp-web.js
```

Deberías ver: `whatsapp-web.js@1.34.2`

---

### PASO 8: Crear Carpetas Necesarias

```bash
# Crear carpetas si no existen
mkdir -p assets/wpp-comprobantes
mkdir -p assets/banco
```

---

### PASO 9: Configurar Módulo de Conciliación (Opcional)

Si vas a usar el módulo de conciliación bancaria:

1. **Verificar que existe `bank_config.json`** en la raíz:
```bash
ls bank_config.json
```

2. **Si NO existe**, créalo:
```json
{
  "description": "Configuración para conciliación bancaria",
  "column_mapping": {
    "fecha": "Fecha",
    "cuit": "CUIT",
    "monto": "Importe"
  },
  "tolerances": {
    "fecha_dias": 1,
    "monto_diferencia": 0.01
  },
  "data_formats": {
    "fecha_format": "%d/%m/%Y",
    "monto_decimal_separator": ",",
    "monto_thousands_separator": ".",
    "cuit_format": "with_dashes"
  },
  "excel_options": {
    "sheet_name": 0,
    "header_row": 0,
    "skip_rows": 0
  }
}
```

---

## Ejecución del Sistema

### 1. Iniciar Backend Python (Flask)

En una terminal:
```bash
# Activar entorno virtual si usaste venv
source venv/bin/activate  # Linux/macOS
# o
venv\Scripts\activate     # Windows

# Ejecutar servidor
python visualizador.py
```

**Salida esperada:**
```
 * Running on http://127.0.0.1:5000
```

**Verificar:** Abre navegador en http://localhost:5000

---

### 2. Iniciar Bot de WhatsApp

En otra terminal:
```bash
cd whatsapp-bot
node bot.js
```

**Primera ejecución:**
1. Mostrará un código QR en la terminal
2. Escanea el QR con WhatsApp (tu teléfono)
3. El bot se conectará y dirá: `Cliente de WhatsApp listo.`
4. Ejecutará sincronización histórica
5. Comenzará a escuchar mensajes en tiempo real

**Ejecuciones posteriores:**
- NO pide QR (usa autenticación guardada en `.wwebjs_auth/`)
- Se conecta automáticamente

---

## Verificación Final

### Test 1: Base de datos funciona
```bash
python -c "from src.database import SessionLocal; db = SessionLocal(); print('✅ BD conectada')"
```

### Test 2: Backend funciona
```bash
curl http://localhost:5000
```

Deberías ver HTML del dashboard.

### Test 3: Bot funciona
Envía una imagen al grupo "Transferencias Badie" y verifica:
1. Se descarga en `assets/wpp-comprobantes/`
2. Aparece log en la terminal del bot
3. Aparece en el dashboard (http://localhost:5000)

---

## Comandos Útiles

### Ver comprobantes en BD:
```bash
python -c "from src.database import SessionLocal; from src.data_models import Comprobante; db = SessionLocal(); print(len(db.query(Comprobante).all()), 'comprobantes')"
```

### Resetear base de datos:
```bash
python reset_db.py
python main.py init-db
```

### Clasificar imágenes:
```bash
python main.py classify -d /ruta/a/imagenes
```

### Extraer datos de imágenes:
```bash
python main.py extract -d /ruta/a/imagenes
```

### Conciliar con Excel del banco:
```bash
python main.py reconcile -e assets/banco/movimientos.xlsx
```

---

## Troubleshooting

### Error: "No module named 'flask'"
**Solución:** No activaste el entorno virtual o no instalaste dependencias
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

### Error: "could not connect to server: Connection refused"
**Solución:** PostgreSQL no está corriendo
```bash
# Linux:
sudo systemctl start postgresql

# macOS:
brew services start postgresql

# Windows:
Ir a Servicios y arrancar PostgreSQL
```

---

### Error: "relation 'comprobantes' does not exist"
**Solución:** No ejecutaste `init-db`
```bash
python main.py init-db
```

---

### Error en bot: "Evaluation failed: Node is either not visible or not an HTMLElement"
**Solución:** Problema con Puppeteer. Reinicia el bot:
```bash
# Eliminar sesión y volver a escanear QR
rm -rf .wwebjs_auth/
node bot.js
```

---

### Bot no descarga imágenes
**Solución:** Verifica que la carpeta assets existe
```bash
mkdir -p assets/wpp-comprobantes
```

---

### Error: "column 'conciliado' does not exist"
**Solución:** Modelo no sincronizado. Ejecuta migración:
```bash
python migrate_conciliacion.py
```

---

## Archivos Importantes

### Configuración:
- `.env` - Credenciales y variables de entorno
- `src/config.py` - Configuración de Python
- `bank_config.json` - Configuración de conciliación
- `whatsapp-bot/bot.js` - Configuración del bot (líneas 8-14)

### Datos:
- `assets/wpp-comprobantes/` - Imágenes descargadas de WhatsApp
- `assets/banco/` - Excel del banco para conciliación
- `.wwebjs_auth/` - Sesión de WhatsApp (NO borrar)

### Logs:
- `whatsapp-bot/bot_debug.log` - Log del bot (si DEBUG_MODE activo)

---

## Backups

### Backup de la base de datos:
```bash
pg_dump -U badie_user comprobantes_badie > backup_$(date +%Y%m%d).sql
```

### Restaurar backup:
```bash
psql -U badie_user comprobantes_badie < backup_20241206.sql
```

### Backup de imágenes:
```bash
tar -czf imagenes_backup.tar.gz assets/wpp-comprobantes/
```

---

## Resumen: Instalación Rápida

```bash
# 1. Instalar PostgreSQL, Python, Node.js

# 2. Crear BD
sudo -u postgres psql -c "CREATE DATABASE comprobantes_badie;"
sudo -u postgres psql -c "CREATE USER badie_user WITH PASSWORD 'password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE comprobantes_badie TO badie_user;"

# 3. Configurar .env
echo "GEMINI_API_KEY=tu_key" > .env
echo "DATABASE_URL=postgresql://badie_user:password@localhost/comprobantes_badie" >> .env

# 4. Instalar dependencias
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd whatsapp-bot && npm install && cd ..

# 5. Crear carpetas
mkdir -p assets/wpp-comprobantes assets/banco

# 6. Inicializar BD
python main.py init-db

# 7. Ejecutar
python visualizador.py &
cd whatsapp-bot && node bot.js
```

---

## Contacto/Ayuda

Si tienes problemas:
1. Revisa la sección de Troubleshooting
2. Verifica los logs del bot (`whatsapp-bot/bot_debug.log` con DEBUG=true)
3. Revisa la consola de Python para errores del backend
4. Consulta la documentación en `DOCUMENTACION.md` y `CLAUDE.md`
