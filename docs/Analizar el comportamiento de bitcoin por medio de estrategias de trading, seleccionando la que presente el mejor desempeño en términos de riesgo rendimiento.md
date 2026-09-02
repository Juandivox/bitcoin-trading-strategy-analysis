Analizar el comportamiento de bitcoin por medio de estrategias de trading, seleccionando la que presente el mejor desempeño en términos de riesgo rendimiento. 

Javier Antonio Reyes Espinosa  
 Juan David Ramirez Castilla

ASESOR DEL TRABAJO:   
Jose luis Flores Rueda

UNIVERSIDAD AUTÓNOMA DE BUCARAMANGA   
FACULTAD DE INGENIERÍAS ADMINISTRATIVAS   
PROGRAMA DE INGENIERÍA FINANCIERA  
 LUNES, 18 DE AGOSTO DE 2026  
LÍNEA INVERSIONES BUCARAMANGA 

INTRODUCCIÓN:

OBJETIVOS:   
OBJETIVO GENERAL:  
Analizar el comportamiento de bitcoin por medio de estrategias de trading, seleccionando la que presente el mejor desempeño en términos de riesgo rendimiento.  
OBJETIVOS ESPECÍFICOS:  
   
1\.               Caracterizar las estrategias de trading aplicables a Bitcoin reportadas en la literatura científica reciente, identificando sus elementos principales.  
2\.               Seleccionar las dos estrategias que más se ajusten a las características o al comportamiento de bitcoin, obteniendo la mejor relación riesgo rendimiento.  
3\.               Evaluar el desempeño de las estrategias seleccionadas mediante backtesting y forward Testing, enfocado en la relación riesgo rendimiento.  
4\.               Optimizar la estrategia con mejor desempeño, mediante técnicas de inteligencia artificial potenciado los resultados esperados

PLANTEAMIENTO DEL PROBLEMA Y JUSTIFICACIÓN: 

El mercado de las criptomonedas se caracteriza por presentar importantes fluctuaciones en los precios, siendo Bitcoin uno de los activos de mayor relevancia dentro de este mercado. Su comportamiento presenta diferentes condiciones de volatilidad y tendencia a lo largo del tiempo, lo que representa un desafío para los participantes que buscan desarrollar estrategias de negociación capaces de mantener un desempeño consistente. Veloso et al. (2025) analizaron los cuatro ciclos de *halving* de Bitcoin y evidenciaron una disminución progresiva de las fluctuaciones de precios y de los niveles de volatilidad, lo que sugiere cambios en las condiciones del mercado entre ciclos.

En este contexto, el problema de investigación se centra en determinar qué estrategias de trading pueden presentar un desempeño consistente y robusto en el mercado de Bitcoin bajo diferentes condiciones. Aunque existen numerosos indicadores técnicos y estrategias utilizadas para generar señales de compra y venta, una estrategia que obtiene buenos resultados durante un periodo determinado no necesariamente mantiene su efectividad cuando cambian las condiciones del mercado. Además, los parámetros tradicionales de los indicadores no necesariamente son los más adecuados para las características particulares de Bitcoin. Por esta razón, surge la necesidad de evaluar y comparar diferentes estrategias mediante procedimientos cuantitativos que permitan determinar cuáles presentan mejores niveles de rendimiento y robustez.

La importancia del problema radica en que una estrategia puede presentar una rentabilidad elevada durante determinados periodos y generar pérdidas significativas cuando cambia la dinámica del mercado. Por ello, evaluarla únicamente con información histórica puede producir resultados poco representativos de su comportamiento futuro. El uso conjunto de *backtesting* y *forward testing* permite analizar su desempeño histórico y posteriormente comprobar su comportamiento con información que no fue utilizada durante su construcción o selección, proporcionando una evaluación más rigurosa de su robustez.

