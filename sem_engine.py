"""
sem_engine.py — Motor del Semáforo de Alertas SAC (rewrite)

Implementa las 6 alertas independientes (ALERTA 01..06) según las reglas
oficiales del equipo SAC. Cada aviso recibe 6 evaluaciones: cada alerta
tiene su propio color y string descriptivo.

Reglas resumidas (ver semaforo_alertas.py:render_semaforo_tab para UI):

REGLA TRANSVERSAL (aplica a todas las alertas):
  - Si DUPLICIDAD == REPETIDO o OBSERVACION contiene REPETIDO:
       todas las 6 alertas = "ALERTA ATENCION OK"
  - Si OBSERVACION contiene NUL: idem
  - Si OBSERVACION contiene SIN COBERTURA: alertas 02-06 = "ALERTA ATENCION OK"
    (la 01 sí se evalúa)

ALERTA 01 ATENCION:
  - Con FECHA_ATENCION:
      d = (atencion - aviso).days, formato "ATENCION OK (d días)" si d <= 10
      "ALERTA ROJA CON ATENCION (d días)" si d > 10
  - Sin FECHA_ATENCION:
      d = (today - aviso).days
      1-6 → ALERTA VERDE SIN ATENCION (d días)
      7-10 → ALERTA AMBAR SIN ATENCION (d días)
      >10 → ALERTA ROJA SIN ATENCION (d días)

ALERTA 02 PROGRAMACION:
  - Si OBSERVACION contiene PROG → "NO EVALUADO (PROG)"
  - Si tiene FECHA_AJUSTE_ACTA_1 → "ATENCION OK CON AJUSTE"
  - Si tiene FECHA_PROGRAMACION_AJUSTE (sin acta1):
      d = (today - prog).days  o  (prog - aviso).days  (revisar empíricamente)
      1-11 verde, 12-15 ámbar, >15 rojo → "ALERTA <X> CON PROGRAMACION (d días)"
  - Sin FECHA_PROGRAMACION_AJUSTE:
      d = (today - aviso).days
      Mismos rangos → "ALERTA <X> SIN PROGRAMACION (d días)"

ALERTA 03 AJUSTE:
  - Si OBSERVACION contiene PROG o SIN COBERTURA → "ALERTA ATENCION OK"
  - Si tiene FECHA_AJUSTE_ACTA_1:
      d = (acta1 - aviso).days, formato "AJUSTE OK (d días)"
      Si d > 15 → "ALERTA ROJA CON AJUSTE 01 (d días)"
  - Sin FECHA_AJUSTE_ACTA_1 (con o sin programación):
      d = (today - aviso).days
      1-11 verde, 12-14 ámbar, >15 rojo
      Distinguir SIN AJUSTE 01 SIN PROG vs SIN AJUSTE 01 (con prog)

ALERTA 04 REPROGRAMACION:
  - Si tiene FECHA_AJUSTE_ACTA_FINAL → "ATENCION OK AJUSTE FINAL"
  - Si NO tiene reprog 01/02/03 → "REPROGRAMACION OK"
  - Si tiene reprog (1, 2 o 3 — el más alto):
      d = (reprog - today).days  (cuántos días faltan)
      Si d > 0 (futura): si d <= 7 → ALERTA AMBAR CON REPROGRAMACION 0X (d días)
      Si d <= 0 (pasada): ALERTA ROJA CON REPROGRAMACION 0X
  - Caso especial: ESTADO_INSPECCION == "REPROGRAMADO" sin reprog 01:
      "ALERTA ROJA SIN REPROGRAMACION 01"

ALERTA 05 PADRON Y VALIDACION:
  - Solo aplica si DICTAMEN == "INDEMNIZABLE" y FECHA_AJUSTE_ACTA_FINAL existe.
  - Sin envío DRAS:
      d = (today - acta_final).days
      1-15 verde, 16-20 ámbar, >20 rojo → "ALERTA <X> SIN PADRON (d días)"
  - Con envío DRAS, sin validación:
      d = (today - envio).days
      1-6 verde, 7-15 ámbar, >15 rojo → "ALERTA <X> SIN VALIDACION (d días)"
  - Con validación → "ATENCION OK CON VALIDACION (d días)"

ALERTA 06 PAGO SAC:
  - Solo aplica si DICTAMEN == "INDEMNIZABLE" y FECHA_VALIDACION existe.
  - Días HÁBILES (excluir sáb/dom y feriados Perú).
  - Sin pago: 1-11 verde, 12-15 ámbar, >15 rojo
  - Con pago: d = (pago - validacion).days_habiles, "ATENCION OK CON PAGO (d días)"
"""
from datetime import date
from typing import Optional, Tuple

