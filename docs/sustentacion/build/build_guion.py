"""Genera el guion de la sustentacion (Word): guion por diapositiva, preguntas probables,
glosario y puntos a verificar antes de sustentar.

Salida: docs/sustentacion/Guion_Sustentacion_Bitcoin.docx
"""
from __future__ import annotations
from pathlib import Path
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

OUT = Path(__file__).parent.parent / "Guion_Sustentacion_Bitcoin.docx"
PURPLE, GREY, DARK = RGBColor(0x92, 0x00, 0xEE), RGBColor(0x6B, 0x6B, 0x6B), RGBColor(0x26, 0x26, 0x26)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.59), Cm(27.94)
sec.left_margin = sec.right_margin = Cm(2.3)
sec.top_margin = sec.bottom_margin = Cm(2.0)
st = doc.styles["Normal"]
st.font.name, st.font.size = "Arial", Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
st.paragraph_format.space_after = Pt(6)
st.paragraph_format.line_spacing = 1.15
for name, size in (("Heading 1", 18), ("Heading 2", 14), ("Heading 3", 12)):
    h = doc.styles[name]
    h.font.name, h.font.size, h.font.bold, h.font.color.rgb = "Arial", Pt(size), True, PURPLE
    h.element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    h.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 10)
    h.paragraph_format.space_after = Pt(6)
    h.paragraph_format.keep_with_next = True


def shade(cell, hex_):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hex_)
    tcPr.append(sh)


def para(t, bold=False, italic=False, color=None, size=None, after=None, style=None):
    p = doc.add_paragraph(style=style)
    r = p.add_run(t)
    r.bold, r.italic = bold, italic
    if color: r.font.color.rgb = color
    if size: r.font.size = Pt(size)
    if after is not None: p.paragraph_format.space_after = Pt(after)
    return p


def rich(parts, style=None, after=None):
    p = doc.add_paragraph(style=style)
    for t, b in parts:
        r = p.add_run(t); r.bold = b
    if after is not None: p.paragraph_format.space_after = Pt(after)
    return p


def bullet(t, label=None):
    p = doc.add_paragraph(style="List Bullet")
    if label:
        r = p.add_run(label); r.bold = True
    p.add_run(t)
    p.paragraph_format.space_after = Pt(3)
    return p


def table(rows, widths, header=True, fill_first=None):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            c = t.cell(i, j)
            c.width = Cm(widths[j])
            c.text = ""
            p = c.paragraphs[0]
            r = p.add_run(str(v))
            r.font.size = Pt(10)
            if header and i == 0:
                r.bold = True; r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF); shade(c, "9200EE")
            elif fill_first and j == 0:
                r.bold = True
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


# ============================================================ portada
p = para("Guion de sustentación", bold=True, size=26, color=PURPLE, after=2)
para("Estrategias de trading en Bitcoin: evaluación, selección y optimización de la estrategia con mejor relación riesgo–rendimiento",
     size=13, color=DARK, after=10)
para("Javier Antonio Reyes Espinosa · Juan David Ramírez Castilla", bold=True, after=0)
para("Asesor: José Luis Flórez Rueda", after=0)
para("Ingeniería Financiera · Universidad Autónoma de Bucaramanga", color=GREY, after=14)

doc.add_heading("Cómo usar este documento", level=2)
bullet("Duración objetivo: unos 18 minutos de exposición (la carrera indica entre 15 y 20). Los tiempos de cada diapositiva suman lo que aparece al final de la sección 1.")
bullet("Cada diapositiva tiene: tiempo, mensaje clave (la idea que el jurado debe recordar), texto sugerido para decir y transición a la siguiente.")
bullet("El texto sugerido es una guía, no para leer. Ensáyenlo hasta decirlo con sus palabras.")
bullet("Reparto sugerido: Javier presenta las diapositivas 2 a 13 (problema, contexto, evaluación y cálculo del Sharpe) y Juan David las 14 a 25 (selección, optimización, bot y conclusiones). Ajústenlo si prefieren otro.")
bullet("Si van cortos de tiempo, resuman las diapositivas 15 y 22; si sobra tiempo, amplíen la 17 (la operación real) o la 20 (PSO frente a TPE).")
bullet("Las diapositivas 26 a 28 son de respaldo: solo se muestran si el jurado pregunta.")
bullet("Antes de sustentar, revisen la sección «Puntos a verificar»: hay diferencias entre el informe y el código que el jurado podría notar.", )

# ============================================================ guion
doc.add_heading("1. Guion por diapositiva", level=1)

