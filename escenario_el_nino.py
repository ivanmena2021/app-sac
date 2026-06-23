"""
Escenario El Niño 2026-2027 — página de planificación de stress del SAC.

Lee el JSON precomputado (static_data/escenario_el_nino.json), generado por
escenario_el_nino_2026_2027/exportar_escenario_app.py a partir de las 5
campañas históricas + la materia asegurada. NO requiere datos en vivo.

Metodología (toda en hectáreas; monto = ha × S/1000, tasa 2026):
  - Banda de severidad: peor año real → ancla (peor año×depto) → envolvente
    (máx histórico por celda territorio×sector×siniestro×cultivo).
  - Escalera de planificación: base crónica (enferm.+plagas) + shock El Niño
    (sierra sequía/helada + lluvia/inundación) = campaña El Niño.
  - Sensibilidad costa norte: stress de exposición (las grandes carteras
    costeras que el histórico nunca vio golpeadas por un Niño fuerte).
"""
import os
import json

import pandas as pd
import streamlit as st

try:
    _cache = st.cache_data
except Exception:  # pragma: no cover
    def _cache(*a, **k):
        def _d(fn):
            return fn
        return _d(a[0]) if a and callable(a[0]) else _d

_JSON = os.path.join(os.path.dirname(__file__), "static_data", "escenario_el_nino.json")

VERDE = "#408B14"
SIERRA_C = "#da8824"   # ámbar (sequía/helada)
COSTA_C = "#00758d"    # teal (lluvia/inundación)
CRON_C = "#7e57a8"     # morado (crónico)
ROJO = "#c0392b"
GRIS = "#8a938f"


@_cache(show_spinner=False)
def _load():
    if not os.path.exists(_JSON):
        return None
    with open(_JSON, encoding="utf-8") as f:
        return json.load(f)


def _M(v):
    """S/ en millones compacto."""
    return f"S/{v/1e6:,.0f}M"


def _kpi_row(d):
    e = d["exposicion"]
    cards = [
        ("Superficie asegurada", f"{e['ha_asegurada_total']/1e6:.2f}M ha", "2025-2026"),
        ("Valor asegurado", _M(e["valor_asegurado_S"]), f"S/{int(e['suma_aseg_ha']):,}/ha"),
        ("Productores", f"{e['productores']/1e3:,.0f}K", "asegurados"),
        ("Sectores estadísticos", f"{d['meta']['n_sectores']:,}", f"{d['meta']['total_avisos_hist']:,} avisos hist."),
    ]
    html = '<div class="esc-kpis">'
    for label, val, sub in cards:
        html += (f'<div class="esc-kpi"><div class="esc-kpi-v">{val}</div>'
                 f'<div class="esc-kpi-l">{label}</div>'
                 f'<div class="esc-kpi-s">{sub}</div></div>')
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _bar(label, monto, ref, color, sub="", dashed=False):
    pct = max(2.0, min(100.0, 100 * monto / ref))
    style = (f"width:{pct:.1f}%;background:{color};"
             + ("background-image:repeating-linear-gradient(45deg,rgba(255,255,255,.25) 0 6px,transparent 6px 12px);" if dashed else ""))
    return (f'<div class="esc-row"><span class="esc-row-l">{label}</span>'
            f'<div class="esc-track"><div class="esc-fill" style="{style}"></div></div>'
            f'<span class="esc-row-v">{_M(monto)}</span></div>'
            + (f'<div class="esc-row-sub">{sub}</div>' if sub else ""))


def _escalera(d):
    esc = d["escalera"]
    band = d["banda_nacional"]
    cron = esc["base_cronica"]["monto"]
    shock = esc["shock_el_nino"]["monto"]
    camp = esc["campana_el_nino"]["monto"]
    sierra = esc["shock_el_nino"]["sierra_seq_hel"]["monto"]
    costa = esc["shock_el_nino"]["costa_lluvia"]["monto"]
    stress = esc["stress_costero"]["monto"]
    techo = band["envolvente"]["monto_S1000"]
    ref = max(techo, camp, stress) * 1.05

    st.markdown('<div class="esc-h">Escalera de planificación — campaña El Niño 2026-2027</div>',
                unsafe_allow_html=True)
    html = '<div class="esc-block">'
    html += _bar("Base crónica", cron, ref, CRON_C, "enfermedades + plagas (endémicas, siempre presentes)")
    html += _bar("+ Shock El Niño", shock, ref, SIERRA_C,
                 f"sierra sequía/helada {_M(sierra)} · lluvia/inundación {_M(costa)}")
    html += _bar("= Campaña El Niño", camp, ref, VERDE,
                 "presupuesto base sugerido (crónica + shock climático)")
    html += '<div class="esc-div"></div>'
    html += _bar("⚠ Sensibilidad costa norte", stress, ref, COSTA_C,
                 esc["stress_costero"]["supuesto"], dashed=True)
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

    st.markdown('<div class="esc-h">Banda de severidad histórica (referencia)</div>',
                unsafe_allow_html=True)
    html = '<div class="esc-block">'
    html += _bar(f"Peor año real ({band['peor_ano_real']['campana']})",
                 band["peor_ano_real"]["monto_S1000"], ref, GRIS)
    html += _bar("Ancla (peor año × depto)", band["ancla"]["monto_S1000"], ref, "#5a9")
    html += _bar("Envolvente (techo)", techo, ref, ROJO,
                 "todos los extremos por celda, a la vez")
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _geojson_disponible():
    try:
        from gen_mapa_coropleta import _load_geojson
        return _load_geojson() is not None
    except Exception:
        return False


