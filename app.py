"""
app.py — Carga de Ajustes CFE - Telcel
Flask app: lógica de negocio + rutas.
Todo lo de HANA vive en db.py.
Soporta entorno local (.env) y SAP BTP Cloud Foundry (VCAP_SERVICES).
"""

import logging
import os

import pandas as pd
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, session

import db

# ── Cargar .env solo en local (CF lo ignora) ────────────────────────────────
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ajustes-cfe-local-dev-secret")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Endpoint del hub TLCL (notificación final de ejecución) ─────────────────
# HUB_NOTIFY_URL  = os.environ.get("HubNotifyUrl", "http://localhost:5000/tlcl-hub/tlcl12")
HUB_NOTIFY_URL  = os.environ.get("HubNotifyUrl", "https://tlcl-processes-hub.cfapps.us10.hana.ondemand.com/tlcl-hub/tlcl12")
HUB_NOTIFY_USER = "BASE_AJUSTES_USER"


# ════════════════════════════════════════════════════════════════════════════
# MAPEO DE COLUMNAS EXCEL → ENTIDAD CDS TempBillingAdjustmentBase
# ════════════════════════════════════════════════════════════════════════════

COLUMN_MAP = {
    "DIVISION CFE":                          "DIVISION",
    "DIVISION":                              "DIVISION",
    "RPU":                                   "RPU",
    "SITIO":                                 "NAME",
    "NOMBRE SITIO":                          "NAME",
    "NAME":                                  "NAME",
    "ID":                                    "EXTERNALID",
    "ID SITIO":                              "EXTERNALID",
    "EXTERNALID":                            "EXTERNALID",
    "REGION":                                "REGION",
    "PROYECTO":                              "SITETYPE",
    "TIPO SITIO":                            "SITETYPE",
    "SITETYPE":                              "SITETYPE",
    "TARIFA":                                "FARE",
    "FARE":                                  "FARE",
    "DESDE":                                 "FROMDATE",
    "PERIODO DESDE":                         "FROMDATE",
    "FROMDATE":                              "FROMDATE",
    "HASTA":                                 "TODATE",
    "PERIODO HASTA":                         "TODATE",
    "TODATE":                                "TODATE",
    "KWH DE AJUSTE":                         "KWHADJUSTMENT",
    "AJUSTE DE CONSUMO":                     "KWHADJUSTMENT",
    "KWHADJUSTMENT":                         "KWHADJUSTMENT",
    "MONTO DE AJUSTE":                       "ADJUSTMENTAMOUNT",
    "AJUSTE DE IMPORTE":                     "ADJUSTMENTAMOUNT",
    "ADJUSTMENTAMOUNT":                      "ADJUSTMENTAMOUNT",
    "FECHA RECEPCION CORPORATIVO":           "CORPORATERECEPTIONDATE",
    "FECHA DE RECEPCION CORPORATIVA":        "CORPORATERECEPTIONDATE",
    "CORPORATERECEPTIONDATE":                "CORPORATERECEPTIONDATE",
    "CARGADO A COBCEN":                      "LOADEDTOCOBCEN",
    "IS CARGA A COBCEN":                     "LOADEDTOCOBCEN",
    "LOADEDTOCOBCEN":                        "LOADEDTOCOBCEN",
    "SE ENVIO A":                            "SENDTO",
    "ENVIADO A":                             "SENDTO",
    "SENDTO":                                "SENDTO",
    "NOTIFICACION CFE":                      "CFENOTIFICATION",
    "CFENOTIFICATION":                       "CFENOTIFICATION",
    "ESTATUS DEL SERVICIO":                  "STATUS",
    "ESTATUS":                               "STATUS",
    "STATUS":                                "STATUS",
    "PORTEO":                                "ELECTRICWHEELING",
    "PORTEO ELECTRICO":                      "ELECTRICWHEELING",
    "ELECTRICWHEELING":                      "ELECTRICWHEELING",
    "COMENTARIOS":                           "COMMENTS",
    "COMMENTS":                              "COMMENTS",
    "COMENTARIO 2":                          "COMMENTS2",
    "COMENTARIOS 2":                         "COMMENTS2",
    "COMMENTS2":                             "COMMENTS2",
    "CARGA CONECTADA ANTES DE LA MEDICION":  "PREMETERLOAD",
    "PREMETERLOAD":                          "PREMETERLOAD",
}

