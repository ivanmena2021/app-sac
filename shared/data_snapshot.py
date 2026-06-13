"""Snapshot del último consolidado descargado exitosamente.

Permite que el equipo siga trabajando cuando los portales de Rímac o
La Positiva fallan: en vez de bloquear el flujo, la app ofrece cargar
la última descarga buena con su fecha/hora visible.

Diseño:
- Tras cada descarga automática exitosa se guardan los bytes Excel de
  ambas fuentes en data_cache/ + un meta.json con timestamp y conteos.
- La carga desde snapshot pasa por process_dynamic_data exactamente
  igual que una descarga fresca o una subida manual (mismos bytes,
  mismo code path) — cero riesgo de divergencia de formatos.
- Solo las descargas AUTOMÁTICAS generan snapshot. Las subidas manuales
  no, para que "última descarga exitosa" siempre signifique eso.

Limitación conocida (Railway): el filesystem del container es efímero.
Un redeploy borra el snapshot hasta la próxima descarga exitosa. Para
persistencia entre deploys haría falta un Railway Volume.
"""
import io
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple

TZ_PERU = timezone(timedelta(hours=-5))

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data_cache")
PATH_RIMAC = os.path.join(CACHE_DIR, "rimac_siniestros.xlsx")
PATH_LP = os.path.join(CACHE_DIR, "lp_midagri.xlsx")
PATH_META = os.path.join(CACHE_DIR, "meta.json")


def save_snapshot(rimac_bytes: bytes, lp_bytes: bytes,
                  rimac_rows: Optional[int] = None,
                  lp_rows: Optional[int] = None) -> None:
    """Guarda los bytes Excel de ambas fuentes + metadata.

    Best-effort: el snapshot es una red de seguridad, nunca debe romper
    el flujo principal. Se escribe meta.json al final, así su presencia
    implica que los dos Excel quedaron completos.
    """
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(PATH_RIMAC, "wb") as f:
            f.write(rimac_bytes)
        with open(PATH_LP, "wb") as f:
            f.write(lp_bytes)
        now = datetime.now(TZ_PERU)
        meta = {
            "timestamp": now.isoformat(),
            "timestamp_display": now.strftime("%d/%m/%Y %H:%M"),
            "rimac_rows": rimac_rows,
            "lp_rows": lp_rows,
        }
        with open(PATH_META, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
    except Exception:
        pass


def snapshot_info() -> Optional[dict]:
    """Metadata del snapshot disponible, o None si no hay uno completo."""
    try:
        if not (os.path.exists(PATH_RIMAC) and os.path.exists(PATH_LP)
                and os.path.exists(PATH_META)):
            return None
        with open(PATH_META, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_snapshot() -> Optional[Tuple[io.BytesIO, io.BytesIO, dict]]:
    """Devuelve (rimac_buf, lp_buf, meta) listos para process_dynamic_data,
    o None si el snapshot no existe o no se puede leer."""
    meta = snapshot_info()
    if meta is None:
        return None
    try:
        with open(PATH_RIMAC, "rb") as f:
            rimac_buf = io.BytesIO(f.read())
        with open(PATH_LP, "rb") as f:
            lp_buf = io.BytesIO(f.read())
        return rimac_buf, lp_buf, meta
    except Exception:
        return None