def _choropleth(d):
    try:
        import plotly.express as px
        from gen_mapa_coropleta import _load_geojson, _normalize_dept
    except Exception:
        return
    gj = _load_geojson()
    if gj is None:
        return
    rows = [{"DEPARTAMENTO": _normalize_dept(x["departamento"]),
             "siniestralidad": x["siniestralidad"] or 0,
             "monto": x["monto_envolvente"]} for x in d["por_departamento"]]
    dfm = pd.DataFrame(rows)
    prop = None
    fp = gj["features"][0]["properties"] if gj["features"] else {}
    for k in ["DEPARTAMEN", "NOMBDEP", "DEPARTAMENTO", "NAME_1", "name"]:
        if k in fp:
            prop = k
            break
    for feat in gj["features"]:
        feat["properties"]["_m"] = _normalize_dept(feat["properties"].get(prop, ""))
    fig = px.choropleth(
        dfm, geojson=gj, locations="DEPARTAMENTO", featureidkey="properties._m",
        color="siniestralidad", color_continuous_scale="YlOrRd",
        hover_name="DEPARTAMENTO",
        hover_data={"siniestralidad": ":.1f", "DEPARTAMENTO": False},
        labels={"siniestralidad": "Siniestralidad %"},
    )
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=560,
                      paper_bgcolor="rgba(0,0,0,0)",
                      coloraxis_colorbar=dict(title="Siniestr. %", thickness=14, len=0.7))
    st.plotly_chart(fig, use_container_width=True, key="esc_choropleth")
    st.caption("Siniestralidad = hectáreas indemnizadas (envolvente histórica) ÷ superficie asegurada 2025-2026.")


def _bars_departamento(d):
    from shared.charts import apply_theme, PALETTE
    import plotly.graph_objects as go
    top = d["por_departamento"][:12]
    deps = [x["departamento"].title() for x in top][::-1]
    montos = [x["monto_envolvente"] / 1e6 for x in top][::-1]
    cols = [SIERRA_C if x["region"] == "SIERRA" else COSTA_C for x in top][::-1]
    fig = go.Figure(go.Bar(x=montos, y=deps, orientation="h",
                           marker=dict(color=cols, cornerradius=4),
                           text=[f"S/{m:.0f}M" for m in montos], textposition="auto"))
    apply_theme(fig, title="Envolvente por departamento", height=420,
                xaxis_title="S/ millones (a S/1000/ha)", legend_position="none")
    st.plotly_chart(fig, use_container_width=True, key="esc_dep_bars")


def _bars_peligro(d):
    from shared.charts import apply_theme
    import plotly.graph_objects as go
    per = [p for p in d["por_siniestro"] if p["ha"] > 0][:10][::-1]
    names = [p["peligro"].replace("_", " ").title() for p in per]
    montos = [p["monto"] / 1e6 for p in per]
    cols = [VERDE if p["es_shock"] else GRIS for p in per]
    fig = go.Figure(go.Bar(x=montos, y=names, orientation="h",
                           marker=dict(color=cols, cornerradius=4),
                           text=[f"S/{m:.0f}M" for m in montos], textposition="auto"))
    apply_theme(fig, title="Envolvente por tipo de siniestro",
                subtitle="verde = peligro disparado por El Niño", height=420,
                xaxis_title="S/ millones", legend_position="none")
    st.plotly_chart(fig, use_container_width=True, key="esc_per_bars")


def _bars_cultivo(d):
    from shared.charts import apply_theme
    import plotly.graph_objects as go
    cul = d["por_cultivo"][:12][::-1]
    names = [c["cultivo"].title()[:22] for c in cul]
    montos = [c["monto"] / 1e6 for c in cul]
    fig = go.Figure(go.Bar(x=montos, y=names, orientation="h",
                           marker=dict(color=VERDE, cornerradius=4),
                           text=[f"S/{m:.0f}M" for m in montos], textposition="auto"))
    apply_theme(fig, title="Envolvente por cultivo (top 12)", height=420,
                xaxis_title="S/ millones", legend_position="none")
    st.plotly_chart(fig, use_container_width=True, key="esc_cul_bars")


