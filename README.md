# SAC - Generador de Reportes 2025-2026

Aplicación web para la generación automatizada de reportes del **Seguro Agrícola Catastrófico (SAC)** del MIDAGRI.

## Funcionalidades

- **Ayuda Memoria Nacional**: Documento Word con resumen nacional del SAC
- **Ayuda Memoria Departamental**: Documento Word por departamento (24 departamentos)
- **Reporte EME**: Actualización en formato Excel del reporte nacional

## Archivos de entrada

La app requiere **2 archivos dinámicos** (Excel) que se cargan desde la barra lateral:

1. **Reporte MIDAGRI** - Archivo de avisos de La Positiva (18 departamentos)
2. **Sistema de Siniestros** - Archivo de Rímac (6 departamentos)

Los archivos estáticos (Materia Asegurada y Resumen SAC) están incluidos en `static_data/`.

## Despliegue en Streamlit Cloud

1. Sube este repositorio a GitHub
2. Ve a [share.streamlit.io](https://share.streamlit.io)
3. Conecta tu cuenta de GitHub
4. Selecciona el repositorio y `app.py` como archivo principal
5. Haz clic en **Deploy**

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```