# Columnas en el orden de la entidad CDS (YEAR al final)
DB_COLUMNS = [
    "DIVISION",
    "RPU",
    "NAME",
    "EXTERNALID",
    "REGION",
    "SITETYPE",
    "FARE",
    "FROMDATE",
    "TODATE",
    "KWHADJUSTMENT",
    "ADJUSTMENTAMOUNT",
    "CORPORATERECEPTIONDATE",
    "LOADEDTOCOBCEN",
    "SENDTO",
    "CFENOTIFICATION",
    "STATUS",
    "ELECTRICWHEELING",
    "COMMENTS",
    "COMMENTS2",
    "PREMETERLOAD",
    "YEAR",
]

DATE_COLUMNS    = ["FROMDATE", "TODATE", "CORPORATERECEPTIONDATE"]
DECIMAL_COLUMNS = ["KWHADJUSTMENT", "ADJUSTMENTAMOUNT"]
LONG_STRING_COLS = {
    "SENDTO":         5000,
    "LOADEDTOCOBCEN": 500,
    "COMMENTS":       2000,
    "COMMENTS2":      2000,
}


# ════════════════════════════════════════════════════════════════════════════
# LÓGICA DE NEGOCIO — LECTURA Y TRANSFORMACIÓN DE EXCEL
# ════════════════════════════════════════════════════════════════════════════

def leer_pestanas(file_obj) -> list[str]:
    """Devuelve lista de nombres de hojas del Excel."""
    import openpyxl
    wb = openpyxl.load_workbook(file_obj, read_only=True)
    nombres = wb.sheetnames
    wb.close()
    return nombres


def leer_hoja(file_obj, sheet_name: str, preview_rows: int = 50) -> dict:
    """
    Lee una hoja del Excel:
      - Fila 1 (SUBTOTAL / fórmulas) → se salta
      - Fila 2 → encabezados reales
      - Fila 3+ → datos

    Devuelve dict con columns, rows (preview) y total.
    """
    df = pd.read_excel(file_obj, sheet_name=sheet_name, header=1, dtype=str)

    df = df[[c for c in df.columns
             if str(c) != "None" and not str(c).startswith("Unnamed")]]
    df = df.dropna(how="all")

    total   = len(df)
    preview = df.head(preview_rows).where(pd.notnull(df.head(preview_rows)), None)

    return {
        "columns": list(df.columns),
        "rows":    preview.values.tolist(),
        "total":   total,
    }


def preparar_dataframe(file_obj, sheet_name: str, year: str) -> tuple[pd.DataFrame, list[dict]]:
    """
    Lee la hoja completa y devuelve (df_limpio, duplicados_internos).

    df_limpio         — DataFrame listo para insertar, sin duplicados internos.
    duplicados_internos — filas que tenían RPU+FROMDATE+TODATE repetida dentro
                          del mismo archivo (se conserva la primera ocurrencia).

    Transformaciones aplicadas:
      - Mapeo de columnas Excel → nombres canónicos CDS
      - RPU normalizado: strip + upper (elimina espacios y mayúsculas inconsistentes)
      - Fechas → string YYYY-MM-DD (elimina diferencias de formato como origen del dup)
      - Decimales → float
      - YEAR → string (viene del selector del frontend)
    """
    df = pd.read_excel(file_obj, sheet_name=sheet_name, header=1)

    # Limpiar columnas sin nombre
    df = df[[c for c in df.columns
             if str(c) != "None" and not str(c).startswith("Unnamed")]]
    df = df.dropna(how="all")

    # Mapear nombres de columna
    rename = {}
    for col in df.columns:
        key = str(col).strip().upper()
        if key in COLUMN_MAP:
            rename[col] = COLUMN_MAP[key]
    df = df.rename(columns=rename)

    # Año desde el selector del frontend
    df["YEAR"] = str(year)

    # Asegurar que existan todas las columnas destino
    for db_col in DB_COLUMNS:
        if db_col not in df.columns:
            df[db_col] = None

    # ── Normalizar RPU antes de comparar (strip + upper) ────────────────
    # Espacios invisibles o mayúsculas distintas generan falsos únicos en HANA.
    if "RPU" in df.columns:
        df["RPU"] = df["RPU"].apply(
            lambda x: str(x).strip().upper() if x is not None and str(x) != "nan" else None
        )

    # ── Fechas → string YYYY-MM-DD ───────────────────────────────────────
    # Hacerlo ANTES de deduplicar para que "01/01/2024" y "2024-01-01"
    # queden iguales y se detecten como duplicado correctamente.
    for date_col in DATE_COLUMNS:
        if date_col in df.columns:
            parsed = pd.to_datetime(df[date_col], errors="coerce")
            df[date_col] = parsed.apply(
                lambda d: d.strftime("%Y-%m-%d") if pd.notnull(d) else None
            )

    # ── Detectar duplicados internos (RPU + FROMDATE + TODATE) ──────────
    KEYS = ["RPU", "FROMDATE", "TODATE"]
    mascara_dup = df.duplicated(subset=KEYS, keep="first")
    df_dups     = df[mascara_dup].copy()
    df_clean    = df[~mascara_dup].copy()

    duplicados_internos = []
    for _, row in df_dups.iterrows():
        duplicados_internos.append({
            "RPU":      row.get("RPU"),
            "FROMDATE": row.get("FROMDATE"),
            "TODATE":   row.get("TODATE"),
            "DIVISION": row.get("DIVISION"),
            "NAME":     row.get("NAME"),
            "motivo":   "Duplicado en archivo",
            "detalle":  "RPU+FROMDATE+TODATE repetido dentro del mismo Excel (se conservó la primera ocurrencia)",
        })

    if duplicados_internos:
        log.warning(
            f"{len(duplicados_internos)} filas duplicadas encontradas en el Excel "
            f"(misma clave RPU+FROMDATE+TODATE). Se omitirán de la inserción."
        )

    # ── Decimales ────────────────────────────────────────────────────────
    for dec_col in DECIMAL_COLUMNS:
        if dec_col in df_clean.columns:
            df_clean[dec_col] = pd.to_numeric(df_clean[dec_col], errors="coerce")

    # ── Truncar strings largos ───────────────────────────────────────────
    for col, max_len in LONG_STRING_COLS.items():
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].apply(
                lambda x: str(x)[:max_len]
                if x is not None and str(x) != "nan" else None
            )

    # ── NaN → None ───────────────────────────────────────────────────────
    df_clean = df_clean.where(df_clean.notna(), None)
    df_clean = df_clean.replace("nan", None)

    return df_clean[DB_COLUMNS], duplicados_internos


