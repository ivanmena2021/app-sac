# Metodologia de Procesamiento de Datos Historicos del SAC
## Guia de normalizaciones, decisiones y criterios

**Version:** 1.0 — Marzo 2026
**Fuente de datos:** 5 campanas agricolas SAC (2020-2021 a 2024-2025)
**Total de registros procesados:** 66,346 avisos de siniestro
**Archivos generados:** calendario_cultivos_historico.json, perfil_riesgo_distrital.json, mapeo_siniestros.json, resumen_campanas.json

---

## 1. FUENTES DE DATOS

| Campana | Archivo | Hoja | Registros |
|---------|---------|------|-----------|
| 2020-2021 | Dashboard SAC 20-21 Aviso Siniestro Agricola_Consolidado_25.10.21.xlsx | AVISOS | 11,868 |
| 2021-2022 | Dashboard SAC 21-22 Aviso Siniestro Agricola_Consolidado_06.09.22.xlsx | AVISOS | 7,675 |
| 2022-2023 | Dashboard SAC 22-23 Aviso Siniestro Agricola_Consolidado 23.10.23.xlsx | AVISOS | 16,139 |
| 2023-2024 | Dashboard SAC 23-24 Aviso Siniestro Agricola 19.12.24.xlsx | AVISOS | 11,438 |
| 2024-2025 | Dashboard SAC 24-25 Aviso Siniestro Agricola 02.02.26.xlsx | AVISOS | 19,229 |

**Nota:** Para 2023-2024, inicialmente solo se disponia del archivo de desembolsos (3,409 registros = solo indemnizables). Se uso el archivo completo de avisos que contiene los 11,438 registros con ambos dictamenes.

---

## 2. NORMALIZACION DE COLUMNAS

Los nombres de columnas varian entre campanas. Se aplica un mapeo automatico:

| Columna estandarizada | Variantes encontradas |
|----------------------|----------------------|
| DEPARTAMENTO | DEPARTAMENTO |
| PROVINCIA | PROVINCIA |
| DISTRITO | DISTRITO |
| TIPO_CULTIVO | TIPO CULTIVO |
| TIPO_SINIESTRO | TIPO SINIESTRO |
| FECHA_SINIESTRO | FECHA DE SINIESTRO |
| FECHA_AJUSTE | FECHA DE AJUSTE COSECHA (2020-2023), FECHA DE AJUSTE ACTA (2024-2025) |
| FECHA_SIEMBRA | FECHA SIEMBRA (no disponible en 2020-2021) |
| FENOLOGIA | FENOLOGIA (no disponible en 2020-2021) |
| TIPO_COBERTURA | TIPO COBERTURA (no disponible en 2020-2021) |
| DICTAMEN | DICTAMEN |
| ESTADO_INSPECCION | ESTADO INSPECCION |

**Limpieza aplicada a todos los campos de texto:** `str.strip().str.upper()`
- Elimina espacios sobrantes al inicio/final
- Unifica mayusculas/minusculas
- Ejemplo: "Indemnizable" y "INDEMNIZABLE" y "indemnizable" -> "INDEMNIZABLE"

---

## 3. NORMALIZACION DE TIPO_SINIESTRO

### Problema
Los nombres de tipos de siniestro cambiaron entre campanas. Ejemplos:
- "GRANIZO" (2020) -> "GRANIZO Y NIEVE" (2021-2023) -> "GRANIZO" + "NIEVE" separados (2024)
- "HELADA Y BAJAS TEMPERATURAS" (2020-2023) -> "HELADA" (2024)

### Decision tomada
Se creo un mapeo de 36 entradas que normaliza todos los nombres a un valor estandar.

### Tabla completa de normalizacion

