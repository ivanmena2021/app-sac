"""
sem_engine.py — Motor del Semáforo de Alertas SAC (7 etapas)

Port FIEL de las fórmulas Excel del equipo SAC, archivo de referencia:
"Dashboard_SAC_25-26_..._SEMAFOROS.xlsx", columnas BK..BX de la hoja AVISOS.

Reglas clave:
  - Etapas A01..A06 cuentan DÍAS CALENDARIO: MAX(0, INT(fecha2)-INT(fecha1))
    (réplica exacta del Excel — el conteo arranca el día siguiente al inicial).
  - Etapa A07 (PAGO) cuenta DÍAS HÁBILES desde el DÍA SIGUIENTE a la fecha de
    validación: NETWORKDAYS.INTL(inicio, fin, 1, feriados) - 1, con sábado y
    domingo no laborables y la lista de feriados BZ2:BZ25.
    *** DIVERGENCIA DELIBERADA del Excel original (decisión del equipo SAC,
    2026-07): el Excel usa NETWORKDAYS inclusivo del día inicial, que mostraba
    un día de más y hacía saltar la alerta un día antes. ***
  - Semáforo numérico por etapa: -1 EXCLUIDO | 0 CONFORME | 1 VERDE |
    2 ÁMBAR | 3 ROJA | NaN (no aplica / sin fecha base).
  - Exclusión transversal (REPETIDO / NULO / SIN COBERTURA) por OBSERVACIÓN
    y por la columna DUPLIC RESULT.

La fidelidad de las etapas 1-6 se verifica fila-a-fila contra el Excel; la
etapa 7 se verifica contra la regla 2026-07 (ver
tests/test_reconciliacion_semaforo.py — EXP_07 re-baseado).
"""
import numpy as np
import pandas as pd

# ============================================================
# Feriados Perú del equipo SAC (BZ2:BZ25 del Excel). Solo se usan
# para la etapa A07 (PAGO, días hábiles).
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
WEEKMASK_SUN_OFF = "1111110"     # weekend_code 11: solo domingo
WEEKMASK_SATSUN_OFF = "1111100"  # weekend_code 1: sábado+domingo


def _networkdays_intl(start, end, weekend_code=1):
    """Equivalente Python de Excel NETWORKDAYS.INTL(start, end, weekend, holidays).

    INCLUSIVO de ambos extremos. Si start > end, retorna negativo.
    NaN-safe: 0 cuando alguna fecha es NaT.

    weekend_code: 1 = sáb+dom no laborables (A07 PAGO); 11 = solo domingo.
    """
    weekmask = WEEKMASK_SUN_OFF if weekend_code == 11 else WEEKMASK_SATSUN_OFF

    out = pd.Series(0, index=start.index, dtype="int64")
    mask = start.notna() & end.notna()
    if mask.sum() == 0:
        return out

    s_arr = start[mask].dt.normalize().values.astype("datetime64[D]")
    e_arr = end[mask].dt.normalize().values.astype("datetime64[D]")

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


def _caldays(start, end):
    """Días CALENDARIO = MAX(0, INT(end)-INT(start)). 0 si alguna fecha es NaT
    (replica IFERROR(MAX(0, INT(b)-INT(a)), 0) del Excel). Acepta un escalar
    Timestamp en cualquiera de los extremos (se difunde al índice del otro)."""
    if not isinstance(start, pd.Series):
        ref = end if isinstance(end, pd.Series) else None
        start = pd.Series(pd.Timestamp(start), index=ref.index)
    if not isinstance(end, pd.Series):
        end = pd.Series(pd.Timestamp(end), index=start.index)
    out = pd.Series(0, index=start.index, dtype="int64")
    mask = start.notna() & end.notna()
    if mask.any():
        diff = (end[mask].dt.normalize() - start[mask].dt.normalize()).dt.days
        out.loc[mask] = diff.clip(lower=0).astype("int64")
    return out


# ============================================================
# Helpers de lectura de columnas (degradan a NaT/"" si faltan)
# ============================================================
def _dt(df, col):
    if col in df.columns:
        return pd.to_datetime(df[col], errors="coerce")
    return pd.Series(pd.NaT, index=df.index)


