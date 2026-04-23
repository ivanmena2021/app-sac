"""Página: Calendario Agrícola."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.state import require_data, get_datos
from shared.components import page_header, footer
from calendario_agricola import render_calendario_tab

require_data()
datos = get_datos()

page_header("Calendario Agrícola",
            "Períodos de siembra, cosecha y riesgo por departamento — basado en datos históricos de 5 campañas SAC",
            badge="Ciclo Agrícola")

render_calendario_tab(datos)
footer()
