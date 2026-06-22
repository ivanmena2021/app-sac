"""Reconciliación automatizada del semáforo contra el Excel oficial (CI).

Congela el contrato: para una muestra representativa de avisos reales (que
cubre todos los semáforos posibles en cada una de las 7 etapas), el motor de
la app debe producir EXACTAMENTE el mismo semáforo que el Excel del equipo SAC.

El fixture tests/fixtures/semaforo_reconciliacion.csv se genera con
tools/generar_fixture_semaforo.py a partir del Excel oficial; sus columnas
EXP_01..07 son los semáforos cacheados por el Excel (la verdad). La fecha de
corte es la del Excel de referencia (celda BY2).

Validación exhaustiva sobre el archivo completo (12,914 filas):
    python tools/reconciliar_semaforo.py "<ruta_xlsx>"
"""
import os

import numpy as np
import pandas as pd
import pytest

import sem_engine as se

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "semaforo_reconciliacion.csv")
# Corte del Excel de referencia (BY2). El fixture se calculó con esta fecha.
FECHA_CORTE = pd.Timestamp("2026-06-15")
SUFIJOS = ["01", "02", "03", "04", "05", "06", "07"]


def _norm(v):
    """Semáforo → {-1,0,1,2,3} o None (blanco)."""
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, str):
        v = v.strip()
        if v == "":
            return None
    try:
        return int(round(float(v)))
    except (ValueError, TypeError):
        return None


@pytest.fixture(scope="module")
def fixture_df():
    if not os.path.exists(FIXTURE):
        pytest.skip("fixture de reconciliación no generado")
    return pd.read_csv(FIXTURE, dtype=str, keep_default_na=False, encoding="utf-8")


def test_fixture_existe_y_tiene_filas(fixture_df):
    assert len(fixture_df) > 100, "el fixture debería cubrir cientos de casos"
    for suf in SUFIJOS:
        assert f"EXP_{suf}" in fixture_df.columns


def test_reconciliacion_fila_a_fila(fixture_df):
    """Cada aviso × cada etapa: semáforo de la app == semáforo del Excel."""
    out = se.compute_alerts(fixture_df.copy(), today=FECHA_CORTE)

    mismatches = []
    for suf in SUFIJOS:
        app = [_norm(v) for v in out[f"SEMAFORO_{suf}"]]
        exp = [_norm(v) for v in fixture_df[f"EXP_{suf}"]]
        for i, (a, x) in enumerate(zip(app, exp)):
            if a != x:
                mismatches.append((suf, i, a, x))

    assert not mismatches, (
        f"{len(mismatches)} discrepancias semáforo app vs Excel. "
        f"Primeras 10: {mismatches[:10]}"
    )


def test_cobertura_de_todos_los_colores(fixture_df):
    """El fixture debe ejercitar verde/ámbar/roja/conforme/excluido en agregado
    (si no, el test de reconciliación sería trivialmente verde)."""
    valores = set()
    for suf in SUFIJOS:
        valores.update(_norm(v) for v in fixture_df[f"EXP_{suf}"])
    for esperado in (-1, 0, 1, 2, 3, None):
        assert esperado in valores, f"el fixture no cubre el semáforo {esperado}"