S = [
 ("1", "Portada institucional", "0:10",
  "Diapositiva de apertura mientras se prepara el equipo.",
  "Buenas tardes. Somos Javier Reyes y Juan David Ramírez, del programa de Ingeniería Financiera.",
  None),
 ("2", "Estrategias de trading en Bitcoin", "0:30",
  "Presentar el trabajo y la pregunta que guía la investigación.",
  "Nuestro trabajo de grado, asesorado por el profesor José Luis Flórez, busca responder una pregunta: entre varias estrategias de trading aplicadas a Bitcoin, ¿cuál ofrece la mejor relación entre rentabilidad y riesgo? Y, una vez elegida, ¿se puede mejorar calibrando sus parámetros con inteligencia artificial?",
  "Empecemos por entender por qué esta pregunta importa en Bitcoin."),
 ("3", "Planteamiento del problema", "0:45",
  "Bitcoin es volátil y las estrategias publicadas no son comparables: hay que probarlas en Bitcoin.",
  "Bitcoin tiene tres características que hacen difícil elegir una estrategia. Primero, es muy volátil y cambia de comportamiento entre ciclos de halving: quien compró y mantuvo llegó a perder 83,91 %. Segundo, la mayoría de las estrategias publicadas se probó en otros mercados: cinco de las ocho referencias que revisamos usan Forex, acciones o índices. Tercero, cada estudio usa otra temporalidad, de un minuto a un día, y otros parámetros, así que sus resultados no se pueden comparar. De ahí nuestra pregunta: ¿qué estrategia ofrece la mejor relación riesgo–rendimiento en Bitcoin, y cómo optimizar sus parámetros?",
  "Veamos primero cómo se comporta Bitcoin."),
 ("3", "Bitcoin crece mucho, pero también cae mucho", "0:40",
  "En Bitcoin, el riesgo de caída es tan importante como la rentabilidad.",
  "Este es el precio de Bitcoin desde agosto de 2017, en escala logarítmica. Las líneas naranjas marcan los halvings de 2020 y 2024: cada cuatro años, aproximadamente, la emisión de nuevos bitcoins se reduce a la mitad y el mercado cambia de ciclo. Abajo está la caída desde el máximo anterior: quien compró y mantuvo llegó a perder 83,91 %. Por eso, en este activo, una estrategia no se puede juzgar solo por lo que gana; también por cuánto puede perder.",
  "¿Qué dice la literatura sobre cómo operar este activo?"),
 ("4", "La literatura usa otros mercados y plazos", "0:40",
  "Los estudios previos no son comparables entre sí ni con Bitcoin en 4 horas.",
  "Revisamos ocho trabajos representativos, ordenados aquí por mercado y temporalidad. Solo tres usan Bitcoin, y cada uno con una temporalidad y un método distintos. El resto se probó en Forex, acciones o índices, desde velas de un minuto hasta diarias. Con esa diversidad, los resultados no se pueden comparar. Ese es el vacío: probar varias estrategias técnicas sobre Bitcoin con las mismas condiciones para todas.",
  "De ahí salen nuestros objetivos."),
 ("5", "Cuatro objetivos, un capítulo cada uno", "0:30",
  "La estructura del trabajo sigue los cuatro objetivos específicos.",
  "El objetivo general es seleccionar y optimizar la estrategia con mejor relación riesgo–rendimiento. Lo dividimos en cuatro pasos, uno por capítulo: caracterizar, evaluar, seleccionar y optimizar.",
  "Para que la comparación sea justa, todas se probaron con las mismas reglas."),
 ("6", "Mismas reglas para todas las estrategias", "1:00",
  "La comparación es homogénea: mismos datos, costos y ejecución.",
  "Una sola fuente: Binance Data Vision, BTC/USDT en velas de 4 horas; 19.800 velas, de agosto de 2017 a septiembre de 2026. El 70 % inicial se usó para construir (backtesting) y el 30 % final, que la estrategia nunca vio, para validar (forward testing). Todas parten de 10.000 USDT, pagan una comisión de 0,15 % en cada compra y en cada venta (0,10 % de Binance más 0,05 % de deslizamiento), y ejecutan la señal una vela después, para no usar información del futuro. Solo se compra, sin cortos ni apalancamiento. Buy & Hold es la referencia pasiva.",
  "Veamos los resultados."),
 ("7", "Separador: Evaluación", "0:05", "Inicio de la parte de resultados.", "—", None),
 ("8", "SMA y Buy & Hold ganaron más que E2-A A2", "0:45",
  "Si solo se mira la rentabilidad, SMA gana.",
  "Esta es la evolución de los 10.000 USDT en nueve años. SMA, en naranja, creció 57,48 % anual compuesto; Buy & Hold, 37,48 %; la estrategia compuesta E2-A A2, en morado, 17,08 %. Si nos quedáramos aquí, la elección sería obvia. Pero esta curva no muestra cuánto sufrió el capital en el camino.",
  "Eso es lo que muestra la siguiente diapositiva."),
 ("9", "Pero SMA cayó 71 % y Buy & Hold 84 %", "1:00",
  "La caída máxima cambia la lectura: perder mucho exige ganar muchísimo para recuperarse.",
  "Aquí está la caída del capital desde su máximo anterior. Buy & Hold llegó a perder 83,91 %; SMA, 70,96 %; E2-A A2, 27,93 %. La relación no es lineal: quien pierde 84 % necesita ganar 521,5 % solo para volver al punto de partida; quien pierde 28 %, 38,8 %.",
  "Si ponemos rentabilidad y riesgo en el mismo gráfico…"),
 ("10", "E2-A A2: la menor caída entre las rentables", "0:45",
  "En el mapa riesgo–rendimiento, E2-A A2 ocupa una posición única.",
  "Hacia arriba, más rentabilidad anual; hacia la derecha, menor caída máxima. SMA, EMA y MACD rinden más con caídas de 60 % a 71 %. E2-A A2 está sola a la derecha: 17,08 % anual con −27,93 %.",
  "Con esto pasamos a la selección."),
 ("11", "Separador: Selección", "0:05", "Inicio de la parte de selección.", "—", None),
 ("12", "Cómo se calcula el Sharpe", "1:15",
  "El Sharpe descuenta la tasa libre de riesgo y se anualiza; para E2-A A2 da 0,872.",
  "Nuestro criterio principal es el ratio de Sharpe. La idea es simple: al retorno medio de la estrategia le restamos lo que daría una inversión sin riesgo, y lo dividimos por la volatilidad, que es la desviación estándar de los retornos. Así medimos cuánto gana por cada unidad de riesgo. Como tasa libre de riesgo usamos 4 % anual, la referencia de los bonos del Tesoro de EE. UU. a 10 años; por vela de 4 horas es 0,001826 %. Como trabajamos con velas de 4 horas, al final multiplicamos por la raíz de 2.190, las velas que hay en un año, para expresarlo en términos anuales. Ejemplo con E2-A A2: retorno medio de 0,007696 % por vela, menos la tasa libre de riesgo, deja 0,005869 %. Dividido por la volatilidad, 0,3149 %, y anualizado, da 0,872.",
  "Con esta medida comparamos las estrategias."),
 ("13", "El Sharpe más alto no implica el menor riesgo", "0:50",
  "El Sharpe es el criterio principal, pero no basta por sí solo.",
  "SMA tiene el mejor Sharpe, 1,123; E2-A A2 tiene 0,872, por encima de Buy & Hold con 0,749. Pero el Sharpe de SMA viene con una caída de −70,96 %. Por eso lo complementamos con tres criterios: la caída máxima, la consistencia entre construcción y validación, y el número de operaciones, que determina cuánto pesan los costos.",
  "Otro ángulo es cómo gana cada estrategia."),
 ("14", "Acertar más no siempre significa ganar más", "0:45",
  "Hay tres perfiles de operación; E2-A A2 combina alto acierto y alto factor de beneficio.",
  "En horizontal, el porcentaje de operaciones ganadoras; en vertical, el factor de beneficio, lo que se gana por cada unidad perdida. SMA y EMA aciertan una de cada tres, pero cada ganancia es grande. CCI y RSI aciertan tres de cada cuatro, pero ganan poco. E2-A A2 combina las dos cosas: 76,92 % de acierto y factor de beneficio 3,17.",
  "¿Por qué E2-A A2 se comporta así?"),
 ("15", "E2-A A2 opera solo el 9,3 % del tiempo", "0:45",
  "E2-A A2 es selectiva: solo entra al mercado cuando hay confirmación.",
  "Cada franja es un periodo con posición abierta. SMA está dentro del mercado la mitad del tiempo; E2-A A2, solo el 9,3 %, con 39 operaciones en nueve años. Esa selectividad la deja fuera de buena parte de las caídas; el costo es que también se pierde parte de las subidas.",
  "Veamos cómo decide."),
 ("16", "E2-A A2 compra solo si tres filtros coinciden", "1:15",
  "La lógica de la estrategia, explicada con una operación real del backtest.",
  "Primero, tendencia: la media de 18 velas por encima de la de 221. Segundo, impulso: el CCI de 58 velas cruza hacia arriba el nivel −3. Tercero, participación: el volumen estandarizado supera 0,58, es decir, más volumen del habitual. Solo cuando los tres coinciden, compra. Sale cuando el CCI supera 186 o cuando la media corta cae bajo la larga. A la derecha, el 6 de noviembre de 2024 se cumplieron los tres filtros; la estrategia compró y salió el 11 de noviembre, con 20,8 % de ganancia bruta.",
  "Estos parámetros no son los del artículo original: los calibramos."),
 ("17", "Separador: Optimización y bot", "0:05", "Inicio de la parte de optimización y automatización.", "—", None),
 ("18", "Dos formas de buscar los mejores parámetros", "1:00",
  "PSO, la técnica de la literatura, se estancó en los bordes; TPE aprende de cada intento.",
  "Para calibrar E2-A probamos dos técnicas de inteligencia artificial. PSO, optimización por enjambre de partículas, es la que usa la literatura: muchas soluciones candidatas se mueven juntas hacia la mejor que van encontrando. En nuestro caso terminaron amontonadas en los bordes del rango de búsqueda, una señal de que se estaba ajustando demasiado a los datos del pasado. TPE, optimización bayesiana, funciona distinto: aprende de cada intento, compara las combinaciones que dieron buenos y malos resultados, y prueba la siguiente donde hubo mejores resultados. Además, lo evaluamos con años que no usó para calibrar.",
  "¿Cuál funcionó mejor con datos nuevos?"),
 ("19", "PSO se ajustó al pasado; TPE generalizó", "1:00",
  "PSO pierde la mitad de su Sharpe fuera de muestra y queda en los bordes; TPE mejora fuera de muestra.",
  "En gris, el Sharpe en el 70 % de construcción; en morado, en el 30 % de validación. Con los parámetros de PSO, E2-A tenía 1,526 donde se calibró, pero cayó a 0,699 en datos nuevos. Con TPE pasó lo contrario: 0,762 dentro de muestra y 1,412 fuera. A la derecha, el rango de búsqueda de cada parámetro: el punto negro es PSO y el morado TPE. Cuatro de los siete valores de PSO quedaron pegados al borde. Eso indica que el algoritmo se ajustaba al pasado y no a un patrón estable. Por eso descartamos PSO.",
  "Estos son los parámetros que encontró TPE."),
 ("20", "TPE calibró E2-A para Bitcoin", "0:45",
  "Con los parámetros originales la estrategia pierde; calibrada con TPE, gana.",
  "A la izquierda, los parámetros del artículo original frente a los de TPE. El cambio más grande es la media lenta, de 50 a 221 velas: la estrategia pasa a mirar la tendencia de largo plazo. El resultado: el Sharpe sube de −1,463 a 0,872, la rentabilidad de −2,92 % a 17,08 % anual y el acierto de 23,33 % a 76,92 %.",
  "Con la estrategia calibrada, la automatizamos."),
 ("21", "Un bot ejecuta la estrategia cada 4 horas", "0:45",
  "La estrategia se ejecutó de forma automática en Binance.",
  "El bot repite un ciclo cada 4 horas: descarga la vela, calcula los tres filtros, envía la orden a mercado por la API de Binance y registra todo. Funcionó 30 días en el entorno de pruebas de Binance. Abajo, el historial: una compra el 30 de septiembre y una venta el 2 de octubre.",
  "Esa venta tiene una historia."),
 ("22", "Un corte de energía obligó a cerrar a mano", "1:00",
  "La prueba en vivo reveló un riesgo operativo: la continuidad del sistema.",
  "El 30 de septiembre el bot compró a 84.140,36 USDT. Entre el 1 y el 2 de octubre hubo cortes de energía y el equipo se reinició sin recuperar el estado de la posición, así que la cerramos a mano el 2 de octubre. Según el informe, con la regla de salida la pérdida estimada habría sido de 3,41 %, frente a 6,30 % de Buy & Hold. La lección: un bot debe guardar su estado y conciliar sus posiciones al reiniciarse; la continuidad operativa también es control del riesgo.",
  "Cerramos con las conclusiones."),
 ("23", "Conclusiones", "1:15",
  "Cada objetivo tiene un resultado concreto; E2-A A2 equilibra rentabilidad y riesgo.",
  "Primero: de ocho referencias, solo tres usan Bitcoin, cada una con condiciones distintas. Segundo: comparamos las estrategias con los mismos datos, costos y reglas. Tercero: aunque SMA tiene el mayor Sharpe, seleccionamos E2-A A2 porque limita la caída a −27,93 %, frente a −70,96 % de SMA y −83,91 % de Buy & Hold. Cuarto: TPE generalizó mejor que PSO y llevó a E2-A de un Sharpe negativo a 0,872; el bot operó 30 días en Binance Demo. Como trabajo futuro: mejorar la toma de ganancias, validar en otros ciclos de Bitcoin y operar el bot más tiempo antes de usar capital real.",
  None),
 ("24", "Gracias", "0:10",
  "Cierre y apertura de preguntas.",
  "Muchas gracias. Quedamos atentos a sus preguntas y comentarios.", None),
]