import numpy as np
import pandas as pd


# ============================================================
# Feriados Perú (lista mínima — extender según necesidad)
# Fuente: feriados nacionales calendario peruano
# ============================================================
FERIADOS_PERU_2025 = [
    "2025-01-01",  # Año Nuevo
    "2025-04-17",  # Jueves Santo
    "2025-04-18",  # Viernes Santo
    "2025-05-01",  # Día del Trabajo
    "2025-06-07",  # Batalla de Arica y Día de la Bandera
    "2025-06-29",  # San Pedro y San Pablo
    "2025-07-23",  # Día de la Fuerza Aérea
    "2025-07-28",  # Día de la Independencia
    "2025-07-29",  # Día de la Independencia
    "2025-08-06",  # Batalla de Junín
    "2025-08-30",  # Santa Rosa de Lima
    "2025-10-08",  # Combate de Angamos
    "2025-11-01",  # Día de Todos los Santos
    "2025-12-08",  # Inmaculada Concepción
    "2025-12-09",  # Batalla de Ayacucho
    "2025-12-25",  # Navidad
]
FERIADOS_PERU_2026 = [
    "2026-01-01",
    "2026-04-02",  # Jueves Santo
    "2026-04-03",  # Viernes Santo
    "2026-05-01",
    "2026-06-07",
    "2026-06-29",
    "2026-07-23",
    "2026-07-28",
    "2026-07-29",
    "2026-08-06",
    "2026-08-30",
    "2026-10-08",
    "2026-11-01",
    "2026-12-08",
    "2026-12-09",
    "2026-12-25",
]
FERIADOS_PERU = pd.to_datetime(FERIADOS_PERU_2025 + FERIADOS_PERU_2026).normalize()
_FERIADOS_NP = FERIADOS_PERU.values.astype("datetime64[D]")


# ============================================================
# Helpers
# ============================================================
def _safe_dt(df, col):
    """Devuelve la columna como datetime64; NaT si no existe."""
    if col in df.columns:
        return pd.to_datetime(df[col], errors="coerce")
    return pd.Series(pd.NaT, index=df.index)


def _safe_str(df, col):
    """Devuelve la columna como string upper-strip; vacío si no existe."""
    if col in df.columns:
        return df[col].astype(str).str.strip().str.upper().fillna("")
    return pd.Series("", index=df.index)


def _days_calendar(b, a):
    """Días calendario b - a, NaN-safe. Retorna float."""
    return (b - a).dt.days


def _days_hab(b, a):
    """Días hábiles entre a y b (excluyendo sáb, dom y feriados Perú).
    Retorna Series de int. NaN si alguna fecha es NaT.
    """
    out = pd.Series(np.nan, index=b.index, dtype="float64")
    mask = b.notna() & a.notna()
    if mask.sum() == 0:
        return out
    a_arr = a[mask].dt.normalize().values.astype("datetime64[D]")
    b_arr = b[mask].dt.normalize().values.astype("datetime64[D]")
    # numpy.busday_count: cuenta días hábiles desde a (incluido) hasta b (excluido)
    res = np.busday_count(a_arr, b_arr, holidays=_FERIADOS_NP)
    out.loc[mask] = res
    return out


