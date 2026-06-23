"""Página: Escenario El Niño 2026-2027.

No requiere datos en vivo — se basa en el escenario precomputado
(static_data/escenario_el_nino.json)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from escenario_el_nino import render_escenario

render_escenario()
