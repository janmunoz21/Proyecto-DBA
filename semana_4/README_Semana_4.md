# Entrega Semana 4 - Análisis Geoespacial Reproducible por Municipio

## 1. Objetivo de la semana

Esta entrega documenta el flujo reproducible que calcula, para cada municipio PDET, el número total de huellas de edificios y el área acumulada de techos en metros cuadrados. El análisis se ejecuta sobre las colecciones `buildings_microsoft` y `buildings_google`, y los resultados se persisten en MongoDB para consultas posteriores, comparación entre fuentes y trazabilidad.

---

## 2. Lo que pide la entrega de la semana 4

Según [project.md](../project.md), la semana 4 debe incluir:

- reproducibilidad y metodología;
- precisión de las operaciones espaciales;
- estructura de salida con tablas y mapas.

En el código actual, eso se materializa en el análisis geoespacial por municipio, el ranking de municipios, la tabla comparativa y la auditoría exploratoria completa.

---

## 3. Funcionalidades implementadas

### 3.1 Análisis geoespacial por municipio

El módulo [eda_buildings.py](../eda_buildings.py) implementa `run_spatial_analysis()`, que:

- carga los municipios PDET desde la colección `municipalities`;
- consulta las huellas de edificios de Microsoft y Google con operaciones espaciales sobre MongoDB;
- calcula `building_count`, `total_area_m2` y `avg_area_m2` por municipio y por dataset;
- persiste los resultados en `analysis_results`;
- reanuda el cálculo solo para municipios pendientes, sin repetir lo ya procesado.

### 3.2 Ranking y comparación

El mismo módulo genera:

- top 10 municipios por área total de techos para cada dataset;
- tabla comparativa Microsoft vs Google con conteos, estadísticas de área y presencia de índice espacial.

### 3.3 Auditoría exploratoria completa

La función `run_eda()` añade una auditoría integral con:

- conteo de documentos por colección;
- estadísticas de `area_m2`;
- validación de calidad de datos;
- análisis del campo de confianza de Google;
- revisión de índices;
- muestra de documentos;
- ejecución del análisis geoespacial;
- ranking por área;
- tabla comparativa final.

### 3.4 Reparación y reindexación

El módulo [load_buildings.py](../load_buildings.py) también incluye un flujo de reparación para geometrías problemáticas y recreación de índices `2dsphere`, útil cuando una colección necesita saneamiento antes de volver a consultar.

---

## 4. Estructura de salida

Los documentos persistidos en `analysis_results` contienen:

- `municipality_code`;
- `municipality_name`;
- `department`;
- `dataset`;
- `building_count`;
- `total_area_m2`;
- `avg_area_m2`;
- `computed_at`.

Esto permite reproducir el análisis sin recalcular todo desde cero y deja una base lista para reportes o visualizaciones externas.

---

## 5. Evidencia de ejecución

La salida de consola utilizada como evidencia confirma que el flujo completo quedó operativo:

```text
============================================================
VERIFICACION DE ARCHIVOS
============================================================

1. Verificando MunicipiosPDET.xlsx...
	 Municipios PDET en Excel: 170

2. Verificando shapefile...
	 Shapefile encontrado en MGN_2025_COLOMBIA/ADMINISTRATIVO/MGN_ADM_MPIO_GRAFICO.shp

============================================================
MENU PRINCIPAL
============================================================
1. Cargar municipios PDET en MongoDB
2. Verificar municipios PDET
3. Ingestar huellas de edificios - MICROSOFT
4. Ingestar huellas de edificios - GOOGLE
5. Reparar y reindexar colecciones de edificios
6. Análisis geoespacial (conteo y área por municipio)
7. EDA - Auditoría exploratoria completa

8. Salir

Selecciona una opcion (1-8): 1
...
 170 municipios sincronizados
 Índice 2dsphere creado

Selecciona una opcion (1-8): 2
...
	 Verificacion exitosa: todos los 170 municipios PDET estan en MongoDB

Selecciona una opcion (1-8): 3
-> Verificando dataset Microsoft Buildings en 'ms_buildings/'
	136 particiones ya descargadas en 'ms_buildings/'.
	0 particiones relevantes a procesar.
	Ingesta completada: 0 documentos insertados en esta sesion.

Selecciona una opcion (1-8): 4
-> Verificando dataset Google Open Buildings en 'google_buildings/'
	20 tiles ya descargados en 'google_buildings/'.
	Ingesta completada: 0 documentos insertados en esta sesion.

Selecciona una opcion (1-8): 6
============================================================
 SEMANA 4 - ANALISIS GEOESPACIAL POR MUNICIPIO
 Base de datos: upme-project
============================================================

	Procesando dataset: MICROSOFT
		170/170 ya calculados, 0 pendientes.
		Municipios procesados : 170
		Edificios totales     : 1,235,576
		Area total acumulada  : 159,880,080.08 m2

	Procesando dataset: GOOGLE
		170/170 ya calculados, 0 pendientes.
		Municipios procesados : 170
		Edificios totales     : 2,690,174
		Area total acumulada  : 222,643,644.57 m2

	Resultados almacenados en 'analysis_results'.

============================================================
 8. TOP 10 MUNICIPIOS POR AREA DE TECHOS
============================================================

	Dataset: MICROSOFT
		1    SANTA MARTA               MAGDALENA            67,615  14,217,875.29       210.28
		2    VALLEDUPAR                CESAR                63,696  13,529,663.43       212.41

	Dataset: GOOGLE
		1    SANTA MARTA               MAGDALENA           183,504  16,036,668.47        87.39
		2    VALLEDUPAR                CESAR               171,414  15,391,687.39        89.79

============================================================
 EDA - BUILDING FOOTPRINTS (Microsoft & Google)
 Base de datos: upme-project
============================================================

	buildings_microsoft    :    1,237,245 documentos  [OK]
	buildings_google       :    2,693,803 documentos  [OK]

	Registros con confidence_score:  2,693,803  (100.00%)
	Registros sin confidence_score:          0  (0.00%)

	Índices 2dsphere presentes en ambas colecciones
```

---

## 6. Archivos relacionados

- [main.py](../main.py) - invocación del análisis desde el menú principal.
- [eda_buildings.py](../eda_buildings.py) - lógica del EDA, agregaciones y comparativas.
- [load_pdet_municipalities.py](../load_pdet_municipalities.py) - base territorial usada como filtro espacial.
- [load_buildings.py](../load_buildings.py) - colecciones espaciales de entrada y reparación.

---

## 7. Conclusión

La semana 4 consolida el objetivo central del proyecto: estimar número y área total de techos por municipio PDET a partir de dos fuentes abiertas de huellas de edificios. La solución ya opera sobre MongoDB con índices espaciales, resultados persistidos y un flujo reproducible desde el menú principal.