def _su(df, col):
    if col in df.columns:
        return df[col].astype(str).str.strip().str.upper().replace("NAN", "")
    return pd.Series("", index=df.index)


def _find_dup_col(df):
    """Columna 'DUPLIC RESULT' (AT del Excel): cualquiera que contenga
    DUPLIC pero no SINTAXIS."""
    for c in df.columns:
        cu = str(c).upper()
        if "DUPLIC" in cu and "SINTAXIS" not in cu and "RESULT" in cu:
            return c
    for c in df.columns:
        cu = str(c).upper()
        if "DUPLIC" in cu and "SINTAXIS" not in cu:
            return c
    return None


def _exclusion(obs, dup):
    """Réplica de la cabecera de exclusión común a las 7 etapas.
    Retorna (mask bool, texto categoría)."""
    def has(tok):
        return obs.str.contains(tok, na=False, regex=False)

    g_rep = (dup == "REPETIDO") | has("OBS 01") | has("REPETIDO") | has("AVISO REPETIDO")
    g_nulo = has("OBS 03") | has("AVISO NULO") | has("NUL")
    g_sincob = has("OBS 08") | has("AVISO SIN COBERTURA") | has("SIN COBERTURA")
    excl = g_rep | g_nulo | g_sincob
    txt = np.select(
        [g_rep.values, g_nulo.values],
        ["AVISO EXCLUIDO-REPETIDO", "AVISO EXCLUIDO-NULO"],
        default="AVISO EXCLUIDO-SIN COBERTURA",
    )
    return excl, pd.Series(txt, index=obs.index)


def _select(idx, conds, sem_choices, txt_choices):
    """np.select envuelto en Series con índice. conds: lista de Series bool."""
    cond_arr = [c.values if isinstance(c, pd.Series) else c for c in conds]
    sem = np.select(cond_arr, sem_choices, default=np.nan)
    txt = np.select(cond_arr, txt_choices, default="")
    return pd.Series(txt, index=idx, dtype="object"), pd.Series(sem, index=idx, dtype="float64")


# ============================================================
# A01 — ATENCIÓN  (calendario, ≤6 V / 7-10 A / >10 R)
# ============================================================
def alerta_01_atencion(C, today, excl, excl_txt):
    P, S = C["FECHA_AVISO"], C["FECHA_ATENCION"]
    hasP, hasS = P.notna(), S.notna()
    d_sin = _caldays(P, today); ds = d_sin.astype(str)
    d_con = _caldays(P, S); dc = d_con.astype(str)
    conds = [
        excl,
        ~hasP,
        hasS & (d_con <= 10),
        hasS & (d_con > 10),
        ~hasS & (d_sin <= 6),
        ~hasS & (d_sin <= 10),
        ~hasS,
    ]
    sem = [-1.0, np.nan, 0.0, 3.0, 1.0, 2.0, 3.0]
    txt = [
        excl_txt,
        "",
        "CONFORME CON ATENCION (" + dc + " días)",
        "ALERTA ROJA CON ATENCION (" + dc + " días)",
        "ALERTA VERDE SIN ATENCION (" + ds + " días)",
        "ALERTA AMBAR SIN ATENCION (" + ds + " días)",
        "ALERTA ROJA SIN ATENCION (" + ds + " días)",
    ]
    return _select(P.index, conds, sem, txt)


