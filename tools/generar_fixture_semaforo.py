# -*- coding: utf-8 -*-
"""Genera el fixture de reconciliación para CI a partir del Excel oficial.

Selecciona una muestra REPRESENTATIVA de avisos que cubre, para cada una de
las 7 etapas, todos los valores de semáforo posibles (-1/0/1/2/3/blanco), más
una muestra aleatoria estable, y guarda las columnas de entrada canónicas +
los 7 semáforos ESPERADOS (los cacheados por el Excel = la verdad) en
tests/fixtures/semaforo_reconciliacion.csv.

Correr una sola vez en LENOVO cuando el Excel oficial cambie:
    python tools/generar_fixture_semaforo.py "C:/ruta/...SEMAFOROS.xlsx"
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from tools.reconciliar_semaforo import cargar_avisos, SEM_CACHE_COL, _norm_sem

DATE_COLS = [
    "FECHA_AVISO", "FECHA_ATENCION", "FECHA_PROGRAMACION_AJUSTE",
    "FECHA_AJUSTE_ACTA_1", "FECHA_AJUSTE_ACTA_FINAL",
    "FECHA_REPROGRAMACION_01", "FECHA_REPROGRAMACION_02",
    "FECHA_REPROGRAMACION_03", "FECHA_REPROGRAMACION_04",
    "FECHA_REPROGRAMACION_05", "FECHA_REPROGRAMACION_06",
    "FECHA_ENVIO_DRAS", "FECHA_VALIDACION", "FECHA_DESEMBOLSO",
]
STR_COLS = ["ESTADO_SINIESTRO", "ESTADO_INSPECCION", "DICTAMEN",
            "OBSERVACION", "DUPLIC RESULT", "CODIGO_PADRON"]


def _iso(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    try:
        return pd.Timestamp(v).strftime("%Y-%m-%d")
    except Exception:
        return ""


def main(xlsx_path, k_per_combo=8, n_random=200):
    df, sem_xl, fecha_reporte = cargar_avisos(xlsx_path)
    n = len(df)
    sem_norm = {suf: [_norm_sem(v) for v in vals] for suf, vals in sem_xl.items()}

    # Selección de filas que cubren cada (etapa, valor de semáforo)
    chosen = set()
    for suf in SEM_CACHE_COL:
        buckets = {}
        for i, v in enumerate(sem_norm[suf]):
            buckets.setdefault(v, []).append(i)
        for v, idxs in buckets.items():
            chosen.update(idxs[:k_per_combo])

    # Muestra aleatoria estable (semilla fija → reproducible, sin Math.random)
    rng = np.random.RandomState(20260615)
    chosen.update(rng.choice(n, size=min(n_random, n), replace=False).tolist())
    chosen = sorted(chosen)

    rows = []
    for i in chosen:
        row = {}
        for c in DATE_COLS:
            row[c] = _iso(df[c].iloc[i])
        for c in STR_COLS:
            val = df[c].iloc[i]
            row[c] = "" if val is None else str(val).strip()
            if row[c].lower() in ("nan", "none", "nat"):
                row[c] = ""
        for suf in SEM_CACHE_COL:
            ev = sem_norm[suf][i]
            row[f"EXP_{suf}"] = "" if ev is None else int(ev)
        rows.append(row)

    out = pd.DataFrame(rows)
    dest_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "tests", "fixtures")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "semaforo_reconciliacion.csv")
    out.to_csv(dest, index=False, encoding="utf-8")
    print(f"Fixture: {dest}")
    print(f"Filas  : {len(out)} (de {n})  | corte {pd.Timestamp(fecha_reporte).date()}")
    # Resumen de cobertura
    for suf in SEM_CACHE_COL:
        vc = out[f"EXP_{suf}"].value_counts(dropna=False).to_dict()
        print(f"  A{suf}: {vc}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python tools/generar_fixture_semaforo.py <ruta_xlsx>")
        sys.exit(2)
    main(sys.argv[1])
