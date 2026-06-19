"""Configuración de pytest: pone la raíz del proyecto en sys.path para
que los tests puedan importar los módulos de la app (prediccion_siniestralidad,
sem_engine, data_processor, etc.) sin instalarlos como paquete."""
import io
import os
import sys

import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─────────────────────────────────────────────────────────────────
# Fixture: `datos` realista para smoke-testear los generadores de
# reportes (Word/PPT/Excel/PDF). Se construye con datos sintéticos que
# pasan por process_dynamic_data — el mismo code path que la app real,
# así el `datos` tiene todas las claves/cuadros que esperan los generadores.
# ─────────────────────────────────────────────────────────────────
def _rimac_demo():
    return pd.DataFrame({
        "CAMPAÑA": ["2025-2026"] * 4,
        "CODIGO DE AVISO": ["R1", "R2", "R3", "R4"],
        "DEPARTAMENTO": ["CUSCO", "CUSCO", "PUNO", "AYACUCHO"],
        "PROVINCIA": ["CALCA", "URUBAMBA", "PUNO", "HUAMANGA"],
        "DISTRITO": ["PISAC", "MARAS", "ACORA", "QUINUA"],
        "TIPO SINIESTRO": ["SEQUIA", "HELADA", "GRANIZO", "INUNDACION"],
        "FECHA DE AVISO": ["2025-10-05", "2025-11-10", "2026-01-15", "2026-02-20"],
        "FECHA DE ATENCIÓN": ["2025-10-08", "2025-11-14", "2026-01-20", "2026-02-25"],
        "ESTADO INSPECCION": ["CERRADO", "CERRADO", "", "CERRADO"],
        "DICTAMEN": ["INDEMNIZABLE", "NO INDEMNIZABLE", "INDEMNIZABLE", "INDEMNIZABLE"],
        "INDEMNIZACIÓN": [15000, 0, 8000, 22000],
        "SUPERFICIE INDEMNIZADA": [10, 0, 5, 12],
        "MONTO DESEMBOLSADO": [15000, 0, 0, 22000],
        "N° PRODUCTORES": [3, 1, 2, 5],
        "PRIMA NETA": [50000, 50000, 30000, 40000],
        "TIPO COBERTURA": ["CATASTROFICA"] * 4,
        "SUPERFICIE AFECTADA": [12, 3, 6, 15],
    })


def _lp_demo():
    cols = ["CAMPAÑA", "CÓDIGO DE AVISO", "DEPARTAMENTO", "PROVINCIA", "DISTRITO",
            "TIPO DE SINIESTRO", "FECHA DE AVISO", "FECHA DE ATENCIÓN",
            "ESTADO INSPECCION", "DICTAMEN", "INDEMNIZACION", "SUPERFICIE INDEMNIZADA",
            "MONTO DESEMBOLSADO", "N° DE PRODUCTORES", "PRIMA NETA",
            "TIPO DE COBERTURA", "SUPERFICIE AFECTADA"]
    rows = [["REPORTE LISTAR TODOS LOS AVISOS"] + [None] * (len(cols) - 1), cols]
    for i in range(4):
        rows.append([
            "2025-2026", f"L{i}", "AMAZONAS", "BAGUA", "IMAZA", "SEQUIA",
            f"2025-12-0{i + 1}", f"2025-12-1{i + 1}", "CERRADO", "INDEMNIZABLE",
            5000 + i * 1000, 4 + i, 5000, 2, 25000, "COBERTURA CATASTROFICA", 5 + i,
        ])
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def datos_demo():
    """`datos` completo (vía process_dynamic_data) para los generadores."""
    import data_processor as dp
    buf_rim = io.BytesIO()
    _rimac_demo().to_excel(buf_rim, index=False)
    buf_rim.seek(0)
    buf_lp = io.BytesIO()
    _lp_demo().to_excel(buf_lp, index=False, header=False)
    buf_lp.seek(0)
    return dp.process_dynamic_data(buf_lp, buf_rim)
