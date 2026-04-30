# Inconsistencias detectadas en el Excel del Semáforo de Alertas SAC

**Documento:** `Dashboard SAC 25-26 Aviso Siniestro Agricola 13.04.26 Con semáforo.xlsx`
**Hoja:** AVISOS (9,568 filas, 72 columnas, fecha de corte 13/04/2026)
**Fecha del análisis:** 30/04/2026

Hola — al integrar el motor del Semáforo en la app SAC y validar fila a fila contra este Excel, **logramos match 100% exacto en las 6 alertas** (todas las 9,568 filas). En el camino detectamos algunas pequeñas inconsistencias en las fórmulas que vale la pena conocer y, eventualmente, ajustar. Nada crítico — los resultados son correctos en términos de clasificación verde/ámbar/rojo. Son detalles de pulido que ahora la app reproduce literalmente para mantener compatibilidad con tu archivo, pero que se podrían normalizar en una próxima versión del Excel.

Las ordeno de menor a mayor impacto.

---

## 1. Bugs tipográficos: falta espacio antes de "días"

**Severidad:** baja (cosmético, no afecta cálculos)

En 3 de las variantes de output, la fórmula tiene un espacio faltante antes de la palabra "días":

| Alerta | Celda | Output del Excel | Output esperado |
|--------|-------|-----|-----|
| 01 ATENCION | BG2 | `ALERTA ROJA SIN ATENCION (12días)` | `ALERTA ROJA SIN ATENCION (12 días)` |
| 03 AJUSTE | BK2 | `ALERTA VERDE SIN AJUSTE 01 (10días)` | `ALERTA VERDE SIN AJUSTE 01 (10 días)` |
| 03 AJUSTE | BK2 | `ALERTA AMBAR SIN AJUSTE PROG (12días)` | `ALERTA AMBAR SIN AJUSTE PROG (12 días)` |

**Por qué pasa:** las fórmulas tienen `&"d días)"` con espacio en la mayoría de casos pero `&"días)"` (sin espacio) en estos tres.

**Cómo arreglarlo:** en la fórmula de las celdas BG2 y BK2, agregar el espacio faltante:

```
ANTES:  "ALERTA VERDE SIN AJUSTE 01 ("&NETWORKDAYS.INTL(...)&"días)"
DESPUÉS: "ALERTA VERDE SIN AJUSTE 01 ("&NETWORKDAYS.INTL(...)&" días)"
```

**Impacto:** ninguno en la lógica. Solo afecta la legibilidad y rompe la consistencia entre las distintas variantes de la misma alerta.

---

## 2. Espacio faltante en "REPROGRAMACION01"

**Severidad:** baja (cosmético)

La fórmula BM2 (Alerta 04) tiene una variante con espacio inconsistente:

| Output del Excel | Output esperado |
|-----|-----|
| `ALERTA ROJA SIN REPROGRAMACION01` | `ALERTA ROJA SIN REPROGRAMACION 01` |

Mientras que las otras variantes sí tienen espacio: `"REPROGRAMACION 01"`, `"REPROGRAMACION 02"`, `"REPROGRAMACION 03"`.

**Cómo arreglarlo:** en la fórmula de BM2, cambiar `"ALERTA ROJA SIN REPROGRAMACION01"` por `"ALERTA ROJA SIN REPROGRAMACION 01"`.

---

## 3. Typo en nombre de columna: "Diferecna"

**Severidad:** muy baja (solo nombre de columna interna)

La columna BF se llama `Diferecna` en el header — debería ser `Diferencia`. No la usa ninguna fórmula visible, pero confunde al revisar.

---

## 4. "ATENCION OK" como output de Alerta 03 puede generar ambigüedad

**Severidad:** media (puede confundir reportes)

En la Alerta 03 (AJUSTE), cuando OBSERVACION contiene "PROGRAMADO CARTA" y los días superan 15, el Excel devuelve `"ATENCION OK (X días)"`. Esto suena como un output de la Alerta 01 (ATENCION), lo que puede confundir al filtrar o agrupar por tipo de alerta.

**Caso concreto:**
- Alerta 01 (ATENCION) puede devolver: `"ATENCION OK (3 días)"`
- Alerta 03 (AJUSTE) puede devolver el mismo string: `"ATENCION OK (X días)"` (caso "PROGRAMADO CARTA")

Si alguien filtra avisos por `"ATENCION OK"` sin distinguir la alerta de origen, los puede mezclar.

**Sugerencia:** cambiar el output de la Alerta 03 a algo más específico, como `"AJUSTE OK CON CARTA (X días)"` o `"ATENCION OK POR CARTA (X días)"`. Así queda claro de qué alerta proviene.

---

## 5. Lista reducida de feriados (24 fechas en vez de 32)

**Severidad:** media (puede afectar conteo de días)

La columna BT2:BT25 lista 24 feriados (12 por año, 2025 y 2026). La lista oficial de feriados nacionales del Perú tiene **16 feriados/año** (32 en 2 años). En la lista del Excel **no se incluyen**:

