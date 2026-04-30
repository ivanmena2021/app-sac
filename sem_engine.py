"""
sem_engine.py — Motor del Semáforo de Alertas SAC

Implementa las 6 alertas independientes (ALERTA 01..06) replicando
EXACTAMENTE las fórmulas Excel del equipo SAC oficial.

Fórmulas extraídas del Excel "Dashboard SAC 25-26 ... Con semáforo.xlsx":
- Función central: NETWORKDAYS.INTL(start, end, weekend_code, holidays)
  - weekend_code=11: solo domingo no laborable (sábados sí cuentan)
                    → Alertas 01, 02, 03, 04, 05
  - weekend_code=1:  sábado+domingo no laborables (clásico)
                    → Alerta 06 (PAGO SAC)
- Inclusivo de ambos extremos
- Lista de 24 feriados específica del equipo SAC (BT2:BT25 del Excel)
- Inicio del intervalo es típicamente fecha+1 (día siguiente al evento)
"""
import numpy as np
import pandas as pd

# ============================================================
# Feriados de Perú según el equipo SAC (BT2:BT25 del Excel)
# Lista REDUCIDA — no incluye Batalla de Junín, Día de la Fuerza
# Aérea, Battalla de Ayacucho, Battalla de Arica.
# ============================================================
FERIADOS_SAC = [
    "2025-01-01", "2025-04-17", "2025-04-18", "2025-05-01",
    "2025-06-29", "2025-07-28", "2025-07-29", "2025-08-30",
    "2025-10-08", "2025-11-01", "2025-12-08", "2025-12-25",
    "2026-01-01", "2026-04-02", "2026-04-03", "2026-05-01",
    "2026-06-29", "2026-07-28", "2026-07-29", "2026-08-30",
    "2026-10-08", "2026-11-01", "2026-12-08", "2026-12-25",
]
_HOLIDAYS_NP = pd.to_datetime(FERIADOS_SAC).normalize().values.astype("datetime64[D]")

# weekmasks para numpy.busday_count
# weekend_code 11 (solo domingo): mon-sat=1, sun=0
WEEKMASK_SUN_OFF = "1111110"
# weekend_code 1 (clásico): mon-fri=1, sat-sun=0
WEEKMASK_SATSUN_OFF = "1111100"


def _networkdays_intl(start, end, weekend_code=11):
    """
    Equivalente Python de Excel NETWORKDAYS.INTL(start, end, weekend, holidays).

    INCLUSIVO de ambos extremos. Si start > end, retorna valor negativo.
    NaN-safe: retorna 0 cuando alguna fecha es NaT.

    weekend_code:
      - 11: solo domingo no laborable (Alertas 01-05 del Excel)
      - 1:  sábado y domingo no laborables (Alerta 06)
    """
    weekmask = WEEKMASK_SUN_OFF if weekend_code == 11 else WEEKMASK_SATSUN_OFF

    out = pd.Series(0, index=start.index, dtype="int64")
    mask = start.notna() & end.notna()
    if mask.sum() == 0:
        return out

    s_arr = start[mask].dt.normalize().values.astype("datetime64[D]")
    e_arr = end[mask].dt.normalize().values.astype("datetime64[D]")

    # busday_count(a, b) = días hábiles desde a (inclusive) hasta b (exclusive)
    # NETWORKDAYS.INTL es inclusive de ambos. Diferencia: hay que sumar 1 día al final
    # cuando start <= end. Cuando start > end, restar 1 a start (caso negativo).
    pos = e_arr >= s_arr
    days = np.zeros(len(s_arr), dtype="int64")

    if pos.any():
        e_plus1 = e_arr[pos] + np.timedelta64(1, "D")
        days[pos] = np.busday_count(s_arr[pos], e_plus1,
                                     weekmask=weekmask, holidays=_HOLIDAYS_NP)
    if (~pos).any():
        s_plus1 = s_arr[~pos] + np.timedelta64(1, "D")
        days[~pos] = -np.busday_count(e_arr[~pos], s_plus1,
                                       weekmask=weekmask, holidays=_HOLIDAYS_NP)

    out.loc[mask] = days
    return out


