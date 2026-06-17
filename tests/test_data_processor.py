"""Tests de normalización de data_processor — el borde donde el formato
de los Excel de Rímac/LP entra al sistema.

Es exactamente donde nos mordió el cambio de formato (TXT_TIPO_DE_COBERTURA,
detección de header de LP en fila 1). Estos tests fijan el contrato de
mapeo de columnas para que un cambio de los portales se detecte temprano.
"""
import io

import pandas as pd
import pytest

import data_processor as dp


def _excel_bytes(df, header=True):
    """Serializa un DataFrame a bytes Excel (.xlsx) en memoria."""
    buf = io.BytesIO()
    df.to_excel(buf, index=False, header=header)
    buf.seek(0)
    return buf


# ─── _normalize_siniestros (Rímac, header en fila 0) ───
def test_siniestros_mapea_columnas_canonicas():
    df = pd.DataFrame({
        "CAMPAÑA": ["2025-2026"],
        "CODIGO DE AVISO": ["123-1"],
        "DEPARTAMENTO": ["cusco"],
        "TIPO SINIESTRO": ["sequia"],
        "INDEMNIZACIÓN": [1500.0],
    })
    out = dp._normalize_siniestros(_excel_bytes(df))
    assert "CODIGO_AVISO" in out.columns
    assert "TIPO_SINIESTRO" in out.columns
    assert "INDEMNIZACION" in out.columns


def test_siniestros_departamento_upper_y_filtra_vacios():
    df = pd.DataFrame({
        "CAMPAÑA": ["2025-2026", "2025-2026", "2025-2026"],
        "DEPARTAMENTO": ["cusco", "", "puno"],
    })
    out = dp._normalize_siniestros(_excel_bytes(df))
    deptos = set(out["DEPARTAMENTO"])
    assert "CUSCO" in deptos and "PUNO" in deptos
    assert "" not in deptos, "las filas con DEPARTAMENTO vacío deben filtrarse"


def test_siniestros_indemnizacion_es_numerica():
    df = pd.DataFrame({
        "CAMPAÑA": ["2025-2026", "2025-2026"],
        "DEPARTAMENTO": ["CUSCO", "PUNO"],
        "INDEMNIZACIÓN": ["1500", "-"],   # '-' es vacío en estos Excel
    })
    out = dp._normalize_siniestros(_excel_bytes(df))
    assert pd.api.types.is_numeric_dtype(out["INDEMNIZACION"])
    assert out["INDEMNIZACION"].iloc[0] == 1500
    assert pd.isna(out["INDEMNIZACION"].iloc[1])   # '-' → NaN


# ─── _normalize_midagri (La Positiva, header real en fila 1) ───
def test_midagri_detecta_header_en_fila_1():
    # LP trae una fila de título en la 0 y los encabezados reales en la 1.
    # Nombres de columna VERIFICADOS contra un Excel real de La Positiva
    # (midagri_2026-02-26): la columna es "CÓDIGO DE AVISO" (con DE y tilde).
    raw = pd.DataFrame([
        ["REPORTE LISTAR TODOS LOS AVISOS", None, None],
        ["CAMPAÑA", "CÓDIGO DE AVISO", "DEPARTAMENTO"],
        ["2025-2026", "999-1", "AMAZONAS"],
    ])
    # header=False para que la fila de título quede como datos (como en LP real)
    out = dp._normalize_midagri(_excel_bytes(raw, header=False))
    assert "CODIGO_AVISO" in out.columns, "el header de LP debe detectarse en la fila 1"
    assert "DEPARTAMENTO" in out.columns
    assert "AMAZONAS" in set(out["DEPARTAMENTO"])


# ─── _consolidar_columnas_duplicadas (limpieza del consolidado) ───
def test_consolida_empresa_y_dropea_compania():
    df = pd.DataFrame({
        "EMPRESA": ["RIMAC", "LA POSITIVA"],
        "COMPAÑIA DE SEGUROS": ["RIMAC", "La Positiva Seguros"],
    })
    out = dp._consolidar_columnas_duplicadas(df)
    assert "EMPRESA" in out.columns
    assert "COMPAÑIA DE SEGUROS" not in out.columns
    assert list(out["EMPRESA"]) == ["RIMAC", "LA POSITIVA"]  # EMPRESA gana


