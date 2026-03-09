"""
query_llm.py — Motor de consultas SAC potenciado con LLM + SQL (v2)
====================================================================
Flujo mejorado:
  1. Carga DataFrames en DuckDB (base de datos en memoria)
  2. Envía la pregunta + esquema de tablas a Claude API
  3. Claude genera una consulta SQL de DETALLE
  4. Se ejecuta la SQL sobre DuckDB → resultados detallados
  5. Se genera automáticamente un RESUMEN AGREGADO verificado
  6. Claude redacta párrafos profesionales usando AMBOS (detalle + resumen)
  7. Devuelve texto listo para comunicar

Mejoras v2 (control de calidad):
  - Totales agregados calculados programáticamente (no por el LLM)
  - El redactor recibe cifras verificadas que DEBE usar textualmente
  - Porcentajes de avance calculados correctamente sobre registros individuales
  - Validación de coherencia entre detalle y resumen

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
                # Provincias (muestra algunas para contexto)
                try:
                    provs = conn.execute("SELECT DISTINCT PROVINCIA FROM avisos WHERE PROVINCIA IS NOT NULL ORDER BY 1 LIMIT 30").fetchall()
                    if provs:
                        schema_parts.append(f"  Provincias (muestra): {', '.join([r[0] for r in provs if r[0]])}")
                except Exception:
                    pass
                # Contar niveles geográficos
                try:
                    geo_counts = conn.execute("""
                        SELECT
                            COUNT(DISTINCT DEPARTAMENTO) as n_deptos,
                            COUNT(DISTINCT PROVINCIA) as n_provs,
                            COUNT(DISTINCT DISTRITO) as n_dists,
                            COUNT(DISTINCT SECTOR_ESTADISTICO) as n_sectors
                        FROM avisos
                    """).fetchone()
                    schema_parts.append(f"  Niveles geográficos: {geo_counts[0]} departamentos, {geo_counts[1]} provincias, {geo_counts[2]} distritos, {geo_counts[3]} sectores estadísticos")
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

COLUMNAS GEOGRÁFICAS en la tabla "avisos":
- DEPARTAMENTO: nivel más alto (24 departamentos, en MAYÚSCULAS: "LAMBAYEQUE", "PIURA", etc.)
- PROVINCIA: nivel intermedio (en MAYÚSCULAS). Ejemplo: "CHICLAYO", "SULLANA", "HUANCAYO"
- DISTRITO: nivel detallado (en MAYÚSCULAS). Ejemplo: "MORROPE", "TAMBOGRANDE"
- SECTOR_ESTADISTICO: nivel más granular (en MAYÚSCULAS). Ubicación específica dentro del distrito.
- EMPRESA: "LA POSITIVA" o "RIMAC" (derivada de materia_asegurada)

AGRUPACIÓN GEOGRÁFICA:
- Si preguntan "por provincia", agrupa con GROUP BY PROVINCIA
- Si preguntan "por distrito", agrupa con GROUP BY DISTRITO (puedes incluir PROVINCIA también)
- Si preguntan "por sector", agrupa con GROUP BY SECTOR_ESTADISTICO
- Si mencionan un distrito/provincia/sector específico, filtra con WHERE
- Cuando agrupes por provincia o distrito, incluye el DEPARTAMENTO para contexto
- Si mencionan una provincia o distrito concreto, usa UPPER(PROVINCIA) = 'NOMBRE' o UPPER(DISTRITO) = 'NOMBRE'

Métricas de avance importantes:
  * % Avance de evaluación = avisos con ESTADO_INSPECCION='CERRADO' / total avisos * 100
  * % Avance de desembolso = SUM(MONTO_DESEMBOLSADO) / SUM(INDEMNIZACION) * 100
  Incluye siempre estos porcentajes cuando hagan resúmenes o consultas generales.

FECHAS: Las columnas FECHA_AVISO, FECHA_SINIESTRO, FECHA_ATENCION, FECHA_DESEMBOLSO son de tipo DATE/TIMESTAMP.
  Para filtrar por año: YEAR(FECHA_SINIESTRO) = 2026
  Para filtrar por mes: MONTH(FECHA_SINIESTRO) = 3
  Para rangos: FECHA_SINIESTRO >= '2026-01-01'
  NUNCA uses strptime con formato '%d-%m-%Y'.
  Para "fecha de ocurrencia" usa FECHA_SINIESTRO. Para "fecha de reporte" usa FECHA_AVISO.

CONCEPTOS SEMÁNTICOS:
- "eventos asociados a lluvias" → TIPO_SINIESTRO IN ('INUNDACION', 'LLUVIAS EXCESIVAS', 'HUAYCO', 'DESLIZAMIENTO', 'DESLIZAMIENTOS')
- "frío" o "bajas temperaturas" → TIPO_SINIESTRO IN ('HELADA', 'FRIAJE', 'NIEVE')
- "plagas y enfermedades" o "biológicos" → TIPO_SINIESTRO IN ('ENFERMEDADES', 'PLAGAS')
- "intervenciones", "acciones", "emergencia" o "resumen" → avisos totales, indemnizaciones, desembolsos y productores

IMPORTANTE — ESTRUCTURA DE LA SQL:
- Genera UNA SOLA consulta SQL de detalle con el desglose que pida el usuario.
- NO necesitas generar totales ni resúmenes; el sistema los calculará automáticamente a partir de tu consulta.
- Si la pregunta pide enfocarse en una zona/cultivo/tipo específico, incluye TODOS los registros del ámbito geográfico
  (departamento completo) y usa ORDER BY con CASE WHEN para priorizar los de interés, NO filtres con WHERE
  porque se necesita el contexto completo para el resumen.

Ejemplo: si preguntan por "Moyobamba con inundaciones y arroz en San Martín":
  - Filtra WHERE DEPARTAMENTO = 'SAN MARTIN' (nivel departamento completo)
  - Agrupa por PROVINCIA, DISTRITO, TIPO_SINIESTRO, TIPO_CULTIVO
  - Ordena priorizando Moyobamba, inundación, arroz con CASE WHEN
  - NO filtres por provincia/tipo/cultivo específico porque perderías el contexto departamental

OTRAS REGLAS:
- Redondea montos a 2 decimales.
- Siempre incluye ORDER BY relevante.
- Si preguntan genéricamente sin nivel, da resumen agrupado por departamento.
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
# PASO 2.5: RESUMEN AGREGADO VERIFICADO
# ═══════════════════════════════════════════════════════════════════

def _compute_verified_summary(conn, sql, result_df):
    """
    Calcula un resumen agregado verificado programáticamente.
    Extrae la cláusula WHERE de la SQL original para aplicar los mismos filtros,
    pero calcula totales sobre registros individuales (no sobre filas agrupadas).

    Retorna un dict con métricas verificadas y un texto formateado.
    """
    if result_df is None or len(result_df) == 0:
        return None, ""

    # Extraer la cláusula WHERE de la SQL original
    where_clause = _extract_where_clause(sql)

    # Construir SQL de resumen con los mismos filtros
    summary_sql = f"""
    SELECT
        COUNT(*) AS total_avisos,
        ROUND(SUM(COALESCE(INDEMNIZACION, 0)), 2) AS total_indemnizacion,
        ROUND(SUM(COALESCE(MONTO_DESEMBOLSADO, 0)), 2) AS total_desembolso,
        ROUND(SUM(COALESCE(SUP_INDEMNIZADA, 0)), 2) AS total_ha_indemnizadas,
        COALESCE(SUM(COALESCE(N_PRODUCTORES, 0)), 0) AS total_productores,
        SUM(CASE WHEN UPPER(COALESCE(ESTADO_INSPECCION, '')) = 'CERRADO' THEN 1 ELSE 0 END) AS avisos_cerrados,
        ROUND(
            SUM(CASE WHEN UPPER(COALESCE(ESTADO_INSPECCION, '')) = 'CERRADO' THEN 1 ELSE 0 END) * 100.0
            / NULLIF(COUNT(*), 0), 1
        ) AS pct_avance_evaluacion,
        ROUND(
            SUM(COALESCE(MONTO_DESEMBOLSADO, 0)) * 100.0
            / NULLIF(SUM(COALESCE(INDEMNIZACION, 0)), 0), 1
        ) AS pct_avance_desembolso
    FROM avisos
    {where_clause}
    """

    try:
        summary_row = conn.execute(summary_sql).fetchone()
    except Exception:
        # Si falla la extracción de WHERE, intentar calcular desde result_df
        return _compute_summary_from_df(result_df), ""

    if summary_row is None:
        return None, ""

    summary = {
        "total_avisos": int(summary_row[0] or 0),
        "total_indemnizacion": float(summary_row[1] or 0),
        "total_desembolso": float(summary_row[2] or 0),
        "total_ha_indemnizadas": float(summary_row[3] or 0),
        "total_productores": int(summary_row[4] or 0),
        "avisos_cerrados": int(summary_row[5] or 0),
        "pct_avance_evaluacion": float(summary_row[6] or 0),
        "pct_avance_desembolso": float(summary_row[7] or 0),
    }

    # Generar resumen por provincia si hay columna PROVINCIA en los resultados
    summary_by_provincia = ""
    if "PROVINCIA" in result_df.columns:
        try:
            prov_sql = f"""
            SELECT
                PROVINCIA,
                COUNT(*) AS avisos,
                ROUND(SUM(COALESCE(INDEMNIZACION, 0)), 2) AS indemnizacion,
                ROUND(SUM(COALESCE(MONTO_DESEMBOLSADO, 0)), 2) AS desembolso,
                ROUND(SUM(COALESCE(SUP_INDEMNIZADA, 0)), 2) AS ha_indemnizadas,
                COALESCE(SUM(COALESCE(N_PRODUCTORES, 0)), 0) AS productores,
                ROUND(
                    SUM(CASE WHEN UPPER(COALESCE(ESTADO_INSPECCION, '')) = 'CERRADO' THEN 1 ELSE 0 END) * 100.0
                    / NULLIF(COUNT(*), 0), 1
                ) AS pct_evaluacion,
                ROUND(
                    SUM(COALESCE(MONTO_DESEMBOLSADO, 0)) * 100.0
                    / NULLIF(SUM(COALESCE(INDEMNIZACION, 0)), 0), 1
                ) AS pct_desembolso
            FROM avisos
            {where_clause}
            GROUP BY PROVINCIA
            ORDER BY indemnizacion DESC
            """
            prov_df = conn.execute(prov_sql).fetchdf()
            if len(prov_df) > 0:
                summary_by_provincia = "\nRESUMEN POR PROVINCIA (cifras verificadas):\n"
                summary_by_provincia += prov_df.to_string(index=False)
        except Exception:
            pass

    # Generar resumen por tipo de siniestro
    summary_by_tipo = ""
    if "TIPO_SINIESTRO" in result_df.columns:
        try:
            tipo_sql = f"""
            SELECT
                TIPO_SINIESTRO,
                COUNT(*) AS avisos,
                ROUND(SUM(COALESCE(INDEMNIZACION, 0)), 2) AS indemnizacion
            FROM avisos
            {where_clause}
            GROUP BY TIPO_SINIESTRO
            ORDER BY avisos DESC
            """
            tipo_df = conn.execute(tipo_sql).fetchdf()
            if len(tipo_df) > 0:
                summary_by_tipo = "\nRESUMEN POR TIPO DE SINIESTRO (cifras verificadas):\n"
                summary_by_tipo += tipo_df.to_string(index=False)
        except Exception:
            pass

    # Formatear texto de resumen
    summary_text = (
        f"\n{'='*60}\n"
        f"RESUMEN AGREGADO VERIFICADO (calculado sobre registros individuales):\n"
        f"{'='*60}\n"
        f"Total avisos de siniestro: {summary['total_avisos']:,}\n"
        f"Indemnización total reconocida: S/ {summary['total_indemnizacion']:,.2f}\n"
        f"Monto total desembolsado: S/ {summary['total_desembolso']:,.2f}\n"
        f"Hectáreas indemnizadas: {summary['total_ha_indemnizadas']:,.2f} ha\n"
        f"Productores beneficiados: {summary['total_productores']:,}\n"
        f"Avisos cerrados (evaluados): {summary['avisos_cerrados']:,} de {summary['total_avisos']:,}\n"
        f"% Avance evaluación: {summary['pct_avance_evaluacion']:.1f}%\n"
        f"% Avance desembolso: {summary['pct_avance_desembolso']:.1f}%\n"
        f"{summary_by_provincia}"
        f"{summary_by_tipo}"
        f"\n{'='*60}\n"
    )

    return summary, summary_text


def _extract_where_clause(sql):
    """
    Extrae la cláusula WHERE de una SQL.
    Retorna la cláusula completa incluyendo 'WHERE ...' o string vacío.
    """
    sql_upper = sql.upper()

    # Buscar WHERE
    where_start = -1
    # Encontrar el WHERE principal (no de subconsultas)
    depth = 0
    i = 0
    while i < len(sql_upper):
        if sql_upper[i] == '(':
            depth += 1
        elif sql_upper[i] == ')':
            depth -= 1
        elif depth == 0 and sql_upper[i:i+5] == 'WHERE':
            where_start = i
            break
        i += 1

    if where_start == -1:
        return ""

    # Encontrar el final de WHERE (antes de GROUP BY, ORDER BY, LIMIT, HAVING, UNION, o fin)
    where_end = len(sql)
    for keyword in ['GROUP BY', 'ORDER BY', 'LIMIT', 'HAVING', 'UNION']:
        pos = sql_upper.find(keyword, where_start + 5)
        if pos != -1 and pos < where_end:
            # Verificar que no estemos dentro de paréntesis
            depth = 0
            valid = True
            for j in range(where_start, pos):
                if sql[j] == '(':
                    depth += 1
                elif sql[j] == ')':
                    depth -= 1
                if depth < 0:
                    valid = False
                    break
            if valid and depth == 0:
                where_end = pos

    return sql[where_start:where_end].strip()


def _compute_summary_from_df(result_df):
    """
    Fallback: calcula resumen desde el DataFrame de resultados.
    Nota: Esto puede tener los mismos problemas que antes si las filas están agrupadas,
    pero es mejor que nada.
    """
    summary = {
        "total_avisos": 0,
        "total_indemnizacion": 0,
        "total_desembolso": 0,
        "total_ha_indemnizadas": 0,
        "total_productores": 0,
        "avisos_cerrados": 0,
        "pct_avance_evaluacion": 0,
        "pct_avance_desembolso": 0,
    }

    # Buscar columnas que contengan "aviso" o "total_avisos"
    for col in result_df.columns:
        cl = col.lower()
        if "total_aviso" in cl or cl == "avisos":
            summary["total_avisos"] = int(result_df[col].sum())
        elif "indemniz" in cl and "monto" in cl:
            summary["total_indemnizacion"] = float(result_df[col].sum())
        elif "desembol" in cl and "monto" in cl:
            summary["total_desembolso"] = float(result_df[col].sum())
        elif "hectare" in cl or "ha_indemn" in cl:
            summary["total_ha_indemnizadas"] = float(result_df[col].sum())
        elif "productor" in cl:
            summary["total_productores"] = int(result_df[col].sum())

    if summary["total_indemnizacion"] > 0:
        summary["pct_avance_desembolso"] = round(
            summary["total_desembolso"] / summary["total_indemnizacion"] * 100, 1
        )

    return summary


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
- Contexto: la póliza SAC cubre del 01/08/2025 al 01/08/2026, con suma asegurada de S/ 1,000/ha.
- Empresas aseguradoras: La Positiva (18 dptos) y Rímac (6 dptos).
- El texto debe poder copiarse y pegarse directamente en un correo, informe o chat de WhatsApp.
- Inicia con un encabezado breve indicando el tema y la fecha de corte.
- Termina con "Fuente: Dirección de Seguro y Fomento del Financiamiento Agrario - MIDAGRI, SAC 2025-2026."
- NO uses formato markdown (no #, no **, no -), solo texto plano con párrafos.
- Usa saltos de línea entre párrafos para legibilidad.
- Si hay múltiples departamentos, redáctalos en un solo párrafo consolidado o uno por departamento según convenga.
- Sé conciso pero completo. Cada dato relevante debe aparecer.

REGLA CRÍTICA SOBRE CIFRAS — LEE CON ATENCIÓN:
Se te proporcionarán DOS bloques de datos:
1. TABLA DETALLADA: filas agrupadas por provincia/distrito/cultivo/etc. Úsala para describir detalles específicos.
2. RESUMEN AGREGADO VERIFICADO: cifras TOTALES calculadas programáticamente sobre los registros individuales.

DEBES usar las cifras del RESUMEN AGREGADO VERIFICADO para:
- Total de avisos de siniestro
- Indemnización total
- Monto desembolsado total
- Hectáreas indemnizadas total
- Productores beneficiados total
- % Avance de evaluación
- % Avance de desembolso
- Totales por provincia (si se proporcionan)

NUNCA recalcules estos totales sumando las filas de la tabla detallada, porque las filas
están agrupadas y podrías obtener cifras incorrectas. Las cifras del RESUMEN son las únicas
correctas y verificadas.

Para cifras a nivel de distrito o detalle específico (ej: "en el distrito X se registraron Y avisos
con indemnización de S/ Z"), SÍ puedes usar la tabla detallada.

Métricas de avance clave que SIEMPRE debes mencionar en resúmenes:
  * Avance de evaluación: % de avisos evaluados (cerrados) respecto al total.
  * Avance de desembolso: % del monto desembolsado respecto a la indemnización reconocida."""


