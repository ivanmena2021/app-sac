"""Tests del caché del semáforo (mejora #4 rendimiento).

compute_semaforo es el cálculo más pesado de la app y se cachea cuando
se le pasa cache_key. Estos tests fijan el contrato: el camino cacheado
debe dar EXACTAMENTE el mismo resultado que el directo.

semaforo_alertas importa plotly/streamlit (no están en el CI liviano);
con importorskip estos tests corren localmente y se saltean en CI sin
romperlo. Si el CI suma esas deps, se activan solos.
"""
import pandas as pd
import pytest

pytest.importorskip("plotly")
pytest.importorskip("streamlit")

import semaforo_alertas as sa


def _df_demo():
    # Fila 0: atención vencida (FECHA_ATENCION NaT, aviso viejo) → alerta roja.
    # Fila 1: atendida al día siguiente → sin alerta (verde/completado).
    return pd.DataFrame({
        "FECHA_AVISO":       [pd.Timestamp("2026-05-01"), pd.Timestamp("2026-06-10")],
        "FECHA_ATENCION":    [pd.NaT,                      pd.Timestamp("2026-06-11")],
        "ESTADO_INSPECCION": ["",                          "CERRADO"],
        "OBSERVACION":       ["",                          ""],
        "DEPARTAMENTO":      ["CUSCO",                     "PUNO"],
    })


def test_compute_semaforo_genera_columnas_sem():
    out = sa.compute_semaforo(_df_demo(), pd.Timestamp("2026-06-12"))
    for col in ("SEM_ETAPA", "SEM_ALERTA", "SEM_DIAS", "SEM_DETALLE"):
        assert col in out.columns


def test_cache_key_no_altera_resultado():
    df = _df_demo()
    today = pd.Timestamp("2026-06-12")
    directo = sa.compute_semaforo(df, today)
    cacheado = sa.compute_semaforo(df, today, cache_key=("2025-2026", len(df)))
    # El camino cacheado debe ser idéntico al directo en las columnas SEM_*
    assert list(directo["SEM_ALERTA"]) == list(cacheado["SEM_ALERTA"])
    assert list(directo["SEM_ETAPA"]) == list(cacheado["SEM_ETAPA"])
    assert list(directo["SEM_DIAS"]) == list(cacheado["SEM_DIAS"])


def test_atencion_vencida_es_roja():
    # Sanity: la fila con atención vencida debe quedar en rojo
    out = sa.compute_semaforo(_df_demo(), pd.Timestamp("2026-06-12"))
    assert out["SEM_ALERTA"].iloc[0] == "rojo"