Esta problemática ha sido abordada mediante el uso de indicadores técnicos y técnicas de optimización. Roncancio y Valenzuela (2010), Ozturk et al. (2016) y Harsha y Rao (2024) evaluaron diferentes indicadores y combinaciones de reglas de negociación, encontrando resultados favorables para herramientas como el RSI, las medias móviles y la combinación de indicadores de tendencia, volumen y momento. Por otra parte, Mendes et al. (2012), Deng y Sakurai (2014) y Zhang y Khushi (2020) emplearon algoritmos genéticos y otros métodos de optimización para ajustar parámetros de estrategias. En el caso específico de Bitcoin, Omran (2023) utilizó optimización por enjambre de partículas para ajustar parámetros de indicadores técnicos, obteniendo mejoras frente a configuraciones tradicionales.

A pesar de estos avances, se identifica una oportunidad de investigación en la evaluación comparativa de diferentes estrategias específicamente sobre Bitcoin, considerando las variaciones de sus condiciones de mercado. Los antecedentes muestran investigaciones sobre indicadores, combinaciones de reglas y optimización de parámetros; sin embargo, existe la posibilidad de integrar estos enfoques mediante un proceso que permita seleccionar estrategias, evaluar su robustez mediante *backtesting* y *forward testing* y posteriormente optimizar aquella que presente los mejores resultados.

Por lo anterior, la presente investigación busca identificar y evaluar diferentes estrategias de trading aplicables al mercado de Bitcoin, determinar cuáles presentan la mejor relación entre rendimiento y riesgo mediante *backtesting* y *forward testing* y, posteriormente, optimizar la estrategia seleccionada mediante técnicas de inteligencia artificial. Con ello, se pretende aportar evidencia cuantitativa sobre la capacidad de determinadas estrategias para adaptarse a las condiciones del mercado de Bitcoin y establecer parámetros que contribuyan a mejorar su desempeño.

ANTECEDENTES Y ESTADO DEL ARTE : 

En los últimos años, el mercado de las criptomonedas ha despertado un creciente interés entre investigadores e inversores debido a su volatilidad y a las oportunidades de generación de rendimientos asociadas con las fluctuaciones de sus precios. En particular, Bitcoin ha sido objeto de diversas investigaciones orientadas a comprender su comportamiento y desarrollar estrategias de negociación. Por ello, resulta relevante analizar sus ciclos, la efectividad de los indicadores técnicos y las herramientas utilizadas para optimizar estrategias de trading.

Veloso et al. (2025) analizaron el comportamiento de los retornos anormales acumulados y la volatilidad de Bitcoin durante los cuatro halvings ocurridos en 2012, 2016, 2020 y 2024\. Los resultados evidenciaron una disminución progresiva de las fluctuaciones de precios y de los niveles de volatilidad entre los diferentes ciclos, lo que sugiere un proceso de maduración y estabilización del mercado. Este antecedente es relevante para la presente investigación, debido a que las condiciones del mercado pueden variar entre ciclos y, por tanto, una estrategia de negociación puede presentar diferentes niveles de desempeño según el periodo analizado.

Diversos estudios han evaluado el uso de indicadores técnicos tradicionales para generar señales de negociación en mercados financieros. Roncancio y Valenzuela (2010) desarrollaron un modelo de trading algorítmico mecánico para evaluar indicadores como el índice de fuerza relativa (RSI), el oscilador estocástico, Larry Williams %R y la convergencia/divergencia de medias móviles (MACD), aplicados al índice colombiano IGBC, el S\&P 500, el Dow Jones y el par EUR/USD. Los resultados mostraron que el RSI presentó un desempeño superior al de los demás osciladores en términos de rentabilidad acumulada, mientras que Williams %R obtuvo el menor desempeño. Estos resultados evidencian que la efectividad de los indicadores puede variar según el activo y las condiciones del mercado.

De manera similar, Ozturk et al. (2016) desarrollaron un sistema híbrido basado en algoritmos genéticos para seleccionar y combinar reglas de negociación a partir de 24 indicadores técnicos, entre ellos MACD, RSI, media móvil exponencial (EMA) y rango verdadero promedio (ATR). El estudio fue aplicado a los pares EUR/USD y GBP/USD, obteniendo diferentes reglas de negociación con resultados favorables para cada activo. Este trabajo demuestra la utilidad de los métodos de optimización para seleccionar y combinar indicadores técnicos de acuerdo con las características de cada mercado.

