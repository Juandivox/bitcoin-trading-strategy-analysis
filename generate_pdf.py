import os
import subprocess

html_content = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Informe Técnico - Optimización IA, Buy & Hold y Auditoría de Avances</title>
<style>
  @page {
    size: A4;
    margin: 16mm 14mm 16mm 14mm;
    @bottom-right {
      content: counter(page) " / " counter(pages);
      font-size: 8pt;
      color: #64748b;
    }
  }

  body {
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif;
    color: #1e293b;
    line-height: 1.5;
    font-size: 9.5pt;
    margin: 0;
    padding: 0;
  }

  .header-container {
    border-bottom: 2px solid #2563eb;
    padding-bottom: 12px;
    margin-bottom: 14px;
  }

  .institution {
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #64748b;
    font-weight: 600;
    margin-bottom: 3px;
  }

  h1.title {
    font-size: 14pt;
    color: #0f172a;
    font-weight: 700;
    margin: 0 0 6px 0;
    line-height: 1.25;
  }

  .meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 8px 12px;
    margin-bottom: 16px;
    font-size: 8.5pt;
  }

  .meta-item strong {
    color: #334155;
  }

  h2 {
    font-size: 11pt;
    color: #1e3a8a;
    border-left: 4px solid #2563eb;
    padding-left: 8px;
    margin-top: 16px;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }

  h3 {
    font-size: 9.5pt;
    color: #0f172a;
    margin-top: 10px;
    margin-bottom: 5px;
    font-weight: 600;
  }

  p {
    margin: 0 0 8px 0;
    text-align: justify;
  }

  .card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px 12px;
    margin-bottom: 12px;
    page-break-inside: avoid;
  }

  .card-highlight {
    background: #f0fdf4;
    border-color: #bbf7d0;
  }

  .card-blue {
    background: #eff6ff;
    border-color: #bfdbfe;
  }

  .formula-box {
    background: #f8fafc;
    border-left: 3px solid #3b82f6;
    padding: 6px 10px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 8pt;
    margin: 8px 0;
    color: #1e293b;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 12px 0;
    font-size: 8.5pt;
    page-break-inside: avoid;
  }

  th {
    background: #1e3a8a;
    color: #ffffff;
    font-weight: 600;
    text-align: left;
    padding: 6px 8px;
    border: 1px solid #1e3a8a;
  }

  th.num, td.num {
    text-align: right;
  }

  th.center, td.center {
    text-align: center;
  }

  td {
    padding: 5px 8px;
    border: 1px solid #cbd5e1;
  }

  tr:nth-child(even) td {
    background: #f8fafc;
  }

  ul, ol {
    margin: 0 0 8px 0;
    padding-left: 18px;
  }

  li {
    margin-bottom: 3px;
    text-align: justify;
  }

  .page-break {
    page-break-before: always;
  }

  .footer-note {
    font-size: 7.5pt;
    color: #64748b;
    border-top: 1px solid #e2e8f0;
    padding-top: 6px;
    margin-top: 14px;
    text-align: center;
  }
</style>
</head>
<body>

<div class="header-container">
  <div class="institution">Universidad Autónoma de Bucaramanga · Facultad de Ingenierías Administrativas · Ing. Financiera</div>
  <h1 class="title">Informe de Investigación: Optimización con Inteligencia Artificial, Desempeño Buy & Hold y Auditoría Metodológica</h1>
</div>

<div class="meta-grid">
  <div class="meta-item">
    <strong>Proyecto:</strong> Estrategias de trading algorítmico en Bitcoin (Criterio Riesgo–Rendimiento)<br>
    <strong>Investigadores:</strong> Javier Antonio Reyes Espinosa & Juan David Ramírez Castilla
  </div>
  <div class="meta-item">
    <strong>Asesor Académico:</strong> José Luis Flórez Rueda<br>
    <strong>Fecha de Emisión:</strong> Octubre de 2026 · <strong>Mercado:</strong> Binance Spot (BTC/USDT)
  </div>
</div>

<!-- ========================================== -->
<!-- SECCIÓN 1: OPTIMIZACIÓN IA -->
<!-- ========================================== -->
<h2>1. Parámetros Empleados por la IA para el Optimizador</h2>

<p>
  En el marco de la investigación se utilizó como base estructural la arquitectura de trading compuesta <strong>E2-A (SMA + CCI + Volumen + ATR)</strong> operando en temporalidad de <strong>4 Horas (4H)</strong>. Para maximizar la relación riesgo–rendimiento y mitigar drawdowns severos, se desarrollaron dos fases de optimización algorítmica con Inteligencia Artificial:
</p>

