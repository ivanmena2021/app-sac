"""
gen_word_bridge_py.py — Pure Python Bridge for Word Document Generation

Replaces gen_word_bridge.py (Node.js dependency removed).
Uses gen_word_nacional_py.py and gen_word_departamental_py.py for document generation.

Compatible with Streamlit Community Cloud (no Node.js required).
"""

from gen_word_nacional_py import generate_nacional_docx as _gen_nacional
from gen_word_departamental_py import generate_departamental_docx as _gen_departamental


def generate_nacional_docx(datos):
    """
    Generate Nacional document using pure Python.
    Accepts raw data from data_processor (with DataFrames) and converts to dicts.
    """
    # Prepare cuadro1 from DataFrame if needed
    cuadro1 = []
    if hasattr(datos.get("cuadro1"), "iterrows"):
        for _, row in datos["cuadro1"].iterrows():
            cuadro1.append({
                "departamento": str(row.get("Departamento", "")),
                "prima_total": float(row.get("Prima Total (S/)", 0) or 0),
                "hectareas": float(row.get("Hectáreas Aseguradas", 0) or 0),
                "suma_asegurada": float(row.get("Suma Asegurada Máxima (S/)", 0) or 0),
            })
    else:
        cuadro1 = datos.get("cuadro1", [])

    cuadro2 = []
    if hasattr(datos.get("cuadro2"), "iterrows"):
        for _, row in datos["cuadro2"].iterrows():
            cuadro2.append({
                "departamento": str(row.get("Departamento", "")),
                "ha_indemnizadas": float(row.get("Hectáreas Indemnizadas", 0) or 0),
                "monto_indemnizado": float(row.get("Monto Indemnizado (S/)", 0) or 0),
                "monto_desembolsado": float(row.get("Monto Desembolsado (S/)", 0) or 0),
                "productores": float(row.get("Productores con Desembolso", 0) or 0),
            })
    else:
        cuadro2 = datos.get("cuadro2", [])

    cuadro3 = []
    if hasattr(datos.get("cuadro3"), "iterrows"):
        for _, row in datos["cuadro3"].iterrows():
            cuadro3.append({
                "departamento": str(row.get("Departamento", "")),
                "avisos": float(row.get("Avisos", 0) or 0),
                "ha_indemn": float(row.get("Ha Indemn.", 0) or 0),
                "monto_indemnizado": float(row.get("Monto Indemnizado (S/)", 0) or 0),
                "monto_desembolsado": float(row.get("Monto Desembolsado (S/)", 0) or 0),
                "productores": float(row.get("Productores", 0) or 0),
            })
    else:
        cuadro3 = datos.get("cuadro3", [])

    # Empresas text
    empresas_text = "La Positiva y Rímac"
    if len(datos.get("empresas", {})) > 0:
        partes = []
        for emp, count in datos["empresas"].items():
            partes.append(f"{emp} ({int(count)} departamentos)")
        empresas_text = " y ".join(partes)

    # Lluvia description
    lluvia_desc = "inundación, huayco, lluvias excesivas y deslizamiento"
    lluvia_tipos = datos.get("lluvia_por_tipo", {})
    if hasattr(lluvia_tipos, "items") and len(lluvia_tipos) > 0:
        parts = [f"{t.lower()} ({int(c)})" for t, c in lluvia_tipos.items()]
        lluvia_desc = ", ".join(parts)

    # Top 3 lluvia
    top3_lluvia_text = ""
    if hasattr(datos.get("cuadro3"), "iterrows"):
        c3_temp = datos["cuadro3"][datos["cuadro3"]["Departamento"] != "TOTAL"]
        if len(c3_temp) > 0:
            top3 = c3_temp.nlargest(3, "Avisos")
            parts = [f"{r['Departamento'].title()} ({int(r['Avisos'])} avisos)" for _, r in top3.iterrows()]
            top3_lluvia_text = ", ".join(parts)

    # Top 3 siniestros text
    top3_sin_text = ""
    if len(datos.get("top3_siniestros", {})) > 0:
        parts = []
        for tipo, count in datos["top3_siniestros"].items():
            pct = (count / datos["total_avisos"] * 100) if datos["total_avisos"] > 0 else 0
            parts.append(f"{tipo.lower()} ({pct:.1f}%)")
        top3_sin_text = f"Los siniestros principales son {', '.join(parts)}."

    payload = {
        "fecha_corte": datos.get("fecha_corte", ""),
        "total_avisos": datos.get("total_avisos", 0),
        "total_ajustados": datos.get("total_ajustados", 0),
        "pct_ajustados": datos.get("pct_ajustados", 0),
        "monto_indemnizado": datos.get("monto_indemnizado", 0),
        "monto_desembolsado": datos.get("monto_desembolsado", 0),
        "productores_desembolso": datos.get("productores_desembolso", 0),
        "prima_total": datos.get("prima_total", 0),
        "prima_neta": datos.get("prima_neta", 0),
        "sup_asegurada": datos.get("sup_asegurada", 0),
        "prod_asegurados": datos.get("prod_asegurados", 0),
        "indice_siniestralidad": datos.get("indice_siniestralidad", 0),
        "pct_desembolso": datos.get("pct_desembolso", 0),
        "deptos_con_desembolso": datos.get("deptos_con_desembolso", 0),
        "empresas_text": empresas_text,
        "cuadro1": cuadro1,
        "cuadro2": cuadro2,
        "cuadro3": cuadro3,
        "total_lluvia": datos.get("total_lluvia", 0),
        "pct_lluvia": datos.get("pct_lluvia", 0),
        "lluvia_desc": lluvia_desc,
        "top3_lluvia_text": top3_lluvia_text,
        "top3_siniestros_text": top3_sin_text,
    }

    return _gen_nacional(payload)