def _tabla_departamentos(d):
    rows = [{"Departamento": x["departamento"].title(),
             "Región": x["region"].replace("_", " ").title(),
             "Ha asegurada": x["ha_asegurada"],
             "Ha envolvente": x["ha_envolvente"],
             "Siniestralidad %": x["siniestralidad"],
             "Peligro top": (x["top_peligro"] or "").replace("_", " ").title(),
             "Monto S/": x["monto_envolvente"]}
            for x in d["por_departamento"]]
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, height=430, hide_index=True,
                 column_config={"Ha asegurada": st.column_config.NumberColumn(format="%d"),
                                "Ha envolvente": st.column_config.NumberColumn(format="%d"),
                                "Siniestralidad %": st.column_config.NumberColumn(format="%.1f%%"),
                                "Monto S/": st.column_config.NumberColumn(format="S/ %d")})


def _tabla_sectores(d):
    rows = [{"Departamento": s["departamento"].title(), "Provincia": s["provincia"].title(),
             "Distrito": s["distrito"].title(), "Sector": s["sector"],
             "Peligro": s["peligro"].replace("_", " ").title(),
             "Cultivo": s["cultivo"].title(), "Hectáreas": s["ha"], "Monto S/": s["monto"]}
            for s in d["por_sector"]]
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, height=440, hide_index=True,
                 column_config={"Hectáreas": st.column_config.NumberColumn(format="%d"),
                                "Monto S/": st.column_config.NumberColumn(format="S/ %d")})
    st.caption("Top 50 sectores estadísticos por envolvente histórica — la unidad donde dispara el índice del SAC.")


def _exposicion(d):
    from shared.charts import apply_theme
    import plotly.graph_objects as go
    pts = [x for x in d["por_departamento"] if x["ha_asegurada"]]
    fig = go.Figure()
    for reg, col in [("SIERRA", SIERRA_C), ("COSTA_NORTE", COSTA_C),
                     ("COSTA_CENTRO_SUR", "#00b2e3"), ("SELVA", "#45a041")]:
        sub = [x for x in pts if x["region"] == reg]
        if not sub:
            continue
        fig.add_trace(go.Scatter(
            x=[x["ha_asegurada"] / 1000 for x in sub],
            y=[x["siniestralidad"] for x in sub],
            mode="markers+text", name=reg.replace("_", " ").title(),
            text=[x["departamento"].title() if (x["ha_asegurada"] > 90000 or x["siniestralidad"] > 20) else ""
                  for x in sub],
            textposition="top center", textfont=dict(size=9),
            marker=dict(size=[max(8, min(26, (x["ha_asegurada"] / 9000) ** 0.5 * 3)) for x in sub],
                        color=col, opacity=0.8, line=dict(width=0))))
    apply_theme(fig, title="Exposición vs siniestralidad histórica",
                subtitle="abajo-derecha = comodines El Niño (mucha área asegurada, poca pérdida histórica)",
                height=460, xaxis_title="superficie asegurada (miles de ha)",
                yaxis_title="siniestralidad histórica %", legend_position="bottom")
    st.plotly_chart(fig, use_container_width=True, key="esc_expo")

    com = d.get("comodines", [])
    if com:
        chips = "".join(
            f'<span class="esc-chip">{c["departamento"].title()} · '
            f'{c["ha_asegurada"]/1000:.0f}K ha · {c["siniestralidad"]:.0f}%</span>'
            for c in com[:8])
        st.markdown(f'<div class="esc-com"><b>Comodines El Niño</b> (alta exposición, '
                    f'baja pérdida histórica — el registro nunca vio un Niño costero fuerte '
                    f'golpearlos): {chips}</div>', unsafe_allow_html=True)