# ============================================================
# Helpers
# ============================================================
def _safe_dt(df, col):
    if col in df.columns:
        return pd.to_datetime(df[col], errors="coerce")
    return pd.Series(pd.NaT, index=df.index)


def _safe_str_upper(df, col):
    if col in df.columns:
        return df[col].astype(str).str.strip().str.upper().fillna("")
    return pd.Series("", index=df.index)


def _detect_flags(df):
    """Devuelve dict de Series booleanas con las banderas transversales."""
    obs = _safe_str_upper(df, "OBSERVACION")

    # DUPLICIDAD: cualquier columna que contenga "DUPLIC" pero no "SINTAXIS"
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
    is_nul = obs.str.contains("NUL", na=False)
    is_sin_cob = obs.str.contains("SIN COBERTURA", na=False)
    is_prog = obs.str.contains("PROG", na=False)
    is_acta_obs = obs.str.contains("ACTA OBS", na=False)
    is_prog_carta = obs.str.contains("PROGRAMADO CARTA", na=False)

    return {
        "ok_all": is_repetido_dup | is_repetido_obs | is_nul,
        "ok_2_to_6": is_sin_cob,
        "is_prog": is_prog,
        "is_acta_obs": is_acta_obs,
        "is_prog_carta": is_prog_carta,
        "obs": obs,
    }


def _series_today(today, index):
    return pd.Series(today, index=index)


# ============================================================
# ALERTA 01: ATENCION
# ============================================================
def alerta_01_atencion(df, today, flags):
    aviso = _safe_dt(df, "FECHA_AVISO")
    atencion = _safe_dt(df, "FECHA_ATENCION")
    today_s = _series_today(today, df.index)

    has_aviso = aviso.notna()
    has_atn = atencion.notna()

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    # SIN ATENCION: d = NETWORKDAYS(aviso, today, 11)
    d_sin = _networkdays_intl(aviso, today_s, 11)
    sin_atn = has_aviso & ~has_atn
    cond_v = sin_atn & (d_sin <= 6)
    cond_a = sin_atn & (d_sin > 6) & (d_sin <= 10)
    cond_r = sin_atn & (d_sin > 10)
    texto = texto.where(~cond_v, "ALERTA VERDE SIN ATENCION (" + d_sin.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v, 1.0)
    texto = texto.where(~cond_a, "ALERTA AMBAR SIN ATENCION (" + d_sin.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a, 2.0)
    # Bug tipográfico Excel: ROJA SIN ATENCION va sin espacio antes de "días"
    texto = texto.where(~cond_r, "ALERTA ROJA SIN ATENCION (" + d_sin.astype(str) + "días)")
    semaforo = semaforo.where(~cond_r, 3.0)

    # CON ATENCION: d = NETWORKDAYS(aviso, atencion, 11)
    d_con = _networkdays_intl(aviso, atencion, 11)
    con_atn = has_aviso & has_atn
    cond_ok = con_atn & (d_con <= 10)
    cond_rj = con_atn & (d_con > 10)
    texto = texto.where(~cond_ok, "ATENCION OK (" + d_con.astype(str) + " días)")
    texto = texto.where(~cond_rj, "ALERTA ROJA CON ATENCION (" + d_con.astype(str) + " días)")
    semaforo = semaforo.where(~cond_rj, 3.0)

    # Bandera transversal: REPETIDO/NUL → "ALERTA ATENCION OK"
    flag_all = flags["ok_all"]
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)

    return texto, semaforo