# ============================================================
# Detección de banderas transversales
# ============================================================
def _detect_flags(df):
    """Devuelve un dict de Series booleanas con las banderas que activan
    'ALERTA ATENCION OK' en alguna o todas las alertas.
    """
    obs = _safe_str(df, "OBSERVACION") if "OBSERVACION" in df.columns else pd.Series("", index=df.index)

    # DUPLICIDAD: buscar columna que contenga 'DUPLIC' (e.g. DUPLIC RESULT, DUPLICIDAD)
    dup_col = None
    for c in df.columns:
        cu = str(c).upper()
        if "DUPLIC" in cu and "SINTAXIS" not in cu:
            dup_col = c
            break
    if dup_col:
        dup_val = df[dup_col].astype(str).str.upper().fillna("")
        is_repetido_dup = dup_val.str.contains("REPETIDO", na=False)
    else:
        is_repetido_dup = pd.Series(False, index=df.index)

    is_repetido_obs = obs.str.contains("REPETIDO", na=False)
    is_nul = obs.str.contains("NUL", na=False) & ~obs.str.contains("ANULAD", na=False)
    is_sin_cobertura = obs.str.contains("SIN COBERTURA", na=False)
    is_prog = obs.str.contains("PROG", na=False)
    is_acta_obs = obs.str.contains("ACTA OBS", na=False)

    return {
        "atencion_ok_all": is_repetido_dup | is_repetido_obs | is_nul,
        "atencion_ok_2_to_6": is_sin_cobertura,
        "is_prog": is_prog,
        "is_acta_obs": is_acta_obs,
        "obs": obs,
    }


# ============================================================
# ALERTA 01: ATENCION
# ============================================================
def alerta_01_atencion(df, today, flags):
    """
    Devuelve (texto, semaforo) para ALERTA 01.
    """
    n = len(df)
    aviso = _safe_dt(df, "FECHA_AVISO")
    atencion = _safe_dt(df, "FECHA_ATENCION")

    # Días con atención: calendar(atencion - aviso)
    d_con = _days_calendar(atencion, aviso)
    # Días sin atención: calendar(today - aviso)
    d_sin = (today - aviso).dt.days

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    has_atn = atencion.notna()
    has_aviso = aviso.notna()

    # Sin atención
    sin_atn = has_aviso & ~has_atn
    d = d_sin.fillna(0).astype("Int64")
    # Verde 1-6, ámbar 7-10, rojo >10
    cond_v = sin_atn & (d <= 6)
    cond_a = sin_atn & (d >= 7) & (d <= 10)
    cond_r = sin_atn & (d > 10)

    texto = texto.where(~cond_v, "ALERTA VERDE SIN ATENCION (" + d.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v, 1.0)
    texto = texto.where(~cond_a, "ALERTA AMBAR SIN ATENCION (" + d.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a, 2.0)
    texto = texto.where(~cond_r, "ALERTA ROJA SIN ATENCION (" + d.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r, 3.0)

    # Con atención
    # Empíricamente: la fórmula de "días" en CON ATENCION es:
    #   max(networkdays_business(aviso, atencion), calendar_days)
    # Donde networkdays cuenta lun-vie inclusive.
    # Casos verificados:
    #   - AVISO=jue, ATEN=vie (cal=1, business=2): output 2 → max=2 ✓
    #   - AVISO=mié, ATEN=lun next (cal=5, business=4): output 5 → max=5 ✓
    #   - AVISO=vie, ATEN=lun next next (cal=10, business=7): output 7 → ¿?
    #   - Caso 7 no calza con max. Pero la mayoría sí. Iteramos.
    # Por ahora usamos calendario directo (sin offset) porque match es mayor que con +1.
    con_atn = has_aviso & has_atn
    dc = d_con.fillna(0).astype("Int64")
    # business days inclusive (cuenta ambos extremos)
    business = _days_hab(atencion, aviso) + 1  # busday_count es exclusivo del fin
    business = business.fillna(0).astype("Int64")
    dc_disp = pd.Series(np.where(business > dc, business, dc), index=df.index).astype("Int64")

    cond_ok = con_atn & (dc <= 10)
    cond_rj = con_atn & (dc > 10)

    texto = texto.where(~cond_ok, "ATENCION OK (" + dc_disp.astype(str) + " días)")
    # ATENCION OK no tiene semáforo (NaN según Excel)
    texto = texto.where(~cond_rj, "ALERTA ROJA CON ATENCION (" + dc_disp.astype(str) + " días)")
    semaforo = semaforo.where(~cond_rj, 3.0)

    # Banderas REPETIDO/NUL → "ALERTA ATENCION OK"
    flag_all = flags["atencion_ok_all"]
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)

    return texto, semaforo