total = 0
for n, (_, t, tm, msg, say, trans) in enumerate(S, 1):
    mm, ss = tm.split(":"); total += int(mm) * 60 + int(ss)
    doc.add_heading(f"Diapositiva {n} · {t}", level=3)
    rich([("Tiempo: ", True), (tm + " min", False), ("    Mensaje clave: ", True), (msg, False)], after=3)
    if say != "—":
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.6)
        r = p.add_run(say); r.font.size = Pt(11)
    if trans:
        p = para("Transición: " + trans, italic=True, color=GREY, size=10, after=8)
para(f"Tiempo total estimado: {total // 60} min {total % 60:02d} s.", bold=True, color=PURPLE)

doc.add_heading("Diapositivas de respaldo (26 a 28)", level=3)
bullet(" tabla completa del informe (Tabla 2) por si preguntan por una estrategia concreta.", "Anexo A:")
bullet(" Sharpe en el periodo de construcción (70 %) frente al de validación (30 %). E2-A A2 es la única que mejora fuera de muestra: de 0,762 a 1,412, con caída máxima de −8,82 % en ese tramo. SMA se mantiene (1,154 a 1,119) y RSI pasa a negativo (0,531 a −0,772). Úsenla si preguntan por sobreajuste. Estos datos están en el repositorio, no en las tablas del informe; díganlo así si la muestran.", "Anexo B:")