# ============================================================
# ALERTA 02: PROGRAMACION
# ============================================================
def alerta_02_programacion(df, today, flags):
    aviso = _safe_dt(df, "FECHA_AVISO")
    prog = _safe_dt(df, "FECHA_PROGRAMACION_AJUSTE")
    acta1 = _safe_dt(df, "FECHA_AJUSTE_ACTA_1")
    today_s = _series_today(today, df.index)

    has_aviso = aviso.notna()
    has_prog = prog.notna()
    has_acta1 = acta1.notna()

    aviso_plus1 = aviso + pd.Timedelta(days=1)

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    # ATENCION OK CON AJUSTE
    cond_ok_aj = has_aviso & has_acta1
    texto = texto.where(~cond_ok_aj, "ATENCION OK CON AJUSTE")

    # NO EVALUADO (PROG)
    cond_no_eval = has_aviso & ~has_acta1 & flags["is_prog"]
    texto = texto.where(~cond_no_eval, "NO EVALUADO (PROG)")

    # SIN PROGRAMACION
    sin_prog = has_aviso & ~has_acta1 & ~has_prog & ~flags["is_prog"]
    d_sin = _networkdays_intl(aviso_plus1, today_s, 11)
    cond_v_sp = sin_prog & (d_sin <= 11)
    cond_a_sp = sin_prog & (d_sin > 11) & (d_sin <= 15)
    cond_r_sp = sin_prog & (d_sin > 15)
    texto = texto.where(~cond_v_sp, "ALERTA VERDE SIN PROGRAMACION (" + d_sin.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v_sp, 1.0)
    texto = texto.where(~cond_a_sp, "ALERTA AMBAR SIN PROGRAMACION (" + d_sin.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a_sp, 2.0)
    texto = texto.where(~cond_r_sp, "ALERTA ROJA SIN PROGRAMACION (" + d_sin.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r_sp, 3.0)

    # CON PROGRAMACION
    con_prog = has_aviso & ~has_acta1 & has_prog & ~flags["is_prog"]
    d_con = _networkdays_intl(aviso_plus1, prog, 11)
    cond_v_cp = con_prog & (d_con <= 11)
    cond_a_cp = con_prog & (d_con > 11) & (d_con <= 15)
    cond_r_cp = con_prog & (d_con > 15)
    texto = texto.where(~cond_v_cp, "ALERTA VERDE CON PROGRAMACION (" + d_con.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v_cp, 1.0)
    texto = texto.where(~cond_a_cp, "ALERTA AMBAR CON PROGRAMACION (" + d_con.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a_cp, 2.0)
    texto = texto.where(~cond_r_cp, "ALERTA ROJA CON PROGRAMACION (" + d_con.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r_cp, 3.0)

    # Bandera transversal
    flag_all = flags["ok_all"] | flags["ok_2_to_6"]
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
    today_s = _series_today(today, df.index)

    has_aviso = aviso.notna()
    has_prog = prog.notna()
    has_acta1 = acta1.notna()

    aviso_plus1 = aviso + pd.Timedelta(days=1)

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    # CON ACTA1
    d_aa = _networkdays_intl(aviso_plus1, acta1, 11)
    con_acta = has_aviso & has_acta1 & ~flags["is_prog"]
    cond_ok = con_acta & (d_aa <= 15)
    cond_rj_carta = con_acta & (d_aa > 15) & flags["is_prog_carta"]
    cond_rj = con_acta & (d_aa > 15) & ~flags["is_prog_carta"]
    texto = texto.where(~cond_ok, "AJUSTE OK (" + d_aa.astype(str) + " días)")
    texto = texto.where(~cond_rj_carta, "ATENCION OK (" + d_aa.astype(str) + " días)")
    texto = texto.where(~cond_rj, "ALERTA ROJA CON AJUSTE 01 (" + d_aa.astype(str) + " días)")
    semaforo = semaforo.where(~cond_rj, 3.0)

    # SIN ACTA1
    d_sa = _networkdays_intl(aviso_plus1, today_s, 11)
    sin_acta = has_aviso & ~has_acta1 & ~flags["is_prog"]
    sin_acta_sp = sin_acta & ~has_prog
    sin_acta_cp = sin_acta & has_prog

    # 1-11 verde
    cond_v_sp = sin_acta_sp & (d_sa <= 11)
    cond_v_cp = sin_acta_cp & (d_sa <= 11)
    texto = texto.where(~cond_v_sp, "ALERTA VERDE SIN PROG (" + d_sa.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v_sp, 1.0)
    # NOTA: el Excel original tiene un bug tipográfico — falta el espacio
    # antes de "días" en estas dos variantes ("ALERTA VERDE SIN AJUSTE 01"
    # y "ALERTA AMBAR SIN AJUSTE PROG"). Lo replicamos para match exacto.
    texto = texto.where(~cond_v_cp, "ALERTA VERDE SIN AJUSTE 01 (" + d_sa.astype(str) + "días)")
    semaforo = semaforo.where(~cond_v_cp, 1.0)

    # 12-15 ámbar
    cond_a_sp = sin_acta_sp & (d_sa > 11) & (d_sa <= 15)
    cond_a_cp = sin_acta_cp & (d_sa > 11) & (d_sa <= 15)
    texto = texto.where(~cond_a_sp, "ALERTA AMBAR SIN AJUSTE 01 SIN PROG (" + d_sa.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a_sp, 2.0)
    # Bug tipográfico Excel: falta espacio antes de "días"
    texto = texto.where(~cond_a_cp, "ALERTA AMBAR SIN AJUSTE PROG (" + d_sa.astype(str) + "días)")
    semaforo = semaforo.where(~cond_a_cp, 2.0)

    # >15 rojo (con caso especial PROGRAMADO CARTA → ATENCION OK)
    cond_r_carta = sin_acta & (d_sa > 15) & flags["is_prog_carta"]
    cond_r = sin_acta & (d_sa > 15) & ~flags["is_prog_carta"]
    texto = texto.where(~cond_r_carta, "ATENCION OK (" + d_sa.astype(str) + " días)")
    texto = texto.where(~cond_r, "ALERTA ROJA SIN AJUSTE 01 (" + d_sa.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r, 3.0)

    # Bandera transversal
    flag_all = flags["ok_all"] | flags["ok_2_to_6"]
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)

    return texto, semaforo