# ════════════════════════════════════════════════════════════════════════════
# RUTAS FLASK
# ════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/pestanas", methods=["POST"])
def api_pestanas():
    """Recibe el archivo y devuelve la lista de pestañas."""
    if "file" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo."}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
        return jsonify({"error": "El archivo debe ser .xlsx, .xlsm o .xls"}), 400

    try:
        pestanas = leer_pestanas(f.stream)
        session["filename"] = f.filename
        return jsonify({"pestanas": pestanas})
    except Exception as e:
        log.exception("Error leyendo pestañas")
        return jsonify({"error": str(e)}), 500


@app.route("/api/preview", methods=["POST"])
def api_preview():
    """Recibe archivo + hoja → devuelve preview (primeras 50 filas)."""
    if "file" not in request.files:
        return jsonify({"error": "No se recibió el archivo."}), 400

    f     = request.files["file"]
    sheet = request.form.get("sheet", "").strip()
    if not sheet:
        return jsonify({"error": "Debes seleccionar una pestaña."}), 400

    try:
        data = leer_hoja(f.stream, sheet_name=sheet)
        return jsonify(data)
    except Exception as e:
        log.exception("Error generando preview")
        return jsonify({"error": str(e)}), 500


@app.route("/api/cargar", methods=["POST"])
def api_cargar():
    """
    Carga completa a HANA:
      1. Trunca la tabla.
      2. Prepara el DataFrame desde el Excel.
      3. Inserta por batches; si un batch falla, reintenta fila por fila.
      4. Devuelve el resumen AL FRONTEND, junto con executionId/rowsRead,
         para que el frontend dispare la notificación al hub por separado
         una vez que ya pintó el resumen en pantalla.
    """
    if "file" not in request.files:
        return jsonify({"error": "No se recibió el archivo."}), 400

    f     = request.files["file"]
    sheet = request.form.get("sheet", "").strip()
    year  = request.form.get("year", "").strip()

    if not sheet:
        return jsonify({"error": "Debes seleccionar una pestaña."}), 400
    if not year or not year.isdigit():
        return jsonify({"error": "Debes seleccionar un año válido."}), 400

    try:
        tabla_full = db.get_table_name()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    try:
        df, dups_internos = preparar_dataframe(f.stream, sheet, year)
    except Exception as e:
        log.exception("Error preparando DataFrame")
        return jsonify({"error": f"Error leyendo Excel: {e}"}), 500

    if len(df) == 0 and not dups_internos:
        return jsonify({"error": "La hoja no contiene datos para cargar."}), 400

    # Total de filas leídas del archivo, sin importar si están mal o duplicadas
    rows_read = len(df) + len(dups_internos)

    # ID de ejecución — uno solo por corrida, se reenvía luego al hub
    try:
        execution_id = db.get_sysuuid()
    except Exception as e:
        log.exception("Error generando execution_id (SYSUUID)")
        return jsonify({"error": f"Error generando ID de ejecución: {e}"}), 500

    if len(df) == 0:
        # Todo el archivo eran duplicados internos — nada que insertar
        return jsonify({
            "ok":          True,
            "mensaje":     f"No se insertó ningún registro: las {len(dups_internos)} filas del archivo son duplicadas entre sí.",
            "insertados":  0,
            "nErrores":    len(dups_internos),
            "tabla":       tabla_full,
            "anio":        year,
            "errores":     dups_internos[:100],
            "executionId": execution_id,
            "rowsRead":    rows_read,
        })

    try:
        conn = db.get_hana_connection()
        db.truncar_tabla(conn, tabla_full)
        resultado = db.insertar_dataframe(conn, tabla_full, df, DB_COLUMNS)
        conn.close()
    except Exception as e:
        log.exception("Error en operación HANA")
        return jsonify({"error": str(e)}), 500

    insertados  = resultado["insertados"]
    errores_bd  = resultado["filas_error"]

    todos_errores = errores_bd + dups_internos
    n_errores     = len(todos_errores)

    if insertados == 0 and n_errores > 0:
        # No hubo resumen exitoso que mostrar → no se notifica al hub aquí
        return jsonify({
            "error": (
                f"No se pudo insertar ningún registro. "
                f"{n_errores} filas con error o duplicadas. "
                f"Revisa el detalle a continuación."
            ),
            "errores": todos_errores[:50],
        }), 500

    partes = [f"{insertados} registros cargados correctamente"]
    if errores_bd:
        partes.append(f"{len(errores_bd)} con error de inserción en BD")
    if dups_internos:
        partes.append(f"{len(dups_internos)} duplicados omitidos del archivo fuente")
    mensaje = ". ".join(partes) + "."
    log.info(mensaje)

    return jsonify({
        "ok":          True,
        "mensaje":     mensaje,
        "insertados":  insertados,
        "nErrores":    n_errores,
        "nErroresBD":  len(errores_bd),
        "nDupsExcel":  len(dups_internos),
        "tabla":       tabla_full,
        "anio":        year,
        "errores":     todos_errores[:100],
        "executionId": execution_id,
        "rowsRead":    rows_read,
    })


