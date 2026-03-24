"""
query_engine.py — Motor de consultas sobre datos SAC
=====================================================
Recibe una pregunta en lenguaje natural y devuelve datos filtrados
y resúmenes formateados del DataFrame combinado (midagri).

Detecta:
  - Departamentos mencionados
  - Provincias, distritos y sectores estadísticos
  - Tipos de siniestro
  - Empresa aseguradora
  - Métricas solicitadas (avisos, indemnizaciones, desembolsos, etc.)
  - Períodos de tiempo
"""

import pandas as pd
import numpy as np
import unicodedata
import re
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════
# CATÁLOGOS DE REFERENCIA
# ═══════════════════════════════════════════════════════════════════

DEPARTAMENTOS = [
    "AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO",
    "CAJAMARCA", "CUSCO", "HUANCAVELICA", "HUANUCO", "ICA",
    "JUNIN", "LA LIBERTAD", "LAMBAYEQUE", "LIMA", "LORETO",
    "MADRE DE DIOS", "MOQUEGUA", "PASCO", "PIURA", "PUNO",
    "SAN MARTIN", "TACNA", "TUMBES", "UCAYALI",
]

# Variantes comunes
DEPTO_ALIASES = {
    "APURÍMAC": "APURIMAC", "JUNÍN": "JUNIN", "HUÁNUCO": "HUANUCO",
    "ÁNCASH": "ANCASH", "SAN MARTÍN": "SAN MARTIN",
    "CHICLAYO": "LAMBAYEQUE", "TRUJILLO": "LA LIBERTAD",
    "AREQUIPA": "AREQUIPA", "CUSCO": "CUSCO", "CUZCO": "CUSCO",
    "IQUITOS": "LORETO", "PUCALLPA": "UCAYALI",
    "MOYOBAMBA": "SAN MARTIN", "HUANCAYO": "JUNIN",
    "PIURA": "PIURA", "TUMBES": "TUMBES",
    "CHACHAPOYAS": "AMAZONAS", "ABANCAY": "APURIMAC",
    "CAJAMARCA": "CAJAMARCA", "HUARAZ": "ANCASH",
    "CERRO DE PASCO": "PASCO", "PUNO": "PUNO",
    "ICA": "ICA", "TACNA": "TACNA", "MOQUEGUA": "MOQUEGUA",
    "PUERTO MALDONADO": "MADRE DE DIOS",
    "MADRE DE DIOS": "MADRE DE DIOS",
    # Distritos/localidades mencionables
    "MÓRROPE": "LAMBAYEQUE", "MORROPE": "LAMBAYEQUE",
    "OYOTÚN": "LAMBAYEQUE", "OYOTUN": "LAMBAYEQUE",
    "BOLIVAR": "LA LIBERTAD", "NANCHOC": "CAJAMARCA",
}

TIPOS_SINIESTRO = [
    "HELADA", "SEQUIA", "SEQUÍA", "GRANIZO", "INUNDACION", "INUNDACIÓN",
    "DESLIZAMIENTO", "ENFERMEDADES", "HUAYCO", "PLAGAS",
    "LLUVIAS EXCESIVAS", "VIENTO FUERTE", "INCENDIO",
    "ALTAS TEMPERATURAS", "NIEVE", "FRIAJE",
]

# Grupos semánticos: conceptos que engloban múltiples tipos de siniestro
CONCEPTOS_SINIESTRO = {
    "lluvias": ["INUNDACION", "LLUVIAS EXCESIVAS", "HUAYCO", "DESLIZAMIENTO"],
    "lluvia": ["INUNDACION", "LLUVIAS EXCESIVAS", "HUAYCO", "DESLIZAMIENTO"],
    "exceso de agua": ["INUNDACION", "LLUVIAS EXCESIVAS", "HUAYCO", "DESLIZAMIENTO"],
    "exceso hídrico": ["INUNDACION", "LLUVIAS EXCESIVAS", "HUAYCO", "DESLIZAMIENTO"],
    "hidricos": ["INUNDACION", "LLUVIAS EXCESIVAS", "HUAYCO", "DESLIZAMIENTO"],
    "hídricos": ["INUNDACION", "LLUVIAS EXCESIVAS", "HUAYCO", "DESLIZAMIENTO"],
    "frio": ["HELADA", "FRIAJE", "NIEVE"],
    "frío": ["HELADA", "FRIAJE", "NIEVE"],
    "bajas temperaturas": ["HELADA", "FRIAJE", "NIEVE"],
    "temperaturas bajas": ["HELADA", "FRIAJE", "NIEVE"],
    "climaticos": ["HELADA", "SEQUIA", "GRANIZO", "INUNDACION", "LLUVIAS EXCESIVAS",
                    "HUAYCO", "DESLIZAMIENTO", "VIENTO FUERTE", "NIEVE", "FRIAJE",
                    "ALTAS TEMPERATURAS", "INCENDIO"],
    "climáticos": ["HELADA", "SEQUIA", "GRANIZO", "INUNDACION", "LLUVIAS EXCESIVAS",
                    "HUAYCO", "DESLIZAMIENTO", "VIENTO FUERTE", "NIEVE", "FRIAJE",
                    "ALTAS TEMPERATURAS", "INCENDIO"],
    "biologicos": ["ENFERMEDADES", "PLAGAS"],
    "biológicos": ["ENFERMEDADES", "PLAGAS"],
    "fitosanitarios": ["ENFERMEDADES", "PLAGAS"],
    "plagas y enfermedades": ["ENFERMEDADES", "PLAGAS"],
    "sequia": ["SEQUIA"],
    "sequía": ["SEQUIA"],
    "deficit hídrico": ["SEQUIA"],
    "déficit hídrico": ["SEQUIA"],
    "falta de agua": ["SEQUIA"],
    "calor": ["ALTAS TEMPERATURAS", "INCENDIO"],
    "altas temperaturas": ["ALTAS TEMPERATURAS", "INCENDIO"],
    "vientos": ["VIENTO FUERTE"],
}

