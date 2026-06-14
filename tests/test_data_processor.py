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