# ============================================================ preguntas
doc.add_heading("2. Preguntas probables del jurado", level=1)
Q = [
 ("Si SMA tiene el mejor Sharpe, ¿por qué eligieron E2-A A2?",
  "Porque el Sharpe no fue el único criterio. SMA tiene Sharpe 1,123 pero una caída máxima de −70,96 %; E2-A A2 tiene 0,872 con −27,93 %. Para recuperar una caída de 71 % se necesita ganar 244 %; para una de 28 %, 39 %. Además, A2 tiene 76,92 % de acierto, factor de beneficio 3,17 y solo está en el mercado el 9,3 % del tiempo. Elegimos un equilibrio entre un perfil agresivo y uno conservador."),
 ("¿Las diferencias de Sharpe son estadísticamente significativas?",
  "No. En la prueba de hipótesis del repositorio (Jobson-Korkie con corrección de Memmel, bootstrap por bloques y corrección de Holm, sobre retornos diarios) ninguna diferencia entre SMA, E2-A A2 y Buy & Hold es significativa: todos los p-valores superan 0,14. Por eso la elección de A2 no se apoya en un Sharpe superior, sino en su caída máxima mucho menor y su consistencia."),
 ("¿Cómo evitaron el sobreajuste?",
  "Con cuatro medidas: separamos 70 % de los datos para construir y 30 % para validar; incluimos una comisión de 0,15 % en cada compra y en cada venta; ejecutamos las señales con una vela de retraso; y TPE optimizó la mediana del Sharpe en cuatro años fuera de muestra (2021 a 2024), no el resultado de un solo periodo. En el tramo de validación, E2-A A2 mejoró su Sharpe de 0,762 a 1,412 (Anexo B). Descartamos PSO justamente porque mostraba señales de sobreajuste."),
 ("¿Por qué velas de 4 horas?",
  "Es un punto intermedio: filtra buena parte del ruido de las velas de minutos, que además multiplica las operaciones y los costos, y conserva suficientes observaciones (19.800 velas) para evaluar. También es una temporalidad usada en estudios de Bitcoin como el de Tomás (2026)."),
 ("¿Qué pasa con E2-A A2 en un mercado alcista?",
  "Gana menos que el mercado; es el costo de su protección. Entre el 9 de agosto y el 9 de noviembre de 2026, Bitcoin subió 16,02 % y A2 perdió 3,74 % con dos operaciones perdedoras, mientras SMA ganó 12,51 %. En el mes bajista anterior, A2 perdió menos que Bitcoin y que SMA. Es una estrategia para un perfil que prefiere perder poco en las caídas y acepta ganar menos en las subidas."),
 ("¿39 operaciones son suficientes para sacar conclusiones?",
  "Es una muestra pequeña, y lo reconocemos como limitación. Por eso no basamos la selección solo en el porcentaje de acierto, sino también en la caída máxima y en el comportamiento por periodos, y proponemos validar la estrategia en otros ciclos antes de usar capital real."),
 ("Si con los parámetros de PSO el Sharpe del periodo completo es 1,326, mayor que el de A2, ¿por qué no lo usaron?",
  "Porque ese 1,326 incluye el 70 % de los datos con el que PSO se calibró, donde su Sharpe era 1,526. En el 30 % que no vio cayó a 0,699, y su caída máxima del periodo completo es de −50,34 %, frente a −27,93 % de A2. Un Sharpe alto en los datos de calibración no dice nada de cómo se comportará después; por eso medimos fuera de muestra."),
 ("¿Por qué el Sharpe se multiplica por la raíz de 2.190?",
  "Porque el retorno medio y la volatilidad se calculan por vela de 4 horas. La media crece proporcional al número de periodos y la volatilidad con su raíz, así que el cociente anual es el cociente por vela multiplicado por la raíz de las velas al año: 6 velas al día por 365 días, 2.190."),
 ("¿Por qué TPE y no PSO, que es lo que usa la literatura?",
  "Probamos PSO primero. Convergía a los límites del espacio de búsqueda: el periodo del CCI quedó en el mínimo permitido (10) y la salida del CCI y la SMA lenta en el máximo (250). Eso indica que el algoritmo estaba ajustándose al pasado más que encontrando una configuración estable. TPE construye un modelo probabilístico de qué combinaciones funcionan y explora de forma más eficiente; con él usamos una función objetivo fuera de muestra."),
 ("¿El bot operó con dinero real?",
  "No. Operó en Binance Demo, el entorno de pruebas de Binance, que usa precios reales de mercado pero saldo simulado."),
 ("¿Qué hicieron después del corte de energía?",
  "Cerramos la posición manualmente. El incidente mostró que el bot necesita guardar su estado y conciliar la posición con el exchange al reiniciarse. Lo dejamos como hallazgo operativo y como parte del trabajo futuro (infraestructura con respaldo o en la nube)."),
 ("¿Por qué una tasa libre de riesgo de 4 %?",
  "Es la referencia del rendimiento de los bonos del Tesoro de EE. UU. a 10 años, que estuvo cerca de 4 % entre 2023 y 2025; entre 2017 y 2021 fue más bajo, así que 4 % es una exigencia conservadora. Por vela de 4 horas equivale a 0,001826 %. Probamos la sensibilidad con 0 %, 3,8 % y 5 %: SMA conserva el mayor Sharpe y E2-A A2 sigue por encima de Buy & Hold en todos los casos. Con rf = 0 %, A2 sube a 1,144, porque pasa la mayor parte del tiempo fuera del mercado y la tasa libre de riesgo le resta más."),
 ("¿Los costos son realistas?",
  "Sí. Usamos 0,10 % de comisión, que es la tarifa estándar de Binance spot, más 0,05 % de deslizamiento en cada compra y en cada venta: 0,15 % en total. Como E2-A A2 hace pocas operaciones, los costos le pesan menos que a RSI o MACD, que hacen cientos."),
 ("¿Qué es E2-A y de dónde vienen los parámetros A1?",
  "E2-A es una estrategia compuesta: tendencia con medias móviles, impulso con CCI y confirmación con volumen, en línea con Harsha y Rao (2024), que muestran que combinar indicadores de distinta naturaleza puede mejorar el desempeño. A1 usa los parámetros de referencia; A2 es la misma lógica calibrada con TPE para Bitcoin."),
]
for q, a in Q:
    p = doc.add_paragraph(); r = p.add_run(q); r.bold = True; r.font.color.rgb = PURPLE
    p.paragraph_format.space_after = Pt(2); p.paragraph_format.keep_with_next = True
    para(a, after=10)

