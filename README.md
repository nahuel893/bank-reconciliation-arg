# Comprobantes Badie

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=for-the-badge&logo=node.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Gemini_AI-2.5_Flash-4285F4?style=for-the-badge&logo=google&logoColor=white)

**Sistema automatizado de extracción y conciliación de comprobantes bancarios mediante IA**

[Arquitectura](#arquitectura) •
[Instalación](#instalación) •
[Uso](#uso) •
[API](#api-endpoints) •
[Configuración](#configuración)

</div>

---

## Descripción

**Comprobantes Badie** es un sistema ETL (Extract, Transform, Load) que automatiza la extracción de datos de comprobantes de transferencias bancarias enviados por WhatsApp. Utiliza **Google Gemini AI** para procesar imágenes y extraer información estructurada, almacenándola en PostgreSQL para su posterior análisis y conciliación bancaria.

### Problema que Resuelve

En negocios que reciben múltiples transferencias diarias vía WhatsApp, el registro manual de cada comprobante es:
- **Lento**: Cada comprobante requiere 2-3 minutos de transcripción manual
- **Propenso a errores**: Montos mal ingresados, fechas incorrectas, CUITs confundidos
- **Difícil de conciliar**: Cruzar cientos de comprobantes con extractos bancarios es tedioso

Este sistema **automatiza todo el proceso**, reduciendo el tiempo de procesamiento de minutos a segundos por comprobante.

---

## Características Principales

| Característica | Descripción |
|----------------|-------------|
| **Extracción Automática con IA** | Google Gemini 2.5 Flash analiza imágenes y extrae: banco, monto, fecha, CUIT, CBU/CVU, código de operación |
| **Bot de WhatsApp** | Monitorea grupos en tiempo real, descarga imágenes automáticamente y asocia códigos de cliente |
| **Conciliación Bancaria** | Cruza comprobantes procesados con extractos Excel del banco usando fecha + CUIT + monto |
| **Dashboard Web** | Visualización en tiempo real de todos los comprobantes procesados |
| **Idempotencia** | Prevención de duplicados mediante `message_id` único de WhatsApp |
| **Sincronización Histórica** | Procesa hasta 500 mensajes históricos al iniciar el bot |

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              COMPROBANTES BADIE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────────────────┐  │
│  │   WhatsApp   │      │   Node.js    │      │      Python Backend      │  │
│  │    Group     │─────▶│     Bot      │─────▶│                          │  │
│  │              │      │              │      │  ┌────────────────────┐  │  │
│  │ "Transferen- │      │ • Download   │ POST │  │   Flask REST API   │  │  │
│  │  cias Badie" │      │   images     │──────│  └─────────┬──────────┘  │  │
│  │              │      │ • Extract    │      │            │             │  │
│  │  [IMAGE]     │      │   client     │      │            ▼             │  │
│  │  [CODE]      │      │   codes      │      │  ┌────────────────────┐  │  │
│  └──────────────┘      │ • Historical │      │  │   Gemini AI 2.5    │  │  │
│                        │   sync       │      │  │   Flash (Vision)   │  │  │
│                        └──────────────┘      │  └─────────┬──────────┘  │  │
│                                              │            │             │  │
│  ┌──────────────┐                            │            ▼             │  │
│  │  Bank Excel  │      ┌──────────────┐      │  ┌────────────────────┐  │  │
│  │   Export     │─────▶│ Reconcilia-  │◀────▶│  │    PostgreSQL      │  │  │
│  │              │      │    tor       │      │  │    Database        │  │  │
│  │ fecha, cuit, │      │              │      │  │                    │  │  │
│  │ monto        │      │ Match by:    │      │  │ • mensajes         │  │  │
│  └──────────────┘      │ fecha±1 día  │      │  │ • comprobantes     │  │  │
│                        │ cuit exact   │      │  └────────────────────┘  │  │
│                        │ monto±0.01   │      │            │             │  │
│                        └──────────────┘      │            ▼             │  │
│                                              │  ┌────────────────────┐  │  │
│                                              │  │   Web Dashboard    │  │  │
│                                              │  │   (Bootstrap 5)    │  │  │
│                                              │  └────────────────────┘  │  │
│                                              └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stack Tecnológico

**Backend (Python)**
- Flask 3.1 - REST API y servidor web
- SQLAlchemy - ORM para PostgreSQL
- Google Generative AI - Procesamiento de imágenes con Gemini
- Pandas - Manipulación de datos y conciliación bancaria
- Pydantic - Validación de configuración

**Bot (Node.js)**
- whatsapp-web.js - Cliente de WhatsApp Web
- Puppeteer - Automatización de navegador headless
- Axios - Cliente HTTP para comunicación con backend

**Base de Datos**
- PostgreSQL 15+ - Almacenamiento persistente

**Frontend**
- Bootstrap 5 - Dashboard responsive
- Jinja2 - Templates HTML

---

## Instalación

### Prerrequisitos

- Python 3.10+
- Node.js 18+
- PostgreSQL 15+
- Cuenta de Google Cloud con API de Gemini habilitada

### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/comprobantes-badie.git
cd comprobantes-badie
```

### 2. Configurar Variables de Entorno

Crear archivo `.env` en la raíz del proyecto:

```env
# Google Gemini AI
GEMINI_API_KEY=your_gemini_api_key_here

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
DATABASE=comprobantes_db
IP_SERVER=localhost

# Rutas de archivos (opcionales)
BANK_ASSETS_DIR=assets/bank/
BANK_CONFIG_FILE=assets/bank/bank_config.json
```

### 3. Instalar Dependencias

```bash
# Python
pip install -r requirements.txt

# Node.js
cd whatsapp-bot && npm install && cd ..
```

### 4. Inicializar Base de Datos

```bash
# Crear tablas
python main.py init-db
```

### 5. Ejecutar la Aplicación

```bash
# Terminal 1: Backend Python
python visualizador.py

# Terminal 2: Bot de WhatsApp
cd whatsapp-bot && node bot.js
```

En la primera ejecución, escanear el código QR que aparece en terminal para vincular WhatsApp.

---

## Uso

### Interfaz de Línea de Comandos

```bash
# Menú interactivo
python main.py

# Comandos específicos
python main.py init-db                    # Inicializar base de datos
python main.py classify -d /path/images  # Clasificar imágenes por calidad
python main.py extract -d /path/images   # Extraer datos de imágenes
python main.py reconcile -e banco.xlsx   # Conciliar con extracto bancario
```

### Dashboard Web

Acceder a `http://localhost:5000` para visualizar:
- Todos los comprobantes procesados
- Estado de conciliación
- Imágenes originales
- Filtros y búsqueda

### Flujo de Trabajo del Bot

1. Un usuario envía una imagen de comprobante al grupo "Transferencias Badie"
2. Opcionalmente, envía un código de cliente en el mismo mensaje o en el siguiente
3. El bot descarga la imagen y la envía al backend
4. Gemini AI extrae los datos estructurados
5. Los datos se almacenan en PostgreSQL
6. El dashboard se actualiza automáticamente

---

## API Endpoints

### `POST /api/receive-message`

Recibe mensajes del bot de WhatsApp.

**Request Body:**
```json
{
  "id": "whatsapp_message_id",
  "sender": "5491112345678@c.us",
  "author": "5491112345678",
  "body": "Código cliente: 12345",
  "cliente_codigo": "12345",
  "has_media": true,
  "image_path": "assets/wpp-comprobantes/imagen.jpg"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Comprobante procesado y guardado",
  "id": 42,
  "cliente_codigo": "12345"
}
```

### `GET /`

Dashboard web con todos los comprobantes procesados.

---

## Configuración

### Configuración del Bot (`whatsapp-bot/bot.js`)

| Variable | Valor por Defecto | Descripción |
|----------|-------------------|-------------|
| `TARGET_GROUP_NAME` | "Transferencias Badie" | Nombre del grupo a monitorear |
| `HISTORY_LIMIT` | 500 | Mensajes históricos a sincronizar |
| `NEXT_MESSAGE_TIMEOUT` | 60000 | Tiempo de espera para código (ms) |
| `DEBUG_MODE` | false | Habilitar logs detallados |

### Configuración de Conciliación (`assets/bank/bank_config.json`)

```json
{
  "default_name": "extracto_banco.xls",
  "excel_options": {
    "sheet_name": "Movimientos",
    "header_row": 0
  },
  "column_mapping": {
    "fecha": "Fecha",
    "cuit": "CUIT Ordenante",
    "monto": "Importe"
  },
  "tolerances": {
    "fecha_dias": 1,
    "monto_diferencia": 0.01
  }
}
```

---

## Estructura del Proyecto

```
comprobantes-badie/
├── src/
│   ├── config.py              # Configuración y variables de entorno
│   ├── data_models.py         # Modelos SQLAlchemy (Mensaje, Comprobante)
│   ├── database.py            # Conexión a PostgreSQL
│   ├── gemini_processor.py    # Integración con Google Gemini AI
│   ├── reconciliator.py       # Módulo de conciliación bancaria
│   ├── logger.py              # Sistema de logging centralizado
│   └── ...
├── whatsapp-bot/
│   ├── bot.js                 # Cliente de WhatsApp
│   └── package.json
├── assets/
│   ├── wpp-comprobantes/      # Imágenes descargadas de WhatsApp
│   └── bank/                  # Archivos Excel del banco
├── templates/
│   └── index.html             # Dashboard web
├── logs/                      # Archivos de log
├── main.py                    # CLI principal
├── visualizador.py            # Servidor Flask
├── requirements.txt           # Dependencias Python
└── README.md
```

---

## Modelo de Datos

### Tabla `mensajes`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | INTEGER | Primary key |
| `message_id` | VARCHAR | ID único de WhatsApp (índice único) |
| `timestamp` | DATETIME | Fecha/hora del mensaje |
| `sender` | VARCHAR | Número del grupo |
| `author` | VARCHAR | Número del autor real |
| `body` | TEXT | Contenido del mensaje |

### Tabla `comprobantes`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | INTEGER | Primary key |
| `mensaje_id` | INTEGER | FK a mensajes |
| `banco` | VARCHAR | Nombre del banco/billetera |
| `monto` | VARCHAR | Monto de la transferencia |
| `fecha_transferencia` | VARCHAR | Fecha de la operación |
| `id_transferencia` | VARCHAR | Código de operación |
| `remitente_nombre` | VARCHAR | Nombre del ordenante |
| `remitente_id` | VARCHAR | CUIT/CUIL del ordenante |
| `destinatario_nombre` | VARCHAR | Nombre del beneficiario |
| `destinatario_id` | VARCHAR | CUIT/CUIL del beneficiario |
| `cliente_codigo` | VARCHAR | Código interno del cliente |
| `conciliado` | BOOLEAN | Estado de conciliación |
| `fecha_conciliacion` | DATETIME | Fecha de conciliación |

---

## Testing

```bash
# Ejecutar tests unitarios
pytest

# Ejecutar tests de integración (requiere API key)
pytest -m integration

# Coverage report
pytest --cov=src --cov-report=html
```

---

## Roadmap

- [ ] Soporte para múltiples grupos de WhatsApp
- [ ] Exportación a formatos contables (CSV, XLSX)
- [ ] Dashboard con métricas y gráficos
- [ ] Notificaciones de errores vía Telegram/Email
- [ ] API REST completa con autenticación
- [ ] Dockerización del proyecto

---

## Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el repositorio
2. Crear una rama para tu feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit de los cambios (`git commit -m 'Add: nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Abrir un Pull Request

---

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

---

## Contacto

**Nahuel** - [GitHub](https://github.com/tu-usuario)

---

<div align="center">

Desarrollado con Python, Node.js y Google Gemini AI

</div>
