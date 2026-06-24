"""Tests del Escenario El Niño 2026-2027.

Congelan el contrato del JSON precomputado y la coherencia interna de las
cifras (escalera, banda de severidad, monto = ha × tasa). El módulo importa
streamlit (no está en el CI liviano) → importorskip lo saltea en CI.
"""
import pytest

pytest.importorskip("streamlit")

import escenario_el_nino as E


@pytest.fixture(scope="module")
def d():
    data = E._load()
    if data is None:
        pytest.skip("escenario_el_nino.json no generado")
    return data


def test_estructura(d):
    for k in ["meta", "exposicion", "banda_nacional", "escalera",
              "por_departamento", "por_siniestro", "por_cultivo", "por_sector"]:
        assert k in d, f"falta {k}"
    assert len(d["por_departamento"]) >= 20
    assert len(d["por_sector"]) > 0


def test_banda_monotona(d):
    b = d["banda_nacional"]
    assert (b["peor_ano_real"]["monto_S1000"] <= b["ancla"]["monto_S1000"]
            <= b["envolvente"]["monto_S1000"]), "la banda debe ser creciente"


def test_monto_es_ha_por_tasa(d):
    tasa = d["meta"]["tasa_2026"]
    env = d["banda_nacional"]["envolvente"]
    assert env["monto_S1000"] == pytest.approx(env["ha"] * tasa, rel=0.005)


def test_escalera_coherente(d):
    esc = d["escalera"]
    suma = esc["base_cronica"]["monto"] + esc["shock_el_nino"]["monto"]
    assert abs(esc["campana_el_nino"]["monto"] - suma) <= 5
    # el shock se descompone en sierra + costa
    sh = esc["shock_el_nino"]
    assert abs(sh["monto"] - (sh["sierra_seq_hel"]["monto"] + sh["costa_lluvia"]["monto"])) <= 5


def test_exposicion_y_render(d):
    assert d["exposicion"]["ha_asegurada_total"] > 1_000_000
    assert d["exposicion"]["suma_aseg_ha"] == 1000
    assert hasattr(E, "render_escenario")


def test_presupuesto_y_historico(d):
    pr = d.get("presupuesto"); hist = d.get("historico")
    assert pr and hist, "falta la sección presupuesto/historico"
    assert len(hist) == 5
    # siniestralidad creciente: año típico < El Niño < techo
    s = pr["siniestralidad"]
    assert s["central_pct"] < s["elnino_pct"] < s["techo_pct"]
    # más recursos → más cobertura SAC; y queda una brecha de crédito positiva
    a = pr["alcance"]
    assert a["con_130"]["sac_ha"] >= a["solo_80"]["sac_ha"]
    assert pr["sagro"]["brecha_credito"] > 0