# ============================================================
# ALERTA 02: PROGRAMACION
# ============================================================
def alerta_02_programacion(df, today, flags):
    n = len(df)
    aviso = _safe_dt(df, "FECHA_AVISO")
    prog = _safe_dt(df, "FECHA_PROGRAMACION_AJUSTE")
    acta1 = _safe_dt(df, "FECHA_AJUSTE_ACTA_1")

    has_acta1 = acta1.notna()
    has_prog = prog.notna()

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    # NO EVALUADO (PROG): observación con PROG (programado carta)
    is_prog_obs = flags["is_prog"]
    cond_no_eval = is_prog_obs & ~has_acta1
    texto = texto.where(~cond_no_eval, "NO EVALUADO (PROG)")

    # ATENCION OK CON AJUSTE: tiene acta1 → ya pasó programación
    cond_ok_ajuste = has_acta1 & ~cond_no_eval
    texto = texto.where(~cond_ok_ajuste, "ATENCION OK CON AJUSTE")

    # CON PROGRAMACION (sin ajuste, con prog)
    con_prog_sin_acta = has_prog & ~has_acta1 & ~cond_no_eval
    # Días empíricamente = business_inclusive(aviso, prog) - 1
    business_pa = (_days_hab(prog, aviso) + 1).fillna(0).astype("Int64")
    d_disp = business_pa - 1

    # Umbrales sobre el display (no sobre cal):
    # 1-11 verde, 12-15 ámbar, >15 rojo
    cond_v = con_prog_sin_acta & (d_disp <= 11)
    cond_a = con_prog_sin_acta & (d_disp >= 12) & (d_disp <= 15)
    cond_r = con_prog_sin_acta & (d_disp > 15)

    texto = texto.where(~cond_v, "ALERTA VERDE CON PROGRAMACION (" + d_disp.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v, 1.0)
    texto = texto.where(~cond_a, "ALERTA AMBAR CON PROGRAMACION (" + d_disp.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a, 2.0)
    texto = texto.where(~cond_r, "ALERTA ROJA CON PROGRAMACION (" + d_disp.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r, 3.0)

    # SIN PROGRAMACION (sin prog, sin acta)
    sin_prog = ~has_prog & ~has_acta1 & ~cond_no_eval
    # Empíricamente: d_excel = (today - aviso).days - 1
    d_ta_raw = (today - aviso).dt.days.fillna(0).astype("Int64")
    d_ta = d_ta_raw - 1

    cond_v2 = sin_prog & (d_ta <= 11)
    cond_a2 = sin_prog & (d_ta >= 12) & (d_ta <= 15)
    cond_r2 = sin_prog & (d_ta > 15)

    texto = texto.where(~cond_v2, "ALERTA VERDE SIN PROGRAMACION (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v2, 1.0)
    texto = texto.where(~cond_a2, "ALERTA AMBAR SIN PROGRAMACION (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a2, 2.0)
    texto = texto.where(~cond_r2, "ALERTA ROJA SIN PROGRAMACION (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r2, 3.0)

    # Banderas
    flag_all = flags["atencion_ok_all"] | flags["atencion_ok_2_to_6"]
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)

    return texto, semaforo


# ============================================================
# ALERTA 03: AJUSTE
# ============================================================
def alerta_03_ajuste(df, today, flags):
    aviso = _safe_dt(df, "FECHA_AVISO")
    prog = _safe_dt(df, "FECHA_PROGRAMACION_AJUSTE")
    acta1 = _safe_dt(df, "FECHA_AJUSTE_ACTA_1")

    has_prog = prog.notna()
    has_acta1 = acta1.notna()

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    # CON AJUSTE 01: días empíricamente = business_inclusive(aviso, acta1)
    # Sin offset adicional (probado: -1 empeoraba match).
    d_aa = _days_calendar(acta1, aviso).fillna(0).astype("Int64")
    business_aa_inc = _days_hab(acta1, aviso) + 1
    business_aa_inc = business_aa_inc.fillna(0).astype("Int64")
    d_aa_disp = business_aa_inc

    cond_ok = has_acta1 & (business_aa_inc <= 15)
    cond_rj = has_acta1 & (business_aa_inc > 15)

    texto = texto.where(~cond_ok, "AJUSTE OK (" + d_aa_disp.astype(str) + " días)")
    texto = texto.where(~cond_rj, "ALERTA ROJA CON AJUSTE 01 (" + d_aa_disp.astype(str) + " días)")
    semaforo = semaforo.where(~cond_rj, 3.0)

    # SIN AJUSTE 01: días = today - aviso
    d_ta = (today - aviso).dt.days.fillna(0).astype("Int64")
    sin_acta1 = ~has_acta1

    # SIN AJUSTE 01 SIN PROG (12-14 ambar) según reglas, los demás verde
    sin_acta_sin_prog = sin_acta1 & ~has_prog
    sin_acta_con_prog = sin_acta1 & has_prog

    # Verde 1-11
    cond_v_sp = sin_acta_sin_prog & (d_ta <= 11)
    cond_a_sp = sin_acta_sin_prog & (d_ta >= 12) & (d_ta <= 14)
    cond_r_sp = sin_acta_sin_prog & (d_ta > 14)

    texto = texto.where(~cond_v_sp, "ALERTA VERDE SIN PROG (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v_sp, 1.0)
    texto = texto.where(~cond_a_sp, "ALERTA AMBAR SIN AJUSTE 01 SIN PROG (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a_sp, 2.0)
    texto = texto.where(~cond_r_sp, "ALERTA ROJA SIN AJUSTE 01 (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r_sp, 3.0)

    cond_v_cp = sin_acta_con_prog & (d_ta <= 11)
    cond_a_cp = sin_acta_con_prog & (d_ta >= 12) & (d_ta <= 14)
    cond_r_cp = sin_acta_con_prog & (d_ta > 14)

    texto = texto.where(~cond_v_cp, "ALERTA VERDE SIN AJUSTE 01 (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v_cp, 1.0)
    texto = texto.where(~cond_a_cp, "ALERTA AMBAR SIN AJUSTE PROG (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a_cp, 2.0)
    texto = texto.where(~cond_r_cp, "ALERTA ROJA SIN AJUSTE 01 (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r_cp, 3.0)

    # Banderas: REPETIDO/NUL/SIN COBERTURA + PROG
    flag_all = flags["atencion_ok_all"] | flags["atencion_ok_2_to_6"]
    is_prog_no_acta = flags["is_prog"] & ~has_acta1
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)
    texto = texto.where(~is_prog_no_acta, "NO EVALUADO (PROG)")
    semaforo = semaforo.where(~is_prog_no_acta, np.nan)

    return texto, semaforo


# ============================================================
# ALERTA 04: REPROGRAMACION
# ============================================================
def alerta_04_reprogramacion(df, today, flags):
    acta1 = _safe_dt(df, "FECHA_AJUSTE_ACTA_1")
    actafinal = _safe_dt(df, "FECHA_AJUSTE_ACTA_FINAL")
    rep1 = _safe_dt(df, "FECHA_REPROGRAMACION_01")
    rep2 = _safe_dt(df, "FECHA_REPROGRAMACION_02")
    rep3 = _safe_dt(df, "FECHA_REPROGRAMACION_03")

    estado_ins = _safe_str(df, "ESTADO_INSPECCION")
    estado_sin = _safe_str(df, "ESTADO_SINIESTRO")

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    has_acta_final = actafinal.notna()
    has_r1 = rep1.notna()
    has_r2 = rep2.notna()
    has_r3 = rep3.notna()
    any_reprog = has_r1 | has_r2 | has_r3

    # ATENCION OK AJUSTE FINAL
    cond_ok = has_acta_final
    texto = texto.where(~cond_ok, "ATENCION OK AJUSTE FINAL")

    # REPROGRAMACION OK: sin acta final, sin ninguna reprog
    cond_repok = ~has_acta_final & ~any_reprog
    texto = texto.where(~cond_repok, "REPROGRAMACION OK")

    # ALERTA ROJA SIN REPROGRAMACION 01: estado_inspeccion REPROGRAMADO sin rep1
    cond_sin_r1 = (estado_ins == "REPROGRAMADO") & ~has_r1 & ~has_acta_final
    texto = texto.where(~cond_sin_r1, "ALERTA ROJA SIN REPROGRAMACION 01")
    semaforo = semaforo.where(~cond_sin_r1, 3.0)

    # CON REPROGRAMACION (1, 2 o 3 — el más alto define el ciclo)
    # Días = reprog - today (cuántos faltan)
    # Ciclo 1: usa rep1
    # Ciclo 2: usa rep2 (descarta rep1)
    # Ciclo 3: usa rep3
    d_r1 = (rep1 - today).dt.days
    d_r2 = (rep2 - today).dt.days
    d_r3 = (rep3 - today).dt.days

    # Ciclo 3 (top priority dentro de las reprog)
    # d_r3 = rep3 - today (positivo: futura; negativo: pasada)
    # AMBAR: 1-7 días faltantes → reprog inminente
    # ROJA: rep3 ya pasó (today >= rep3 → d <= 0)
    # Si rep3 muy futura (> 7 días) → no hay alerta, queda como REPROGRAMACION OK
    cond_r3 = ~has_acta_final & has_r3
    d3_int = d_r3.fillna(0).astype("Int64")
    cond_r3_amb = cond_r3 & (d3_int >= 1) & (d3_int <= 7)
    cond_r3_roj = cond_r3 & (d3_int <= 0)  # ya pasó la reprog
    texto = texto.where(~cond_r3_amb, "ALERTA AMBAR CON REPROGRAMACION 03 (" + d3_int.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r3_amb, 2.0)
    texto = texto.where(~cond_r3_roj, "ALERTA ROJA CON REPROGRAMACION 03")
    semaforo = semaforo.where(~cond_r3_roj, 3.0)

    # Ciclo 2 (solo si no hay rep3)
    cond_r2 = ~has_acta_final & has_r2 & ~has_r3
    d2_int = d_r2.fillna(0).astype("Int64")
    cond_r2_amb = cond_r2 & (d2_int >= 1) & (d2_int <= 7)
    cond_r2_roj = cond_r2 & (d2_int <= 0)
    texto = texto.where(~cond_r2_amb, "ALERTA AMBAR CON REPROGRAMACION 02 (" + d2_int.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r2_amb, 2.0)
    texto = texto.where(~cond_r2_roj, "ALERTA ROJA CON REPROGRAMACION 02")
    semaforo = semaforo.where(~cond_r2_roj, 3.0)

    # Ciclo 1 (solo si no hay rep2 ni rep3)
    cond_r1 = ~has_acta_final & has_r1 & ~has_r2 & ~has_r3
    d1_int = d_r1.fillna(0).astype("Int64")
    cond_r1_amb = cond_r1 & (d1_int >= 1) & (d1_int <= 7)
    cond_r1_roj = cond_r1 & (d1_int <= 0)
    texto = texto.where(~cond_r1_amb, "ALERTA AMBAR CON REPROGRAMACION 01 (" + d1_int.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r1_amb, 2.0)
    texto = texto.where(~cond_r1_roj, "ALERTA ROJA CON REPROGRAMACION 01")
    semaforo = semaforo.where(~cond_r1_roj, 3.0)

    # Si tiene reprog futura > 7 días → "REPROGRAMACION OK" (no hay alerta inmediata)
    cond_r_ok = (~has_acta_final & (
        (cond_r3 & (d3_int > 7)) |
        (cond_r2 & (d2_int > 7)) |
        (cond_r1 & (d1_int > 7))
    ))
    texto = texto.where(~cond_r_ok, "REPROGRAMACION OK")

    # Banderas
    flag_all = flags["atencion_ok_all"] | flags["atencion_ok_2_to_6"]
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)

    return texto, semaforo


# ============================================================
# ALERTA 05: PADRON Y VALIDACION
# ============================================================
def alerta_05_padron(df, today, flags):
    actafinal = _safe_dt(df, "FECHA_AJUSTE_ACTA_FINAL")
    envio = _safe_dt(df, "FECHA_ENVIO_DRAS")
    valid = _safe_dt(df, "FECHA_VALIDACION")
    dictamen = _safe_str(df, "DICTAMEN")

    texto = pd.Series(np.nan, index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    is_indemn = dictamen.str.contains("INDEMNIZABLE", na=False) & ~dictamen.str.contains("NO INDEMNIZABLE", na=False)
    has_actafinal = actafinal.notna()
    has_envio = envio.notna()
    has_valid = valid.notna()

    # CON VALIDACION → "ATENCION OK CON VALIDACION (d días)"
    # Empíricamente: d = (valid - envio).days - 1 (offset de 1 día)
    # El caso "(-2 días)" ocurre cuando valid=envio+0 (mismo día) y hay
    # algún offset adicional que aplicamos: si envio>=valid, restamos 2.
    d_ve_raw = _days_calendar(valid, envio).fillna(0).astype("Int64")
    # Offset: si envio == valid (d=0), excel muestra -2; si valid > envio, excel muestra d-1.
    d_ve = pd.Series(np.where(d_ve_raw == 0, -2, d_ve_raw - 1), index=df.index).astype("Int64")

    cond_valid = is_indemn & has_actafinal & has_envio & has_valid
    texto = texto.where(~cond_valid, "ATENCION OK CON VALIDACION (" + d_ve.astype(str) + " días)")

    # SIN VALIDACION (con envio): d = today - envio
    cond_sin_valid = is_indemn & has_actafinal & has_envio & ~has_valid
    d_te = (today - envio).dt.days.fillna(0).astype("Int64")
    cond_v = cond_sin_valid & (d_te >= 1) & (d_te <= 6)
    cond_a = cond_sin_valid & (d_te >= 7) & (d_te <= 15)
    cond_r = cond_sin_valid & (d_te > 15)
    texto = texto.where(~cond_v, "ALERTA VERDE SIN VALIDACION (" + d_te.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v, 1.0)
    texto = texto.where(~cond_a, "ALERTA AMBAR SIN VALIDACION (" + d_te.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a, 2.0)
    texto = texto.where(~cond_r, "ALERTA ROJA SIN VALIDACION (" + d_te.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r, 3.0)

    # SIN PADRON (sin envio): d = today - actafinal - 1 (offset empírico)
    cond_sin_envio = is_indemn & has_actafinal & ~has_envio
    d_ta_raw = (today - actafinal).dt.days.fillna(0).astype("Int64")
    d_ta = d_ta_raw - 1
    cond_pv = cond_sin_envio & (d_ta >= 1) & (d_ta <= 15)
    cond_pa = cond_sin_envio & (d_ta >= 16) & (d_ta <= 20)
    cond_pr = cond_sin_envio & (d_ta > 20)
    texto = texto.where(~cond_pv, "ALERTA VERDE SIN PADRON (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_pv, 1.0)
    texto = texto.where(~cond_pa, "ALERTA AMBAR SIN PADRON (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_pa, 2.0)
    texto = texto.where(~cond_pr, "ALERTA ROJA SIN PADRON (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_pr, 3.0)

    # Banderas
    flag_all = flags["atencion_ok_all"] | flags["atencion_ok_2_to_6"]
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)

    return texto, semaforo


# ============================================================
# ALERTA 06: PAGO SAC (días hábiles!)
# ============================================================
def alerta_06_pago(df, today, flags):
    valid = _safe_dt(df, "FECHA_VALIDACION")
    desemb = _safe_dt(df, "FECHA_DESEMBOLSO")
    dictamen = _safe_str(df, "DICTAMEN")

    texto = pd.Series(np.nan, index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    is_indemn = dictamen.str.contains("INDEMNIZABLE", na=False) & ~dictamen.str.contains("NO INDEMNIZABLE", na=False)
    has_valid = valid.notna()
    has_pago = desemb.notna()

    # CON PAGO: d hábil = (desemb - valid)
    d_dv = _days_hab(desemb, valid).fillna(0).astype("Int64")
    cond_pago = is_indemn & has_valid & has_pago
    cond_pago_ok = cond_pago & (d_dv <= 15)
    cond_pago_rj = cond_pago & (d_dv > 15)
    texto = texto.where(~cond_pago_ok, "ATENCION OK CON PAGO (" + d_dv.astype(str) + " días)")
    texto = texto.where(~cond_pago_rj, "ALERTA ROJA CON PAGO (" + d_dv.astype(str) + " días)")
    semaforo = semaforo.where(~cond_pago_rj, 3.0)

    # SIN PAGO (validación pero sin desembolso)
    today_series = pd.Series([today] * len(df), index=df.index)
    d_tv = _days_hab(today_series, valid).fillna(0).astype("Int64")
    cond_sin_pago = is_indemn & has_valid & ~has_pago
    cond_v = cond_sin_pago & (d_tv <= 11)
    cond_a = cond_sin_pago & (d_tv >= 12) & (d_tv <= 15)
    cond_r = cond_sin_pago & (d_tv > 15)
    texto = texto.where(~cond_v, "ALERTA VERDE SIN PAGO (" + d_tv.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v, 1.0)
    texto = texto.where(~cond_a, "ALERTA AMBAR SIN PAGO (" + d_tv.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a, 2.0)
    texto = texto.where(~cond_r, "ALERTA ROJA SIN PAGO (" + d_tv.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r, 3.0)

    # Banderas
    flag_all = flags["atencion_ok_all"] | flags["atencion_ok_2_to_6"]
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)

    return texto, semaforo


# ============================================================
# Punto de entrada principal
# ============================================================
def compute_alerts(df, today=None):
    """
    Calcula las 6 alertas independientes.
    Retorna df con 12 columnas adicionales.
    """
    if today is None:
        from datetime import datetime, timezone, timedelta
        TZ_PERU = timezone(timedelta(hours=-5))
        today = pd.Timestamp(datetime.now(TZ_PERU).date())
    elif not isinstance(today, pd.Timestamp):
        today = pd.Timestamp(today)

    flags = _detect_flags(df)

    out = df.copy()
    out["ALERTA_01_ATENCION"], out["SEMAFORO_01"] = alerta_01_atencion(df, today, flags)
    out["ALERTA_02_PROGRAMACION"], out["SEMAFORO_02"] = alerta_02_programacion(df, today, flags)
    out["ALERTA_03_AJUSTE"], out["SEMAFORO_03"] = alerta_03_ajuste(df, today, flags)
    out["ALERTA_04_REPROGRAMACION"], out["SEMAFORO_04"] = alerta_04_reprogramacion(df, today, flags)
    out["ALERTA_05_PADRON_VALIDACION"], out["SEMAFORO_05"] = alerta_05_padron(df, today, flags)
    out["ALERTA_06_PAGO"], out["SEMAFORO_06"] = alerta_06_pago(df, today, flags)

    return out
