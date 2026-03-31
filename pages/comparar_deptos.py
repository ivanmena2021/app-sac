"""Página: Comparar Departamentos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.state import require_data, get_datos
from shared.components import page_header, footer
from comparativo_departamentos import render_comparativo_departamentos

require_data()
datos = get_datos()

page_header("Comparar Departamentos",
            "Análisis comparativo de indicadores SAC entre departamentos seleccionados")

render_comparativo_departamentos(datos)
footer()