# ============================================================
# A02 — PROGRAMACIÓN  (calendario, ≤11 V / 12-15 A / >15 R)
# ============================================================
def alerta_02_programacion(C, today, excl, excl_txt):
    P, V, T, obs = C["FECHA_AVISO"], C["FECHA_AJUSTE_ACTA_1"], C["FECHA_PROGRAMACION_AJUSTE"], C["obs"]
    hasP, hasV, hasT = P.notna(), V.notna(), T.notna()
    isprog = obs.str.contains("PROGRAM", na=False, regex=False)
    d_PV = _caldays(P, V).astype(str)
    d_PB = _caldays(P, today); pb = d_PB.astype(str)
    d_PT = _caldays(P, T); pt = d_PT.astype(str)
    d_TB = _caldays(today, T); tb = d_TB.astype(str)
    conds = [
        excl,
        ~hasP,
        hasV & isprog,
        hasV & ~isprog,
        isprog & ~hasT,
        isprog & hasT & (d_TB > 7),
        isprog & hasT,
        ~hasT & (d_PB <= 11),
        ~hasT & (d_PB <= 15),
        ~hasT,
        (d_PT <= 11),
        (d_PT <= 15),
        pd.Series(True, index=P.index),
    ]
    sem = [-1.0, np.nan, 0.0, 0.0, np.nan, 3.0, 2.0, 1.0, 2.0, 3.0, 1.0, 2.0, 3.0]
    txt = [
        excl_txt, "",
        "CONFORME CON AJUSTE 01 (PROGRAMADO CARTA - " + d_PV + " días)",
        "CONFORME CON AJUSTE 01 (" + d_PV + " días)",
        "",
        "ALERTA ROJA CON PROG OBS05 (" + tb + " días)",
        "ALERTA AMBAR CON PROG OBS05 (" + tb + " días)",
        "ALERTA VERDE SIN PROGRAMACION (" + pb + " días)",
        "ALERTA AMBAR SIN PROGRAMACION (" + pb + " días)",
        "ALERTA ROJA SIN PROGRAMACION (" + pb + " días)",
        "ALERTA VERDE CON PROGRAMACION (" + pt + " días)",
        "ALERTA AMBAR CON PROGRAMACION (" + pt + " días)",
        "ALERTA ROJA CON PROGRAMACION (" + pt + " días)",
    ]
    return _select(P.index, conds, sem, txt)


# ============================================================
# A03 — AJUSTE 01  (calendario, ≤11 V / 12-15 A / >15 R)
# ============================================================
def alerta_03_ajuste(C, today, excl, excl_txt):
    P, V, T, obs = C["FECHA_AVISO"], C["FECHA_AJUSTE_ACTA_1"], C["FECHA_PROGRAMACION_AJUSTE"], C["obs"]
    hasP, hasV, hasT = P.notna(), V.notna(), T.notna()
    isprog = obs.str.contains("PROGRAM", na=False, regex=False)
    d_PV = _caldays(P, V); pv = d_PV.astype(str)
    d_PB = _caldays(P, today); pb = d_PB.astype(str)
    # Orden: excl → P vacío → rama PROGRAM (hasV / ~hasT / hasT) → rama
    # normal hasV (≤15 / >15) → rama V vacío (≤11 / ≤15 / >15, con/sin T).
    conds = [
        excl,                              # 0
        ~hasP,                             # 1
        isprog & hasV,                     # 2
        isprog & ~hasT,                    # 3  (isprog & ~hasV)
        isprog,                            # 4  (isprog & ~hasV & hasT)
        hasV & (d_PV <= 15),               # 5  (~isprog)
        hasV,                              # 6  (~isprog & d_PV>15)
        (d_PB <= 11) & ~hasT,              # 7  (~isprog & ~hasV)
        (d_PB <= 11),                      # 8  (hasT)
        (d_PB <= 15) & ~hasT,              # 9
        (d_PB <= 15),                      # 10 (hasT)
        ~hasT,                             # 11 (d_PB>15)
        pd.Series(True, index=P.index),    # 12 (d_PB>15, hasT)
    ]
    sem = [-1.0, np.nan, 0.0, 2.0, 2.0, 0.0, 3.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0]
    txt = [
        excl_txt, "",
        "CONFORME CON AJUSTE 01 (PROGRAMADO CARTA - " + pv + " días)",
        "ALERTA AMBAR CON PROGRAMADO CARTA SIN FECHA AJUSTE (" + pb + " días)",
        "ALERTA AMBAR CON PROGRAMADO CARTA PENDIENTE AJUSTE (" + pb + " días)",
        "CONFORME CON AJUSTE 01 (" + pv + " días)",
        "ALERTA ROJA CON AJUSTE 01 (" + pv + " días)",
        "ALERTA VERDE SIN PROG (" + pb + " días)",
        "ALERTA VERDE SIN AJUSTE 01 (" + pb + " días)",
        "ALERTA AMBAR SIN AJUSTE 01 SIN PROG (" + pb + " días)",
        "ALERTA AMBAR SIN AJUSTE PROG (" + pb + " días)",
        "ALERTA ROJA SIN AJUSTE 01 SIN PROG (" + pb + " días)",
        "ALERTA ROJA SIN AJUSTE 01 (" + pb + " días)",
    ]
    return _select(P.index, conds, sem, txt)