def test_consolida_fechas_recupera_datos_partidos():
    # Caso real: una fuente puso la fecha en la canónica, la otra en la cruda.
    # combine_first debe recuperar AMBAS en una sola columna.
    df = pd.DataFrame({
        "FECHA_ATENCION":   [pd.Timestamp("2026-05-01"), pd.NaT],
        "FECHA DE ATENCION": [pd.NaT,                     pd.Timestamp("2026-06-02")],
    })
    out = dp._consolidar_columnas_duplicadas(df)
    assert "FECHA DE ATENCION" not in out.columns
    assert out["FECHA_ATENCION"].iloc[0] == pd.Timestamp("2026-05-01")
    assert out["FECHA_ATENCION"].iloc[1] == pd.Timestamp("2026-06-02")


def test_consolida_tipo_cobertura_y_envio():
    df = pd.DataFrame({
        "TIPO_COBERTURA": ["CATASTROFICA", None],
        "TIPO DE COBERTURA": [None, "COMPLEMENTARIA"],
        "FECHA_ENVIO_DRAS": [pd.Timestamp("2026-05-01"), pd.NaT],
        "FECHA DE ENVIO DE PADRON DRAS/AGENCIA AGRARIA": [pd.NaT, pd.Timestamp("2026-06-01")],
    })
    out = dp._consolidar_columnas_duplicadas(df)
    assert "TIPO DE COBERTURA" not in out.columns
    assert "FECHA DE ENVIO DE PADRON DRAS/AGENCIA AGRARIA" not in out.columns
    assert list(out["TIPO_COBERTURA"]) == ["CATASTROFICA", "COMPLEMENTARIA"]


def test_reprogramaciones_consecutivas_sin_asterisco_duplicado():
    df = pd.DataFrame({
        "FECHA_REPROGRAMACION_01": [pd.Timestamp("2026-01-01")],
        "FECHA_REPROGRAMACION_02": [pd.NaT],
        "FECHA_REPROGRAMACION_03": [pd.NaT],
        "FECHA DE REPROGRAMACION 04": [pd.Timestamp("2026-04-04")],
        "FECHA DE REPROGRAMACION 04 (*)": [pd.NaT],
        "FECHA DE REPROGRAMACION 05": [pd.NaT],
        "FECHA DE REPROGRAMACION 05 (*)": [pd.Timestamp("2026-05-05")],
        "FECHA DE REPROGRAMACION 06": [pd.NaT],
        "FECHA DE REPROGRAMACION 06 (*)": [pd.NaT],
    })
    out = dp._consolidar_columnas_duplicadas(df)
    reprog = sorted(c for c in out.columns if "REPROGRAMAC" in c.upper())
    # Solo deben quedar las 6 canónicas consecutivas, sin asterisco ni crudas
    assert reprog == [
        "FECHA_REPROGRAMACION_01", "FECHA_REPROGRAMACION_02",
        "FECHA_REPROGRAMACION_03", "FECHA_REPROGRAMACION_04",
        "FECHA_REPROGRAMACION_05", "FECHA_REPROGRAMACION_06",
    ]
    # Los valores se recuperan (incluso desde la variante con asterisco en 05)
    assert out["FECHA_REPROGRAMACION_04"].iloc[0] == pd.Timestamp("2026-04-04")
    assert out["FECHA_REPROGRAMACION_05"].iloc[0] == pd.Timestamp("2026-05-05")


def test_midagri_no_incluye_fila_titulo_como_dato():
    raw = pd.DataFrame([
        ["REPORTE LISTAR TODOS LOS AVISOS", None, None],
        ["CAMPAÑA", "CODIGO AVISO", "DEPARTAMENTO"],
        ["2025-2026", "999-1", "AMAZONAS"],
    ])
    out = dp._normalize_midagri(_excel_bytes(raw, header=False))
    # El título no debe aparecer como un valor de departamento
    assert "REPORTE LISTAR TODOS LOS AVISOS" not in set(out["DEPARTAMENTO"].astype(str))
    assert len(out) == 1   # solo la fila de datos real