def _generate_prose(client, question, sql, result_df, fecha_corte, summary_text=""):
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

    # Construir el mensaje con ambos bloques
    user_content = (
        f"Fecha de corte: {fecha_corte}\n"
        f"Pregunta original: {question}\n\n"
        f"TABLA DETALLADA ({n_rows} filas):\n{result_text}\n"
    )

    if summary_text:
        user_content += f"\n{summary_text}\n"

    user_content += (
        "\nRECUERDA: Usa las cifras del RESUMEN AGREGADO VERIFICADO para todos los totales. "
        "No sumes manualmente las filas de la tabla detallada.\n\n"
        "Redacta el texto profesional con estos datos."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_PROSE,
        system=SYSTEM_PROSE,
        messages=[{
            "role": "user",
            "content": user_content
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
          - summary: Dict con resumen verificado
          - error: Mensaje de error (None si todo OK)
    """
    fecha_corte = datos.get("fecha_corte", datetime.now().strftime("%d/%m/%Y"))

    # 1. Obtener cliente Anthropic
    try:
        client = _get_client()
    except ValueError as e:
        return {"prose": None, "sql": None, "data": None, "summary": None, "error": str(e)}

    # 2. Cargar datos en DuckDB
    try:
        conn, schema = _load_to_duckdb(datos)
    except Exception as e:
        return {"prose": None, "sql": None, "data": None, "summary": None,
                "error": f"Error al cargar datos en DuckDB: {str(e)}"}

    # 3. Generar SQL
    try:
        sql = _generate_sql(client, question, schema)
    except Exception as e:
        conn.close()
        return {"prose": None, "sql": None, "data": None, "summary": None,
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
        return {"prose": None, "sql": sql, "data": None, "summary": None,
                "error": f"Error SQL: {sql_error}"}

    # 5. Calcular resumen agregado verificado
    summary, summary_text = _compute_verified_summary(conn, sql, result_df)

    # 6. Generar prosa con resumen verificado
    try:
        prose = _generate_prose(client, question, sql, result_df, fecha_corte, summary_text)
    except Exception as e:
        conn.close()
        return {"prose": None, "sql": sql, "data": result_df, "summary": summary,
                "error": f"Error al redactar respuesta: {str(e)}"}

    conn.close()

    return {
        "prose": prose,
        "sql": sql,
        "data": result_df,
        "summary": summary,
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
        "Avisos por provincia en Cusco y Junín",
        "Top distritos con mayor indemnización en Lambayeque",
        "Resumen por distrito en Piura con lluvias",
    ]