# ============================================================
# A04 — REPROGRAMACIÓN  (calendario; usa última de 6 fechas reprog)
# ============================================================
def alerta_04_reprogramacion(C, today, excl, excl_txt):
    idx = C["FECHA_AVISO"].index
    AF = C["ESTADO_INSPECCION"]; W = C["ESTADO_SINIESTRO"]
    AE = C["FECHA_AJUSTE_ACTA_FINAL"]; V = C["FECHA_AJUSTE_ACTA_1"]
    Y = C["FECHA_REPROGRAMACION_01"]
    # FR = última fecha de reprogramación no vacía (prioridad 06>05>...>01)
    fr = C["FECHA_REPROGRAMACION_06"]
    for col in ("FECHA_REPROGRAMACION_05", "FECHA_REPROGRAMACION_04",
                "FECHA_REPROGRAMACION_03", "FECHA_REPROGRAMACION_02",
                "FECHA_REPROGRAMACION_01"):
        fr = fr.combine_first(C[col])

    activo = (AF == "REPROGRAMADO") & (W == "EN CURSO")
    hasAE, hasV, hasY = AE.notna(), V.notna(), Y.notna()

    d_VB = _caldays(V, today); vb = d_VB.astype(str)
    d_fut = _caldays(today, fr); fut = d_fut.astype(str)   # MAX(0, FR-today)
    d_pas = _caldays(fr, today); pas = d_pas.astype(str)   # MAX(0, today-FR)
    futuro = today < fr

    conds = [
        excl,
        ~activo,
        hasAE,
        ~hasY & ~hasV,
        ~hasY & (d_VB > 7),
        ~hasY & (d_VB >= 4),
        ~hasY,                                   # d_VB < 4
        futuro & (d_fut > 7),
        futuro,                                  # d_fut <= 7
        (d_pas > 10),
        (d_pas >= 7),
        pd.Series(True, index=idx),              # pasado < 7
    ]
    sem = [-1.0, np.nan, 0.0,
           3.0, 3.0, 2.0, 1.0,
           3.0, 2.0,
           1.0, 1.0, 1.0]
    txt = [
        excl_txt, "", "CONFORME CON AJUSTE FINAL",
        "ALERTA ROJA SIN REPROG",
        "ALERTA ROJA SIN REPROGRAMACION (" + vb + " días)",
        "ALERTA AMBAR SIN REPROGRAMACION (" + vb + " días)",
        "ALERTA VERDE SIN REPROGRAMACION (" + vb + " días)",
        "ALERTA ROJA CON REPROGRAMACION (" + fut + " días)",
        "ALERTA AMBAR CON REPROGRAMACION (" + fut + " días)",
        "ALERTA VERDE CON REPROG +10dias (" + pas + " días)",
        "ALERTA VERDE INSPECCION (" + pas + " días)",
        "ALERTA VERDE SEGUIMIENTO (" + pas + " días)",
    ]
    return _select(idx, conds, sem, txt)