Por otra parte, Harsha y Rao (2024) analizaron la combinación de indicadores de tendencia, volumen y momento en acciones subvaloradas y en el índice NIFTY50. Entre los indicadores utilizados se encontraban la media móvil simple (SMA), el volumen en balance (OBV) y el índice de canal de materias primas (CCI). Los resultados mostraron que determinadas combinaciones presentaron un desempeño favorable durante el periodo analizado. Este antecedente resalta la importancia de integrar diferentes tipos de indicadores para construir reglas de negociación.

En conjunto, estas investigaciones evidencian que los indicadores técnicos pueden utilizarse para desarrollar estrategias de negociación y generar señales en diferentes mercados financieros. Entre los indicadores estudiados destacan el RSI y las medias móviles, debido a su capacidad para identificar condiciones de tendencia y posibles señales de entrada o salida. Sin embargo, la mayoría de estos trabajos se concentra en mercados tradicionales, por lo que sus resultados no pueden trasladarse directamente al mercado de Bitcoin. En consecuencia, resulta necesario evaluar empíricamente el comportamiento de estas estrategias en este activo.

Otra línea de investigación corresponde al uso de técnicas de inteligencia artificial y optimización para mejorar los parámetros de las estrategias de trading. Mendes et al. (2012) desarrollaron un sistema aplicado al mercado Forex que utilizó algoritmos genéticos para optimizar diferentes reglas de negociación fundamentadas en indicadores técnicos. Asimismo, Deng y Sakurai (2014) propusieron una metodología para optimizar los parámetros y ponderaciones del RSI en diferentes marcos temporales mediante la integración de algoritmos genéticos y evolución diferencial. Estos estudios muestran que las técnicas de optimización evolutiva permiten adaptar los parámetros de los indicadores a diferentes condiciones de negociación.

Zhang y Khushi (2020) también utilizaron algoritmos genéticos para calibrar las ventanas temporales y los umbrales de diferentes indicadores técnicos, orientando la función de evaluación hacia la mejora del desempeño mediante métricas como los ratios de Sharpe y Sterling. Estos resultados resaltan la importancia de optimizar los parámetros de una estrategia, dado que los valores tradicionales de los indicadores no necesariamente son los más adecuados para todas las condiciones del mercado.

En el contexto específico de Bitcoin, Omran (2023), en su investigación *Bitcoin Optimized Signal Allocation Strategies using Decomposition*, desarrolló una metodología basada en optimización por enjambre de partículas (PSO) con descomposición de doble peso, aplicada al par BTC/USD. El método permitió optimizar las ventanas y umbrales de los indicadores DWMA, ES-ROC y S-RSI, considerando objetivos relacionados con el desempeño de la estrategia y el número de operaciones. Los resultados mostraron mejoras frente a configuraciones tradicionales, evidenciando que los métodos de optimización pueden encontrar parámetros diferentes a los valores convencionales. Este estudio constituye un antecedente relevante debido a que aplica directamente una técnica de optimización al mercado de Bitcoin.

A partir de los estudios revisados se identifican dos tendencias principales. La primera corresponde al uso de indicadores técnicos para construir estrategias de negociación, destacándose herramientas como el RSI, las medias móviles y la combinación de indicadores de tendencia, volumen y momento. La segunda se relaciona con la aplicación de técnicas de inteligencia artificial, como los algoritmos genéticos, la evolución diferencial y la optimización por enjambre de partículas, para seleccionar reglas y ajustar parámetros. No obstante, los resultados dependen del activo, la temporalidad, los indicadores seleccionados y la función objetivo utilizada.

