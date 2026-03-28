"""
batch_reports.py
Genera un ZIP con todos los reportes departamentales + nacional del SAC.
"""

import io
import zipfile
from datetime import datetime

import streamlit as st

from gen_word_bridge_py import generate_nacional_docx, generate_departamental_docx
from data_processor import get_departamento_data


# ---------------------------------------------------------------------------
# Core: ZIP generation
# ---------------------------------------------------------------------------

def generate_batch_zip(datos, progress_callback=None):
    """
    Generates a ZIP containing:
      1. Ayuda_Memoria_Nacional_SAC.docx
      2. One DOCX per department: Ayuda_Memoria_{DEPTO}_SAC.docx

    progress_callback(current, total, label) is called for UI updates.
    Returns bytes of the ZIP file.
    """
    deptos = datos.get("departamentos_list", [])
    total = 1 + len(deptos)  # nacional + each department
    step = 0

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # --- Nacional ---
        if progress_callback:
            progress_callback(step, total, "Generando reporte nacional...")
        try:
            nac_bytes = generate_nacional_docx(datos)
            zf.writestr("Ayuda_Memoria_Nacional_SAC.docx", nac_bytes)
        except Exception as e:
            print(f"[batch] Error generando reporte nacional: {e}")
        step += 1

        # --- Departamentales ---
        for depto in deptos:
            if progress_callback:
                progress_callback(step, total, f"Generando reporte: {depto}...")
            try:
                depto_data = get_departamento_data(datos, depto)
                doc_bytes = generate_departamental_docx(depto_data)
                safe_name = depto.replace(" ", "_")
                zf.writestr(f"Ayuda_Memoria_{safe_name}_SAC.docx", doc_bytes)
            except Exception as e:
                print(f"[batch] Error generando reporte de {depto}: {e}")
            step += 1

    if progress_callback:
        progress_callback(total, total, "Listo!")

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

def render_batch_tab(datos):
    """Streamlit UI for batch report generation."""

    deptos = datos.get("departamentos_list", [])

    st.subheader("Generacion masiva de reportes")
    st.info(
        f"Se generaran reportes Word para **{len(deptos)} departamentos** "
        "y el reporte **Nacional**, empaquetados en un solo archivo ZIP."
    )

    col1, col2, col3 = st.columns(3)
    inc_nacional = col1.checkbox("Nacional", value=True)
    inc_deptos = col2.checkbox("Todos los departamentales", value=True)
    inc_excel = col3.checkbox("Excel consolidado", value=False, disabled=True)

    if st.button("Generar paquete completo"):
        if not inc_nacional and not inc_deptos:
            st.warning("Selecciona al menos una opcion.")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()

        # Build a filtered datos copy based on checkboxes
        batch_datos = dict(datos)
        if not inc_deptos:
            batch_datos["departamentos_list"] = []
        if not inc_nacional:
            # Still iterate departments; nacional step will be skipped below
            pass

        def _progress(current, total, label):
            pct = current / total if total else 1.0
            progress_bar.progress(min(pct, 1.0))
            status_text.text(label)

        try:
            # --- build zip manually to respect checkboxes ---
            depto_list = batch_datos.get("departamentos_list", [])
            total_steps = (1 if inc_nacional else 0) + len(depto_list)
            step = 0
            buf = io.BytesIO()
            errors = []

            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                if inc_nacional:
                    _progress(step, total_steps, "Generando reporte nacional...")
                    try:
                        zf.writestr(
                            "Ayuda_Memoria_Nacional_SAC.docx",
                            generate_nacional_docx(datos),
                        )
                    except Exception as e:
                        errors.append(f"Nacional: {e}")
                    step += 1

                for depto in depto_list:
                    _progress(step, total_steps, f"Generando: {depto}...")
                    try:
                        d = get_departamento_data(datos, depto)
                        safe = depto.replace(" ", "_")
                        zf.writestr(
                            f"Ayuda_Memoria_{safe}_SAC.docx",
                            generate_departamental_docx(d),
                        )
                    except Exception as e:
                        errors.append(f"{depto}: {e}")
                    step += 1

            _progress(total_steps, total_steps, "Listo!")
            zip_bytes = buf.getvalue()

            ts = datetime.now().strftime("%Y%m%d_%H%M")
            zip_name = f"Reportes_SAC_{ts}.zip"
            st.session_state["batch_zip"] = zip_bytes
            st.session_state["batch_zip_name"] = zip_name

            if errors:
                st.warning(
                    f"{len(errors)} reporte(s) con error (omitidos): "
                    + "; ".join(errors)
                )

            st.success(f"ZIP generado: **{zip_name}** ({len(zip_bytes)/1024:.0f} KB)")

        except Exception as e:
            st.error(f"Error inesperado: {e}")

    # Persistent download button
    if st.session_state.get("batch_zip"):
        st.download_button(
            label="Descargar ZIP",
            data=st.session_state["batch_zip"],
            file_name=st.session_state.get("batch_zip_name", "reportes.zip"),
            mime="application/zip",
        )