<div class="card card-blue">
  <h3 style="margin-top: 0; color: #1e40af;">A. Optimizador Principal: Enjambre de Partículas (PSO - Particle Swarm Optimization)</h3>
  <p>
    El algoritmo metaheurístico de <strong>Optimización por Enjambre de Partículas (PSO)</strong> fue configurado como el motor definitivo de la tesis (versión 2) para explorar de manera continua y discreta el espacio de parámetros de E2-A.
  </p>
  <ul>
    <li><strong>Población y Evaluación:</strong> 12 partículas navegando simultáneamente durante 20 iteraciones (240 simulaciones de backtesting completas).</li>
    <li><strong>Parámetros Dinámicos del Enjambre:</strong> Factor de inercia <code>w = 0.72</code>, coeficiente cognitivo <code>c₁ = 1.49</code>, coeficiente social <code>c₂ = 1.49</code>, con semilla fija <code>seed = 42</code> para reproducibilidad.</li>
    <li><strong>Inicialización Guiada (Warm-start):</strong> La partícula inicial se ancló en la mejor solución previa (A2), asegurando convergencia superior o idéntica en la muestra.</li>
    <li><strong>Función Objetivo (Fitness):</strong> Maximización del <strong>Ratio de Sharpe anualizado en 4H</strong> sobre el periodo In-Sample (IS70: 2017-08-17 a 2023-12-16).</li>
    <li><strong>Restricciones Matemáticas de Factibilidad:</strong> Penalización severa para configuraciones que generaran menos de 10 operaciones (descartando soluciones artificialmente inactivas) y descarte inmediato de combinaciones ilógicas (<code>entry ≥ exit</code> o <code>sma_fast ≥ sma_slow</code>).</li>
  </ul>

  <div class="formula-box">
    Espacio de Búsqueda: CCI_period [10, 60] | CCI_entry [-150, 50] | CCI_exit [50, 250] | SMA_fast [5, 30] | SMA_slow [100, 250] | Vol_window [10, 60] | Vol_z [-0.5, 1.5]
  </div>
</div>

<p>
  Adicionalmente, en la etapa preliminar se utilizó <strong>TPE / Optuna (Tree-structured Parzen Estimator)</strong> a lo largo de 150 trials, el cual configuró la variante <strong>E2-A A2</strong>. A continuación se presenta el cuadro comparativo definitivo entre la versión base de la literatura (A1), la optimizada por Optuna (A2) y la optimizada por PSO:
</p>

<table>
  <thead>
    <tr>
      <th>Parámetro / Métrica</th>
      <th class="center">E2-A A1 (Paper Original)</th>
      <th class="center">E2-A A2 (Optuna / Base)</th>
      <th class="center">E2-A PSO (Optimizado IA)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Periodo CCI</strong></td>
      <td class="center">20</td>
      <td class="center">58</td>
      <td class="center"><strong>10</strong> (Impulso rápido)</td>
    </tr>
    <tr>
      <td><strong>Umbral Entrada CCI</strong></td>
      <td class="center">-100.0</td>
      <td class="center">-3.0</td>
      <td class="center"><strong>+50.0</strong> (Filtro exigente)</td>
    </tr>
    <tr>
      <td><strong>Umbral Salida CCI</strong></td>
      <td class="center">+100.0</td>
      <td class="center">+186.0</td>
      <td class="center"><strong>+250.0</strong> (Salida extendida)</td>
    </tr>
    <tr>
      <td><strong>SMA Rápida / Lenta</strong></td>
      <td class="center">20 / 50</td>
      <td class="center">18 / 221</td>
      <td class="center"><strong>27 / 227</strong> (~38 días de tendencia)</td>
    </tr>
    <tr>
      <td><strong>Ventana Vol. / Umbral z</strong></td>
      <td class="center">20 / 0.50</td>
      <td class="center">40 / 0.5816</td>
      <td class="center"><strong>60 / 0.1431</strong> (Confirmación)</td>
    </tr>
    <tr>
      <td><strong>Stop Loss Dinámico ATR</strong></td>
      <td class="center">14 / 2.0</td>
      <td class="center">28 / 2.44</td>
      <td class="center"><strong>14 / 2.0</strong></td>
    </tr>
    <tr style="background: #f1f5f9;">
      <td><strong>Sharpe In-Sample (IS70)</strong></td>
      <td class="center" style="color: #dc2626;">-0.579</td>
      <td class="center">1.006</td>
      <td class="center" style="color: #16a34a; font-weight: bold;">1.616 (+60.6%)</td>
    </tr>
    <tr style="background: #f1f5f9;">
      <td><strong>Retorno Total In-Sample</strong></td>
      <td class="center" style="color: #dc2626;">-17.04%</td>
      <td class="center">+160.76%</td>
      <td class="center" style="color: #16a34a; font-weight: bold;">+4,944.71%</td>
    </tr>
    <tr>
      <td><strong>Sharpe Out-of-Sample (OOS30)</strong></td>
      <td class="center" style="color: #dc2626;">-0.699</td>
      <td class="center" style="color: #16a34a; font-weight: bold;">1.816 (Consistente)</td>
      <td class="center">0.847 (Sobreajuste parcial)</td>
    </tr>
    <tr>
      <td><strong>Max Drawdown (OOS30)</strong></td>
      <td class="center">-11.58%</td>
      <td class="center" style="color: #16a34a; font-weight: bold;">-8.82% (Excelente)</td>
      <td class="center">-26.14%</td>
    </tr>
    <tr>
      <td><strong>Retorno Total (FULL 2017–2026)</strong></td>
      <td class="center">-23.51%</td>
      <td class="center">+316.21%</td>
      <td class="center" style="color: #16a34a; font-weight: bold;">+8,351.33%</td>
    </tr>
  </tbody>