def generate_departamental_docx(depto_data):
    """
    Generate Departamental document using pure Python.
    Accepts raw data from data_processor and converts to serializable format.
    """
    import pandas as pd

    d = depto_data
    total = d.get("total_avisos", 0)
    estados = d.get("estados", {})
    cerrados = int(estados.get("CERRADO", 0)) if hasattr(estados, "get") and len(estados) > 0 else 0
    pendientes = total - cerrados

    pct_cerrados = f"{(cerrados / total * 100):.1f}" if total > 0 else "0"
    pct_pendientes = f"{(pendientes / total * 100):.1f}" if total > 0 else "0"

    resumen_op = (
        f"Del total de {total} avisos registrados, se han evaluado y ajustado {cerrados} "
        f"({pct_cerrados}%), quedando {pendientes} pendientes ({pct_pendientes}%). "
        f"De los {cerrados} avisos cerrados, {d.get('indemnizables', 0)} resultaron indemnizables y "
        f"{d.get('no_indemnizables', 0)} no indemnizables. "
        f"El monto total de indemnizaciones reconocidas asciende a S/ {d.get('monto_indemnizado', 0):,.2f} "
        f"sobre una superficie indemnizada de {d.get('ha_indemnizadas', 0):,.2f} hectáreas."
    )

    if d.get("monto_desembolsado", 0) > 0:
        resumen_desemb = (
            f"Se han realizado desembolsos por S/ {d['monto_desembolsado']:,.2f} "
            f"a {d.get('productores_desembolso', 0)} productores."
        )
    else:
        resumen_desemb = (
            f"A la fecha, no se han realizado desembolsos. Los "
            f"{d.get('indemnizables', 0)} casos indemnizables se encuentran pendientes de pago."
        )

    # Avisos por tipo
    avisos_tipo = []
    if hasattr(d.get("avisos_tipo"), "items") and len(d["avisos_tipo"]) > 0:
        for tipo, count in d["avisos_tipo"].items():
            pct = (count / total * 100) if total > 0 else 0
            avisos_tipo.append([tipo.title(), str(int(count)), f"{pct:.1f}%"])

    # Distribución por provincia
    dist_prov = []
    dist_prov_headers = ["Provincia", "Avisos", "Sup. Indemn.", "Prod. Benef.", "Indemniz.", "Desembolso", "% Avance"]
    if hasattr(d.get("dist_provincia"), "iterrows") and len(d["dist_provincia"]) > 0:
        for _, row in d["dist_provincia"].iterrows():
            prov_name = str(row.get("PROVINCIA", "")).title()
            avisos = str(int(row.get("avisos", 0)))
            sup = f"{float(row.get('sup_indemn', 0) or 0):,.2f} ha"
            prod = str(int(float(row.get("productores", 0) or 0)))
            indemn = f"S/ {float(row.get('indemniz', 0) or 0):,.0f}"
            desemb = f"S/ {float(row.get('desembolso', 0) or 0):,.0f}"
            pct = str(row.get("pct_avance", "0%"))
            dist_prov.append([prov_name, avisos, sup, prod, indemn, desemb, pct])

    # Eventos recientes
    eventos = []
    eventos_headers = ["Fecha", "Provincia", "Distrito / Sector", "Cultivo", "Estado"]
    if hasattr(d.get("eventos_recientes"), "iterrows") and len(d["eventos_recientes"]) > 0:
        for _, row in d["eventos_recientes"].iterrows():
            fecha = ""
            if "_fecha" in row.index and pd.notna(row["_fecha"]):
                try:
                    fecha = row["_fecha"].strftime("%d/%m/%Y")
                except Exception:
                    fecha = str(row["_fecha"])
            prov = str(row.get("PROVINCIA", "")).title()
            dist = str(row.get("DISTRITO", "")).title()
            sector = str(row.get("SECTOR_ESTADISTICO", ""))
            if sector and sector not in ["", "nan", "-", "None"]:
                dist = f"{dist} / {sector.title()}"
            cultivo = str(row.get("TIPO_CULTIVO", "")).title()
            estado = str(row.get("ESTADO_INSPECCION", "")).title()
            eventos.append([fecha, prov, dist, cultivo, estado])

    payload = {
        "departamento": d.get("departamento", ""),
        "empresa": d.get("empresa", ""),
        "prima_neta": d.get("prima_neta", 0),
        "sup_asegurada": d.get("sup_asegurada", 0),
        "total_avisos": d.get("total_avisos", 0),
        "ha_indemnizadas": d.get("ha_indemnizadas", 0),
        "monto_indemnizado": d.get("monto_indemnizado", 0),
        "monto_desembolsado": d.get("monto_desembolsado", 0),
        "productores_desembolso": d.get("productores_desembolso", 0),
        "indemnizables": d.get("indemnizables", 0),
        "no_indemnizables": d.get("no_indemnizables", 0),
        "fecha_corte": d.get("fecha_corte", ""),
        "avisos_tipo": avisos_tipo,
        "dist_provincia": dist_prov,
        "dist_provincia_headers": dist_prov_headers,
        "eventos_recientes": eventos,
        "eventos_headers": eventos_headers,
        "resumen_operativo": resumen_op,
        "resumen_desembolso": resumen_desemb,
    }

    return _gen_departamental(payload)
