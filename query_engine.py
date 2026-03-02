"""
query_engine.py — Motor de consultas sobre datos SAC
=====================================================
Recibe una pregunta en lenguaje natural y devuelve datos filtrados
y resúmenes formateados del DataFrame combinado (midagri).

Detecta:
  - Departamentos mencionados
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


def _detect_tipos_siniestro(query):
    """Detecta tipos de siniestro mencionados."""
    query_upper = _normalize(query)
    found = []
    for tipo in TIPOS_SINIESTRO:
        if _normalize(tipo) in query_upper:
            found.append(tipo.upper())
    return found


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
    """Detecta período temporal mencionado."""
    query_lower = query.lower()
    for keyword, days in sorted(TEMPORAL_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in query_lower:
            return days
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

    # Ajustados
    if "ESTADO_INSPECCION" in df_depto.columns:
        ajust = len(df_depto[df_depto["ESTADO_INSPECCION"].astype(str).str.upper() == "CERRADO"])
        pct = (ajust / total * 100) if total > 0 else 0
        lines.append(f"- **Ajustados/evaluados:** {ajust:,} ({pct:.1f}%)")

    # Indemnización
    if "INDEMNIZACION" in df_depto.columns:
        indemn = df_depto["INDEMNIZACION"].sum()
        lines.append(f"- **Indemnización reconocida:** {_fmt(indemn)}")

    # Superficie indemnizada
    if "SUP_INDEMNIZADA" in df_depto.columns:
        sup = df_depto["SUP_INDEMNIZADA"].sum()
        lines.append(f"- **Superficie indemnizada:** {_fmt(sup, 2, '')} ha")

    # Desembolso
    if "MONTO_DESEMBOLSADO" in df_depto.columns:
        desemb = df_depto["MONTO_DESEMBOLSADO"].sum()
        indemn = df_depto["INDEMNIZACION"].sum() if "INDEMNIZACION" in df_depto.columns else 0
        pct_d = (desemb / indemn * 100) if indemn > 0 else 0
        lines.append(f"- **Desembolso:** {_fmt(desemb)} ({pct_d:.1f}%)")

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
    total_indemn = df_filtered["INDEMNIZACION"].sum() if "INDEMNIZACION" in df_filtered.columns else 0
    total_desemb = df_filtered["MONTO_DESEMBOLSADO"].sum() if "MONTO_DESEMBOLSADO" in df_filtered.columns else 0
    total_prod = df_filtered["N_PRODUCTORES"].sum() if "N_PRODUCTORES" in df_filtered.columns else 0
    total_sup = df_filtered["SUP_INDEMNIZADA"].sum() if "SUP_INDEMNIZADA" in df_filtered.columns else 0

    lines.append(f"### Cifras consolidadas:")
    lines.append(f"- **Avisos de siniestro:** {total_avisos:,}")
    lines.append(f"- **Indemnizaciones reconocidas:** {_fmt(total_indemn)}")
    lines.append(f"- **Desembolsos realizados:** {_fmt(total_desemb)}")
    lines.append(f"- **Productores beneficiados:** {int(total_prod):,}")
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

    # Asignar empresa al DataFrame
    depto_empresa = {}
    if "EMPRESA_ASEGURADORA" in materia.columns and "DEPARTAMENTO" in materia.columns:
        for _, row in materia.iterrows():
            d = str(row["DEPARTAMENTO"]).strip().upper()
            e = str(row["EMPRESA_ASEGURADORA"]).strip().upper()
            depto_empresa[d] = e

    df = midagri.copy()
    if "DEPARTAMENTO" in df.columns:
        df["EMPRESA"] = df["DEPARTAMENTO"].map(depto_empresa).fillna("OTROS")
        def _norm_emp(e):
            eu = str(e).upper()
            if "POSITIVA" in eu:
                return "LA POSITIVA"
            elif "RIMAC" in eu or "RÍMAC" in eu:
                return "RÍMAC"
            return eu
        df["EMPRESA"] = df["EMPRESA"].apply(_norm_emp)

    # ─── Filtrar por departamentos ───
    if deptos:
        df = df[df["DEPARTAMENTO"].isin(deptos)]

    # ─── Filtrar por empresa ───
    if empresa:
        df = df[df["EMPRESA"] == empresa]

    # ─── Filtrar por tipo de siniestro ───
    if tipos and "TIPO_SINIESTRO" in df.columns:
        df = df[df["TIPO_SINIESTRO"].isin([_normalize(t) for t in tipos])]

    # ─── Filtrar por período temporal ───
    if days:
        date_col = None
        for col in ["FECHA_AVISO", "FECHA_SINIESTRO", "FECHA_ATENCION"]:
            if col in df.columns:
                date_col = col
                break
        if date_col:
            df["_fecha_tmp"] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
            cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
            df = df[df["_fecha_tmp"] >= cutoff]
            df = df.drop(columns=["_fecha_tmp"], errors="ignore")

    # ─── Construir respuesta ───
    sections = []

    if len(df) == 0:
        filters_text = []
        if deptos:
            filters_text.append(f"departamentos: {', '.join([d.title() for d in deptos])}")
        if tipos:
            filters_text.append(f"siniestros: {', '.join([t.title() for t in tipos])}")
        if empresa:
            filters_text.append(f"empresa: {empresa}")
        if days:
            filters_text.append(f"últimos {days} días")

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
    if empresa:
        context_parts.append(f"**Empresa:** {empresa}")
    if tipos:
        context_parts.append(f"**Siniestros:** {', '.join([t.title() for t in tipos])}")
    if days:
        context_parts.append(f"**Período:** últimos {days} días")

    # ─── Tipo emergencia / resumen general ───
    if "emergencia" in metrics or "resumen" in metrics:
        if deptos:
            sections.append(_build_emergency_summary(df, deptos, fecha_corte))

            # Detalle por departamento
            for depto in deptos:
                df_d = df[df["DEPARTAMENTO"] == depto]
                mat_d = materia[materia["DEPARTAMENTO"] == depto] if "DEPARTAMENTO" in materia.columns else None
                sections.append(_build_depto_summary(df_d, depto, mat_d))
                sections.append("")
        else:
            # Resumen nacional
            sections.append(f"## 📊 Resumen Nacional SAC 2025-2026")
            sections.append(f"**Fecha de corte:** {fecha_corte}\n")
            sections.append(f"- **Avisos totales:** {datos['total_avisos']:,}")
            sections.append(f"- **Ajustados:** {datos['total_ajustados']:,} ({datos['pct_ajustados']}%)")
            sections.append(f"- **Indemnización:** {_fmt(datos['monto_indemnizado'])}")
            sections.append(f"- **Desembolso:** {_fmt(datos['monto_desembolsado'])} ({datos['pct_desembolso']}%)")
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

    response += f"\n\n---\n*Fuente: SAC 2025-2026, datos al {fecha_corte}*"

    return response


def get_suggested_queries():
    """Retorna consultas sugeridas como ejemplo."""
    return [
        "Resumen de Tumbes, Piura, Lambayeque, Lima y Arequipa",
        "Intervenciones del SAC en Cajamarca y Lambayeque",
        "¿Cuántos avisos tiene Ayacucho?",
        "Desembolsos en Junín y Cusco",
        "Heladas en Puno y Huancavelica",
        "Resumen de La Positiva",
        "Siniestros en la última semana",
        "¿Cuál es la siniestralidad de Rímac?",
    ]