En este sentido, se identifica una oportunidad de investigación relacionada con la evaluación comparativa de diferentes estrategias de trading específicamente sobre Bitcoin. Aunque existen estudios que analizan indicadores técnicos y otros que utilizan inteligencia artificial para optimizar estrategias, son menos frecuentes las investigaciones que integran la comparación de estrategias, la evaluación de su robustez mediante *backtesting* y *forward testing* y la posterior optimización de la estrategia seleccionada.

Por lo anterior, el seguimiento de tendencia constituye una estrategia de interés para la presente investigación, debido a que puede apoyarse en indicadores como las medias móviles para identificar y aprovechar movimientos direccionales del mercado. Sin embargo, su superioridad frente a otras estrategias no se asumirá previamente, sino que será determinada mediante evidencia empírica. Así, la investigación propone identificar diferentes estrategias aplicables a Bitcoin, evaluar su desempeño mediante *backtesting* y *forward testing*, seleccionar aquellas que presenten mayor rendimiento y robustez y, posteriormente, optimizar la estrategia seleccionada mediante técnicas de inteligencia artificial con el propósito de mejorar su adaptación a las condiciones del mercado.

MARCO CONCEPTUAL: 

Bitcoin (BTC) es conceptualmente un sistema monetario digital descentralizado diseñado para operar en una red distribuida de igual a igual (peer-to-peer) sin necesidad de intermediarios financieros o de una autoridad gubernamental centralizada.Btc se diferencia del dinero fiduciario tradicional tradicional, la dinámica monetaria de Bitcoin se rige por una escasez programada, debido a que este tiene un protocolo que limita su volumen a solo 21 millones de unidades, mediante un proceso denominado mineria, en el cual nodos especializados aportan potencia computacional para resolver  eventos programados como halving, influyendo directamente en el precio del activo por la disminución de su oferta en el mercado.

Tecnologia Blockchain y la infraestructura de Registro Distribuido:

La tecnología *Blockchain* se define como una arquitectura de registro distribuido (*Distributed Ledger Technology* o DLT) que constituye un pilar fundamental de carácter inalterable y auditable, garantizando la transparencia en las transacciones digitales de valor.

Mercado de valores: 

Referencias:

1. Corazza, M., Pizzi, C., & Marchioni, A. (2024). A financial trading system with optimized indicator setting, trading rule definition, and signal aggregation through Particle Swarm Optimization. Computational Management Science, 21, Artículo 26\.  
2. Tomás, M. (2026). Evaluación comparativa de arquitecturas de aprendizaje profundo para trading algorítmico de Bitcoin mediante etiquetado por Triple Barrier Labeling (Trabajo final de grado, Ingeniería en Informática). Universidad Católica de Santiago del Estero, Rafaela, Santa Fe, Argentina.  
3. Bello Pérez, F. J. (2025). Diseño y Evaluación de Estrategias de Trading Algorítmico en Bitcoin mediante Modelos Predictivos de Aprendizaje Automático (Trabajo de fin de grado, Grado en Estadística Aplicada). Universidad Complutense de Madrid, Facultad de Estudios Estadísticos, Madrid, España.  
4. López Benítez, E. J. (2023). Sistema de trading algorítmico utilizando un modelo de machine learning generado por auto-machine learning como regla de filtro (Tesis de maestría, Magister en Ingeniería Industrial). Universidad Nacional de Colombia, Departamento de Sistemas e Industrial, Bogotá D.C., Colombia.  
5. Veloso, V., Gatsios, R. C., Magnani, V. M., & Lima, F. G. (2025). Is Bitcoin’s Market Maturing? Cumulative Abnormal Returns and Volatility in the 2024 Halving and Past Cycles. Journal of Risk and Financial Management, 18(5), Artículo 242\.  
6. Khalfouni, M., Frij, R., Lakchouch, N., & Lamarti Sefian, M. (2025). Bitcoin Halving Cycles and Their Impact on the Gold Relationship. Statistics, Optimization and Information Computing, 14, 105–129.  
7. Shynkevich, A. (2026). When the clock strikes: algorithmic trading in cryptocurrency markets. Applied Economics Letters, 33(4).  
8. Hoan, N. T. T., Khang, N. N., & Khanh, P. V. (2025). Applying reinforcement learning in Bitcoin trading to select technical strategies based on Deep Q-Network. Cogent Economics & Finance, 13(1), Artículo 2594873\. https://doi.org/10.1080/23322039.2025.2594873  
9. Polanco, A., & Castellanos-Gamboa, S. (2023). Evaluando técnicas de aprendizaje en refuerzo profundo para realizar trading algorítmico aplicado en acciones de la bolsa de valores de Colombia (Trabajo de grado de maestría, Maestría en Inteligencia Artificial). Pontificia Universidad Javeriana, Bogotá, Colombia.  
10. Ozturk, M., Toroslu, I. H., & Fidan, G. (2016). Heuristic based trading system on Forex data using technical indicator rules. Applied Soft Computing, 43, 170–186.  
11. Garcia, D., & Schweitzer, F. (2015). Social signals and algorithmic trading of Bitcoin. Royal Society Open Science, 2, Artículo 150288\. http://dx.doi.org/10.1098/rsos.150288  
12. Fang, J., Qin, Y., & Jacobsen, B. (2014). How useful are stock market indicators? Journal of Behavioral and Experimental Finance, 4, 25–56.  
13. Mukund Harsha, A., & Kesava Rao, V. V. S. (2024). Exploring profitable opportunities: Analysing technical indicators combinations for profitable trading. Corporate & Business Strategy Review, 5(1), 148–160.  
14. Guerola Pérez, L. (2020). Desarrollo de un sistema de trading algorítmico (Trabajo de fin de grado, Grado en Ingeniería Informática). Universidad Politécnica de Madrid, Escuela Técnica Superior de Ingenieros Industriales, Madrid, España.  
15. López Díaz, E. (2017). Desarrollo de un sistema de trading algorítmico bajo Metatrader (Trabajo de fin de grado, Grado en Ingeniería Informática). Universidad Carlos III de Madrid, Escuela Politécnica Superior, Leganés, España.  
16. Roncancio, C. A., & Valenzuela, A. F. (2010). Desarrollo de un modelo de Trading algorítmico para índices bursátiles y divisas (Taller de grado, Administración de Empresas). Pontificia Universidad Javeriana, Bogotá, Colombia.  
17. Díaz Pérez, M. T., Toro Martínez, B. S., & Álvarez Agudelo, A. K. (2019). Bitcoin como bien intangible en Estados Unidos (Trabajo de grado, Profesional en Negocios Internacionales). Institución Universitaria Esumer, Facultad de Estudios Internacionales, Medellín, Colombia.  
18. Omran, S. M. (2023). Bitcoin Optimized Signal Allocation Strategies. Paper 93, 14(11).  
19. Jiménez Gracia, I. D. (2021). Análisis Financiero y Bursátil del Bitcoin y otras criptomonedas (Trabajo de fin de grado). Universidad de Zaragoza, Facultad de Economía y Empresa, Zaragoza, España.  
20. Izquierdo Cervera, E. (2018). Bitcoin (Trabajo de fin de grado, Grado en Administración y Dirección de Empresas). Universidad Miguel Hernández de Elche, Elche, España.  
21. Thogaram, U., & Asthana, P. K. (2022). Algo Trading: A New Paradigm in The Stock Trading. Amity Business School, Amity University, Raipur, India.  
22. Torres Ardila, M. A., & Sanabria Ospino, A. E. (2004). Metodología de la especulación (Trabajo de investigación). Universidad Autónoma de Bucaramanga, Facultad de Ingeniería Financiera, Bucaramanga, Colombia. \[Anexo / Portada\]  
23. Cruz Martín, R. (2025). \[Trabajo de Fin de Grado sobre Big Data, NLP e Implementación de Modelos de Trading en AWS\] (Trabajo de fin de grado, Ingeniería Informática).  
24. Gomez Sierra, J. S. (2022). \[Diseño y Programación de un Expert Advisor para Metatrader utilizando FxDreema\] (Artículo de investigación académica).

