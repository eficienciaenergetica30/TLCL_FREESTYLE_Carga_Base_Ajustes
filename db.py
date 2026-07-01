"""
db.py — Capa de acceso a datos SAP HANA
Maneja: conexión, nombre de tabla, truncate, insert por batches con fallback fila por fila.
Sin lógica de negocio ni transformación de datos.
"""

import json
import logging
import os

import pandas as pd

log = logging.getLogger(__name__)

# ── Tamaño de lote para inserciones ─────────────────────────────────────────
BATCH_SIZE = 100


# ════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN — VCAP_SERVICES (Cloud Foundry) o .env local
# ════════════════════════════════════════════════════════════════════════════


def get_table_name() -> str:
    """
    Lee el nombre completo de la tabla destino.
    Prioridad:
      1. Variable de entorno BillingAdjustmentTable (en .env local o CF env vars)
      2. Credenciales dentro de VCAP_SERVICES (user-provided-service)
    """
    tabla = os.environ.get("BillingAdjustmentTable")
    if tabla:
        return tabla.strip()

    vcap_raw = os.environ.get("VCAP_SERVICES")
    if vcap_raw:
        vcap = json.loads(vcap_raw)
        for _, bindings in vcap.items():
            for binding in bindings:
                creds = binding.get("credentials", {})
                if "BillingAdjustmentTable" in creds:
                    return creds["BillingAdjustmentTable"].strip()

    raise RuntimeError(
        "No se encontró BillingAdjustmentTable en el entorno. "
        "Verifica tu .env o las variables de la app en CF."
    )


def get_hana_connection():
    """
    Devuelve una conexión hdbcli activa.
    Prioridad:
      1. VCAP_SERVICES (Cloud Foundry / SAP BTP)
      2. Variables de entorno locales (.env)
    """
    try:
        from hdbcli import dbapi
    except ImportError:
        raise RuntimeError("hdbcli no está instalado. Ejecuta: pip install hdbcli")

    vcap_raw = os.environ.get("VCAP_SERVICES")
    if vcap_raw:
        log.info("Detectado VCAP_SERVICES — usando credenciales de CF")
        vcap = json.loads(vcap_raw)

        hana_creds = None
        for service_name, bindings in vcap.items():
            if "hana" in service_name.lower():
                hana_creds = bindings[0]["credentials"]
                break

        if not hana_creds:
            raise RuntimeError(
                "No se encontró un servicio HANA en VCAP_SERVICES. "
                "Verifica el binding en SAP BTP."
            )

        host = hana_creds.get("host")
        port = int(hana_creds.get("port", 443))
        user = hana_creds.get("user")
        password = hana_creds.get("password")
        schema = hana_creds.get("schema", "")
    else:
        log.info("Usando credenciales locales (.env)")
        host = os.environ.get("HANA_HOST")
        port = int(os.environ.get("HANA_PORT", 443))
        user = os.environ.get("HANA_USER")
        password = os.environ.get("HANA_PASSWORD")
        schema = os.environ.get("HANA_SCHEMA", "")

        if not all([host, user, password]):
            raise RuntimeError(
                "Faltan variables HANA_HOST / HANA_USER / HANA_PASSWORD en .env"
            )

    conn = dbapi.connect(
        address=host,
        port=port,
        user=user,
        password=password,
        encrypt=True,
        sslValidateCertificate=False,
        currentSchema=schema if schema else None,
    )
    log.info(f"Conexión HANA establecida → {host}:{port}")
    return conn


# ════════════════════════════════════════════════════════════════════════════
# OPERACIONES DE TABLA
# ════════════════════════════════════════════════════════════════════════════


def truncar_tabla(conn, tabla_full: str) -> None:
    """
    Vacía la tabla antes de cada carga para evitar rezagos de cargas anteriores.
    Usa TRUNCATE (más rápido que DELETE y no genera undo log masivo en HANA).
    """
    cursor = conn.cursor()
    try:
        log.info(f"Truncando tabla {tabla_full} …")
        cursor.execute(f"TRUNCATE TABLE {tabla_full}")
        conn.commit()
        log.info("Tabla truncada correctamente.")
    except Exception as e:
        conn.rollback()
        log.error(f"Error al truncar tabla: {e}")
        raise
    finally:
        cursor.close()


# ════════════════════════════════════════════════════════════════════════════
# INSERT CON FALLBACK FILA A FILA
# ════════════════════════════════════════════════════════════════════════════


