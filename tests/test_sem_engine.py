"""Tests del motor del semáforo — foco en _networkdays_intl.

Esta función replica NETWORKDAYS.INTL de Excel y se usa en la etapa 7 (Pago,
días hábiles). La reconciliación fila-a-fila de las 7 etapas vive en
test_reconciliacion_semaforo.py; estos tests congelan el conteo de días
hábiles para que un refactor no lo rompa en silencio (un día mal contado =
alerta en color equivocado).

Referencia de calendario (verificado): 2026-06-01 es LUNES, por lo tanto
2026-06-07 es domingo y 2026-06-29 es lunes (además feriado en FERIADOS_SAC).
"""
import pandas as pd
import pytest

import sem_engine as se


def _nd(start_str, end_str, weekend_code=11):
    """Helper: corre _networkdays_intl sobre un solo par de fechas."""
    start = pd.Series([pd.Timestamp(start_str)])
    end = pd.Series([pd.Timestamp(end_str)])
    return int(se._networkdays_intl(start, end, weekend_code).iloc[0])


# ─── weekend_code=11 (solo domingo no laborable) — Alertas 01-05 ───
def test_mismo_dia_laborable_es_1():
    # Lunes a lunes (mismo día), inclusivo → 1
    assert _nd("2026-06-01", "2026-06-01", 11) == 1


def test_domingo_solo_es_0():
    # 2026-06-07 es domingo; un solo día domingo → 0 días hábiles
    assert _nd("2026-06-07", "2026-06-07", 11) == 0


def test_semana_sin_domingo_cuenta_sabado():
    # Lun 01 → Sáb 06: 6 días, ningún domingo, sábado SÍ cuenta (code 11) → 6
    assert _nd("2026-06-01", "2026-06-06", 11) == 6


def test_semana_completa_descuenta_domingo():
    # Lun 01 → Dom 07: 7 días con 1 domingo → 6 hábiles
    assert _nd("2026-06-01", "2026-06-07", 11) == 6


def test_descuenta_feriado():
    # Lun 22 → Lun 29: 8 días. Descuenta Dom 28 (1) y feriado 29-jun (1) → 6
    assert _nd("2026-06-22", "2026-06-29", 11) == 6


def test_rango_invertido_es_negativo():
    # start > end → negativo (replica el comportamiento de Excel)
    assert _nd("2026-06-06", "2026-06-01", 11) < 0


# ─── weekend_code=1 (sábado y domingo no laborables) — Alerta 06 (PAGO) ───
def test_code1_descuenta_sabado_y_domingo():
    # Lun 01 → Dom 07: 7 días, descuenta sáb 06 y dom 07 → 5 hábiles
    assert _nd("2026-06-01", "2026-06-07", 1) == 5


def test_code1_semana_laboral():
    # Lun 01 → Vie 05: 5 días hábiles clásicos → 5
    assert _nd("2026-06-01", "2026-06-05", 1) == 5


def test_code1_difiere_de_code11_en_sabado():
    # El sábado distingue ambos modos: code11 lo cuenta, code1 no
    c11 = _nd("2026-06-06", "2026-06-06", 11)  # sábado, code 11 → 1
    c1 = _nd("2026-06-06", "2026-06-06", 1)    # sábado, code 1 → 0
    assert c11 == 1 and c1 == 0


# ─── NaN-safety ───
def test_nat_devuelve_cero():
    start = pd.Series([pd.NaT, pd.Timestamp("2026-06-01")])
    end = pd.Series([pd.Timestamp("2026-06-05"), pd.NaT])
    out = se._networkdays_intl(start, end, 11)
    assert list(out) == [0, 0], "cualquier extremo NaT → 0"


def test_serie_vacia_no_rompe():
    start = pd.Series([], dtype="datetime64[ns]")
    end = pd.Series([], dtype="datetime64[ns]")
    out = se._networkdays_intl(start, end, 11)
    assert len(out) == 0


# ─── compute_alerts: smoke de integración ───
def test_compute_alerts_smoke():
    # DataFrame mínimo con las columnas que las alertas leen; no debe crashear
    df = pd.DataFrame({
        "FECHA_AVISO": [pd.Timestamp("2026-06-01")],
        "FECHA_ATENCION": [pd.Timestamp("2026-06-03")],
        "ESTADO_INSPECCION": ["CERRADO"],
        "OBSERVACION": [""],
        "DEPARTAMENTO": ["CUSCO"],
    })
    res = se.compute_alerts(df, today=pd.Timestamp("2026-06-12"))
    assert res is not None


# ─── A07 PAGO: regla 2026-07 — días hábiles desde el DÍA SIGUIENTE ───
def _pago(validacion, hoy, desembolso=None):
    df = pd.DataFrame({
        "DICTAMEN": ["INDEMNIZABLE"],
        "FECHA_VALIDACION": [pd.Timestamp(validacion)],
        "FECHA_DESEMBOLSO": [pd.Timestamp(desembolso) if desembolso else pd.NaT],
        "OBSERVACION": [""],
    })
    out = se.compute_alerts(df, today=pd.Timestamp(hoy))
    return int(out["SEMAFORO_07"].iloc[0]), str(out["ALERTA_07"].iloc[0])


def test_pago_dia_de_validacion_cuenta_cero():
    # Validación lunes 2026-06-01, hoy mismo lunes → 0 días (antes: 1)
    sem, txt = _pago("2026-06-01", "2026-06-01")
    assert sem == 1 and "(0 días hábiles)" in txt


def test_pago_cuenta_desde_dia_siguiente():
    # Validación lunes 01, hoy martes 02 → 1 día hábil (antes: 2)
    sem, txt = _pago("2026-06-01", "2026-06-02")
    assert sem == 1 and "(1 días hábiles)" in txt


def test_pago_limite_15_habiles_sigue_ambar():
    # Validación lun 2026-06-01; 15 hábiles después (sin feriados en el rango
    # hasta el 22-jun) = lunes 22-jun → aún ámbar (rojo recién con >15)
    sem, txt = _pago("2026-06-01", "2026-06-22")
    assert sem == 2 and "(15 días hábiles)" in txt


def test_pago_rojo_recien_al_dia_16():
    # Martes 23-jun = 16 días hábiles desde el día siguiente → ROJA
    sem, txt = _pago("2026-06-01", "2026-06-23")
    assert sem == 3 and "(16 días hábiles)" in txt


def test_pago_conforme_en_15_habiles():
    # Pagado exactamente a los 15 hábiles → CONFORME (antes contaba 16 y daba ROJA)
    sem, txt = _pago("2026-06-01", "2026-07-01", desembolso="2026-06-22")
    assert sem == 0 and "(15 días hábiles)" in txt
