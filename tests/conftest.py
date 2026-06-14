"""Configuración de pytest: pone la raíz del proyecto en sys.path para
que los tests puedan importar los módulos de la app (prediccion_siniestralidad,
sem_engine, data_processor, etc.) sin instalarlos como paquete."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
