"""
query_llm.py — Motor de consultas SAC potenciado con LLM + SQL
================================================================
Flujo:
  1. Carga DataFrames en DuckDB (base de datos en memoria)
  2. Envía la pregunta + esquema de tablas a Claude API
  3. Claude genera una consulta SQL
  4. Se ejecuta la SQL sobre DuckDB → resultados
  5. Claude redacta párrafos profesionales con los resultados
  6. Devuelve texto listo para comunicar

Requiere:
  - ANTHROPIC_API_KEY en variables de entorno
  - pip install anthropic duckdb
"""

import os
import re
import json
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS_SQL = 1024
MAX_TOKENS_PROSE = 2048


def _get_client():
    """Obtiene el cliente de Anthropic."""
    api_key = None
    try:
        import streamlit as st
        api_key = st.secrets.get("anthropic", {}).get("api_key", "")
    except Exception:
        pass
    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError(
            "API key de Anthropic no configurada. "
            "Agregue ANTHROPIC_API_KEY en las variables de entorno."
        )
    from anthropic import Anthropic
    return Anthropic(api_key=api_key)


# ═══════════════════════════════════════════════════════════════════
# CARGA DE DATOS EN DUCKDB
# ═══════════════════════════════════════════════════════════════════

def _load_to_duckdb(datos):
    """
    Carga los DataFrames del procesador en una BD DuckDB en memoria.
    Retorna la conexión y el esquema de tablas.
    """
    conn = duckdb.connect(":memory:")

    midagri = datos["midagri"].copy()
    materia = datos["materia"].copy()

    # Asignar empresa desde materia
    depto_empresa = {}
    if "EMPRESA_ASEGURADORA" in materia.columns and "DEPARTAMENTO" in materia.columns:
        for _, row in materia.iterrows():
            d = str(row["DEPARTAMENTO"]).strip().upper()
            e = str(row["EMPRESA_ASEGURADORA"]).strip().upper()
            depto_empresa[d] = e

    if "DEPARTAMENTO" in midagri.columns:
        midagri["EMPRESA"] = midagri["DEPARTAMENTO"].map(depto_empresa).fillna("OTROS")
        def _norm(e):
            eu = str(e).upper()
            if "POSITIVA" in eu:
                return "LA POSITIVA"
            elif "RIMAC" in eu or "RÍMAC" in eu:
                return "RIMAC"
            return eu
        midagri["EMPRESA"] = midagri["EMPRESA"].apply(_norm)

    # Convertir columnas de fecha a datetime para que DuckDB las maneje nativamente
    date_cols = ["FECHA_AVISO", "FECHA_SINIESTRO", "FECHA_ATENCION",
                 "FECHA_DESEMBOLSO", "FECHA_SIEMBRA", "FECHA_COSECHA",
                 "FECHA_ENVIO_DRAS", "FECHA_VALIDACION"]
    for col in date_cols:
        if col in midagri.columns:
            midagri[col] = pd.to_datetime(midagri[col], errors="coerce", dayfirst=True)

    # Registrar DataFrames como tablas
    conn.register("avisos", midagri)
    conn.register("materia_asegurada", materia)

    # Generar esquema legible
    schema = _generate_schema(conn)

    return conn, schema