| Valor original (en los Excel) | Valor normalizado | Justificacion |
|-------------------------------|-------------------|---------------|
| HELADA Y BAJAS TEMPERATURAS | HELADA | Nombre simplificado en campanas recientes |
| HELADA | HELADA | Ya estandar |
| GRANIZO Y NIEVE | GRANIZO | **Simplificacion: NIEVE se agrupa con GRANIZO en campanas 2021-2023 porque no venian separados** |
| GRANIZO | GRANIZO | Ya estandar |
| NIEVE | NIEVE | Solo disponible separado desde 2024-2025 |
| HUAYCO Y DESLIZAMIENTOS | HUAYCO | **Simplificacion: DESLIZAMIENTO se agrupa con HUAYCO en 2020-2021 porque no venian separados** |
| HUAYCO, AVALANCHA, O DESLIZAMIENTOS | HUAYCO | Idem para 2021-2023 |
| HUAYCO | HUAYCO | Ya estandar |
| DESLIZAMIENTOS | DESLIZAMIENTO | Solo disponible separado desde 2023-2024 |
| LLUVIAS EXCESIVAS O INOPORTUNAS | LLUVIA_EXCESIVA | Nombre 2020-2021 |
| LLUVIA EXCESIVAS O EXTEMPORANEA | LLUVIA_EXCESIVA | Nombre 2021+ (nota: error ortografico original "LLUVIA" sin S) |
| LLUVIAS EXCESIVAS O EXTEMPORANEA | LLUVIA_EXCESIVA | Variante con S |
| INUNDACION / INUNDACION (con tilde) | INUNDACION | Unificacion de tildes |
| SEQUIA / SEQUIA (con tilde) | SEQUIA | Unificacion de tildes |
| SEQUIA CULT RIEGO / SEQUIA CULTIVOS CON RIEGO / SEQUIA PARA CULTIVO CON RIEGO / SEQUIA PARA CULTIVOS DE RIEGO | SEQUIA | **Decision: se unifica sequia de secano y de riego en una sola categoria** |
| VIENTOS FUERTES / VIENTO FUERTE | VIENTO_FUERTE | Singular vs plural |
| EXCESO DE HUMEDAD | EXCESO_HUMEDAD | Directo |
| PLAGAS Y DEPREDADORES | PLAGAS | Abreviacion |
| ENFERMEDADES | ENFERMEDADES | Sin cambio |
| ALTAS TEMPERATURAS | ALTAS_TEMPERATURAS | Directo |
| INCENDIO | INCENDIO | Sin cambio |
| TAPONAMIENTO O NO NACENCIA | TAPONAMIENTO | Abreviacion |
| FALTA DE PISO PARA COSECHAR | FALTA_PISO | Abreviacion |
| ERUPCION VOLCANICA / ERUPCION VOLCANICA (con tildes) | ERUPCION_VOLCANICA | Unificacion tildes |
| TERREMOTO | SISMO | Nombre actualizado en campanas recientes |
| SISMO | SISMO | Ya estandar |
| CONTAMINACION AMBIENTAL (con/sin tilde) | CONTAMINACION_AMBIENTAL | Nuevo desde 2023-2024, 1 caso |

### Implicancias de esta normalizacion
1. **GRANIZO Y NIEVE (2021-2023):** En esas campanas, los ~6,000 avisos de "GRANIZO Y NIEVE" se normalizan a "GRANIZO". Esto significa que eventos de NIEVE pura en esas campanas quedan contados como GRANIZO. Solo desde 2024-2025 se pueden distinguir (252 avisos de NIEVE separados).
2. **HUAYCO Y DESLIZAMIENTOS (2020-2023):** Los ~900 avisos se normalizan a "HUAYCO". Eventos de deslizamiento puro quedan incluidos en HUAYCO. Solo desde 2023-2024 se distinguen.
3. **SEQUIA general vs de riego:** Se unifican en una sola categoria. La distincion (27-135 casos por campana) se pierde.

---

## 4. AGRUPACION POR GRUPO CLIMATICO

### Proposito
Cada riesgo normalizado se asigna a un "grupo climatico" para cruzar con variables medibles de Open-Meteo.

### Tabla de agrupacion