# ============================================================
# ALERTA 04: REPROGRAMACION
# ============================================================
def alerta_04_reprogramacion(df, today, flags):
    rep1 = _safe_dt(df, "FECHA_REPROGRAMACION_01")
    rep2 = _safe_dt(df, "FECHA_REPROGRAMACION_02")
    rep3 = _safe_dt(df, "FECHA_REPROGRAMACION_03")
    actafinal = _safe_dt(df, "FECHA_AJUSTE_ACTA_FINAL")
    estado_ins = _safe_str_upper(df, "ESTADO_INSPECCION")
    estado_sin = _safe_str_upper(df, "ESTADO_SINIESTRO")
    today_s = _series_today(today, df.index)

    has_acta_final = actafinal.notna()
    has_r1 = rep1.notna()
    has_r2 = rep2.notna()
    has_r3 = rep3.notna()

    today_plus1 = today_s + pd.Timedelta(days=1)

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    # ATENCION OK AJUSTE FINAL
    texto = texto.where(~has_acta_final, "ATENCION OK AJUSTE FINAL")

    # ALERTA ROJA SIN REPROGRAMACION01
    cond_sin_rep1 = ~has_acta_final & (estado_ins == "REPROGRAMADO") & (estado_sin == "EN CURSO") & ~has_r1
    texto = texto.where(~cond_sin_rep1, "ALERTA ROJA SIN REPROGRAMACION01")
    semaforo = semaforo.where(~cond_sin_rep1, 3.0)

    # default REPROGRAMACION OK para cuando no hay reprog
    cond_default = ~has_acta_final & ~cond_sin_rep1 & ~has_r1 & ~has_r2 & ~has_r3
    texto = texto.where(~cond_default, "REPROGRAMACION OK")

    # CON REP3 (top priority si existe)
    cond_r3_active = ~has_acta_final & ~cond_sin_rep1 & has_r3
    d_r3_past = _networkdays_intl(rep3, today_s, 11)
    d_r3_future = _networkdays_intl(today_plus1, rep3, 11)
    cond_r3_roj = cond_r3_active & (d_r3_past > 1)
    cond_r3_amb = cond_r3_active & ~(d_r3_past > 1) & (rep3 > today_s) & (d_r3_future <= 7)
    cond_r3_ok  = cond_r3_active & ~(d_r3_past > 1) & ~((rep3 > today_s) & (d_r3_future <= 7))
    texto = texto.where(~cond_r3_roj, "ALERTA ROJA CON REPROGRAMACION 03")
    semaforo = semaforo.where(~cond_r3_roj, 3.0)
    texto = texto.where(~cond_r3_amb, "ALERTA AMBAR CON REPROGRAMACION 03 (" + d_r3_future.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r3_amb, 2.0)
    texto = texto.where(~cond_r3_ok, "REPROGRAMACION OK")

    # CON REP2 (si no hay rep3)
    cond_r2_active = ~has_acta_final & ~cond_sin_rep1 & ~has_r3 & has_r2
    d_r2_past = _networkdays_intl(rep2, today_s, 11)
    d_r2_future = _networkdays_intl(today_plus1, rep2, 11)
    cond_r2_roj = cond_r2_active & (d_r2_past > 1)
    cond_r2_amb = cond_r2_active & ~(d_r2_past > 1) & (rep2 > today_s) & (d_r2_future <= 7)
    cond_r2_ok  = cond_r2_active & ~(d_r2_past > 1) & ~((rep2 > today_s) & (d_r2_future <= 7))
    texto = texto.where(~cond_r2_roj, "ALERTA ROJA CON REPROGRAMACION 02")
    semaforo = semaforo.where(~cond_r2_roj, 3.0)
    texto = texto.where(~cond_r2_amb, "ALERTA AMBAR CON REPROGRAMACION 02 (" + d_r2_future.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r2_amb, 2.0)
    texto = texto.where(~cond_r2_ok, "REPROGRAMACION OK")

    # CON REP1 (si no hay rep2 ni rep3) - con caso especial ACTA OBS
    cond_r1_active = ~has_acta_final & ~cond_sin_rep1 & ~has_r3 & ~has_r2 & has_r1
    d_r1_past = _networkdays_intl(rep1, today_s, 11)
    d_r1_future = _networkdays_intl(today_plus1, rep1, 11)
    cond_r1_roj = cond_r1_active & (d_r1_past > 1)
    cond_r1_obs = cond_r1_active & ~(d_r1_past > 1) & (rep1 > today_s) & (d_r1_future <= 7) & flags["is_acta_obs"]
    cond_r1_amb = cond_r1_active & ~(d_r1_past > 1) & (rep1 > today_s) & (d_r1_future <= 7) & ~flags["is_acta_obs"]
    cond_r1_ok  = cond_r1_active & ~(d_r1_past > 1) & ~((rep1 > today_s) & (d_r1_future <= 7))
    texto = texto.where(~cond_r1_roj, "ALERTA ROJA CON REPROGRAMACION 01")
    semaforo = semaforo.where(~cond_r1_roj, 3.0)
    texto = texto.where(~cond_r1_obs, "ALERTA ACTA OBS (" + d_r1_future.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r1_obs, 4.0)
    texto = texto.where(~cond_r1_amb, "ALERTA AMBAR CON REPROGRAMACION 01 (" + d_r1_future.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r1_amb, 2.0)
    texto = texto.where(~cond_r1_ok, "REPROGRAMACION OK")

    # Bandera transversal
    flag_all = flags["ok_all"] | flags["ok_2_to_6"]
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
    dictamen = _safe_str_upper(df, "DICTAMEN")
    today_s = _series_today(today, df.index)

    is_indemn = (dictamen == "INDEMNIZABLE")
    has_actafinal = actafinal.notna()
    has_envio = envio.notna()
    has_valid = valid.notna()

    envio_plus1 = envio + pd.Timedelta(days=1)
    actafinal_plus1 = actafinal + pd.Timedelta(days=1)

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    # CON VALIDACION
    cond_v_v = is_indemn & has_valid & (valid >= envio)
    d_ve = _networkdays_intl(envio_plus1, valid, 11)
    texto = texto.where(~cond_v_v, "ATENCION OK CON VALIDACION (" + d_ve.astype(str) + " días)")

    # SIN VALIDACION (con envio)
    sin_valid = is_indemn & ~has_valid & has_envio & (today_s >= envio)
    d_te = _networkdays_intl(envio_plus1, today_s, 11)
    cond_v_e = sin_valid & (d_te <= 6)
    cond_a_e = sin_valid & (d_te > 6) & (d_te <= 15)
    cond_r_e = sin_valid & (d_te > 15)
    texto = texto.where(~cond_v_e, "ALERTA VERDE SIN VALIDACION (" + d_te.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v_e, 1.0)
    texto = texto.where(~cond_a_e, "ALERTA AMBAR SIN VALIDACION (" + d_te.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a_e, 2.0)
    texto = texto.where(~cond_r_e, "ALERTA ROJA SIN VALIDACION (" + d_te.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r_e, 3.0)

    # SIN ENVIO (con acta final)
    sin_envio = is_indemn & ~has_valid & ~has_envio & has_actafinal
    d_ta = _networkdays_intl(actafinal_plus1, today_s, 11)
    cond_v_p = sin_envio & (d_ta <= 15)
    cond_a_p = sin_envio & (d_ta > 15) & (d_ta <= 20)
    cond_r_p = sin_envio & (d_ta > 20)
    texto = texto.where(~cond_v_p, "ALERTA VERDE SIN PADRON (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v_p, 1.0)
    texto = texto.where(~cond_a_p, "ALERTA AMBAR SIN PADRON (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a_p, 2.0)
    texto = texto.where(~cond_r_p, "ALERTA ROJA SIN PADRON (" + d_ta.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r_p, 3.0)

    # Bandera transversal
    flag_all = flags["ok_all"] | flags["ok_2_to_6"]
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)

    return texto, semaforo


# ============================================================
# ALERTA 06: PAGO SAC (weekend code 1: sáb+dom no laborables)
# ============================================================
def alerta_06_pago(df, today, flags):
    valid = _safe_dt(df, "FECHA_VALIDACION")
    desemb = _safe_dt(df, "FECHA_DESEMBOLSO")
    dictamen = _safe_str_upper(df, "DICTAMEN")
    today_s = _series_today(today, df.index)

    is_indemn = (dictamen == "INDEMNIZABLE")
    has_valid = valid.notna()
    has_pago = desemb.notna()

    valid_plus1 = valid + pd.Timedelta(days=1)

    texto = pd.Series("", index=df.index, dtype="object")
    semaforo = pd.Series(np.nan, index=df.index, dtype="float64")

    # CON PAGO
    cond_pago = is_indemn & has_pago
    d_dv = _networkdays_intl(valid_plus1, desemb, 1)
    cond_pago_ok = cond_pago & (d_dv <= 15)
    cond_pago_rj = cond_pago & (d_dv > 15)
    texto = texto.where(~cond_pago_ok, "ATENCION OK CON PAGO (" + d_dv.astype(str) + " días)")
    texto = texto.where(~cond_pago_rj, "ALERTA ROJA CON PAGO (" + d_dv.astype(str) + " días)")
    semaforo = semaforo.where(~cond_pago_rj, 3.0)

    # SIN PAGO (con validacion)
    sin_pago = is_indemn & ~has_pago & has_valid
    d_tv = _networkdays_intl(valid_plus1, today_s, 1)
    cond_v = sin_pago & (d_tv <= 11)
    cond_a = sin_pago & (d_tv > 11) & (d_tv <= 15)
    cond_r = sin_pago & (d_tv > 15)
    texto = texto.where(~cond_v, "ALERTA VERDE SIN PAGO (" + d_tv.astype(str) + " días)")
    semaforo = semaforo.where(~cond_v, 1.0)
    texto = texto.where(~cond_a, "ALERTA AMBAR SIN PAGO (" + d_tv.astype(str) + " días)")
    semaforo = semaforo.where(~cond_a, 2.0)
    texto = texto.where(~cond_r, "ALERTA ROJA SIN PAGO (" + d_tv.astype(str) + " días)")
    semaforo = semaforo.where(~cond_r, 3.0)

    # Bandera transversal
    flag_all = flags["ok_all"] | flags["ok_2_to_6"]
    texto = texto.where(~flag_all, "ALERTA ATENCION OK")
    semaforo = semaforo.where(~flag_all, np.nan)

    return texto, semaforo


# ============================================================
# Punto de entrada principal
# ============================================================
def compute_alerts(df, today=None):
    """Calcula las 6 alertas independientes y retorna df con 12 columnas extra."""
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