# ============================================================
# A05 — PADRÓN  (calendario, ≤15 V / 16-20 A / >20 R)
# ============================================================
def alerta_05_padron(C, today, excl, excl_txt):
    AO = C["DICTAMEN"]; AY = C["CODIGO_PADRON"]
    AZ = C["FECHA_ENVIO_DRAS"]; AE = C["FECHA_AJUSTE_ACTA_FINAL"]
    idx = AO.index
    is_ind = (AO == "INDEMNIZABLE")
    hasAY, hasAZ, hasAE = AY.notna(), AZ.notna(), AE.notna()
    d = _caldays(AE, today); ds = d.astype(str)
    conds = [
        excl,
        ~is_ind,
        hasAY,
        hasAZ,
        ~hasAE,
        (d <= 15),
        (d <= 20),
        pd.Series(True, index=idx),
    ]
    sem = [-1.0, np.nan, 0.0, 0.0, np.nan, 1.0, 2.0, 3.0]
    txt = [
        excl_txt, "", "CONFORME CON PADRON", "CONFORME CON PADRON (ENVIADO)", "",
        "ALERTA VERDE SIN PADRON (" + ds + " días)",
        "ALERTA AMBAR SIN PADRON (" + ds + " días)",
        "ALERTA ROJA SIN PADRON (" + ds + " días)",
    ]
    return _select(idx, conds, sem, txt)


# ============================================================
# A06 — VALIDACIÓN  (calendario, ≤6 V / 7-15 A / >15 R)
# ============================================================
def alerta_06_validacion(C, today, excl, excl_txt):
    AO = C["DICTAMEN"]; BA = C["FECHA_VALIDACION"]; AZ = C["FECHA_ENVIO_DRAS"]
    idx = AO.index
    is_ind = (AO == "INDEMNIZABLE")
    hasBA, hasAZ = BA.notna(), AZ.notna()
    d_val = _caldays(AZ, BA).astype(str)
    d = _caldays(AZ, today); ds = d.astype(str)
    conds = [
        excl,
        ~is_ind,
        hasBA,
        ~hasAZ,
        (d <= 6),
        (d <= 15),
        pd.Series(True, index=idx),
    ]
    sem = [-1.0, np.nan, 0.0, np.nan, 1.0, 2.0, 3.0]
    txt = [
        excl_txt, "",
        "CONFORME CON VALIDACION (" + d_val + " días)", "",
        "ALERTA VERDE SIN VALIDACION (" + ds + " días)",
        "ALERTA AMBAR SIN VALIDACION (" + ds + " días)",
        "ALERTA ROJA SIN VALIDACION (" + ds + " días)",
    ]
    return _select(idx, conds, sem, txt)


# ============================================================
# A07 — PAGO SAC  (HÁBILES wk=1, ≤11 V / 12-15 A / >15 R)
# ============================================================
def alerta_07_pago(C, today, excl, excl_txt):
    AO = C["DICTAMEN"]; BA = C["FECHA_VALIDACION"]; BB = C["FECHA_DESEMBOLSO"]
    idx = AO.index
    is_ind = (AO == "INDEMNIZABLE")
    hasBA, hasBB = BA.notna(), BB.notna()
    today_s = pd.Series(today, index=idx)
    # Regla del equipo SAC (2026-07): los días hábiles se cuentan a partir del
    # DÍA SIGUIENTE a la fecha de validación (validación lunes → pago lunes =
    # 0 días). NETWORKDAYS.INTL del Excel original es inclusivo del día inicial
    # y mostraba un día de más ("16 días" cuando en verdad eran 15), haciendo
    # saltar la alerta un día antes. Con esto la etapa 7 queda alineada con las
    # etapas 1-6, que ya contaban desde el día siguiente (INT(fin)-INT(inicio)).
    d_pago = (_networkdays_intl(BA, BB, 1) - 1).clip(lower=0); dp = d_pago.astype(str)
    d_sin = (_networkdays_intl(BA, today_s, 1) - 1).clip(lower=0); dsn = d_sin.astype(str)
    conds = [
        excl,
        ~is_ind,
        ~hasBA,
        hasBB & (d_pago <= 15),
        hasBB,
        (d_sin <= 11),
        (d_sin <= 15),
        pd.Series(True, index=idx),
    ]
    sem = [-1.0, np.nan, np.nan, 0.0, 3.0, 1.0, 2.0, 3.0]
    txt = [
        excl_txt, "", "",
        "CONFORME CON PAGO (" + dp + " días hábiles)",
        "ALERTA ROJA CON PAGO (" + dp + " días hábiles)",
        "ALERTA VERDE SIN PAGO (" + dsn + " días hábiles)",
        "ALERTA AMBAR SIN PAGO (" + dsn + " días hábiles)",
        "ALERTA ROJA SIN PAGO (" + dsn + " días hábiles)",
    ]
    return _select(idx, conds, sem, txt)