@app.route("/api/notificar-hub", methods=["POST"])
def api_notificar_hub():
    """
    Se llama DESPUÉS de que el usuario ya vio el resumen de la carga.
    Reporta al hub TLCL (tlcl12) filas leídas / insertadas en INIT y
    devuelve al frontend solo lo necesario para informar al usuario:
    si el proceso terminó bien y el mensaje final del hub.
    """
    data = request.get_json(silent=True) or {}
    execution_id  = data.get("executionId")
    rows_read     = data.get("rowsRead")
    rows_inserted = data.get("rowsInserted")

    if not execution_id or rows_read is None or rows_inserted is None:
        return jsonify({
            "ok":      False,
            "message": "Datos incompletos para notificar al hub (executionId, rowsRead, rowsInserted).",
        }), 400

    payload = {
        "p_rows_read":          rows_read,
        "p_rows_inserted_init": rows_inserted,
        "p_execution_id_in":    execution_id,
        "p_user":               HUB_NOTIFY_USER,
    }

    try:
        resp = requests.post(HUB_NOTIFY_URL, json=payload, timeout=30)
        resp.raise_for_status()
        hub_data = resp.json()
    except Exception as e:
        log.error(f"Error notificando al hub ({HUB_NOTIFY_URL}) con payload {payload}: {e}")
        return jsonify({
            "ok": False,
            "message": (
                "No se pudo confirmar el proceso final con el hub TLCL. "
                "Los datos ya fueron cargados en HANA, pero no se pudo verificar "
                "el paso INIT → BILLINGADJUSTMENTBASE."
            ),
        }), 502

    success = bool(hub_data.get("success"))
    message = hub_data.get("message") or "El hub no devolvió un mensaje."

    log.info(f"Respuesta del hub: success={success} message={message}")

    return jsonify({
        "ok":      success,
        "message": message,
    })

# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)