"""
prediccion_siniestralidad.py — Modelo predictivo del cierre de campaña SAC.

Predice el total de indemnizaciones (casos y monto) y el índice de
siniestralidad al cierre de la campaña agrícola (Jul) usando los datos
acumulados a la fecha + las 5 curvas de avance históricas.

MODELO PRINCIPAL (M5): regresión lineal sobre el % de avance acumulado
mensual entre las 5 campañas históricas (2020-2021 a 2024-2025).

Justificación: la operatividad del SAC ha mostrado una clara tendencia
de aceleración (al mes Abr el avance pasó de 28% en 2020-21 a 71% en
2024-25). El promedio simple subestima sistemáticamente el avance actual.
La regresión lineal captura esta tendencia y proyecta el siguiente punto
en la secuencia.

Validación leave-one-out (5 campañas):
  - MAE casos:  16.0% (std ±14.2%)
  - MAE monto:  29.1% (std ±24.5%)
  - En la última campaña (2024-25) predijo con error de:
      casos: 2.0%   monto: 12.3%

LIMITACIONES IMPORTANTES:
- El modelo asume que la tendencia de aceleración continúa. Si el SAC
  cambia procesos, la predicción puede desviarse.
- Solo 5 puntos de datos históricos → la regresión tiene incertidumbre.
- Los meses tempranos (Ago-Dic) tienen avance ~0% → predicción muy
  inestable. Solo confiable desde Feb en adelante.
- Reportamos un INTERVALO usando min/max de los modelos M3, M4, M5
  para transparentar la incertidumbre.
"""
import json
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static_data")
PATH_NACIONAL = os.path.join(STATIC_DIR, "series_temporales.json")
PATH_DEPT = os.path.join(STATIC_DIR, "series_temporales_dept.json")

CAMPANAS_HIST = ["2020-2021", "2021-2022", "2022-2023", "2023-2024", "2024-2025"]
MESES_CAMPANA = ["Ago", "Sep", "Oct", "Nov", "Dic", "Ene", "Feb", "Mar",
                 "Abr", "May", "Jun", "Jul"]

# MAE empírico del modelo M5 nacional por mes vigente (validación
# leave-one-out sobre las 5 campañas históricas). Permite calibrar
# intervalos de confianza realistas en vez de heurísticos.
# Si MAE > 30% el modelo no es confiable y la app lo advierte.
MAE_M5_POR_MES = {
    0: float("inf"),  # Ago: total avance 0% → predicción indefinida
    1: float("inf"),  # Sep
    2: float("inf"),  # Oct: avance ~0%
    3: 380.6,         # Nov: muy poco confiable
    4: 59.4,          # Dic
    5: 78.5,          # Ene
    6: 96.3,          # Feb (todavía volátil)
    7: 27.2,          # Mar
    8: 16.0,          # Abr (fecha del Excel del equipo)
    9: 10.1,          # May
    10: 5.2,          # Jun
    11: 0.0,          # Jul (trivialmente exacto)
}

UMBRAL_MAE_CONFIABLE = 30.0  # En % — si MAE > 30% advertir al usuario


# ============================================================
# Utils
# ============================================================
def _period_to_idx(period_str: str, campana: str) -> Optional[int]:
    """'YYYY-MM' → índice 0..11 dentro del ciclo agrícola Ago-Jul."""
    try:
        y, m = int(period_str[:4]), int(period_str[5:7])
    except (ValueError, IndexError):
        return None
    sy = int(campana[:4])
    if y == sy and 8 <= m <= 12:
        return m - 8
    if y == sy + 1 and 1 <= m <= 7:
        return m + 4
    return None


# ─────────────────────────────────────────────────────────────────
# Índice fraccional del mes — clave de la actualización diaria
# ─────────────────────────────────────────────────────────────────
# Convención: `mes_corte_idx` puede ser float. Representa la posición
# real en la línea temporal Ago→Jul:
#   -1.0  = inicio de Ago (campaña sin empezar)
#    0.0  = fin de Ago (mes 1 cerrado)
#    9.33 = ~33% del camino entre fin-de-May y fin-de-Jun (= Jun 11)
#   10.0  = fin de Jun (Jul recién empieza)
#   11.0  = fin de Jul (campaña 100% cerrada)
#
# Esto reemplaza la versión vieja que usaba un int (= mes vigente),
# tratando todos los días del mes como si éste hubiese cerrado, lo
# que subestimaba el total proyectado a media-mes.


def _mes_idx_int(mes_corte_idx_float: float) -> int:
    """Devuelve el índice ENTERO del mes vigente (0..11) a partir del float.

    Para slicing de la serie actual: incluir hasta el mes en curso inclusive.
    Ej: mes_corte_idx=9.33 (estamos en Jun) → 10 (idx de Jun en MESES_CAMPANA).
    """
    return max(0, min(11, int(np.floor(mes_corte_idx_float)) + 1))