# ============================================================ glosario
doc.add_heading("3. Glosario", level=1)
para("Conceptos que pueden aparecer en la exposición o en las preguntas, ordenados por tema.", color=GREY)
G = {
 "Mercado y datos": [
  ("Bitcoin (BTC)", "Moneda digital descentralizada con emisión limitada a 21 millones de unidades."),
  ("Halving", "Evento que, cada cuatro años aproximadamente, reduce a la mitad la recompensa por bloque y, con ella, la emisión de nuevos bitcoins. Suele marcar el cambio de ciclo del mercado."),
  ("Exchange", "Plataforma donde se compran y venden criptoactivos. En este trabajo, Binance."),
  ("Par BTC/USDT", "Precio de Bitcoin expresado en USDT, una moneda estable que sigue al dólar."),
  ("Spot", "Mercado de contado: se compra el activo real, sin derivados ni apalancamiento."),
  ("Vela de 4 horas", "Resumen del precio en un intervalo de 4 horas: apertura, máximo, mínimo, cierre y volumen."),
  ("Binance Data Vision", "Repositorio público de Binance con el histórico de velas y operaciones."),
 ],
 "Indicadores técnicos": [
  ("Análisis técnico", "Estudio de precios y volúmenes históricos para anticipar movimientos futuros."),
  ("SMA (media móvil simple)", "Promedio del precio de cierre de las últimas n velas. Si la SMA corta está por encima de la larga, se considera tendencia alcista."),
  ("EMA (media móvil exponencial)", "Media móvil que da más peso a los precios recientes."),
  ("MACD", "Diferencia entre dos medias exponenciales; su cruce con una línea de señal indica cambios de tendencia."),
  ("RSI (índice de fuerza relativa)", "Oscilador entre 0 y 100 que señala sobrecompra (valores altos) o sobreventa (valores bajos)."),
  ("CCI (índice de canal de materias primas)", "Mide cuánto se aleja el precio de su promedio. En E2-A, su cruce hacia arriba marca el impulso de entrada."),
  ("ATR (rango verdadero promedio)", "Mide la volatilidad a partir del rango de cada vela. Se usa para fijar stops dinámicos."),
  ("Z-score del volumen", "Volumen estandarizado: cuántas desviaciones estándar está el volumen actual por encima o por debajo de su media. Confirma si un movimiento tiene participación."),
 ],
 "Estrategias": [
  ("Seguimiento de tendencia", "Estrategia que compra cuando el precio muestra una dirección alcista y sale cuando esta se pierde."),
  ("Estrategia compuesta", "Combina indicadores de distinta naturaleza (tendencia, impulso, volumen) para filtrar señales falsas. E2-A es compuesta."),
  ("E2-A A1 / E2-A A2", "Misma estrategia compuesta con dos juegos de parámetros: A1, los de referencia; A2, los calibrados con TPE para Bitcoin."),
  ("Buy & Hold", "Comprar al inicio y mantener hasta el final. Es la referencia pasiva."),
  ("Solo largos (long-only)", "La estrategia solo compra y vende lo comprado; no apuesta a la baja (ventas en corto)."),
  ("Apalancamiento", "Operar con dinero prestado para ampliar la posición. No se usó."),
  ("Trading algorítmico", "Ejecución automática de operaciones según reglas programadas, sin decisión manual."),
 ],
 "Evaluación": [
  ("Backtesting", "Simulación de la estrategia sobre datos históricos. Aquí, el 70 % inicial de los datos."),
  ("Forward testing", "Evaluación sobre datos que no se usaron para construir la estrategia. Aquí, el 30 % final y la prueba en vivo."),
  ("Dentro / fuera de muestra (IS / OOS)", "Datos usados para construir la estrategia (in-sample) frente a datos reservados para validarla (out-of-sample)."),
  ("Walk-forward", "Validación por bloques en el tiempo: se calibra con el pasado y se prueba en el año siguiente, repitiendo hacia adelante. TPE usó los años 2021 a 2024."),
  ("Sobreajuste (overfitting)", "Cuando la estrategia se ajusta tanto al pasado que pierde capacidad de funcionar con datos nuevos."),
  ("Sesgo de anticipación y lag", "Usar información que en la realidad aún no se conocía. Se evita ejecutando la señal una vela después (lag = 1)."),
  ("Comisión", "Pago al exchange por cada compra o venta. Aquí, 0,10 % de Binance; con el deslizamiento, 0,15 % por operación."),
  ("Deslizamiento (slippage)", "Diferencia entre el precio esperado y el de ejecución. Aquí, 0,05 % en cada compra o venta (5 puntos básicos)."),
  ("Punto básico (pb)", "Centésima parte de un punto porcentual: 1 pb = 0,01 %."),
 ],
 "Métricas de riesgo y rendimiento": [
  ("CAGR (crecimiento anual compuesto)", "Rentabilidad anual equivalente: (capital final / capital inicial)^(1/años) − 1."),
  ("Volatilidad anual", "Desviación estándar de los retornos, llevada a escala anual. Mide cuánto fluctúa la estrategia."),
  ("Ratio de Sharpe", "(Retorno medio − tasa libre de riesgo) / volatilidad, anualizado. Rentabilidad extra por unidad de riesgo. Se calculó con velas de 4 horas (2.190 por año)."),
  ("Tasa libre de riesgo", "Rendimiento de una inversión sin riesgo; aquí, 4 % anual (bonos del Tesoro de EE. UU. a 10 años)."),
  ("Caída máxima (max drawdown)", "Mayor pérdida desde un máximo hasta un mínimo posterior."),
  ("Duración de la caída", "Tiempo que tarda el capital en recuperar su máximo anterior."),
  ("Asimetría pérdida–recuperación", "Para recuperar una pérdida P se necesita ganar P / (1 − P). Perder 50 % exige ganar 100 %."),
  ("Operación (trade)", "Una entrada y su salida. E2-A A2 hizo 39 en nueve años."),
  ("Porcentaje de acierto (win rate)", "Proporción de operaciones que terminan con ganancia."),
  ("Factor de beneficio (profit factor)", "Suma de las ganancias dividida entre la suma de las pérdidas. 3,17 significa que se ganan 3,17 por cada 1 perdido."),
  ("Payoff", "Ganancia media de las operaciones ganadoras dividida entre la pérdida media de las perdedoras."),
  ("Exposición", "Porcentaje del tiempo con una posición abierta."),
 ],
 "Optimización y estadística": [
  ("Optimización de parámetros", "Búsqueda de los valores de los indicadores (periodos, umbrales) que maximizan una función objetivo."),
  ("Retorno en exceso", "Retorno de la estrategia menos la tasa libre de riesgo del mismo periodo. Es el numerador del Sharpe."),
  ("Anualización", "Llevar una medida por vela a escala anual. En el Sharpe se multiplica por la raíz de 2.190 velas al año."),
  ("Partícula, mejor personal y mejor del grupo (PSO)", "Cada partícula es una combinación de parámetros. Recuerda su mejor posición (mejor personal) y conoce la mejor de todo el enjambre (mejor del grupo); su velocidad se ajusta hacia ambas."),
  ("Densidades ℓ(x) y g(x) (TPE)", "Distribución de los valores de un parámetro entre los ensayos buenos, ℓ(x), y entre los malos, g(x). TPE prueba donde ℓ(x)/g(x) es mayor."),
  ("Parámetro en el límite", "Valor óptimo que queda en el borde del rango de búsqueda. Indica que el optimizador quería ir más allá o que se está ajustando al ruido; es una señal de alerta de sobreajuste."),
  ("Función objetivo", "Lo que el optimizador intenta maximizar. Aquí, la mediana del Sharpe fuera de muestra en 2021–2024."),
  ("TPE (Tree-structured Parzen Estimator)", "Optimizador bayesiano: separa los ensayos buenos de los malos, modela qué valores aparecen en cada grupo y propone el siguiente ensayo donde es más probable mejorar."),
  ("Optuna", "Librería de Python que implementa TPE."),
  ("Ensayo (trial) y semilla", "Cada ensayo es una combinación de parámetros evaluada. La semilla fija la aleatoriedad para que el resultado sea reproducible."),
  ("PSO (optimización por enjambre de partículas)", "Metaheurística en la que un grupo de «partículas» explora el espacio de soluciones guiándose por su mejor resultado propio y el mejor del grupo. Se descartó por sobreajuste."),
  ("Prueba de hipótesis de Sharpe", "Verifica si la diferencia entre dos Sharpe puede deberse al azar. Se usaron Jobson-Korkie con corrección de Memmel y bootstrap por bloques."),
  ("Corrección de Holm", "Ajuste de los p-valores cuando se hacen varias comparaciones a la vez."),
 ],
 "Implementación": [
  ("Bot de trading", "Programa que ejecuta la estrategia automáticamente."),
  ("API", "Interfaz para que un programa se comunique con el exchange: consultar datos y enviar órdenes."),
  ("Orden a mercado", "Orden que se ejecuta de inmediato al mejor precio disponible."),
  ("Binance Demo", "Entorno de pruebas de Binance con precios reales y saldo simulado."),
  ("Conciliación de posiciones", "Verificar que la posición que el bot cree tener coincida con la que registra el exchange, sobre todo tras un reinicio."),
  ("Stop loss", "Orden o regla que cierra la posición si la pérdida alcanza un límite."),
 ],
}
for tema, items in G.items():
    doc.add_heading(tema, level=2)
    table([("Término", "Definición")] + items, [5.0, 11.9], fill_first=True)

