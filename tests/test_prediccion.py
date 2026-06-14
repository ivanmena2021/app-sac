"""Tests del modelo predictivo — foco en el corte fraccional diario.

Protege el fix de junio 2026 (commit c7676ca): mes_corte_idx pasó de int
(asumía mes cerrado) a float (posición real en el año). Un error acá daría
números plausibles pero mal — exactamente lo que un test atrapa y una
revisión visual no.
"""
from datetime import date

import pandas as pd
import pytest

import prediccion_siniestralidad as p


# ─── _mes_idx_int: float → mes entero vigente ───
def test_mes_idx_int_jun_a_media_mes():
    # 11-jun = 9.33 (1/3 entre fin-may=9 y fin-jun=10) → mes vigente Jun = 10
    assert p._mes_idx_int(9.33) == 10


def test_mes_idx_int_clamp():
    assert p._mes_idx_int(-5.0) == 0      # antes del inicio
    assert p._mes_idx_int(99.0) == 11     # después del cierre


def test_mes_idx_int_compat_int():
    # Pasar un int del código viejo (mes vigente) sigue dando un índice válido
    assert 0 <= p._mes_idx_int(8) <= 11


# ─── _avance_en_idx: interpolación lineal del avance ───
def test_avance_interpola_entre_meses_adyacentes():
    # cumsum = [0,0,0,0,0,5,15,30,50,75,105,110]
    serie = [0, 0, 0, 0, 0, 5, 10, 15, 20, 25, 30, 5]
    acu = p._avance_acumulado(serie)
    av_may, av_jun = acu[9], acu[10]
    av_interp = p._avance_en_idx(serie, 9.33)
    assert av_may < av_interp < av_jun, "el avance a media-mes debe quedar entre los dos meses"


def test_avance_punto_medio_exacto():
    serie = [0, 0, 0, 0, 0, 5, 10, 15, 20, 25, 30, 5]
    acu = p._avance_acumulado(serie)
    # idx=9.5 → exactamente a mitad de camino entre acu[9] y acu[10]
    esperado = (acu[9] + acu[10]) / 2
    assert p._avance_en_idx(serie, 9.5) == pytest.approx(esperado)


def test_avance_idx_entero_es_fin_de_mes():
    # Con idx entero, debe coincidir con el avance acumulado de ese mes (frac=0)
    serie = [0, 0, 0, 0, 0, 5, 10, 15, 20, 25, 30, 5]
    acu = p._avance_acumulado(serie)
    assert p._avance_en_idx(serie, 10) == pytest.approx(acu[10])


def test_avance_extremos():
    serie = [0, 0, 0, 0, 0, 5, 10, 15, 20, 25, 30, 5]
    assert p._avance_en_idx(serie, 11) == pytest.approx(1.0)   # cierre de campaña
    assert p._avance_en_idx(serie, -1) == pytest.approx(0.0)   # antes de empezar


# ─── _mae_interpolado ───
def test_mae_interpola_entre_meses():
    mae = p._mae_interpolado(9.33)
    assert p.MAE_M5_POR_MES[10] < mae < p.MAE_M5_POR_MES[9], \
        "el MAE a media-mes debe quedar entre may (mes 9) y jun (mes 10)"


def test_mae_meses_tempranos_inf():
    # Ago/Sep/Oct tienen MAE infinito (avance ~0%) — el modelo no es confiable
    assert p._mae_interpolado(0.0) == float("inf")


# ─── serie_actual_desde_df: cálculo de la fracción del mes ───
def test_serie_actual_fraccion_11_junio():
    # 11-jun: 10 días transcurridos de 30 → 9 + 10/30 = 9.333
    _, _, idx = p.serie_actual_desde_df(pd.DataFrame(), today=date(2026, 6, 11))
    assert idx == pytest.approx(9.333, abs=0.01)


def test_serie_actual_primer_dia_del_mes():
    # 1-jun: 0 días transcurridos → posición = fin de mayo exacto = 9.0
    _, _, idx = p.serie_actual_desde_df(pd.DataFrame(), today=date(2026, 6, 1))
    assert idx == pytest.approx(9.0, abs=0.001)


def test_serie_actual_avanza_dia_a_dia():
    # El corte debe crecer estrictamente cada día (resolución diaria)
    _, _, idx11 = p.serie_actual_desde_df(pd.DataFrame(), today=date(2026, 6, 11))
    _, _, idx12 = p.serie_actual_desde_df(pd.DataFrame(), today=date(2026, 6, 12))
    assert idx12 > idx11


def test_serie_actual_campana_correcta_antes_de_agosto():
    # Antes de agosto, la campaña es (año-1)-(año). En jun-2026 → 2025-2026.
    # Inyectamos un aviso indemnizable de mayo-2026 y verificamos que cae en la serie.
    df = pd.DataFrame({
        "DICTAMEN": ["INDEMNIZABLE"],
        "FECHA_AJUSTE_ACTA_FINAL": [pd.Timestamp("2026-05-15")],
        "INDEMNIZACION": [1000.0],
    })
    serie_n, serie_m, _ = p.serie_actual_desde_df(df, today=date(2026, 6, 11))
    assert sum(serie_n) == 1, "el aviso de mayo debe contarse en la campaña 2025-2026"
    assert sum(serie_m) == pytest.approx(1000.0)


# ─── predecir_cierre_campana: smoke + contrato ───
def test_predecir_cierre_acepta_float():
    serie_n = [0] * 12
    serie_n[10] = 50
    serie_m = [0] * 12
    serie_m[10] = 1_000_000
    res = p.predecir_cierre_campana(serie_n, serie_m, 9.33, 5_000_000)
    assert res["mes_corte"] == "Jun"
    assert res["acumulado_n_actual"] == 50
    assert res["fraccion_mes_transcurrido"] == pytest.approx(0.33, abs=0.01)
    # La proyección nunca puede ser menor al acumulado ya observado
    assert res["predicciones"]["M5_regresion"]["total_n"] >= res["acumulado_n_actual"]


def test_predecir_cierre_compat_int():
    # El código viejo pasaba int; debe seguir funcionando sin romper
    serie_n = [0] * 12
    serie_n[8] = 30
    serie_m = [0] * 12
    serie_m[8] = 500_000
    res = p.predecir_cierre_campana(serie_n, serie_m, 8, 5_000_000)
    assert "predicciones" in res and "intervalo_n" in res