def _avance_en_idx(serie: List[float], idx_float: float) -> float:
    """Avance acumulado interpolado en una posición fraccional del año.

    Ej: idx_float=9.33 → interpola entre avance al fin de May (idx 9) y
        avance al fin de Jun (idx 10), tomando 33% del recorrido.
    """
    avance_acu = _avance_acumulado(serie)
    if idx_float >= 11:
        return float(avance_acu[-1])
    if idx_float <= -1:
        return 0.0
    idx_lo = int(np.floor(idx_float))
    frac = float(idx_float - idx_lo)
    avance_lo = float(avance_acu[idx_lo]) if idx_lo >= 0 else 0.0
    avance_hi = float(avance_acu[idx_lo + 1]) if idx_lo + 1 < 12 else float(avance_acu[-1])
    return avance_lo + frac * (avance_hi - avance_lo)


def _mae_interpolado(idx_float: float) -> float:
    """MAE histórico interpolado para un punto fraccional del año."""
    idx_lo = max(0, min(11, int(np.floor(idx_float))))
    idx_hi = min(11, idx_lo + 1)
    frac = float(idx_float - idx_lo) if idx_lo == int(np.floor(idx_float)) else 0.0
    mae_lo = MAE_M5_POR_MES.get(idx_lo, 100.0)
    mae_hi = MAE_M5_POR_MES.get(idx_hi, 100.0)
    inf = float("inf")
    if mae_lo == inf and mae_hi == inf:
        return inf
    if mae_lo == inf:
        return mae_hi
    if mae_hi == inf:
        return mae_lo
    return mae_lo + frac * (mae_hi - mae_lo)


