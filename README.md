# Carga de Ajustes CFE — Telcel

App Flask para cargar el archivo `BASE_AJUSTES_CFE_TELCEL.xlsx` (múltiples pestañas por año) a SAP HANA Cloud.

---

## Estructura del proyecto

```
carga_ajustes_cfe/
├── app.py               ← App principal Flask
├── requirements.txt
├── runtime.txt          ← Python 3.11 para CF buildpack
├── manifest.yml         ← Deployment SAP BTP Cloud Foundry
├── .env.example         ← Plantilla de variables de entorno locales
├── templates/
│   └── index.html
└── static/
    ├── css/style.css
    └── js/app.js
```

---

## Instalación local

```bash
# 1. Crear entorno virtual
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar credenciales
cp .env.example .env
# Edita .env con tus datos HANA

# 4. Correr en desarrollo
python app.py
# o
flask run
```

La app queda en http://localhost:5000

---

## Flujo de uso

1. **Seleccionar archivo** — sube o arrastra el `.xlsx`
2. **Elegir pestaña** — detecta automáticamente todas las hojas (ej. AJUSTES 2026, AJUSTES 2025…)
3. **Vista previa** — muestra las primeras 50 filas con todos los campos
4. **Cargar a HANA** — configura tabla, schema y modo de inserción, luego ejecuta

### Modos de inserción
- **INSERT** — agrega registros sin tocar los existentes
- **DELETE + INSERT** — borra registros del mismo año antes de insertar (idempotente)

---

## Conexión a HANA

### Local (`.env`)
```
HANA_HOST=xxxxx.hanacloud.ondemand.com
HANA_PORT=443
HANA_USER=DBADMIN
HANA_PASSWORD=Tu.Password.Con Puntos y Espacios
HANA_SCHEMA=MI_SCHEMA
```

Las credenciales con caracteres especiales (puntos, espacios, @) se pasan directamente a `hdbcli.dbapi.connect()` — **no requieren URL-encoding**.

### SAP BTP Cloud Foundry (VCAP_SERVICES)
La app detecta automáticamente `VCAP_SERVICES`. Solo necesitas hacer el binding del servicio HANA en el `manifest.yml`:

```yaml
services:
  - nombre-de-tu-servicio-hana
```

---

## Tabla HANA creada automáticamente

La tabla se crea al primer `INSERT` si no existe:

| Columna | Tipo |
|---|---|
| ID | BIGINT (identity PK) |
| DIVISION_CFE | NVARCHAR(200) |
| RPU | NVARCHAR(100) |
| SITIO | NVARCHAR(200) |
| ID_SITIO | NVARCHAR(100) |
| REGION | NVARCHAR(100) |
| PROYECTO | NVARCHAR(100) |
| TARIFA | NVARCHAR(50) |
| PERIODO_DESDE | DATE |
| PERIODO_HASTA | DATE |
| KWH_AJUSTE | DECIMAL(18,2) |
| MONTO_AJUSTE | DECIMAL(18,2) |
| FECHA_RECEPCION | DATE |
| CARGADO_COBCEN | NVARCHAR(500) |
| SE_ENVIO_A | NVARCHAR(5000) |
| NOTIFICACION_CFE | NVARCHAR(200) |
| ESTATUS_SERVICIO | NVARCHAR(200) |
| PORTEO | NVARCHAR(200) |
| COMENTARIOS | NVARCHAR(2000) |
| COMENTARIO2 | NVARCHAR(2000) |
| CARGA_CONECTADA | NVARCHAR(500) |
| ANIO_AJUSTE | INTEGER |
| FECHA_CARGA | TIMESTAMP (default now) |

---

## Deploy a SAP BTP Cloud Foundry

```bash
cf login -a https://api.cf.<región>.hana.ondemand.com
cf push
# o
cf push -f manifest.yml
```

Configura el secret key seguro:
```bash
cf set-env carga-ajustes-cfe FLASK_SECRET_KEY "tu-secreto-seguro"
cf restage carga-ajustes-cfe
```