| Riesgo normalizado | Grupo climatico | Variable Open-Meteo asociada | Justificacion |
|-------------------|----------------|------------------------------|---------------|
| HELADA | TEMP_BAJA | temperature_2m_min | Evento de temperatura baja |
| GRANIZO | TEMP_BAJA | temperature_2m_min | Precipitacion solida asociada a frentes frios |
| NIEVE | TEMP_BAJA | temperature_2m_min | Precipitacion solida por temperatura baja |
| SEQUIA | DEFICIT_HIDRICO | precipitation_sum (ausencia) | Falta de agua |
| INUNDACION | PRECIP_EXTREMA | precipitation_sum | Exceso de agua |
| LLUVIA_EXCESIVA | PRECIP_EXTREMA | precipitation_sum | Exceso de precipitacion |
| HUAYCO | PRECIP_EXTREMA | precipitation_sum | Desplazamiento de tierra por exceso de lluvia |
| DESLIZAMIENTO | PRECIP_EXTREMA | precipitation_sum | Movimiento de masa por saturacion hidrica |
| EXCESO_HUMEDAD | PRECIP_EXTREMA | precipitation_sum | Humedad excesiva del suelo |
| FALTA_PISO | PRECIP_EXTREMA | precipitation_sum | Suelo inconsistente por exceso de agua |
| PLAGAS | PRECIP_EXTREMA | precipitation_sum | **Decision subjetiva: plagas se asocian a humedad excesiva como causa raiz. Aprobado por usuario.** |
| VIENTO_FUERTE | VIENTO | windspeed_10m_max | Velocidad del viento |
| ALTAS_TEMPERATURAS | TEMP_ALTA | temperature_2m_max | Evento de temperatura alta |
| ENFERMEDADES | ENFERMEDADES | — (no medible) | **Decision: enfermedades se mantienen como categoria independiente, no se asocian a ninguna variable meteorologica directa. Aprobado por usuario.** |
| INCENDIO | NO_CLIMATICO | — | No es evento meteorologico |
| TAPONAMIENTO | NO_CLIMATICO | — | Causa mecanica/hidrica compleja |
| ERUPCION_VOLCANICA | NO_CLIMATICO | — | Evento geologico |
| SISMO | NO_CLIMATICO | — | Evento geologico |
| CONTAMINACION_AMBIENTAL | NO_CLIMATICO | — | Evento antropogenico/ambiental |

### Logica de cruce con Open-Meteo
Cuando clima_riesgo.py evalua el pronostico para un distrito:
- Si el grupo historico del distrito es PRECIP_EXTREMA y Open-Meteo pronostica lluvia > 20mm/dia -> escalar riesgo
- Si el grupo es TEMP_BAJA y Open-Meteo pronostica temp < 5C -> escalar riesgo
- Si el grupo es DEFICIT_HIDRICO y Open-Meteo pronostica 0mm en 7 dias -> escalar riesgo
- Si el grupo es VIENTO y Open-Meteo pronostica viento > 40km/h -> escalar riesgo
- Si el grupo es ENFERMEDADES o NO_CLIMATICO -> no se cruza con pronostico

---

## 5. TRES CAPAS DE CERTEZA

### Definicion de cada capa

**Capa 1: AVISOS (todos los reportes)**
- Filtro: ninguno (todos los registros)
- Significado: "Se reporto este evento climatico para este cultivo en este lugar y mes"
- Incluye avisos que luego fueron desestimados o declarados no indemnizables
- Utilidad: vision general de la exposicion a riesgos

**Capa 2: INDEMNIZADOS**
- Filtro: `DICTAMEN contiene "INDEMNIZABLE" Y NO contiene "NO INDEMNIZABLE"`
- Significado: "El evento supero el umbral de rendimiento/dano establecido por el SAC"
- Para cultivos transitorios: rendimiento obtenido <= rendimiento asegurado
- Para cultivos permanentes: dano >= CDR (Complemento del Disparador de Riesgo)
- Utilidad: correlacion certificada evento-cultivo

**Capa 3: PERDIDA TOTAL**
- Filtro: `ESTADO_INSPECCION contiene "PERDIDA TOTAL"` O `TIPO_COBERTURA en {COMPLEMENTARIA}`
- Significado: "El evento destruyo el cultivo (perdida total certificada)"
- Incluye tanto perdida total por cobertura catastrofica (todo el sector) como complementaria (zona del sector)
- **Excepcion conocida:** 1 caso en 2023-2024 donde Complementaria tiene DICTAMEN=NO INDEMNIZABLE (inconsistencia en los datos)
- Utilidad: identificar los eventos mas destructivos

### Relacion entre capas
- AVISOS contiene a INDEMNIZADOS contiene a PERDIDA TOTAL (con 1 excepcion)
- 66,346 avisos > 13,273 indemnizados > 8,955 perdida total

---

## 6. INFERENCIA DE MESES DE SIEMBRA Y COSECHA

### Meses de siembra
- **Fuente:** Columna FECHA_SIEMBRA (disponible desde 2021-2022)
- **Extraccion:** `mes = FECHA_SIEMBRA.dt.month`
- **Limitacion:** No disponible para campana 2020-2021 (4,736 registros sin dato de siembra)
- **Precision:** Alta — es la fecha real declarada de siembra