def insertar_dataframe(
    conn,
    tabla_full: str,
    df: pd.DataFrame,
    db_columns: list[str],
) -> dict:
    """
    Inserta usando executemany por batch.

    Cuando executemany falla, hdbcli puede haber insertado parte del batch
    antes de lanzar la excepción. El fallback fila por fila detecta esto:
    si una fila da unique violation pero su clave solo aparece una vez en
    el DataFrame, significa que ya fue insertada por el driver → se cuenta
    como éxito en lugar de reportarla como duplicado falso.
    """
    col_str = ", ".join([f'"{c}"' for c in db_columns])
    placeholders = ", ".join(["?" for _ in db_columns])
    sql_insert = f"INSERT INTO {tabla_full} ({col_str}) " f"VALUES ({placeholders})"

    rows_all = [_row_to_tuple(row, db_columns) for _, row in df.iterrows()]
    df_reset = df.reset_index(drop=True)

    # Contar cuántas veces aparece cada clave RPU+FROMDATE+TODATE en el df
    # Para detectar si un unique violation es falso (ya insertado por driver)
    # o real (duplicado genuino dentro del mismo archivo)
    from collections import Counter

    clave_counts = Counter(
        (str(r.get("RPU")), str(r.get("FROMDATE")), str(r.get("TODATE")))
        for _, r in df_reset.iterrows()
    )

    total_insertado = 0
    filas_con_error: list[dict] = []

    cursor = conn.cursor()
    try:
        for batch_num, i in enumerate(range(0, len(rows_all), BATCH_SIZE), start=1):
            batch = rows_all[i : i + BATCH_SIZE]
            batch_df_slice = df_reset.iloc[i : i + BATCH_SIZE]

            try:
                cursor.executemany(sql_insert, batch)
                conn.commit()
                total_insertado += len(batch)
                log.info(f"Batch {batch_num}: {len(batch)} filas OK.")

            except Exception as batch_err:
                conn.rollback()
                log.warning(
                    f"Batch {batch_num} falló ({batch_err}). "
                    "Reintentando fila por fila…"
                )

                claves_insertadas_en_fallback: set[tuple] = set()

                for row_tuple, (_, df_row) in zip(batch, batch_df_slice.iterrows()):
                    clave = (
                        str(df_row.get("RPU")),
                        str(df_row.get("FROMDATE")),
                        str(df_row.get("TODATE")),
                    )
                    try:
                        cursor.execute(sql_insert, row_tuple)
                        conn.commit()
                        total_insertado += 1
                        claves_insertadas_en_fallback.add(clave)

                    except Exception as row_err:
                        conn.rollback()
                        motivo_raw = str(row_err)

                        # ── Detectar unique violation ────────────────────
                        es_unique = (
                            "unique constraint" in motivo_raw.lower()
                            or "duplicate key" in motivo_raw.lower()
                        )

                        if es_unique:
                            # ¿La clave aparece solo una vez en todo el df?
                            # → El driver ya la insertó antes de fallar el batch
                            if clave_counts[clave] <= 1:
                                total_insertado += 1
                                log.debug(
                                    f"  Fila RPU={df_row.get('RPU')} → "
                                    "unique violation pero clave única en df: "
                                    "asumida como ya insertada por el driver."
                                )
                                continue

                            # ¿Ya la insertamos nosotros en este mismo fallback?
                            if clave in claves_insertadas_en_fallback:
                                total_insertado += 1
                                log.debug(
                                    f"  Fila RPU={df_row.get('RPU')} → "
                                    "ya insertada en este fallback."
                                )
                                continue

                        # Error genuino
                        filas_con_error.append(
                            {
                                "RPU": df_row.get("RPU"),
                                "FROMDATE": df_row.get("FROMDATE"),
                                "TODATE": df_row.get("TODATE"),
                                "DIVISION": df_row.get("DIVISION"),
                                "NAME": df_row.get("NAME"),
                                "motivo": _clasificar_error(motivo_raw),
                                "detalle": motivo_raw,
                            }
                        )
                        log.debug(f"  Fila RPU={df_row.get('RPU')} → {motivo_raw}")
    finally:
        cursor.close()

    return {
        "insertados": total_insertado,
        "filas_error": filas_con_error,
    }


# ════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ════════════════════════════════════════════════════════════════════════════


def _row_to_tuple(row, db_columns: list[str]) -> tuple:
    """Convierte una fila del DataFrame a tupla para executemany / execute."""
    values = []
    for col in db_columns:
        val = row.get(col)
        if val is None:
            values.append(None)
        elif isinstance(val, float) and pd.isna(val):
            values.append(None)
        else:
            values.append(val)
    return tuple(values)


def _clasificar_error(mensaje: str) -> str:
    """
    Devuelve una etiqueta legible según el tipo de error de HANA.
    Se extiende fácilmente agregando más casos.
    """
    msg = mensaje.upper()
    if "UNIQUE CONSTRAINT" in msg or "DUPLICATE KEY" in msg:
        return "Duplicado"
    if "NOT NULL" in msg or "CANNOT BE NULL" in msg:
        return "Campo requerido nulo"
    if "DATA TYPE" in msg or "CONVERSION" in msg:
        return "Tipo de dato inválido"
    if "LENGTH" in msg or "TOO LARGE" in msg:
        return "Valor demasiado largo"
    return "Error de inserción"


def get_sysuuid():
    """
    Genera un UUID único consultando SYSUUID de HANA.
    Retorna el UUID como string.
    """
    conn = get_hana_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT SYSUUID FROM DUMMY")
        row = cursor.fetchone()
        cursor.close()
        val = row[0]
        if isinstance(val, (bytes, bytearray, memoryview)):
            return bytes(val).hex().upper()
        return str(val).replace("-", "").upper()
    finally:
        conn.close()