</table>

<p>
  <strong>Conclusión metodológica:</strong> El optimizador PSO demostró una enorme capacidad para maximizar el retorno acumulado aprovechando los ciclos alcistas completos. No obstante, al someter las estrategias al periodo no visto (OOS30: 2023–2026), <strong>E2-A A2</strong> exhibió una superioridad defensiva con un Max Drawdown de solo <strong>-8.82%</strong> y Sharpe de <strong>1.816</strong>. Por tal motivo, ambas estrategias han sido incorporadas al bot en tiempo real en Binance Demo para evaluar su desempeño en paralelo.
</p>

<div class="page-break"></div>

<!-- ========================================== -->
<!-- SECCIÓN 2: ESTIMADO BUY & HOLD -->
<!-- ========================================== -->
<h2>2. Estimación y Comportamiento de Comprar y Mantener (Buy & Hold)</h2>

<p>
  Con el objetivo de cuantificar el rendimiento que habría obtenido un inversionista pasivo bajo la estrategia de <strong>Comprar y Mantener (Buy & Hold)</strong> desde el <strong>28 de septiembre de 2026 hasta la fecha actual (14 de octubre de 2026)</strong>, se consultaron las cotizaciones oficiales de alta frecuencia en el mercado Spot de <strong>Binance (BTC/USDT)</strong>:
</p>

<table>
  <thead>
    <tr>
      <th>Evento / Nivel de Precio</th>
      <th class="num">Precio (USDT)</th>
      <th class="center">Fecha y Hora (UTC)</th>
      <th>Contexto y Observación Técnica</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Apertura de Entrada (28-Sep)</strong></td>
      <td class="num"><strong>$84,472.01</strong></td>
      <td class="center">2026-09-28 00:00</td>
      <td>Precio de apertura al inicio de la jornada analizada.</td>
    </tr>
    <tr>
      <td><strong>Cierre de Entrada (28-Sep)</strong></td>
      <td class="num"><strong>$83,500.01</strong></td>
      <td class="center">2026-09-28 23:59</td>
      <td>Precio al cierre de la vela diaria de confirmación.</td>
    </tr>
    <tr>
      <td><strong>Máximo del Periodo (MFE / Run-up)</strong></td>
      <td class="num" style="color: #16a34a;"><strong>$87,220.00</strong></td>
      <td class="center">2026-10-02 16:00</td>
      <td>Máxima ganancia flotante alcanzada (+3.25% a +4.45%).</td>
    </tr>
    <tr>
      <td><strong>Mínimo del Periodo (MAE / Drawdown)</strong></td>
      <td class="num" style="color: #dc2626;"><strong>$80,393.56</strong></td>
      <td class="center">2026-10-08 12:00</td>
      <td>Piso de corrección antes del rebote técnico (-4.83%).</td>
    </tr>
    <tr style="background: #eff6ff;">
      <td><strong>Precio Actual de Cotización</strong></td>
      <td class="num"><strong>$81,630.18</strong></td>
      <td class="center">2026-10-14 21:00</td>
      <td>Último precio de mercado negociado en Binance.</td>
    </tr>
  </tbody>
</table>

<div class="card card-highlight">
  <h3 style="margin-top: 0; color: #166534;">Balance de Rendimiento de Buy & Hold en 17 Días</h3>
  <ul>
    <li>
      <strong>Entrada en Apertura ($84,472.01):</strong>
      Retorno nominal bruto de <strong>-3.37%</strong> (-$2,841.83 USDT por BTC).
      Con costos de transacción de Binance Spot (0.10% taker fee + 5 bps slippage por lado = ~0.30% ida y vuelta), el retorno neto se ubica en <strong>≈ -3.66%</strong>.
    </li>
    <li>
      <strong>Entrada en Cierre ($83,500.01):</strong>
      Retorno nominal bruto de <strong>-2.25%</strong> (-$1,869.83 USDT por BTC).
      Retorno neto final tras comisiones: <strong>≈ -2.54%</strong>.
    </li>
    <li>
      <strong>Diagnóstico de Mercado:</strong> En estas dos semanas y media, Bitcoin transitó una fase de fallo de ruptura alcista sobre los $87,000, cayendo a un soporte en torno a los $80,400 y estabilizándose en una zona de consolidación lateral bajista alrededor de los $81,600.
    </li>
  </ul>