def _generate_schema(conn):
    """Genera descripción del esquema de tablas para el prompt."""
    schema_parts = []

    for table in ["avisos", "materia_asegurada"]:
        try:
            info = conn.execute(f"DESCRIBE {table}").fetchall()
            cols = []
            for row in info:
                col_name = row[0]
                col_type = row[1]
                cols.append(f"    {col_name} ({col_type})")

            # Obtener sample
            sample = conn.execute(f"SELECT * FROM {table} LIMIT 3").fetchdf()
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

            schema_parts.append(
                f"Tabla: {table} ({count:,} filas)\n"
                f"Columnas:\n" + "\n".join(cols)
            )

            # Valores únicos útiles
            if table == "avisos":
                try:
                    deptos = conn.execute("SELECT DISTINCT DEPARTAMENTO FROM avisos ORDER BY 1").fetchall()
                    schema_parts.append(f"  Departamentos: {', '.join([r[0] for r in deptos])}")
                except Exception:
                    pass
                try:
                    tipos = conn.execute("SELECT DISTINCT TIPO_SINIESTRO FROM avisos ORDER BY 1").fetchall()
                    schema_parts.append(f"  Tipos siniestro: {', '.join([r[0] for r in tipos if r[0]])}")
                except Exception:
                    pass
                try:
                    empresas = conn.execute("SELECT DISTINCT EMPRESA FROM avisos ORDER BY 1").fetchall()
                    schema_parts.append(f"  Empresas: {', '.join([r[0] for r in empresas])}")
                except Exception:
                    pass

        except Exception as e:
            schema_parts.append(f"Tabla: {table} — Error: {str(e)}")

    return "\n\n".join(schema_parts)


# ═══════════════════════════════════════════════════════════════════
# PASO 1: PREGUNTA → SQL
# ═══════════════════════════════════════════════════════════════════

SYSTEM_SQL = """Eres un experto en SQL y datos del Seguro Agrícola Catastrófico (SAC) de Perú.
Tu tarea es convertir preguntas en lenguaje natural a consultas SQL para DuckDB.

REGLAS:
- Usa SOLO las tablas y columnas del esquema proporcionado.
- La tabla principal es "avisos" que contiene todos los registros de siniestros.
- La tabla "materia_asegurada" contiene datos estáticos de pólizas por departamento.
- Columnas numéricas clave en "avisos": INDEMNIZACION, MONTO_DESEMBOLSADO, SUP_INDEMNIZADA, N_PRODUCTORES.
- NUNCA uses ni reportes la columna SUP_AFECTADA (superficie afectada) porque no es un dato confiable.
- Métricas de avance importantes:
  * % Avance de evaluación = avisos con ESTADO_INSPECCION='CERRADO' / total avisos * 100
  * % Avance de desembolso = SUM(MONTO_DESEMBOLSADO) / SUM(INDEMNIZACION) * 100
  Incluye siempre estos porcentajes cuando hagan resúmenes o consultas generales.
- La columna EMPRESA tiene valores: "LA POSITIVA" o "RIMAC".
- Los departamentos están en MAYÚSCULAS (ej: "LAMBAYEQUE", "PIURA").
- FECHAS: Las columnas FECHA_AVISO, FECHA_SINIESTRO, FECHA_ATENCION, FECHA_DESEMBOLSO son strings con formato "YYYY-MM-DD HH:MM:SS" (ej: "2025-10-02 00:00:00").
  Para filtrar por año: CAST(FECHA_SINIESTRO AS DATE) >= '2026-01-01'
  Para extraer año: YEAR(CAST(FECHA_SINIESTRO AS DATE))
  Para extraer mes: MONTH(CAST(FECHA_SINIESTRO AS DATE))
  NUNCA uses strptime con formato '%d-%m-%Y'. Las fechas ya están en formato ISO (YYYY-MM-DD).
  Para "fecha de ocurrencia" usa FECHA_SINIESTRO. Para "fecha de reporte" usa FECHA_AVISO.
- Cuando pregunten por "eventos asociados a lluvias", filtra por TIPO_SINIESTRO IN ('INUNDACION', 'LLUVIAS EXCESIVAS', 'HUAYCO', 'DESLIZAMIENTO', 'DESLIZAMIENTOS').
- Cuando pregunten por "frío" o "bajas temperaturas", filtra por TIPO_SINIESTRO IN ('HELADA', 'FRIAJE', 'NIEVE').
- Cuando pregunten por "plagas y enfermedades" o "biológicos", filtra por TIPO_SINIESTRO IN ('ENFERMEDADES', 'PLAGAS').
- Cuando pregunten por "intervenciones", "acciones", "emergencia" o "resumen", muestra avisos totales, indemnizaciones, desembolsos y productores agrupados por departamento.
- Redondea montos a 2 decimales.
- Si la pregunta menciona varias departamentos, filtra con WHERE DEPARTAMENTO IN (...).
- Si mencionan ciudades o distritos, tradúcelos al departamento correspondiente:
  Chiclayo/Mórrope/Oyotún → LAMBAYEQUE; Nanchoc/Bolívar → CAJAMARCA; etc.
- Siempre incluye ORDER BY relevante.
- Si preguntan genéricamente, da un resumen nacional agrupado por departamento.
- Devuelve SOLAMENTE la consulta SQL, sin explicaciones, sin markdown, sin backticks."""