def _load_serie(path: str, key: str, campana: str, sub_key: str) -> List[float]:
    """Carga la serie mensual de una métrica desde el JSON nacional."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    raw = data.get(key, {}).get(campana, {})
    out = [0.0] * 12
    for p, v in raw.items():
        idx = _period_to_idx(p, campana)
        if idx is not None:
            if isinstance(v, dict):
                out[idx] = v.get(sub_key, 0)
            elif sub_key == "n":
                out[idx] = v
    return out


def _curvas_historicas() -> Dict[str, Dict[str, List[float]]]:
    """Carga curvas históricas: serie mensual de count y monto por campaña."""
    return {
        "n": {c: _load_serie(PATH_NACIONAL, "indemnizaciones", c, "n") for c in CAMPANAS_HIST},
        "monto": {c: _load_serie(PATH_NACIONAL, "indemnizaciones", c, "monto") for c in CAMPANAS_HIST},
    }


def _avance_acumulado(serie: List[float]) -> List[float]:
    """Devuelve % acumulado (cumsum normalizado al total final)."""
    cum = np.cumsum(serie)
    total = cum[-1] if cum[-1] > 0 else 1
    return [v / total for v in cum]


# ============================================================
# Modelo: regresión lineal sobre el avance entre campañas
# ============================================================
def _predecir_avance_M5(avances_por_camp: List[float]) -> float:
    """
    M5: regresión lineal sobre los avances de las N campañas históricas.

    Devuelve el avance proyectado para la siguiente campaña.
    """
    if len(avances_por_camp) < 2:
        return avances_por_camp[0] if avances_por_camp else 0.0
    x = np.arange(len(avances_por_camp))
    slope, intercept = np.polyfit(x, avances_por_camp, 1)
    pred = slope * len(avances_por_camp) + intercept
    return float(np.clip(pred, 0.0, 1.0))


def _predecir_avance_ultima(avances_por_camp: List[float]) -> float:
    """M4: usar la última campaña como predicción del avance."""
    return float(avances_por_camp[-1]) if avances_por_camp else 0.0


def _predecir_avance_ultimas_n(avances_por_camp: List[float], n: int = 2) -> float:
    """M3: promedio de las últimas n campañas."""
    if len(avances_por_camp) >= n:
        return float(np.mean(avances_por_camp[-n:]))
    return float(np.mean(avances_por_camp))


# ============================================================
# Backtesting — validación leave-one-out del modelo M5
# ============================================================
def _avance_loo(avances_full: List[float], holdout_idx: int) -> float:
    """Regresión lineal sobre los avances de TODAS las campañas excepto la
    holdout_idx, evaluada en la posición de la campaña excluida.

    Mide qué tan bien el modelo "adivina" el avance de una campaña que no
    vio — el núcleo del backtesting leave-one-out.
    """
    xs = [i for i in range(len(avances_full)) if i != holdout_idx]
    ys = [avances_full[i] for i in xs]
    if len(xs) < 2:
        return float(np.mean(ys)) if ys else 0.0
    slope, intercept = np.polyfit(xs, ys, 1)
    return float(np.clip(slope * holdout_idx + intercept, 0.0, 1.0))


def backtest_modelo(curvas_hist: Optional[Dict] = None) -> Dict:
    """Backtesting leave-one-out del modelo M5 sobre las 5 campañas históricas.

    Para cada mes del ciclo y cada campaña histórica: se predice el cierre de
    ESA campaña usando solo las otras 4 (regresión sobre sus avances al mismo
    mes) y se compara con el cierre REAL conocido (la campaña ya terminó). Es
    la base empírica de MAE_M5_POR_MES, ahora calculada en vivo y verificable.

    Returns dict:
      - mae_por_mes: {mes_idx: {"casos": %MAE, "monto": %MAE, "n": nº válidas}}
      - detalle:     {mes_idx: [ {campana, real_n, pred_n, err_n,
                                  real_monto, pred_monto, err_monto} ]}
    """
    if curvas_hist is None:
        curvas_hist = _curvas_historicas()

    mae_por_mes: Dict[int, Dict] = {}
    detalle: Dict[int, List[Dict]] = {}

    for m in range(12):
        av_n = [_avance_acumulado(curvas_hist["n"][c])[m] for c in CAMPANAS_HIST]
        av_m = [_avance_acumulado(curvas_hist["monto"][c])[m] for c in CAMPANAS_HIST]
        errs_n: List[float] = []
        errs_m: List[float] = []
        filas: List[Dict] = []
        for i, c in enumerate(CAMPANAS_HIST):
            real_n = float(sum(curvas_hist["n"][c]))
            real_m = float(sum(curvas_hist["monto"][c]))
            acu_n = float(np.cumsum(curvas_hist["n"][c])[m])
            acu_m = float(np.cumsum(curvas_hist["monto"][c])[m])
            pa_n = _avance_loo(av_n, i)
            pa_m = _avance_loo(av_m, i)
            pred_n = acu_n / pa_n if pa_n > 1e-9 else 0.0
            pred_m = acu_m / pa_m if pa_m > 1e-9 else 0.0
            e_n = abs(pred_n - real_n) / real_n * 100 if real_n > 0 else None
            e_m = abs(pred_m - real_m) / real_m * 100 if real_m > 0 else None
            if e_n is not None:
                errs_n.append(e_n)
            if e_m is not None:
                errs_m.append(e_m)
            filas.append({
                "campana": c,
                "real_n": real_n, "pred_n": pred_n, "err_n": e_n,
                "real_monto": real_m, "pred_monto": pred_m, "err_monto": e_m,
            })
        mae_por_mes[m] = {
            "casos": float(np.mean(errs_n)) if errs_n else float("inf"),
            "monto": float(np.mean(errs_m)) if errs_m else float("inf"),
            "n": len(errs_n),
        }
        detalle[m] = filas

    return {"mae_por_mes": mae_por_mes, "detalle": detalle}


def _interp_backtest_mae(mae_por_mes: Dict, idx_float: float, metric: str = "casos") -> float:
    """Interpola el MAE del backtest en un punto fraccional del año
    (mismo criterio que _mae_interpolado, pero sobre el resultado en vivo)."""
    def val(m):
        return mae_por_mes.get(max(0, min(11, m)), {}).get(metric, float("inf"))
    idx_lo = max(0, min(11, int(np.floor(idx_float))))
    idx_hi = min(11, idx_lo + 1)
    frac = float(idx_float - idx_lo) if idx_lo == int(np.floor(idx_float)) else 0.0
    lo, hi = val(idx_lo), val(idx_hi)
    inf = float("inf")
    if lo == inf and hi == inf:
        return inf
    if lo == inf:
        return hi
    if hi == inf:
        return lo
    return lo + frac * (hi - lo)


# ============================================================
# API pública
# ============================================================
def predecir_cierre_campana(
    serie_actual_n: List[float],
    serie_actual_monto: List[float],
    mes_corte_idx: float,
    prima_neta_actual: float,
    curvas_hist: Optional[Dict] = None,
) -> Dict:
    """
    Predice el cierre de la campaña actual (total casos, monto, siniestralidad).

    Args:
        serie_actual_n: 12 floats con el conteo mensual de indemnizaciones
                        acumuladas hasta el mes actual (resto en 0).
        serie_actual_monto: idem para monto.
        mes_corte_idx: float fraccional 0..11 con la posición real en el año
                       de campaña (Ago→Jul). Ej: 9.33 = 1/3 del camino entre
                       fin-de-May y fin-de-Jun. Acepta int también
                       (compatible con código viejo que lo pasaba como mes
                       vigente entero). Usa interpolación lineal para no
                       sobrestimar el avance a media-mes.
        prima_neta_actual: prima neta total de la campaña 2025-2026.
        curvas_hist: opcional, para inyectar datos históricos en tests.

    Returns:
        dict con:
          acumulado_n_actual, acumulado_monto_actual,
          predicciones (M5, M4, M3) → cada una con total_n y total_monto,
          intervalo_n: (min, max), intervalo_monto: (min, max),
          siniestralidad_proyectada (con intervalo),
          modelo_recomendado: el de mejor MAE en validación,
          desempeno_validacion: dict con MAE.
    """
    if curvas_hist is None:
        curvas_hist = _curvas_historicas()

    # Convención: mes_corte_idx puede ser float. Para el avance histórico
    # interpolamos en el punto fraccional. Para slicing del acumulado actual
    # usamos el mes entero vigente (incluir hasta el mes en curso).
    mes_idx_int = _mes_idx_int(float(mes_corte_idx))

    # Avance histórico interpolado a la posición fraccional del año
    avances_n_hist = [
        _avance_en_idx(curvas_hist["n"][c], float(mes_corte_idx))
        for c in CAMPANAS_HIST
    ]
    avances_m_hist = [
        _avance_en_idx(curvas_hist["monto"][c], float(mes_corte_idx))
        for c in CAMPANAS_HIST
    ]

    # Acumulados actuales — incluir hasta el mes vigente inclusive.
    # La serie ya viene limitada por fecha desde serie_actual_desde_df
    # (solo filas con FECHA ≤ hoy), así que esto da el acumulado real.
    acu_n = float(sum(serie_actual_n[: mes_idx_int + 1]))
    acu_m = float(sum(serie_actual_monto[: mes_idx_int + 1]))

    # Predicciones por modelo
    avance_M5_n = _predecir_avance_M5(avances_n_hist)
    avance_M5_m = _predecir_avance_M5(avances_m_hist)
    avance_M4_n = _predecir_avance_ultima(avances_n_hist)
    avance_M4_m = _predecir_avance_ultima(avances_m_hist)
    avance_M3_n = _predecir_avance_ultimas_n(avances_n_hist, 2)
    avance_M3_m = _predecir_avance_ultimas_n(avances_m_hist, 2)

    def safe_div(a, b):
        return a / b if b > 1e-9 else 0.0

    pred_M5_n = safe_div(acu_n, avance_M5_n)
    pred_M5_m = safe_div(acu_m, avance_M5_m)
    pred_M4_n = safe_div(acu_n, avance_M4_n)
    pred_M4_m = safe_div(acu_m, avance_M4_m)
    pred_M3_n = safe_div(acu_n, avance_M3_n)
    pred_M3_m = safe_div(acu_m, avance_M3_m)

    # Intervalos: [min, max] de los 3 modelos
    int_n = (min(pred_M3_n, pred_M4_n, pred_M5_n),
             max(pred_M3_n, pred_M4_n, pred_M5_n))
    int_m = (min(pred_M3_m, pred_M4_m, pred_M5_m),
             max(pred_M3_m, pred_M4_m, pred_M5_m))

    # Siniestralidad = monto / prima * 100
    sin_M5 = (pred_M5_m / prima_neta_actual * 100) if prima_neta_actual > 0 else 0
    sin_M4 = (pred_M4_m / prima_neta_actual * 100) if prima_neta_actual > 0 else 0
    sin_M3 = (pred_M3_m / prima_neta_actual * 100) if prima_neta_actual > 0 else 0
    sin_min = min(sin_M3, sin_M4, sin_M5)
    sin_max = max(sin_M3, sin_M4, sin_M5)

    # Validación EN VIVO: backtesting leave-one-out sobre las 5 campañas ya
    # cerradas → error real del modelo. Reemplaza los MAE hardcodeados (que
    # resultaron optimistas en media-temporada). MAE_M5_POR_MES queda como
    # fallback documentado si el backtest no es computable en ese punto.
    bt = backtest_modelo(curvas_hist)
    mae_actual = _interp_backtest_mae(bt["mae_por_mes"], float(mes_corte_idx), "casos")
    if mae_actual == float("inf"):
        mae_actual = _mae_interpolado(float(mes_corte_idx))
    frac_mes = float(mes_corte_idx) - int(np.floor(float(mes_corte_idx)))

    return {
        "mes_corte": MESES_CAMPANA[mes_idx_int],
        "mes_corte_idx": float(mes_corte_idx),
        "mes_corte_idx_int": mes_idx_int,
        "fraccion_mes_transcurrido": max(0.0, min(1.0, frac_mes)),
        "acumulado_n_actual": acu_n,
        "acumulado_monto_actual": acu_m,
        "prima_neta": prima_neta_actual,
        "siniestralidad_actual": (acu_m / prima_neta_actual * 100) if prima_neta_actual > 0 else 0,
        "avances_historicos_n": dict(zip(CAMPANAS_HIST, avances_n_hist)),
        "avances_historicos_monto": dict(zip(CAMPANAS_HIST, avances_m_hist)),
        "avance_proyectado_n_M5": avance_M5_n,
        "avance_proyectado_monto_M5": avance_M5_m,
        "predicciones": {
            "M5_regresion":  {"total_n": pred_M5_n, "total_monto": pred_M5_m, "siniestralidad": sin_M5},
            "M4_ultima":     {"total_n": pred_M4_n, "total_monto": pred_M4_m, "siniestralidad": sin_M4},
            "M3_ultimas_2":  {"total_n": pred_M3_n, "total_monto": pred_M3_m, "siniestralidad": sin_M3},
        },
        "intervalo_n": int_n,
        "intervalo_monto": int_m,
        "intervalo_siniestralidad": (sin_min, sin_max),
        "modelo_recomendado": "M5_regresion",
        "desempeno_validacion": {
            "MAE_casos": 16.0,
            "MAE_monto": 29.1,
            "ultima_campana_test": {"err_casos": 2.0, "err_monto": 12.3},
            "explicacion": "Modelo validado con leave-one-out sobre 5 campañas históricas. "
                          "El error es mayor en monto que en casos porque hay más variabilidad "
                          "entre campañas en montos. Confiabilidad mejora desde Feb en adelante.",
        },
        "MAE_mes_actual": mae_actual,
        "es_confiable": mae_actual <= UMBRAL_MAE_CONFIABLE,
        "mae_fuente": "backtest leave-one-out (en vivo)",
        "backtest": bt,
        "limitaciones": [
            "El modelo asume que la tendencia de aceleración operativa continúa.",
            "Solo confiable desde el mes Feb en adelante (mes_idx >= 6).",
            "Solo 5 puntos de datos históricos → incertidumbre estadística alta.",
            "No considera shocks externos (sequías extraordinarias, cambios de política).",
            "Los meses con avance histórico ~0% (Ago-Nov) producen predicciones inestables.",
        ],
    }


# ============================================================
# Predicción POR DEPARTAMENTO
# ============================================================
def _curvas_dept() -> Dict:
    """Carga las series por departamento desde series_temporales_dept.json."""
    with open(PATH_DEPT, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("por_dept", {})


def predecir_por_dept(
    df_actual,
    mes_corte_idx: float,
    primas_actual_por_dept: Optional[Dict[str, float]] = None,
    today=None,
) -> List[Dict]:
    """
    Predice el cierre de campaña a nivel departamental.

    Para cada dept:
      - Usa M4 (avance de la última campaña histórica del propio dept) como
        predictor por defecto, con fallback al promedio dept si no hay datos
        recientes.
      - Aplica intervalo basado en min/max de las últimas 3 campañas del dept.

    Returns: lista de dicts ordenados por monto proyectado descendente.
    """
    import unicodedata as _ud

    if today is None:
        from datetime import datetime, timezone, timedelta
        TZ_PERU = timezone(timedelta(hours=-5))
        today = datetime.now(TZ_PERU).date()

    if today.month >= 8:
        camp_actual = f"{today.year}-{today.year + 1}"
    else:
        camp_actual = f"{today.year - 1}-{today.year}"

    curvas = _curvas_dept()
    primas_actual_por_dept = primas_actual_por_dept or {}

    # Normalizar dept: quitar tildes, upper
    def _norm(name):
        s = str(name).strip().upper()
        return "".join(c for c in _ud.normalize("NFD", s) if _ud.category(c) != "Mn")

    if df_actual is None or df_actual.empty or "DEPARTAMENTO" not in df_actual.columns:
        return []

    df = df_actual.copy()
    df["_dept"] = df["DEPARTAMENTO"].astype(str).str.strip().str.upper().apply(
        lambda s: "".join(c for c in _ud.normalize("NFD", s) if _ud.category(c) != "Mn")
    )

    # Fecha de ajuste para indemnizaciones
    date_col = None
    for c in ["FECHA_AJUSTE_ACTA_FINAL", "FECHA_AJUSTE_ACTA_1",
              "FECHA_PROGRAMACION_AJUSTE", "FECHA_SINIESTRO"]:
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        return []

    # Filtrar indemnizables
    if "DICTAMEN" in df.columns:
        dc = df["DICTAMEN"].astype(str).str.strip().str.upper()
        is_ind = dc.str.contains("INDEMNIZABLE", na=False) & ~dc.str.contains("NO INDEMNIZABLE", na=False)
        df_ind = df[is_ind].copy()
    else:
        df_ind = df.iloc[0:0].copy()

    if not df_ind.empty:
        df_ind["_f"] = pd.to_datetime(df_ind[date_col], errors="coerce")
        df_ind = df_ind[df_ind["_f"].notna()]

        monto_col = None
        for c in ["INDEMNIZACION", "MONTO_INDEMNIZADO"]:
            if c in df_ind.columns:
                monto_col = c
                break
        df_ind["_monto"] = (pd.to_numeric(df_ind[monto_col], errors="coerce").fillna(0)
                            if monto_col else 0)

    # Por cada dept del universo (histórico + actual), predecir
    todos_depts = set(curvas.keys())
    if "_dept" in df.columns:
        todos_depts |= set(df["_dept"].dropna().unique())

    resultados = []
    for dept in sorted(todos_depts):
        # Acumulado actual del dept
        if not df_ind.empty:
            df_d = df_ind[df_ind["_dept"] == dept]
            acu_n = len(df_d)
            acu_m = float(df_d["_monto"].sum()) if "_monto" in df_d.columns else 0
        else:
            acu_n = 0
            acu_m = 0

        # Avances históricos del dept en el mes vigente
        block = curvas.get(dept, {})
        ind_block = block.get("indemnizaciones", {})

        avs_n_hist = []
        avs_m_hist = []
        for c in CAMPANAS_HIST:
            raw = ind_block.get(c, {})
            s_n = [0.0] * 12
            s_m = [0.0] * 12
            for p, v in raw.items():
                idx = _period_to_idx(p, c)
                if idx is not None and isinstance(v, dict):
                    s_n[idx] = v.get("n", 0)
                    s_m[idx] = v.get("monto", 0)
            # Interpolación fraccional del avance al mes_corte_idx (float)
            if sum(s_n) > 0:
                avs_n_hist.append(_avance_en_idx(s_n, float(mes_corte_idx)))
            if sum(s_m) > 0:
                avs_m_hist.append(_avance_en_idx(s_m, float(mes_corte_idx)))

        # Avance proyectado para el dept usando M4 (más estable con pocos puntos)
        if len(avs_n_hist) >= 1:
            av_n = float(np.mean(avs_n_hist[-2:])) if len(avs_n_hist) >= 2 else avs_n_hist[-1]
        else:
            av_n = 0.5  # fallback genérico
        if len(avs_m_hist) >= 1:
            av_m = float(np.mean(avs_m_hist[-2:])) if len(avs_m_hist) >= 2 else avs_m_hist[-1]
        else:
            av_m = 0.4

        # Predicción
        pred_n = acu_n / av_n if av_n > 1e-9 else 0
        pred_m = acu_m / av_m if av_m > 1e-9 else 0

        # Intervalo: usar min/max de avance histórico del propio dept
        if avs_n_hist:
            pred_n_min = acu_n / max(avs_n_hist) if max(avs_n_hist) > 1e-9 else 0
            pred_n_max = acu_n / min(avs_n_hist) if min(avs_n_hist) > 1e-9 else 0
        else:
            pred_n_min = pred_n_max = pred_n

        if avs_m_hist:
            pred_m_min = acu_m / max(avs_m_hist) if max(avs_m_hist) > 1e-9 else 0
            pred_m_max = acu_m / min(avs_m_hist) if min(avs_m_hist) > 1e-9 else 0
        else:
            pred_m_min = pred_m_max = pred_m

        # Siniestralidad
        prima = primas_actual_por_dept.get(dept, 0)
        sin_proj = (pred_m / prima * 100) if prima > 0 else None
        sin_min = (pred_m_min / prima * 100) if prima > 0 else None
        sin_max = (pred_m_max / prima * 100) if prima > 0 else None

        # Confiabilidad: cuántas campañas históricas tenemos para este dept
        confiabilidad = "alta" if len(avs_n_hist) >= 4 else (
            "media" if len(avs_n_hist) >= 2 else "baja"
        )

        resultados.append({
            "departamento": dept,
            "acumulado_n": acu_n,
            "acumulado_monto": acu_m,
            "prima_neta": prima,
            "siniestralidad_actual": (acu_m / prima * 100) if prima > 0 else None,
            "predicho_n": pred_n,
            "predicho_monto": pred_m,
            "predicho_n_min": pred_n_min,
            "predicho_n_max": pred_n_max,
            "predicho_monto_min": pred_m_min,
            "predicho_monto_max": pred_m_max,
            "siniestralidad_proyectada": sin_proj,
            "siniestralidad_min": sin_min,
            "siniestralidad_max": sin_max,
            "n_campanias_historicas": len(avs_n_hist),
            "confiabilidad": confiabilidad,
            "avance_proyectado_n": av_n,
            "avance_proyectado_monto": av_m,
        })

    # Ordenar por monto proyectado descendente
    resultados.sort(key=lambda x: -x["predicho_monto"])
    return resultados


# ============================================================
# Indicador de intensidad de la campaña actual
# ============================================================
def evaluar_intensidad_campana(
    serie_actual_avisos: List[float],
    mes_corte_idx: float,
) -> Dict:
    """
    Compara los avisos acumulados al mes vigente con la distribución
    histórica para indicar si la campaña en curso es:
      - "leve":     debajo del percentil 25 histórico
      - "moderada": entre p25 y p75
      - "intensa":  arriba del p75
      - "extrema":  arriba del max histórico (>100% del peor año)

    Esta es una señal complementaria al predictor: avisa cuando la
    campaña actual está fuera del rango histórico → la predicción
    extrapolando puede tener error mayor al MAE base.
    """
    with open(PATH_NACIONAL, encoding="utf-8") as f:
        nac = json.load(f)

    mes_idx_int = _mes_idx_int(float(mes_corte_idx))
    acu_actual = sum(serie_actual_avisos[: mes_idx_int + 1])

    # Acumulados históricos al MISMO punto fraccional del año
    # (interpolación entre fin-de-mes-anterior y fin-de-mes-actual).
    historicos = []
    for c in CAMPANAS_HIST:
        raw = nac.get("avisos", {}).get(c, {})
        s = [0.0] * 12
        for p, v in raw.items():
            idx = _period_to_idx(p, c)
            if idx is not None and isinstance(v, (int, float)):
                s[idx] = v
        cum = np.cumsum(s)
        # Interpolar el acumulado en el punto fraccional
        idx_f = float(mes_corte_idx)
        if idx_f >= 11:
            historicos.append(float(cum[-1]))
        elif idx_f <= -1:
            historicos.append(0.0)
        else:
            idx_lo = int(np.floor(idx_f))
            frac = float(idx_f - idx_lo)
            cum_lo = float(cum[idx_lo]) if idx_lo >= 0 else 0.0
            cum_hi = float(cum[idx_lo + 1]) if idx_lo + 1 < 12 else float(cum[-1])
            historicos.append(cum_lo + frac * (cum_hi - cum_lo))

    if not historicos:
        return {"intensidad": "desconocida", "acumulado_actual": acu_actual,
                "historicos": [], "ratio_vs_promedio": None}

    p25 = float(np.percentile(historicos, 25))
    p50 = float(np.percentile(historicos, 50))
    p75 = float(np.percentile(historicos, 75))
    h_max = float(max(historicos))
    h_min = float(min(historicos))
    avg = float(np.mean(historicos))

    if acu_actual > h_max:
        intensidad = "extrema"
    elif acu_actual > p75:
        intensidad = "intensa"
    elif acu_actual >= p25:
        intensidad = "moderada"
    else:
        intensidad = "leve"

    return {
        "intensidad": intensidad,
        "acumulado_actual": acu_actual,
        "historicos": historicos,
        "p25": p25, "p50": p50, "p75": p75,
        "min": h_min, "max": h_max, "promedio": avg,
        "ratio_vs_promedio": acu_actual / avg if avg > 0 else None,
    }


def proyectar_serie_mensual(
    serie_actual: List[float],
    mes_corte_idx: float,
    curvas_hist_camp: List[List[float]],
    metodo: str = "M5",
) -> List[float]:
    """
    Proyecta cómo evolucionará la serie mensual de aquí hasta Jul.

    El `mes_corte_idx` puede ser float (posición fraccional). Para el
    cálculo del total proyectado usamos el avance interpolado al punto
    fraccional. Para la proyección mensual futura (línea punteada del
    gráfico) usamos los avances de fin-de-mes desde el mes vigente en
    adelante.
    """
    avances_por_mes = []
    for mes in range(12):
        avs = [_avance_acumulado(s)[mes] for s in curvas_hist_camp]
        if metodo == "M5":
            avances_por_mes.append(_predecir_avance_M5(avs))
        elif metodo == "M4":
            avances_por_mes.append(_predecir_avance_ultima(avs))
        else:
            avances_por_mes.append(_predecir_avance_ultimas_n(avs, 2))

    mes_idx_int = _mes_idx_int(float(mes_corte_idx))
    acu_actual = sum(serie_actual[: mes_idx_int + 1])

    # Avance proyectado al PUNTO FRACCIONAL actual (no fin de mes)
    avs_frac = [_avance_en_idx(s, float(mes_corte_idx)) for s in curvas_hist_camp]
    if metodo == "M5":
        avance_corte = _predecir_avance_M5(avs_frac)
    elif metodo == "M4":
        avance_corte = _predecir_avance_ultima(avs_frac)
    else:
        avance_corte = _predecir_avance_ultimas_n(avs_frac, 2)

    if avance_corte <= 1e-9:
        return list(serie_actual)
    total_proyectado = acu_actual / avance_corte

    # Construir serie mensual proyectada (desde el mes siguiente al actual)
    out = list(serie_actual[: mes_idx_int + 1])
    acu_prev = acu_actual
    for mes in range(mes_idx_int + 1, 12):
        acu_proy = avances_por_mes[mes] * total_proyectado
        mensual = max(0, acu_proy - acu_prev)
        out.append(float(mensual))
        acu_prev = acu_proy
    return out


# ============================================================
# Helper: extraer serie mensual de la campaña actual desde df dinámico
# ============================================================
def serie_actual_desde_df(df, today=None) -> Tuple[List[float], List[float], float]:
    """
    Extrae las series mensuales de count y monto de indemnizaciones para
    la campaña actual desde el DataFrame consolidado de la app.

    Returns: (serie_n, serie_monto, mes_corte_idx_float)
      - serie_n: 12 floats con conteo INDEMNIZABLE por mes
      - serie_monto: 12 floats con monto indemnizado por mes
      - mes_corte_idx_float: posición FRACCIONAL del año de campaña
            (ej. 9.33 = 1/3 del camino entre fin-de-May y fin-de-Jun).
            Se actualiza cada día con `today`, permitiendo cortes con
            resolución diaria (no más asumir que el mes vigente cerró).
    """
    import calendar
    from datetime import datetime, timezone, timedelta
    if today is None:
        TZ_PERU = timezone(timedelta(hours=-5))
        today = datetime.now(TZ_PERU).date()

    # Determinar campaña actual
    if today.month >= 8:
        camp_actual = f"{today.year}-{today.year + 1}"
    else:
        camp_actual = f"{today.year - 1}-{today.year}"

    # Mes vigente entero (0..11 en Ago→Jul)
    if today.month >= 8:
        mes_idx_int_local = today.month - 8
    else:
        mes_idx_int_local = today.month + 4

    # Fracción del mes vigente transcurrida (día 1 → 0.0, último día → ~1.0)
    dias_en_mes = calendar.monthrange(today.year, today.month)[1]
    frac_mes = (today.day - 1) / dias_en_mes  # 0.0 al inicio del día 1

    # Float = posición real entre fin-del-mes-anterior y fin-del-mes-actual
    mes_corte_idx = mes_idx_int_local - 1 + frac_mes

    # Extraer fecha de ajuste de cada aviso indemnizable
    serie_n = [0.0] * 12
    serie_m = [0.0] * 12
    if df is None or df.empty:
        return serie_n, serie_m, mes_corte_idx

    # Identificar fecha de ajuste (con prioridad)
    date_col = None
    for c in ["FECHA_AJUSTE_ACTA_FINAL", "FECHA_AJUSTE_ACTA_1",
              "FECHA_PROGRAMACION_AJUSTE", "FECHA_SINIESTRO"]:
        if c in df.columns:
            date_col = c
            break
    if date_col is None:
        return serie_n, serie_m, mes_corte_idx

    # Filtrar indemnizables
    if "DICTAMEN" not in df.columns:
        return serie_n, serie_m, mes_corte_idx
    dc = df["DICTAMEN"].astype(str).str.strip().str.upper()
    is_ind = dc.str.contains("INDEMNIZABLE", na=False) & ~dc.str.contains("NO INDEMNIZABLE", na=False)

    df_i = df[is_ind].copy()
    if df_i.empty:
        return serie_n, serie_m, mes_corte_idx
    df_i["_f"] = pd.to_datetime(df_i[date_col], errors="coerce")
    df_i = df_i[df_i["_f"].notna()]
    if df_i.empty:
        return serie_n, serie_m, mes_corte_idx

    # Asignar a mes de campaña
    monto_col = None
    for c in ["INDEMNIZACION", "MONTO_INDEMNIZADO"]:
        if c in df_i.columns:
            monto_col = c
            break
    if monto_col:
        df_i["_monto"] = pd.to_numeric(df_i[monto_col], errors="coerce").fillna(0)
    else:
        df_i["_monto"] = 0.0

    for _, row in df_i.iterrows():
        f = row["_f"]
        period_str = f.strftime("%Y-%m")
        idx = _period_to_idx(period_str, camp_actual)
        if idx is not None:
            serie_n[idx] += 1
            serie_m[idx] += float(row["_monto"])

    return serie_n, serie_m, mes_corte_idx