</div>

<!-- ========================================== -->
<!-- SECCIÓN 3: AUDITORÍA DE AVANCES.MD -->
<!-- ========================================== -->
<h2>3. Auditoría y Mejoras en el Documento de Avances (avances.md)</h2>

<p>
  Se realizó una revisión minuciosa del archivo <code>C:\\Users\\jugev\\Downloads\\avances.md</code> con el propósito de garantizar que el documento cumpla con los estándares académicos y de investigación de la Universidad Autónoma de Bucaramanga. Se detectaron 6 incidencias, las cuales fueron corregidas en su totalidad:
</p>

<ol>
  <li>
    <strong>Línea 107 truncada e incompleta (Crítico):</strong> El documento original terminaba abruptamente en la frase <em>"En la siguiente tabla se "</em> omitiendo la presentación de los resultados del algoritmo PSO. Se construyó e insertó la <strong>Tabla 3 comparativa</strong> detallando los parámetros de A1, A2 y PSO, sus métricas IS/OOS y el análisis de degradación por sobreajuste frente a estabilidad defensiva.
  </li>
  <li>
    <strong>Secciones de Limitaciones y Soluciones vacías:</strong> Las secciones <em>"Limitaciones presentadas"</em> y <em>"Propuesta de solución"</em> contenían únicamente viñetas vacías. Fueron redactadas abordando con rigor la heterogeneidad de temporalidades en la literatura previa, la asimetría de los drawdowns extremos de Bitcoin y la brecha técnica entre backtest y ejecución real en exchanges.
  </li>
  <li>
    <strong>Párrafo borrador redundante:</strong> Se removió el párrafo informal inicial de la línea 37, el cual repetía con deficiencias sintácticas la redacción formal presente en la línea 39.
  </li>
  <li>
    <strong>Corrección de encabezado conceptual:</strong> Las Tablas 1 y 2 denominaban erróneamente la columna como <code>CAGR (%) (Volatilidad)</code>. Se corrigió a <code>Retorno Anualizado (CAGR %)</code>, ya que el CAGR mide la tasa geométrica de crecimiento anual compuesto y no la dispersión o volatilidad.
  </li>
  <li>
    <strong>Ajuste de Progreso en Plan de Trabajo:</strong> El Objetivo 4 figuraba con 50% de avance argumentando falta de datos del bot. Se recalculó el avance consolidado entre el <strong>85% y 95%</strong>, clarificando que la optimización algorítmica por IA ya concluyó exitosamente en el marco de la investigación y que la fase actual corresponde al monitoreo operativo forward en Binance Demo.
  </li>
  <li>
    <strong>Ortografía, Estilo y Bibliografía:</strong> Se corrigieron las tildes en nombres institucionales (<em>José Luis Flórez Rueda</em>), se estandarizó la grafía del <em>Ratio de Sharpe</em> y se añadió la referencia seminal del algoritmo de enjambre de partículas: <strong>Kennedy & Eberhart (1995)</strong>.
  </li>
</ol>

<div class="footer-note">
  Documento generado automáticamente a partir de la infraestructura de investigación · Repositorio: bitcoin-trading-strategy-analysis · UNAB 2026
</div>

</body>
</html>
"""

temp_html = os.path.join(os.environ.get('TEMP', '.'), 'informe_temp.html')
desktop_pdf = r'C:\Users\jugev\Desktop\Informe_Investigacion_Bitcoin_IA.pdf'

with open(temp_html, 'w', encoding='utf-8') as f:
    f.write(html_content)

edge_exe = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
cmd = [
    edge_exe,
    '--headless=new',
    '--disable-gpu',
    f'--print-to-pdf={desktop_pdf}',
    temp_html
]

res = subprocess.run(cmd, capture_output=True, text=True)

if os.path.exists(temp_html):
    os.remove(temp_html)

if os.path.exists(desktop_pdf):
    size_kb = os.path.getsize(desktop_pdf) / 1024
    print(f'SUCCESS: PDF successfully generated at {desktop_pdf} ({size_kb:.1f} KB)')
else:
    print('ERROR: PDF was not generated. Return code:', res.returncode)
    print(res.stderr)
