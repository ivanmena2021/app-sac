"""Página: Semáforo de Alertas."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.state import require_data, get_datos
from shared.components import footer
from semaforo_alertas import render_semaforo_tab

require_data()
datos = get_datos()

render_semaforo_tab(datos)
footer()