EMPRESAS = {
    "LA POSITIVA": ["POSITIVA", "LP"],
    "RÍMAC": ["RIMAC", "RÍMAC"],
}

# Palabras clave para métricas
METRIC_KEYWORDS = {
    "avisos": ["aviso", "avisos", "siniestro", "siniestros", "reportado", "reportados", "reporte"],
    "indemnizacion": ["indemnizacion", "indemnización", "indemnizaciones", "indemnizado", "monto"],
    "desembolso": ["desembolso", "desembolsos", "desembolsado", "pagado", "pago", "pagos"],
    "productores": ["productor", "productores", "beneficiado", "beneficiados", "agricultor", "agricultores"],
    "superficie": ["hectarea", "hectárea", "hectareas", "hectáreas", "superficie", "ha"],
    "ajustes": ["ajuste", "ajustes", "ajustado", "ajustados", "evaluado", "evaluados", "evaluacion"],
    "siniestralidad": ["siniestralidad", "indice"],
    "emergencia": ["emergencia", "intervenciones", "intervención", "intervencion", "acciones"],
    "resumen": ["resumen", "consolidado", "consolidar", "puntual", "general"],
}

TEMPORAL_KEYWORDS = {
    "semana": 7,
    "última semana": 7,
    "ultima semana": 7,
    "esta semana": 7,
    "últimos días": 7,
    "ultimos dias": 7,
    "mes": 30,
    "último mes": 30,
    "ultimo mes": 30,
    "este mes": 30,
    "quincena": 15,
    "hoy": 1,
    "ayer": 2,
}

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _normalize(text):
    """Normaliza texto eliminando acentos y pasando a mayúsculas."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).upper().strip()


def _detect_departamentos(query):
    """Detecta departamentos mencionados en la consulta."""
    query_upper = _normalize(query)
    found = set()

    # Primero buscar en aliases (incluye ciudades/distritos)
    for alias, depto in DEPTO_ALIASES.items():
        if _normalize(alias) in query_upper:
            found.add(depto)

    # Luego buscar nombres directos de departamentos
    for depto in DEPARTAMENTOS:
        if _normalize(depto) in query_upper:
            found.add(depto)

    return sorted(found)


def _detect_provincias(query, df):
    """Detecta provincias mencionadas en la consulta comparando con los datos."""
    if "PROVINCIA" not in df.columns:
        return []
    query_norm = _normalize(query)
    provincias_unicas = df["PROVINCIA"].dropna().astype(str).str.strip().str.upper().unique()
    found = set()
    for prov in provincias_unicas:
        prov_clean = prov.strip()
        if len(prov_clean) < 3:
            continue
        if _normalize(prov_clean) in query_norm:
            found.add(prov_clean)
    return sorted(found)


def _detect_distritos(query, df):
    """Detecta distritos mencionados en la consulta comparando con los datos."""
    if "DISTRITO" not in df.columns:
        return []
    query_norm = _normalize(query)
    distritos_unicos = df["DISTRITO"].dropna().astype(str).str.strip().str.upper().unique()
    found = set()
    # Excluir nombres muy cortos o genéricos que podrían causar falsos positivos
    stop_words = {"DE", "LA", "EL", "LOS", "LAS", "SAN", "DEL", "EN", "POR", "CON", "PARA", "COMO"}
    for dist in distritos_unicos:
        dist_clean = dist.strip()
        if len(dist_clean) < 4 or dist_clean in stop_words:
            continue
        if _normalize(dist_clean) in query_norm:
            found.add(dist_clean)
    return sorted(found)


def _detect_sectores(query, df):
    """Detecta sectores estadísticos mencionados en la consulta."""
    if "SECTOR_ESTADISTICO" not in df.columns:
        return []
    query_norm = _normalize(query)
    sectores_unicos = df["SECTOR_ESTADISTICO"].dropna().astype(str).str.strip().str.upper().unique()
    found = set()
    for sec in sectores_unicos:
        sec_clean = sec.strip()
        if len(sec_clean) < 4 or sec_clean in ("NAN", "", "NONE", "-"):
            continue
        if _normalize(sec_clean) in query_norm:
            found.add(sec_clean)
    return sorted(found)


def _detect_geographic_level(query):
    """Detecta si el usuario pide agrupar por un nivel geográfico específico."""
    query_lower = query.lower()

    # Detectar pedidos de agrupación por nivel
    if any(w in query_lower for w in ["por distrito", "a nivel de distrito", "por distritos", "nivel distrito", "nivel distrital"]):
        return "distrito"
    if any(w in query_lower for w in ["por provincia", "a nivel de provincia", "por provincias", "nivel provincia", "nivel provincial"]):
        return "provincia"
    if any(w in query_lower for w in ["por sector", "por sectores", "sector estadistico", "sector estadístico", "nivel sector"]):
        return "sector"
    return None


def _detect_tipos_siniestro(query):
    """Detecta tipos de siniestro mencionados, incluyendo conceptos semánticos."""
    query_upper = _normalize(query)
    query_lower = query.lower()
    found = set()

    # 1. Buscar conceptos semánticos primero (e.g., "lluvias" → varios tipos)
    for concepto, tipos_asociados in CONCEPTOS_SINIESTRO.items():
        if concepto in query_lower:
            for t in tipos_asociados:
                found.add(t.upper())

    # 2. Buscar tipos directos
    for tipo in TIPOS_SINIESTRO:
        if _normalize(tipo) in query_upper:
            found.add(tipo.upper())

    return sorted(found)


def _detect_empresa(query):
    """Detecta empresa aseguradora mencionada."""
    query_upper = _normalize(query)
    for empresa, keywords in EMPRESAS.items():
        for kw in keywords:
            if _normalize(kw) in query_upper:
                return empresa
    return None


def _detect_metrics(query):
    """Detecta qué métricas se están preguntando."""
    query_lower = query.lower()
    found = set()
    for metric, keywords in METRIC_KEYWORDS.items():
        for kw in keywords:
            if kw in query_lower:
                found.add(metric)
    # Si no detecta nada específico, devolver resumen general
    if not found:
        found = {"resumen"}
    return found


def _detect_temporal(query):
    """
    Detecta período temporal mencionado.
    Retorna dict con tipo de filtro:
      {"type": "days", "days": N}
      {"type": "year", "year": YYYY}
      {"type": "year_month", "year": YYYY, "month": M}
      {"type": "month", "month": M}
      None si no detecta nada
    """
    query_lower = query.lower()

    # 1. Detectar año explícito (e.g., "2026", "en este 2026", "del 2025")
    year_match = re.search(r'\b(20[2-3]\d)\b', query_lower)
    detected_year = int(year_match.group(1)) if year_match else None

    # 2. Detectar mes explícito (e.g., "enero", "febrero 2026")
    detected_month = None
    for mes_name, mes_num in MESES.items():
        if mes_name in query_lower:
            detected_month = mes_num
            break

    # 3. Si encontró año + mes → rango mes/año
    if detected_year and detected_month:
        return {"type": "year_month", "year": detected_year, "month": detected_month}

    # 4. Si solo año → filtrar por ese año
    if detected_year:
        return {"type": "year", "year": detected_year}

    # 5. Si solo mes → asumir año actual
    if detected_month:
        return {"type": "month", "month": detected_month}

    # 6. Fallback: keywords relativos ("semana", "hoy", etc.)
    for keyword, days in sorted(TEMPORAL_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in query_lower:
            return {"type": "days", "days": days}

    return None


def _fmt(val, dec=2, prefix="S/ "):
    """Formatea número."""
    if val is None or (isinstance(val, float) and np.isnan(val)) or val == 0:
        return f"{prefix}-" if prefix else "-"
    try:
        return f"{prefix}{float(val):,.{dec}f}"
    except (ValueError, TypeError):
        return f"{prefix}-" if prefix else "-"


# ═══════════════════════════════════════════════════════════════════
# GENERADOR DE RESPUESTAS
# ═══════════════════════════════════════════════════════════════════

def _build_depto_summary(df_depto, depto_name, materia_depto=None):
    """Construye resumen para un departamento."""
    total = len(df_depto)
    if total == 0:
        return f"**{depto_name.title()}**: Sin avisos registrados."

    lines = [f"### 📍 {depto_name.title()}"]

    # Avisos
    lines.append(f"- **Avisos reportados:** {total:,}")

    # Ajustados / Avance de evaluación
    if "ESTADO_INSPECCION" in df_depto.columns:
        ajust = len(df_depto[df_depto["ESTADO_INSPECCION"].astype(str).str.upper() == "CERRADO"])
        pct = (ajust / total * 100) if total > 0 else 0
        lines.append(f"- **Evaluados (cerrados):** {ajust:,}")
        lines.append(f"- **Avance de evaluación:** {pct:.1f}%")

    # Indemnización
    if "INDEMNIZACION" in df_depto.columns:
        indemn = df_depto["INDEMNIZACION"].sum()
        lines.append(f"- **Indemnización reconocida:** {_fmt(indemn)}")

    # Superficie indemnizada
    if "SUP_INDEMNIZADA" in df_depto.columns:
        sup = df_depto["SUP_INDEMNIZADA"].sum()
        if sup > 0:
            lines.append(f"- **Superficie indemnizada:** {_fmt(sup, 2, '')} ha")

    # Desembolso / Avance de desembolso
    if "MONTO_DESEMBOLSADO" in df_depto.columns:
        desemb = df_depto["MONTO_DESEMBOLSADO"].sum()
        indemn = df_depto["INDEMNIZACION"].sum() if "INDEMNIZACION" in df_depto.columns else 0
        pct_d = (desemb / indemn * 100) if indemn > 0 else 0
        lines.append(f"- **Desembolso:** {_fmt(desemb)}")
        lines.append(f"- **Avance de desembolso:** {pct_d:.1f}%")

    # Productores
    if "N_PRODUCTORES" in df_depto.columns:
        prod = df_depto["N_PRODUCTORES"].sum()
        if prod > 0:
            lines.append(f"- **Productores beneficiados:** {int(prod):,}")

    # Tipo de siniestro
    if "TIPO_SINIESTRO" in df_depto.columns:
        tipos = df_depto["TIPO_SINIESTRO"].value_counts().head(5)
        if len(tipos) > 0:
            tipos_text = ", ".join([f"{t.title()} ({c:,})" for t, c in tipos.items()])
            lines.append(f"- **Principales siniestros:** {tipos_text}")

    # Materia asegurada
    if materia_depto is not None and len(materia_depto) > 0:
        empresa = materia_depto.iloc[0].get("EMPRESA_ASEGURADORA", "N/D")
        prima = materia_depto.iloc[0].get("PRIMA_NETA", 0)
        sup_aseg = materia_depto.iloc[0].get("SUPERFICIE_ASEGURADA", 0)
        lines.append(f"- **Empresa aseguradora:** {empresa}")
        lines.append(f"- **Prima neta:** {_fmt(prima)}")
        lines.append(f"- **Superficie asegurada:** {_fmt(sup_aseg, 0, '')} ha")

    return "\n".join(lines)


def _build_emergency_summary(df_filtered, deptos, fecha_corte):
    """Construye resumen tipo emergencia/coyuntura."""
    lines = [
        f"## 🚨 Resumen de Intervenciones SAC — Emergencia",
        f"**Fecha de corte:** {fecha_corte}",
        f"**Departamentos:** {', '.join([d.title() for d in deptos])}",
        "",
    ]

    total_avisos = len(df_filtered)
    total_ajust = len(df_filtered[df_filtered["ESTADO_INSPECCION"].astype(str).str.upper() == "CERRADO"]) if "ESTADO_INSPECCION" in df_filtered.columns else 0
    pct_eval = (total_ajust / total_avisos * 100) if total_avisos > 0 else 0
    total_indemn = df_filtered["INDEMNIZACION"].sum() if "INDEMNIZACION" in df_filtered.columns else 0
    total_desemb = df_filtered["MONTO_DESEMBOLSADO"].sum() if "MONTO_DESEMBOLSADO" in df_filtered.columns else 0
    pct_desemb = (total_desemb / total_indemn * 100) if total_indemn > 0 else 0
    total_prod = df_filtered["N_PRODUCTORES"].sum() if "N_PRODUCTORES" in df_filtered.columns else 0
    total_sup = df_filtered["SUP_INDEMNIZADA"].sum() if "SUP_INDEMNIZADA" in df_filtered.columns else 0

    lines.append(f"### Cifras consolidadas:")
    lines.append(f"- **Avisos de siniestro:** {total_avisos:,}")
    lines.append(f"- **Evaluados (cerrados):** {total_ajust:,} — **Avance de evaluación: {pct_eval:.1f}%**")
    lines.append(f"- **Indemnizaciones reconocidas:** {_fmt(total_indemn)}")
    lines.append(f"- **Desembolsos realizados:** {_fmt(total_desemb)} — **Avance de desembolso: {pct_desemb:.1f}%**")
    lines.append(f"- **Productores beneficiados:** {int(total_prod):,}")
    if total_sup > 0:
        lines.append(f"- **Superficie indemnizada:** {_fmt(total_sup, 2, '')} ha")
    lines.append("")

    return "\n".join(lines)


def _build_tipo_siniestro_summary(df_filtered, tipos):
    """Resumen por tipo de siniestro."""
    lines = [f"## 📊 Resumen por Tipo de Siniestro", ""]

    for tipo in tipos:
        df_t = df_filtered[df_filtered["TIPO_SINIESTRO"].astype(str).str.upper() == tipo.upper()] if "TIPO_SINIESTRO" in df_filtered.columns else pd.DataFrame()
        if len(df_t) == 0:
            continue
        indemn = df_t["INDEMNIZACION"].sum() if "INDEMNIZACION" in df_t.columns else 0
        lines.append(f"### {tipo.title()}")
        lines.append(f"- Avisos: {len(df_t):,}")
        lines.append(f"- Indemnización: {_fmt(indemn)}")

        if "DEPARTAMENTO" in df_t.columns:
            by_depto = df_t.groupby("DEPARTAMENTO").size().sort_values(ascending=False).head(5)
            deptos_text = ", ".join([f"{d.title()} ({c:,})" for d, c in by_depto.items()])
            lines.append(f"- Departamentos: {deptos_text}")
        lines.append("")

    return "\n".join(lines)


def _build_geographic_summary(df, group_col, group_label, top_n=15):
    """Construye resumen agrupado por nivel geográfico (provincia, distrito o sector)."""
    if group_col not in df.columns:
        return f"⚠️ No se encontró la columna {group_col} en los datos."

    lines = [f"## 📍 Resumen por {group_label}", ""]

    # Agregar dinámicamente según columnas disponibles
    agg_dict = {}
    agg_dict["avisos"] = (group_col, "count")
    if "INDEMNIZACION" in df.columns:
        agg_dict["indemnizacion"] = ("INDEMNIZACION", "sum")
    if "MONTO_DESEMBOLSADO" in df.columns:
        agg_dict["desembolso"] = ("MONTO_DESEMBOLSADO", "sum")
    if "SUP_INDEMNIZADA" in df.columns:
        agg_dict["sup_indemn"] = ("SUP_INDEMNIZADA", "sum")
    if "N_PRODUCTORES" in df.columns:
        agg_dict["productores"] = ("N_PRODUCTORES", "sum")

    grouped = df.groupby(group_col).agg(**agg_dict).reset_index()
    grouped = grouped.sort_values("avisos", ascending=False).head(top_n)

    total_avisos = len(df)
    lines.append(f"**Total de avisos:** {total_avisos:,} | Mostrando top {min(top_n, len(grouped))} {group_label.lower()}s\n")

    for _, row in grouped.iterrows():
        name = str(row[group_col]).title()
        n = int(row["avisos"])
        pct = (n / total_avisos * 100) if total_avisos > 0 else 0

        line = f"### {name} ({n:,} avisos — {pct:.1f}%)"
        lines.append(line)

        details = []
        if "indemnizacion" in row and row["indemnizacion"] > 0:
            details.append(f"Indemnización: {_fmt(row['indemnizacion'])}")
        if "desembolso" in row and row["desembolso"] > 0:
            details.append(f"Desembolso: {_fmt(row['desembolso'])}")
            if "indemnizacion" in row and row["indemnizacion"] > 0:
                pct_d = (row["desembolso"] / row["indemnizacion"] * 100)
                details.append(f"Avance desembolso: {pct_d:.1f}%")
        if "sup_indemn" in row and row["sup_indemn"] > 0:
            details.append(f"Sup. indemnizada: {row['sup_indemn']:,.2f} ha")
        if "productores" in row and row["productores"] > 0:
            details.append(f"Productores: {int(row['productores']):,}")

        if details:
            lines.append("- " + " | ".join(details))

        # Tipos de siniestro en este grupo
        if "TIPO_SINIESTRO" in df.columns:
            df_g = df[df[group_col] == row[group_col]]
            top_tipos = df_g["TIPO_SINIESTRO"].value_counts().head(3)
            if len(top_tipos) > 0:
                tipos_txt = ", ".join([f"{t.title()} ({c})" for t, c in top_tipos.items()])
                lines.append(f"- Siniestros: {tipos_txt}")

        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

def process_query(query, datos):
    """
    Procesa una consulta en lenguaje natural y devuelve una respuesta
    formateada en Markdown.

    Args:
        query: Texto de la consulta del usuario
        datos: Dict de data_processor.process_dynamic_data()

    Returns:
        str: Respuesta en Markdown
    """
    midagri = datos["midagri"]
    materia = datos["materia"]
    fecha_corte = datos["fecha_corte"]

    # Detectar parámetros
    deptos = _detect_departamentos(query)
    tipos = _detect_tipos_siniestro(query)
    empresa = _detect_empresa(query)
    metrics = _detect_metrics(query)
    days = _detect_temporal(query)
    geo_level = _detect_geographic_level(query)

    # Asignar empresa al DataFrame
    depto_empresa = {}
    if "EMPRESA_ASEGURADORA" in materia.columns and "DEPARTAMENTO" in materia.columns:
        depto_empresa = dict(zip(
            materia["DEPARTAMENTO"].astype(str).str.strip().str.upper(),
            materia["EMPRESA_ASEGURADORA"].astype(str).str.strip().str.upper()
        ))

    df = midagri.copy()
    if "DEPARTAMENTO" in df.columns:
        emp_col = df["DEPARTAMENTO"].map(depto_empresa).fillna("OTROS").str.upper()
        # Vectorizar normalización de empresa
        df["EMPRESA"] = np.where(emp_col.str.contains("POSITIVA", na=False), "LA POSITIVA",
                        np.where(emp_col.str.contains("RIMAC|RÍMAC", na=False, regex=True), "RÍMAC", emp_col))

    # ─── Detectar provincias, distritos, sectores ───
    provincias = _detect_provincias(query, df)
    distritos = _detect_distritos(query, df)
    sectores = _detect_sectores(query, df)

    # ─── Filtrar por departamentos ───
    if deptos:
        df = df[df["DEPARTAMENTO"].isin(deptos)]

    # ─── Filtrar por provincias ───
    if provincias and "PROVINCIA" in df.columns:
        df = df[df["PROVINCIA"].astype(str).str.strip().str.upper().isin(provincias)]

    # ─── Filtrar por distritos ───
    if distritos and "DISTRITO" in df.columns:
        df = df[df["DISTRITO"].astype(str).str.strip().str.upper().isin(distritos)]

    # ─── Filtrar por sectores estadísticos ───
    if sectores and "SECTOR_ESTADISTICO" in df.columns:
        df = df[df["SECTOR_ESTADISTICO"].astype(str).str.strip().str.upper().isin(sectores)]

    # ─── Filtrar por empresa ───
    if empresa:
        df = df[df["EMPRESA"] == empresa]

    # ─── Filtrar por tipo de siniestro ───
    if tipos and "TIPO_SINIESTRO" in df.columns:
        # Normalizar tanto los tipos buscados como los del DataFrame (vectorizado)
        tipos_norm = {_normalize(t) for t in tipos}
        col_norm = df["TIPO_SINIESTRO"].astype(str).str.strip().str.upper()
        df = df[col_norm.isin(tipos_norm)]

    # ─── Filtrar por período temporal ───
    temporal = days  # ahora es dict o None
    temporal_label = None
    if temporal:
        # Determinar columna de fecha preferida
        # Para "fecha de ocurrencia" usar FECHA_SINIESTRO preferentemente
        query_lower_check = query.lower()
        prefer_ocurrencia = any(w in query_lower_check for w in [
            "ocurrencia", "ocurrieron", "ocurrido", "sucedieron", "siniestro"
        ])

        if prefer_ocurrencia:
            date_candidates = ["FECHA_SINIESTRO", "FECHA_AVISO", "FECHA_ATENCION"]
        else:
            date_candidates = ["FECHA_AVISO", "FECHA_SINIESTRO", "FECHA_ATENCION"]

        date_col = None
        for col in date_candidates:
            if col in df.columns:
                date_col = col
                break

        if date_col:
            df["_fecha_tmp"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)

            if temporal["type"] == "days":
                cutoff = pd.Timestamp.now() - pd.Timedelta(days=temporal["days"])
                df = df[df["_fecha_tmp"] >= cutoff]
                temporal_label = f"últimos {temporal['days']} días"

            elif temporal["type"] == "year":
                yr = temporal["year"]
                df = df[df["_fecha_tmp"].dt.year == yr]
                temporal_label = f"año {yr}"

            elif temporal["type"] == "year_month":
                yr = temporal["year"]
                mo = temporal["month"]
                df = df[(df["_fecha_tmp"].dt.year == yr) & (df["_fecha_tmp"].dt.month == mo)]
                mes_nombre = [k for k, v in MESES.items() if v == mo][0].capitalize()
                temporal_label = f"{mes_nombre} {yr}"

            elif temporal["type"] == "month":
                mo = temporal["month"]
                df = df[df["_fecha_tmp"].dt.month == mo]
                mes_nombre = [k for k, v in MESES.items() if v == mo][0].capitalize()
                temporal_label = f"{mes_nombre}"

            df = df.drop(columns=["_fecha_tmp"], errors="ignore")

    # ─── Construir respuesta ───
    sections = []

    if len(df) == 0:
        filters_text = []
        if deptos:
            filters_text.append(f"departamentos: {', '.join([d.title() for d in deptos])}")
        if provincias:
            filters_text.append(f"provincias: {', '.join([p.title() for p in provincias])}")
        if distritos:
            filters_text.append(f"distritos: {', '.join([d.title() for d in distritos])}")
        if sectores:
            filters_text.append(f"sectores: {', '.join([s.title() for s in sectores])}")
        if tipos:
            filters_text.append(f"siniestros: {', '.join([t.title() for t in tipos])}")
        if empresa:
            filters_text.append(f"empresa: {empresa}")
        if temporal_label:
            filters_text.append(f"período: {temporal_label}")

        return (
            f"⚠️ No se encontraron registros con los filtros aplicados: "
            f"{', '.join(filters_text) if filters_text else 'ninguno'}.\n\n"
            f"Verifica que los departamentos/términos estén correctos. "
            f"Datos disponibles al {fecha_corte}."
        )

    # Header de contexto
    context_parts = []
    if deptos:
        context_parts.append(f"**Departamentos:** {', '.join([d.title() for d in deptos])}")
    if provincias:
        context_parts.append(f"**Provincias:** {', '.join([p.title() for p in provincias])}")
    if distritos:
        context_parts.append(f"**Distritos:** {', '.join([d.title() for d in distritos])}")
    if sectores:
        context_parts.append(f"**Sectores:** {', '.join([s.title() for s in sectores])}")
    if empresa:
        context_parts.append(f"**Empresa:** {empresa}")
    if tipos:
        context_parts.append(f"**Siniestros:** {', '.join([t.title() for t in tipos])}")
    if temporal_label:
        context_parts.append(f"**Período:** {temporal_label}")

    # ─── Si se pidió agrupación geográfica ───
    if geo_level:
        col_map = {
            "provincia": ("PROVINCIA", "Provincia"),
            "distrito": ("DISTRITO", "Distrito"),
            "sector": ("SECTOR_ESTADISTICO", "Sector Estadístico"),
        }
        col_name, col_label = col_map.get(geo_level, ("DEPARTAMENTO", "Departamento"))
        sections.append(_build_geographic_summary(df, col_name, col_label))

    # ─── Tipo emergencia / resumen general ───
    elif "emergencia" in metrics or "resumen" in metrics:
        if deptos:
            sections.append(_build_emergency_summary(df, deptos, fecha_corte))

            # Detalle por departamento
            for depto in deptos:
                df_d = df[df["DEPARTAMENTO"] == depto]
                mat_d = materia[materia["DEPARTAMENTO"] == depto] if "DEPARTAMENTO" in materia.columns else None
                sections.append(_build_depto_summary(df_d, depto, mat_d))
                sections.append("")
        else:
            # Resumen nacional — usar df filtrado si hay filtros activos
            has_filters = bool(empresa or temporal_label or tipos or provincias or distritos or sectores)

            if has_filters:
                # Recalcular desde el df filtrado
                n_avisos = len(df)
                n_ajust = len(df[df["ESTADO_INSPECCION"].astype(str).str.upper() == "CERRADO"]) if "ESTADO_INSPECCION" in df.columns else 0
                pct_ajust = round(n_ajust / n_avisos * 100, 2) if n_avisos > 0 else 0
                indemn = df["INDEMNIZACION"].sum() if "INDEMNIZACION" in df.columns else 0
                desemb = df["MONTO_DESEMBOLSADO"].sum() if "MONTO_DESEMBOLSADO" in df.columns else 0
                pct_desemb = round(desemb / indemn * 100, 2) if indemn > 0 else 0
                n_prod = int(df["N_PRODUCTORES"].sum()) if "N_PRODUCTORES" in df.columns else 0
                sup_indemn = df["SUP_INDEMNIZADA"].sum() if "SUP_INDEMNIZADA" in df.columns else 0

                titulo_periodo = f" — {temporal_label}" if temporal_label else ""
                titulo_empresa = f" — {empresa}" if empresa else ""
                sections.append(f"## 📊 Resumen Nacional SAC 2025-2026{titulo_empresa}{titulo_periodo}")
                sections.append(f"**Fecha de corte:** {fecha_corte}\n")
                sections.append(f"- **Avisos totales:** {n_avisos:,}")
                sections.append(f"- **Evaluados (cerrados):** {n_ajust:,} — **Avance de evaluación: {pct_ajust}%**")
                sections.append(f"- **Indemnización reconocida:** {_fmt(indemn)}")
                sections.append(f"- **Desembolso:** {_fmt(desemb)} — **Avance de desembolso: {pct_desemb}%**")
                sections.append(f"- **Productores:** {n_prod:,}")
                if sup_indemn > 0:
                    sections.append(f"- **Superficie indemnizada:** {_fmt(sup_indemn, 2, '')} ha")

                # Top departamentos del subconjunto filtrado
                if "DEPARTAMENTO" in df.columns and len(df) > 0:
                    top_deptos = df["DEPARTAMENTO"].value_counts().head(5)
                    sections.append(f"\n**Principales departamentos:**")
                    for dpto, cnt in top_deptos.items():
                        sections.append(f"- {dpto.title()}: {cnt:,} avisos")

                # Top tipos de siniestro del subconjunto filtrado
                if "TIPO_SINIESTRO" in df.columns and len(df) > 0:
                    top_tipos = df["TIPO_SINIESTRO"].value_counts().head(5)
                    sections.append(f"\n**Principales tipos de siniestro:**")
                    for tipo, cnt in top_tipos.items():
                        sections.append(f"- {tipo.title()}: {cnt:,} avisos")
            else:
                # Sin filtros → usar totales pre-calculados
                sections.append(f"## 📊 Resumen Nacional SAC 2025-2026")
                sections.append(f"**Fecha de corte:** {fecha_corte}\n")
                sections.append(f"- **Avisos totales:** {datos['total_avisos']:,}")
                sections.append(f"- **Evaluados (cerrados):** {datos['total_ajustados']:,} — **Avance de evaluación: {datos['pct_ajustados']}%**")
                sections.append(f"- **Indemnización reconocida:** {_fmt(datos['monto_indemnizado'])}")
                sections.append(f"- **Desembolso:** {_fmt(datos['monto_desembolsado'])} — **Avance de desembolso: {datos['pct_desembolso']}%**")
                sections.append(f"- **Productores:** {datos['productores_desembolso']:,}")
                sections.append(f"- **Siniestralidad:** {datos['indice_siniestralidad']}%")

    # ─── Específico por tipo de siniestro ───
    elif tipos:
        sections.append(_build_tipo_siniestro_summary(df, tipos))

    # ─── Métricas específicas ───
    else:
        if deptos:
            for depto in deptos:
                df_d = df[df["DEPARTAMENTO"] == depto]
                mat_d = materia[materia["DEPARTAMENTO"] == depto] if "DEPARTAMENTO" in materia.columns else None
                sections.append(_build_depto_summary(df_d, depto, mat_d))
                sections.append("")
        else:
            # Sin filtros específicos — resumen general
            sections.append(f"## 📊 Resultado de la consulta")
            sections.append(f"**Registros encontrados:** {len(df):,}\n")

            total_indemn = df["INDEMNIZACION"].sum() if "INDEMNIZACION" in df.columns else 0
            total_desemb = df["MONTO_DESEMBOLSADO"].sum() if "MONTO_DESEMBOLSADO" in df.columns else 0
            total_prod = df["N_PRODUCTORES"].sum() if "N_PRODUCTORES" in df.columns else 0

            sections.append(f"- **Avisos:** {len(df):,}")
            sections.append(f"- **Indemnización:** {_fmt(total_indemn)}")
            sections.append(f"- **Desembolso:** {_fmt(total_desemb)}")
            sections.append(f"- **Productores:** {int(total_prod):,}")

    # Añadir contexto y fuente
    response = "\n".join(sections)

    if context_parts:
        header = " · ".join(context_parts)
        response = f"{header}\n\n---\n\n{response}"

    response += f"\n\n---\n*Fuente: Dirección de Seguro y Fomento del Financiamiento Agrario - MIDAGRI, SAC 2025-2026, datos al {fecha_corte}*"

    return response


def get_suggested_queries():
    """Retorna consultas sugeridas como ejemplo."""
    return [
        "Resumen de Tumbes, Piura, Lambayeque, Lima y Arequipa",
        "Intervenciones del SAC en Cajamarca y Lambayeque",
        "¿Cuántos avisos tiene Ayacucho?",
        "Desembolsos en Junín y Cusco",
        "Avisos por eventos asociados a lluvias en 2026",
        "Heladas y frío en Puno y Huancavelica",
        "Resumen de La Positiva en febrero 2026",
        "Avisos por provincia en Cusco",
        "Resumen por distrito en Lambayeque",
    ]
