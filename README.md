<div align="center">

# Análisis Geoespacial de Potencial Solar en Territorios PDET

## **Administración de Bases de Datos — Pontificia Universidad Javeriana**

![Logo de la Pontificia Universidad Javeriana](https://upload.wikimedia.org/wikipedia/commons/6/6c/Javeriana.svg)

**Autores:** Jan Marco Muñoz, Ana Sofia Arboleda, Valentina García, Nicolás Torres  
**Entregado a:** Ing. Andres Oswaldo Calderon  
**Fecha de inicio:** 27 de Abril 2026

<br>
</div>

---

## Acerca del Proyecto

Este proyecto implementa un **análisis** geoespacial reproducible para estimar el potencial de energía solar en territorios PDET (Programas de Desarrollo con Enfoque Territorial) de Colombia.

El objetivo es desarrollar una solución NoSQL escalable que permita:

- Integrar límites administrativos municipales del Marco Geoestadístico Nacional (MGN) del DANE
- Procesar footprints de edificios de múltiples fuentes (Microsoft, Google)
- Cuantificar el área de techos disponibles para instalación de paneles solares
- Generar análisis agregados por municipio para evaluación de viabilidad

### Stack Tecnológico

- **Base de Datos:** MongoDB 7.x (Almacenamiento de datos geoespaciales)
- **Procesamiento:** Python 3.x, GeoPandas, PyMongo (Procesamiento de datos)
- **Infraestructura:** Docker
- **Datos:** Microsoft Building Footprints, Google Open Buildings, DANE MGN

---

## Entregas por Semana

### **Semana 1: Diseño del Esquema NoSQL y Plan de Implementación**
Definición de la arquitectura de datos, configuración de MongoDB y creación del esquema de colecciones con índices geoespaciales.

[Documentación completa](semana_1/README_Semana_1.md)

**Logros principales:**
- Diseño del modelo de datos (municipios, footprints)
- Configuración de índices 2dsphere para operaciones geoespaciales
- Stack tecnológico y plan de implementación

---

### **Semana 2: Carga de Límites Municipales PDET**
Ingesta y transformación de datos de límites administrativos desde los shapefiles de DANE (MGN).

**Objetivos:**
- Extracción y filtrado de municipios PDET
- Conversión de geometrías a GeoJSON (WGS84)
- Validación y carga en colección `municipalities`

---

### **Semana 3: Carga de Footprints de Edificios**
Integración de datos de footprints desde Microsoft Building Footprints y Google Open Buildings.

**Implementado:**
- Descarga automatizada: 233 particiones Microsoft (GeoJSONL .csv.gz) y 3 tiles Google (WKT CSV)
- Filtrado espacial: solo edificios dentro de municipios PDET (unión de geometrías)
- Sanitización robusta de geometrías antes de insertar:
  - `make_valid()` para reparar self-intersections y loops inválidos
  - Extracción de Polygon/MultiPolygon desde GeometryCollections
  - Normalización a MultiPolygon con orientación right-hand rule (`orient(sign=1.0)`)
  - Geometrías irrecuperables se omiten sin romper la ingesta
- Cálculo de `area_m2` en EPSG:9377 (MAGNA-SIRGAS / Colombia)
- Progreso persistente por partición (reanudable ante fallos)
- Opción de reparación y reindexación para colecciones ya contaminadas
- Índice `2dsphere` creado al final con fallback de limpieza automática

---

### **Semana 4: Análisis Geoespacial y Agregaciones**
Ejecución de joins espaciales y generación de métricas de conteo de edificios y área de techos por municipio.

**Implementado:**
- Consulta `$geoWithin` por cada municipio PDET contra cada dataset de edificios
- Aggregation pipeline: `building_count`, `total_area_m2`, `avg_area_m2` por municipio
- Persistencia en colección `analysis_results` con índice único `(municipality_code, dataset)`
- Top 10 municipios por área de techos
- Tabla comparativa Microsoft vs Google
- Auditoría EDA completa: calidad de datos, distribución de áreas, confidence scores, índices

---

### **Semana 5: Informe Técnico Final**
Consolidación de metodología, resultados y recomendaciones para identificar municipios prioritarios.

**Entregables:**
- Reporte técnico con metodología y hallazgos
- Visualizaciones de resultados
- Recomendaciones para proyectos piloto de energía solar

---

## Estructura del Repositorio

```
Proyecto-DBA/
├── README.md                    # Este archivo
├── semana_1/README_Semana_1.md  # Documentación detallada de Semana 1
├── project.md                   # Enunciado del proyecto y requerimientos
├── Enunciado.pdf                # Especificaciones formales (PDF)
├── main.py                      # Menú principal del pipeline
├── download_manager.py          # Descarga y verificación de datasets
├── load_pdet_municipalities.py  # Ingesta de municipios PDET (Semana 2)
├── load_buildings.py            # Ingesta de edificios Microsoft/Google (Semana 3)
├── eda_buildings.py             # EDA + análisis geoespacial (Semana 3-4)
└── .git/                        # Control de versiones
```

---

## Comenzar

Para reproducir este proyecto en tu entorno local:

```bash
# Clonar el repositorio
git clone <repository-url>
cd Proyecto-DBA

# Instalar dependencias Python
pip install pymongo geopandas shapely pandas openpyxl requests pyproj

# Iniciar MongoDB con Docker
docker run -d --name upme-mongo \
  -p 27017:27017 \
  -v $(pwd)/data:/data/db \
  mongo:7

# Ejecutar el pipeline
python main.py
```

### Menú principal

| Opción | Descripción |
|--------|-------------|
| 1 | Cargar municipios PDET en MongoDB (Semana 2) |
| 2 | Verificar municipios PDET |
| 3 | Ingestar huellas de edificios - Microsoft (Semana 3) |
| 4 | Ingestar huellas de edificios - Google (Semana 3) |
| 5 | Reparar y reindexar colecciones de edificios |
| 6 | Análisis geoespacial por municipio (Semana 4) |
| 7 | EDA - Auditoría exploratoria completa |

Para más detalles sobre configuración y diseño del esquema, consulta [README_Semana_1.md](semana_1/README_Semana_1.md).

---

## Notas

Todas las geometrías se almacenan en formato **GeoJSON** con coordenadas **WGS84 (EPSG:4326)**, garantizando compatibilidad con índices geoespaciales de MongoDB.