def _css():
    return """
    <style>
    .esc-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:10px 0 18px;}
    .esc-kpi{background:#fff;border:1px solid #e6ece8;border-radius:14px;padding:14px 16px;box-shadow:0 1px 3px rgba(16,40,28,.06);}
    .esc-kpi-v{font-size:24px;font-weight:800;color:#1f3d2b;line-height:1.1;}
    .esc-kpi-l{font-size:12px;font-weight:600;color:#3f4a44;margin-top:4px;}
    .esc-kpi-s{font-size:10.5px;color:#8a938f;margin-top:2px;}
    .esc-h{font-size:13px;font-weight:700;color:#1f3d2b;text-transform:uppercase;letter-spacing:.4px;margin:16px 0 8px;}
    .esc-block{background:#f5f7f4;border:1px solid #e6ece8;border-radius:14px;padding:14px 16px;}
    .esc-row{display:flex;align-items:center;gap:12px;margin:7px 0 2px;}
    .esc-row-l{width:185px;font-size:12.5px;font-weight:600;color:#1f3d2b;text-align:right;flex:0 0 auto;}
    .esc-track{flex:1;height:24px;background:#e6eae6;border-radius:7px;overflow:hidden;}
    .esc-fill{height:100%;border-radius:7px;transition:width .3s;}
    .esc-row-v{width:70px;text-align:right;font-size:13px;font-weight:800;color:#1f3d2b;flex:0 0 auto;}
    .esc-row-sub{font-size:10.5px;color:#7c8a82;margin:0 82px 4px 197px;}
    .esc-div{height:1px;background:#cdd6cf;margin:10px 0;}
    .esc-chip{display:inline-block;background:#e8f4fb;color:#00657d;border-radius:20px;padding:3px 11px;margin:3px 4px 0 0;font-size:11.5px;font-weight:600;}
    .esc-com{background:#f0f8fd;border:1px solid #cfe8f5;border-radius:12px;padding:11px 14px;margin-top:10px;font-size:12.5px;color:#345;line-height:1.7;}
    </style>
    """


def render_escenario():
    """Punto de entrada: renderiza la página Escenario El Niño 2026-2027."""
    st.markdown(_css(), unsafe_allow_html=True)
    st.markdown("""
    <div style="background:#1f3d2b;padding:18px 24px;border-radius:10px;margin-bottom:6px;">
        <span style="color:#fff;font-size:22px;font-weight:700;">
        <span class="ms" style="color:inherit;">cyclone</span> Escenario El Niño 2026-2027</span><br>
        <span style="color:#d4edda;font-size:13px;">
        Stress de planificación del SAC combinando los extremos de las campañas 2021-2025</span>
    </div>
    """, unsafe_allow_html=True)

    d = _load()
    if d is None:
        st.error("No se encontró `static_data/escenario_el_nino.json`. "
                 "Genéralo con `escenario_el_nino_2026_2027/exportar_escenario_app.py`.")
        return

    st.info("**No es un pronóstico — es un techo de planificación.** Cada cifra de "
            "hectáreas es un máximo realmente observado en 2021-2025; el monto usa la "
            "tasa 2026 de **S/1,000/ha**. 2020-2021 se excluye (su superficie indemnizada "
            "no es comparable).", icon=":material/info:")

    _kpi_row(d)
    _escalera(d)

    st.divider()
    tabs = st.tabs(["Mapa y departamentos", "Peligros", "Cultivos",
                    "Sectores críticos", "Exposición vs riesgo"])
    with tabs[0]:
        if _geojson_disponible():
            c1, c2 = st.columns([1.1, 1])
            with c1:
                _choropleth(d)
            with c2:
                _bars_departamento(d)
        else:
            _bars_departamento(d)
        _tabla_departamentos(d)
    with tabs[1]:
        _bars_peligro(d)
        st.caption("La sierra sur (sequía/helada) pesa más que las inundaciones: "
                   "para el SAC, El Niño es sobre todo un golpe andino.")
    with tabs[2]:
        _bars_cultivo(d)
    with tabs[3]:
        _tabla_sectores(d)
    with tabs[4]:
        _exposicion(d)

    with st.expander("Metodología y supuestos", expanded=False):
        st.markdown(f"""
- **Base de datos:** {d['meta']['total_avisos_hist']:,} avisos de 4 campañas (2021-2025), {d['meta']['n_sectores']:,} sectores estadísticos. 2020-2021 excluida ({d['meta'].get('excluye','')}).
- **Unidad:** hectáreas indemnizadas (comparables entre campañas; la tasa histórica fue S/650→800/ha). **Monto = ha × S/1,000** (tasa 2026, confirmada en la materia asegurada).
- **Envolvente:** para cada celda territorio × sector × siniestro × cultivo se toma su **peor valor histórico** y se suman. Es un techo, no un promedio.
- **Escalera:** base crónica (enfermedades + plagas, endémicas) + shock El Niño (sierra sequía/helada + lluvia/inundación, por su firma física regional).
- **Sensibilidad costa norte:** {d['escalera']['stress_costero']['supuesto']}. Es el único punto donde se extrapola, porque el histórico nunca vio un Niño costero fuerte sobre la enorme cartera costera actual.
- **Pérdida total** no se usa: el SAC catastrófico es un seguro de índice de área-rendimiento a nivel de sector; no certifica parcial/total por predio.
        """)

    from shared.components import footer
    footer()