def _generate_sql(client, question, schema):
    """Usa Claude para generar SQL a partir de la pregunta."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_SQL,
        system=SYSTEM_SQL,
        messages=[{
            "role": "user",
            "content": f"Esquema de datos:\n{schema}\n\nPregunta: {question}"
        }],
    )
    sql = response.content[0].text.strip()

    # Limpiar si viene con backticks
    sql = re.sub(r'^```(?:sql)?\s*', '', sql)
    sql = re.sub(r'\s*```$', '', sql)

    return sql


# ═══════════════════════════════════════════════════════════════════
# PASO 2: EJECUTAR SQL
# ═══════════════════════════════════════════════════════════════════

def _execute_sql(conn, sql):
    """Ejecuta la SQL y devuelve DataFrame de resultados."""
    try:
        result = conn.execute(sql).fetchdf()
        return result, None
    except Exception as e:
        return None, str(e)


# ═══════════════════════════════════════════════════════════════════
# PASO 3: RESULTADOS → PROSA PROFESIONAL
# ═══════════════════════════════════════════════════════════════════

SYSTEM_PROSE = """Eres un redactor profesional del Ministerio de Desarrollo Agrario y Riego (MIDAGRI) de Perú.
Tu tarea es transformar datos tabulares del Seguro Agrícola Catastrófico (SAC) 2025-2026 en texto profesional listo para comunicar.

REGLAS DE REDACCIÓN:
- Escribe en ESPAÑOL formal pero claro, en tercera persona.
- Redacta PÁRRAFOS fluidos y coherentes, NO listas de bullets ni markdown.
- Los montos van con formato: S/ 1,234,567.89
- Las hectáreas se abrevian: ha
- Incluye porcentajes cuando sean relevantes.
- NUNCA reportes la columna "superficie afectada" (SUP_AFECTADA) porque no es un dato confiable.
- Métricas de avance clave que SIEMPRE debes mencionar en resúmenes:
  * Avance de evaluación: % de avisos evaluados (cerrados) respecto al total.
  * Avance de desembolso: % del monto desembolsado respecto a la indemnización reconocida.
