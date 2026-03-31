"""Página: Clima y Riesgo."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.state import require_data, get_datos
from shared.components import footer
from clima_riesgo import render_clima_tab

require_data()
datos = get_datos()

render_clima_tab(datos)
footer()
