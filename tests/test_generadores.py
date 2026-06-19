"""Smoke tests de los generadores de reportes (Word/PPT/Excel/PDF).

Red de seguridad (mejora #8): los generadores producen los documentos
que usa el equipo y Contraloría y NO tenían ninguna cobertura. Estos
tests verifican que cada generador CORRE con datos realistas y produce
un archivo válido y no vacío (magic bytes correctos). No validan el
contenido exacto — son characterization tests que atrapan que un cambio
rompa la generación (KeyError, API de docx/pptx, etc.).

Los generadores importan docx/pptx/fpdf (no están en el CI liviano);
con importorskip corren localmente y se saltean en CI sin romperlo.

Magic bytes:
  - .xlsx/.docx/.pptx son ZIP → empiezan con b"PK"
  - .pdf → empieza con b"%PDF"
"""
import pytest

ZIP_MAGIC = b"PK\x03\x04"
PDF_MAGIC = b"%PDF"


def _assert_office(b):
    assert isinstance(b, (bytes, bytearray)), f"esperaba bytes, vino {type(b)}"
    assert len(b) > 1024, f"archivo sospechosamente chico: {len(b)} bytes"
    assert bytes(b[:4]) == ZIP_MAGIC, "no parece un archivo Office/ZIP válido"


def _assert_pdf(b):
    assert isinstance(b, (bytes, bytearray))
    assert len(b) > 512
    assert bytes(b[:4]) == PDF_MAGIC, "no parece un PDF válido"


# ─── Excel (openpyxl — disponible también en CI) ───
def test_excel_eme(datos_demo):
    pytest.importorskip("openpyxl")
    from gen_excel_eme import generate_reporte_eme
    _assert_office(generate_reporte_eme(datos_demo))


# NOTA: gen_excel_enhanced.generate_enhanced_excel NO se testea: es código
# muerto (no se importa en ningún lado; el dashboard usa df.to_excel inline).
# Además crashea al escribir fechas datetime64 a Excel — bug latente sin
# impacto en producción. Candidato a borrar (ver flag al usuario).


# ─── Word (python-docx) ───
def test_word_nacional(datos_demo):
    pytest.importorskip("docx")
    from gen_word_bridge_py import generate_nacional_docx
    _assert_office(generate_nacional_docx(datos_demo))


def test_word_departamental(datos_demo):
    pytest.importorskip("docx")
    from gen_word_bridge_py import generate_departamental_docx
    from data_processor import get_departamento_data
    depto_data = get_departamento_data(datos_demo, "CUSCO")
    _assert_office(generate_departamental_docx(depto_data))


def test_word_operatividad(datos_demo):
    pytest.importorskip("docx")
    from gen_word_operatividad import generate_operatividad_docx
    _assert_office(generate_operatividad_docx(datos_demo))


# ─── PDF (fpdf2) ───
def test_pdf_ejecutivo(datos_demo):
    pytest.importorskip("fpdf")
    from gen_pdf_resumen import generate_executive_pdf
    _assert_pdf(generate_executive_pdf(datos_demo))


# ─── PowerPoint (python-pptx) ───
def test_ppt_historico(datos_demo):
    pytest.importorskip("pptx")
    from gen_ppt_historico import generar_ppt_historico
    from data_processor import load_primas_historicas
    primas = load_primas_historicas()
    _assert_office(generar_ppt_historico("CUSCO", datos_demo, primas))


def test_ppt_dinamico(datos_demo):
    pytest.importorskip("pptx")
    from datetime import date
    from gen_ppt_dinamico import generar_ppt_dinamico
    filtros = {
        "scope": "nacional", "incluir_nacional": True,
        "departamentos": [], "provincias": [], "distritos": [],
        "tipos_siniestro": [], "empresa": "ambas",
        "fecha_inicio": date(2025, 8, 1), "fecha_fin": date(2026, 7, 31),
        "col_fecha": "FECHA_AVISO",
    }
    df_ppt = datos_demo["midagri"]
    _assert_office(generar_ppt_dinamico(df_ppt, filtros, datos_demo["fecha_corte"]))