### Meses de cosecha (proxy)
- **Fuente:** Columna FECHA_AJUSTE (fecha de evaluacion en campo)
- **Condicion:** Solo se usa como proxy de cosecha cuando FENOLOGIA esta en {MADURACION, COSECHA, ETAPA PASTOSA, ETAPA LECHOSA}
- **Justificacion:** Si la fenologia al momento del ajuste indica maduracion, significa que el cultivo estaba en fase de cosecha. Las etapas PASTOSA y LECHOSA son fases avanzadas del grano, previas inmediatas a la maduracion completa.
- **Limitacion:** No es la fecha de cosecha real, sino cuando se evaluo. Puede haber dias de diferencia. Ademas, FENOLOGIA no esta disponible para 2020-2021.
- **Decision:** Incluir ETAPA PASTOSA y ETAPA LECHOSA como indicadores de cosecha porque representan estadios avanzados donde ya se puede medir rendimiento. Excluir FLORACION y FRUCTIFICACION porque son etapas intermedias donde aun no se puede evaluar rendimiento.

### Meses de riesgo
- **Fuente:** Columna FECHA_SINIESTRO (fecha de ocurrencia del evento)
- **Extraccion:** `mes = FECHA_SINIESTRO.dt.month`
- **Precision:** Alta — es cuando ocurrio el evento climatico, reportado por el productor
- **Decision de usar mes calendario (1-12) y no mes relativo a la campana:**
  - Open-Meteo trabaja con fechas calendario
  - El clima es estacional por mes calendario (enero = verano/lluvias, julio = invierno/heladas)
  - Es intuitivo para visualizacion ("marzo = pico de lluvias")
  - Los ~480 casos fuera del rango ago-jul de la campana se integran naturalmente

---

## 7. UMBRALES MINIMOS DE REGISTROS

Para evitar que combinaciones con muy pocos datos generen perfiles poco confiables,
se aplican umbrales minimos por capa:

| Nivel | Capa AVISOS | Capa INDEMNIZADOS | Capa PERDIDA TOTAL |
|-------|-------------|-------------------|--------------------|
| Departamental (depto x cultivo) | >= 20 registros | >= 10 registros | >= 5 registros |
| Distrital (depto x prov x dist) | >= 5 registros | >= 3 registros | >= 2 registros |

**Justificacion:** Umbrales mas bajos para capas con menos datos (indemnizados y perdida total son subconjuntos menores). El umbral distrital es menor porque la granularidad geografica reduce naturalmente el conteo.

**Implicancia:** Combinaciones que no alcanzan el umbral NO aparecen en el JSON. Esto significa que algunos distritos o cultivos con pocos avisos historicos no tendran perfil de riesgo.

---

## 8. INTEGRACION CON CAMPANA ACTUAL (2025-2026)

Los JSONs contienen datos de 5 campanas historicas (2020-2025). La campana actual 2025-2026 se integra **dinamicamente** desde `datos["midagri"]` cada vez que la app carga, aplicando las mismas normalizaciones.

Esto significa que:
- El calendario se actualiza automaticamente conforme avanza la campana
- No se requiere regenerar JSONs manualmente
- Los datos de la campana actual se suman a los historicos para el analisis

---

## 9. LIMITACIONES CONOCIDAS

1. **Campana 2020-2021 sin FENOLOGIA/SIEMBRA/COBERTURA:** No se puede inferir siembra/cosecha ni distinguir tipo de cobertura para esa campana.
2. **GRANIZO+NIEVE agrupados (2021-2023):** No se puede distinguir nieve de granizo en esas campanas.
3. **HUAYCO+DESLIZAMIENTO agrupados (2020-2023):** Idem.
4. **SEQUIA de secano y de riego unificadas:** Se pierde la distincion.
5. **PLAGAS como PRECIP_EXTREMA:** Simplificacion — no todas las plagas son por humedad.
6. **Coordenadas distritales aproximadas:** Se generan por jitter desde centroides departamentales, no son las coordenadas reales de los distritos.
7. **Cobertura Open-Meteo:** Grid de 0.25 grados (~28km), puede no capturar microclimas.
8. **1 inconsistencia logica:** Complementaria + NO INDEMNIZABLE en 2023-2024 (se incluye en perdida total igualmente).

---

## 10. REPRODUCIBILIDAD

El script `consolidar_historico.py` en la raiz del proyecto reproduce todo el procesamiento:
```
python consolidar_historico.py
```
Genera los 4 JSONs en `app_sac_github/static_data/`.

El script `auditar_calidad.py` genera el reporte de calidad de datos:
```
python auditar_calidad.py
```
Genera `reporte_calidad_datos_sac.txt` en `app_sac_github/static_data/`.
