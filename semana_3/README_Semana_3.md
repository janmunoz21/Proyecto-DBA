# Entrega Semana 3 - Carga e Integración de Huellas de Edificios

## 1. Objetivo de la semana

Esta entrega documenta la integración de las huellas de edificios de Microsoft y Google en MongoDB, con el fin de dejar listas las colecciones espaciales, sus índices `2dsphere` y la base para el análisis geoespacial posterior.

---

## 2. Lo que pide la entrega de la semana 3

La semana 3 corresponde a la carga de los footprints de edificios y debe incluir como mínimo:

- carga de los dos datasets seleccionados;
- persistencia en MongoDB con índice espacial;
- eficiencia de carga;
- auditoría inicial de los datos.

Eso ya quedó cubierto con el flujo actual del proyecto.

---

## 3. Implementación realizada

### 3.1 Verificación y descarga de insumos

El módulo [download_manager.py](../download_manager.py) valida y gestiona los insumos necesarios para la ejecución:

- verifica `MunicipiosPDET.xlsx` y el shapefile del MGN;
- descarga archivos faltantes con reintentos y reanudación parcial;
- valida el ZIP antes de extraerlo;
- detecta y descarga las particiones de Microsoft y los tiles de Google;
- solicita la configuración de MongoDB desde consola.

### 3.2 Ingesta de huellas de edificios

El módulo [load_buildings.py](../load_buildings.py) implementa la carga optimizada de ambas fuentes. La lógica ya incorporada incluye:

- filtrado espacial previo sobre los municipios PDET cargados en MongoDB;
- uso de `STRtree` para acelerar las intersecciones espaciales;
- prefiltro por `bbox` antes de construir geometrías completas;
- procesamiento por chunks para evitar problemas de memoria;
- sanitización y normalización de geometrías antes de insertar;
- cálculo de `area_m2` con datos fuente o mediante geodesia, según el dataset;
- persistencia incremental del progreso para no repetir particiones ya cargadas;
- creación y reparación automática del índice `2dsphere`.

### 3.3 Esquema de datos

Se usan dos colecciones principales:

- `buildings_microsoft`
- `buildings_google`

Cada documento conserva, como mínimo:

- `geometry` en GeoJSON `MultiPolygon`;
- `area_m2`;
- `source`;
- `ingested_at`;
- `confidence_score` para Google cuando el campo está disponible.

---

## 4. Auditoría inicial

El módulo [eda_buildings.py](../eda_buildings.py) permite revisar que la carga quedó consistente. La auditoría incluye:

- conteo de documentos por colección;
- estadísticas de área: media, mínimo, máximo y desviación estándar;
- distribución por quintiles;
- validación de calidad de datos;
- revisión de índices;
- muestra de documentos representativos.

Con esto queda lista la base para la semana 4, donde se ejecuta el cruce espacial por municipio y el cálculo agregado de edificios y área de techos.

---

## 5. Evidencia de ejecución

La siguiente salida de consola resume la verificación y la carga ya realizadas:

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
6. Análisis geoespacial, conteo y área por municipio
7. EDA - Auditoría exploratoria completa

8. Salir

Selecciona una opcion (1-8): 7
============================================================
 EDA - BUILDING FOOTPRINTS (Microsoft & Google)
 Base de datos: upme-project
============================================================

  buildings_microsoft    :    1,237,245 documentos  [OK]
  buildings_google       :    2,693,803 documentos  [OK]

  Registros con confidence_score:  2,693,803  (100.00%)
  Registros sin confidence_score:          0  (0.00%)

  Índices 2dsphere presentes en ambas colecciones