# ============================================================
# Punto de entrada
# ============================================================
# (col canónica de salida, función). Etiquetas 01..07 = A01..A07 del Excel.
_STAGES = [
    ("01_ATENCION", alerta_01_atencion),
    ("02_PROGRAMACION", alerta_02_programacion),
    ("03_AJUSTE", alerta_03_ajuste),
    ("04_REPROGRAMACION", alerta_04_reprogramacion),
    ("05_PADRON", alerta_05_padron),
    ("06_VALIDACION", alerta_06_validacion),
    ("07_PAGO", alerta_07_pago),
]


def compute_alerts(df, today=None):
    """Calcula las 7 etapas del semáforo y retorna df con 14 columnas extra:
    ALERTA_01..07 (texto) y SEMAFORO_01..07 (-1/0/1/2/3/NaN)."""
    if today is None:
        from datetime import datetime, timezone, timedelta
        TZ_PERU = timezone(timedelta(hours=-5))
        today = pd.Timestamp(datetime.now(TZ_PERU).date())
    elif not isinstance(today, pd.Timestamp):
        today = pd.Timestamp(today)
    today = today.normalize()

    # Construir el diccionario de columnas canónicas una sola vez
    dup_col = _find_dup_col(df)
    obs = _su(df, "OBSERVACION")
    dup = _su(df, dup_col) if dup_col else pd.Series("", index=df.index)
    excl, excl_txt = _exclusion(obs, dup)

    C = {
        "FECHA_AVISO": _dt(df, "FECHA_AVISO"),
        "FECHA_ATENCION": _dt(df, "FECHA_ATENCION"),
        "FECHA_PROGRAMACION_AJUSTE": _dt(df, "FECHA_PROGRAMACION_AJUSTE"),
        "FECHA_AJUSTE_ACTA_1": _dt(df, "FECHA_AJUSTE_ACTA_1"),
        "FECHA_AJUSTE_ACTA_FINAL": _dt(df, "FECHA_AJUSTE_ACTA_FINAL"),
        "ESTADO_SINIESTRO": _su(df, "ESTADO_SINIESTRO"),
        "ESTADO_INSPECCION": _su(df, "ESTADO_INSPECCION"),
        "DICTAMEN": _su(df, "DICTAMEN"),
        "CODIGO_PADRON": _su_to_dt_blank(df, "CODIGO_PADRON"),
        "FECHA_ENVIO_DRAS": _dt(df, "FECHA_ENVIO_DRAS"),
        "FECHA_VALIDACION": _dt(df, "FECHA_VALIDACION"),
        "FECHA_DESEMBOLSO": _dt(df, "FECHA_DESEMBOLSO"),
        "obs": obs,
    }
    for i in range(1, 7):
        C[f"FECHA_REPROGRAMACION_0{i}"] = _dt(df, f"FECHA_REPROGRAMACION_0{i}")

    out = df.copy()
    for label, fn in _STAGES:
        num = label.split("_")[0]
        texto, sem = fn(C, today, excl, excl_txt)
        out[f"ALERTA_{num}"] = texto.values
        out[f"SEMAFORO_{num}"] = sem.values
    return out


def _su_to_dt_blank(df, col):
    """CÓDIGO DE PADRÓN se usa solo por presencia/ausencia (notna). Lo
    representamos como Series donde un valor presente y no vacío → NaT-no
    (un marcador notna), y vacío → NaT. Truco: mapeamos a 1/NaN para usar
    .notna() igual que una fecha."""
    if col in df.columns:
        s = df[col].astype(str).str.strip().replace({"nan": "", "NaN": "", "None": ""})
        return s.where(s != "", other=np.nan)
    return pd.Series(np.nan, index=df.index)