- Contexto: la póliza SAC cubre del 01/08/2025 al 01/08/2026, con suma asegurada de S/ 1,000/ha.
- Empresas aseguradoras: La Positiva (18 dptos) y Rímac (6 dptos).
- El texto debe poder copiarse y pegarse directamente en un correo, informe o chat de WhatsApp.
- Inicia con un encabezado breve indicando el tema y la fecha de corte.
- Termina con "Fuente: Dirección de Seguro y Fomento del Financiamiento Agrario - MIDAGRI, SAC 2025-2026."
- NO uses formato markdown (no #, no **, no -), solo texto plano con párrafos.
- Usa saltos de línea entre párrafos para legibilidad.
- Si hay múltiples departamentos, redáctalos en un solo párrafo consolidado o uno por departamento según convenga.
- Sé conciso pero completo. Cada dato relevante debe aparecer."""


def _generate_prose(client, question, sql, result_df, fecha_corte):
    """Usa Claude para redactar párrafos profesionales."""
    # Convertir resultado a texto tabular
    if result_df is not None and len(result_df) > 0:
        # Limitar filas si es muy largo
        display_df = result_df.head(50)
        result_text = display_df.to_string(index=False)
        n_rows = len(result_df)
    else:
        result_text = "(Sin resultados)"
        n_rows = 0

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_PROSE,
        system=SYSTEM_PROSE,
        messages=[{
            "role": "user",
            "content": (
                f"Fecha de corte: {fecha_corte}\n"
                f"Pregunta original: {question}\n"
                f"SQL ejecutada: {sql}\n"
                f"Resultados ({n_rows} filas):\n{result_text}\n\n"
                f"Redacta el texto profesional con estos datos."
            )
        }],
    )
    return response.content[0].text.strip()


# ═══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

def process_query_llm(question, datos):
    """
    Procesa una consulta con LLM + SQL.

    Args:
        question: Pregunta en lenguaje natural
        datos: Dict de data_processor.process_dynamic_data()

    Returns:
        dict con keys:
          - prose: Texto en párrafos listos para comunicar
          - sql: Consulta SQL generada
          - data: DataFrame con resultados
          - error: Mensaje de error (None si todo OK)
    """
    fecha_corte = datos.get("fecha_corte", datetime.now().strftime("%d/%m/%Y"))

    # 1. Obtener cliente Anthropic
    try:
        client = _get_client()
    except ValueError as e:
        return {"prose": None, "sql": None, "data": None, "error": str(e)}

    # 2. Cargar datos en DuckDB
    try:
        conn, schema = _load_to_duckdb(datos)
    except Exception as e:
        return {"prose": None, "sql": None, "data": None,
                "error": f"Error al cargar datos en DuckDB: {str(e)}"}

    # 3. Generar SQL
    try:
        sql = _generate_sql(client, question, schema)
    except Exception as e:
        conn.close()
        return {"prose": None, "sql": None, "data": None,
                "error": f"Error al generar SQL: {str(e)}"}

    # 4. Ejecutar SQL
    result_df, sql_error = _execute_sql(conn, sql)

    # Si falla, intentar regenerar SQL una vez
    if sql_error:
        try:
            retry_msg = (
                f"La SQL anterior falló con error: {sql_error}\n"
                f"SQL fallida: {sql}\n"
                f"Genera una SQL corregida."
            )
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS_SQL,
                system=SYSTEM_SQL,
                messages=[
                    {"role": "user", "content": f"Esquema:\n{schema}\n\nPregunta: {question}"},
                    {"role": "assistant", "content": sql},
                    {"role": "user", "content": retry_msg},
                ],
            )
            sql = response.content[0].text.strip()
            sql = re.sub(r'^```(?:sql)?\s*', '', sql)
            sql = re.sub(r'\s*```$', '', sql)
            result_df, sql_error = _execute_sql(conn, sql)
        except Exception:
            pass

    if sql_error:
        conn.close()
        return {"prose": None, "sql": sql, "data": None,
                "error": f"Error SQL: {sql_error}"}

    # 5. Generar prosa
    try:
        prose = _generate_prose(client, question, sql, result_df, fecha_corte)
    except Exception as e:
        conn.close()
        return {"prose": None, "sql": sql, "data": result_df,
                "error": f"Error al redactar respuesta: {str(e)}"}

    conn.close()

    return {
        "prose": prose,
        "sql": sql,
        "data": result_df,
        "error": None,
    }


def is_llm_available():
    """Verifica si el LLM está disponible (API key configurada)."""
    try:
        import streamlit as st
        key = st.secrets.get("anthropic", {}).get("api_key", "")
        if key:
            return True
    except Exception:
        pass
    return bool(os.environ.get("ANTHROPIC_API_KEY", ""))


def get_suggested_queries():
    """Consultas sugeridas de ejemplo."""
    return [
        "Resumen de Tumbes, Piura, Lambayeque, Lima y Arequipa",
        "Intervenciones del SAC en Cajamarca y Lambayeque",
        "¿Cuántos avisos por helada hay en Puno?",
        "Desembolsos realizados en Junín y Cusco",
        "¿Cuál es la siniestralidad por departamento?",
        "Resumen de La Positiva vs Rímac",
        "Top 5 departamentos con mayor indemnización",
        "Avisos de la última semana en Ayacucho",
    ]