| Fecha | Feriado oficial Perú |
|-------|---------------------|
| 06-07 | Batalla de Arica y Día de la Bandera |
| 07-23 | Día de la Fuerza Aérea del Perú |
| 08-06 | Batalla de Junín |
| 12-09 | Batalla de Ayacucho |

**Implicancia:** las alertas que cuentan días hábiles considerarán esos días como "trabajados" cuando legalmente son feriados. Para avisos que cruzan estas fechas, el conteo puede tener 1-2 días de diferencia respecto al calendario oficial.

**Sugerencia:**
- Si la intención es contar **días bancarios reales del SAC** (que probablemente trabajan en algunos de esos feriados), está OK como está — pero conviene documentarlo en una nota dentro del Excel.
- Si la intención es **días hábiles legales**, agregar las 4 fechas faltantes a BT26:BT33 y extender el rango referenciado en las fórmulas (`$BT$2:$BT$25` → `$BT$2:$BT$33`).

---

## 6. Dos códigos distintos de "fin de semana" en NETWORKDAYS.INTL

**Severidad:** baja (probablemente intencional, conviene documentarlo)

Las fórmulas usan dos códigos distintos para "qué días son no laborables":

| Alertas | Código | Significado |
|---------|--------|-------------|
| 01, 02, 03, 04, 05 | `11` | **Solo domingo** es no laborable (sábado SÍ cuenta como hábil) |
| 06 (PAGO SAC) | `1`  | Sábado **y** domingo no laborables (clásico) |

**Por qué probablemente esté así:** las alertas 01-05 son operativas (atención, ajuste, padrón) y el equipo trabaja sábados. La alerta 06 (Pago SAC) involucra al banco, que solo opera lun-vie.

Está bien que sea distinto, pero merece quedar **explícitamente documentado** en una nota del Excel, porque a primera vista parece error de tipeo (el `1` vs el `11` se confunde fácil).

**Sugerencia:** agregar una nota al pie del Excel explicando el criterio.

---

## 7. Umbral "1 día" para reprogramación vencida

**Severidad:** muy baja (decisión de negocio que conviene revisar)

En la Alerta 04, la fórmula marca "ALERTA ROJA CON REPROGRAMACION 01/02/03" cuando `NETWORKDAYS.INTL(reprog, today, 11) > 1`. Esto significa que si la reprogramación fue **ayer** (1 día hábil de diferencia), **no** se marca como vencida — solo si fue hace 2+ días hábiles.

**Posibles interpretaciones:**
- **Intencional:** se da margen de 1 día porque la reprogramación se reagenda con frecuencia y el sistema demora en actualizar.
- **Bug:** debería ser `>= 1` (vencida desde el día siguiente).

**Sugerencia:** confirmar con el equipo cuál es la regla deseada y documentarla.

---

## 8. `FECHA DE REPORTE` solo en una celda

**Severidad:** alta (riesgo de romper todo el Excel)

La fecha del corte se guarda únicamente en la celda **BS2** (`$BS$2` en las fórmulas). Si alguien edita esa celda accidentalmente, **todas las alertas se rompen** o devuelven valores incorrectos en las 9,568 filas.

**Sugerencias (cualquiera funciona):**
- **Opción A (mínima):** dar a la celda BS2 un nombre con `Definir nombre → FECHA_CORTE`. Las fórmulas usarían `FECHA_CORTE` en vez de `$BS$2`. Cuando alguien borre la celda, el nombre se mantiene (con error visible).
- **Opción B (mejor):** poner la fecha en una celda destacada con etiqueta clara fuera de la tabla principal (por ejemplo, en una hoja "Configuración" con celda `B1` llamada `FECHA_CORTE`). Permite que cualquier usuario la actualice sin tocar la tabla de avisos.
- **Opción C (mejor todavía):** usar `=TODAY()` directamente. Excel calcula automáticamente la fecha de hoy cada vez que se abre el archivo.

---

## Resumen ejecutivo

| # | Inconsistencia | Severidad | Fix sugerido |
|---|---|---|---|
| 1 | Falta espacio antes de "días" en 3 variantes | Baja | Agregar espacio en BG2 y BK2 |
| 2 | "REPROGRAMACION01" sin espacio | Baja | Agregar espacio en BM2 |
| 3 | Typo "Diferecna" | Muy baja | Renombrar columna BF |
| 4 | "ATENCION OK" ambiguo en Alerta 03 | Media | Renombrar a "AJUSTE OK CON CARTA" |
| 5 | Lista de feriados reducida | Media | Agregar 4 feriados nacionales o documentar |
| 6 | Dos códigos de weekend distintos | Baja | Documentar la decisión en el Excel |
| 7 | Umbral "1 día" en reprogramación | Muy baja | Confirmar regla con el equipo |
| 8 | FECHA DE REPORTE en una sola celda | Alta | Usar nombre definido o `=TODAY()` |

**Lo positivo:** la lógica de las 6 alertas está bien armada y produce resultados correctos. Las inconsistencias son detalles de pulido y mantenibilidad. La app SAC ya replica el comportamiento al 100%.

---

*Validado el 30/04/2026 — match 100% exacto en las 9,568 filas del Excel oficial. Cualquier cambio en las fórmulas del Excel se debe coordinar con el equipo de la app para mantener la consistencia.*