# ============================================================ puntos a verificar
doc.add_heading("4. Puntos a verificar antes de sustentar", level=1)
para("La carrera pide que la información de las diapositivas sea correcta y coherente con el documento entregado. "
     "Al cruzar el informe con el código del repositorio aparecen estas diferencias. Conviene decidir cómo responder "
     "a cada una antes de la sustentación.", after=8)
V = [
 ("Stop ATR.", " El informe (secciones 1.3.2 y 1.3.3, Tabla 5) presenta el ATR como cuarto componente de E2-A. En el código, el stop ATR no se aplicó en ningún backtest ni en el bot (docs/ANEXO_METODOLOGICO.md, sección 6). Las cifras de E2-A A2 (Sharpe 0,872, caída de −27,93 %) son sin stop. Las diapositivas muestran tres filtros y la salida real. Si el jurado pregunta por el ATR, la respuesta honesta es que se evaluó en el diseño pero no forma parte de la versión evaluada."),
 ("«La entrada llegó a stop con una pérdida de 3,41 %».", " No hay stop en la estrategia, y el registro de órdenes muestra una venta manual a 84.434,00 después de comprar a 84.140,36, es decir, por encima del precio de entrada. Las diapositivas presentan el −3,41 % como «escenario de la regla de salida, según el informe (Tabla 6)». Confirmen de dónde sale esa cifra y la de −6,30 % antes de exponer."),
 ("Variante del bot.", " bot-demo/config/bot.yaml tiene strategy_variant: PSO, y AGENTS.md describe el bot como «E2-A PSO». El informe y la presentación anterior dicen que se automatizó E2-A A2. Confirmen qué parámetros corrió el bot en la prueba de 30 días. La diapositiva 22 no nombra la variante. Ojo: si el bot corrió PSO, son justo los parámetros que la diapositiva 20 muestra como sobreajustados; preparen la respuesta."),
 ("PSO frente a TPE.", " El capítulo IV del informe dice que la estrategia se optimizó con PSO; la conclusión del objetivo 4 dice que PSO se descartó y se usó TPE. Las diapositivas siguen la conclusión."),
 ("Fechas y duración.", " El informe menciona el «31 de septiembre», fecha que no existe, y habla de 28 y de 30 días de prueba en distintos lugares. Las diapositivas dicen «1–2 oct» y «30 días»."),
 ("Tabla 3, E2-A A2.", " El texto dice «drawdown del −22,4 %», pero ese valor es el peor año. La caída máxima es −27,93 %. En la sustentación usen −27,93 %."),
 ("Número de estrategias.", " El informe habla de 8 (conclusión del objetivo 2) y de 12 (capítulo III), pero la Tabla 2 tiene 9. Las diapositivas muestran siete: se omitieron E2-A A1 y E2-C, que perdían dinero (Sharpe −1,463 y −0,262). Si preguntan por ellas, están en la Tabla 2 del informe; A1 aparece solo como punto de partida en la diapositiva de calibración con TPE."),
 ("Mercado real o Demo.", " La página del bot dice «mercado real con una API de Binance»; la sección 1.2 dice Binance Demo. Las diapositivas dicen Binance Demo."),
 ("Tabla 2.", " Su título menciona backtesting (IS70) y forward testing (OOS30), pero los valores son del periodo completo 2017–2026. Si preguntan por la separación, usen el Anexo B (diapositiva 28)."),
 ("Datos nuevos de PSO frente a TPE.", " El Sharpe dentro y fuera de muestra de PSO (1,526 y 0,699) y el gráfico de parámetros en el límite (diapositiva 20) salen del backtest del repositorio, no de las tablas del informe. Los parámetros PSO son los de la Tabla 5. Si la muestran, digan que es un cálculo complementario con el mismo motor."),
 ("Tasa libre de riesgo.", " El informe usa rf = 4 % (Tabla 4), pero no dice de dónde sale. La diapositiva 13 la atribuye a los bonos del Tesoro de EE. UU. a 10 años. Ojo: la documentación del repositorio (AGENTS.md) la describe como letras a 3 meses (T-Bill 3M). Usen una sola referencia y, si es posible, agréguenla al informe."),
 ("Detalle del TPE.", " El número de ensayos, la semilla y la función objetivo no aparecen en el informe; vienen del código. Los parámetros de A2 salieron de una búsqueda de 150 ensayos, y la re-selección de 100 ensayos (semilla 42) los confirmó."),
]
for i, (h, t) in enumerate(V, 1):
    p = doc.add_paragraph(style="List Number")
    r = p.add_run(h); r.bold = True
    p.add_run(t)
    p.paragraph_format.space_after = Pt(5)

doc.add_heading("Fuentes de las cifras", level=2)
para("Todas las cifras de las diapositivas principales salen del informe final (Tablas 1 a 6). Las curvas y la operación de ejemplo se "
     "generaron con el motor del repositorio, que reproduce exactamente los valores de la Tabla 2. Los scripts están en "
     "docs/sustentacion/build/ (export_data.py, make_figs.py, build_deck.py, build_guion.py).", color=GREY, size=10)

doc.save(OUT)
print("OK", OUT, "| tiempo total", total // 60, "min", total % 60, "s")
