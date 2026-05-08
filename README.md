# Proyecto-DBA
Documentación y desarrollo del proyecto para DBA

# Entrega Semana 1 — Diseño del Esquema NoSQL y Plan de Implementación

## 1. Plan de Implementación

### Stack Tecnológico

| Componente | Herramienta | Justificación |
|---|---|---|
| Motor NoSQL | **MongoDB 7.x** | Soporte nativo de GeoJSON, índices 2dsphere, aggregation pipeline |
| Driver Python | **PyMongo / Motor** | Compatible con async, estándar para MongoDB |
| Procesamiento geoespacial | **GeoPandas + Shapely** | Lectura de shapefiles (MGN), conversión a GeoJSON |
| Entorno | **Docker** (imagen mongo:7) | Reproducibilidad del ambiente |
| Control de versiones | **GitHub** | Requerido por el proyecto |

### Cronograma por Semanas

| Semana | Tarea |
|---|---|
| 1 | Diseño del esquema, configuración de MongoDB, creación de colecciones e índices |
| 2 | Carga de límites municipales PDET (MGN/DANE) |
| 3 | Carga de footprints de edificios: Microsoft + Google |
| 4 | Joins espaciales: conteo de edificios y agregación de área por municipio |
| 5 | Informe técnico final |

### Configuración del Entorno

```bash
# Iniciar MongoDB con Docker
docker run -d --name upme-mongo \
  -p 27017:27017 \
  -v $(pwd)/data:/data/db \
  mongo:7

# Instalar dependencias Python
pip install pymongo motor geopandas shapely pandas
```

---

## 2. Modelado de Datos

El modelo se organiza alrededor de cuatro entidades principales:

**Municipios PDET** — polígonos administrativos de DANE/MGN, filtrados a los territorios con estatus PDET. Un documento por municipio.

**Footprints Microsoft** — polígonos de edificios del dataset de Microsoft Global ML Building Footprints (formato GeoJSON). Un documento por edificio.

**Footprints Google** — polígonos de edificios de Google Open Buildings (geometría WKT `POLYGON`/`MULTIPOLYGON`, coordenadas en WGS84). Incluye score de confianza (característica propia de este dataset).

**Resultados de Análisis** — conteos y áreas pre-agregadas por municipio y por dataset, para evitar re-ejecutar joins espaciales costosos.

Todas las geometrías se almacenan como **GeoJSON** (`type: "MultiPolygon"`) en coordenadas **WGS84 (EPSG:4326)**, que es el único CRS compatible con los índices `2dsphere` de MongoDB. El área de cada edificio (`area_m2`) se almacena como atributo precalculado en metros cuadrados, aprovechando que ambas fuentes lo suministran directamente (`area_in_meters` en Google, calculado sobre WGS84 en Microsoft). Esto evita la necesidad de reprojectar geometrías para los cálculos de área.

---

## 3. Diseño del Esquema

### Colección: `municipalities`

```json
{
  "_id": ObjectId,
  "dane_code": "string",          // Código DIVIPOLA (ej. "05001")
  "name": "string",               // Nombre del municipio
  "department": "string",         // Nombre del departamento
  "is_pdet": true,                // Siempre true tras el filtrado
  "geometry": {                   // GeoJSON MultiPolygon, coordenadas WGS84 [lon, lat]
    "type": "MultiPolygon",
    "coordinates": [[[[lon, lat], "..."]]]
  },
  "area_km2": 123.45,
  "source": "MGN2025",
  "ingested_at": "ISODate"
}
```

**Índices:**
```javascript
// Solo el índice espacial es necesario; con ~170 municipios PDET
// los escaneos de colección completa son triviales.
db.municipalities.createIndex({ "geometry": "2dsphere" })
```

---

### Colección: `buildings_microsoft`

```json
{
  "_id": ObjectId,
  "geometry": {                   // GeoJSON MultiPolygon, coordenadas WGS84 [lon, lat]
    "type": "MultiPolygon",
    "coordinates": [[[[lon, lat], "..."]]]
  },
  "area_m2": 87.3,               // Suministrado por la fuente (precalculado sobre WGS84)
  "municipality_code": "string", // Asignado mediante join espacial (Semana 4)
  "source": "microsoft",
  "ingested_at": "ISODate"
}
```

**Índices:**
```javascript
db.buildings_microsoft.createIndex({ "geometry": "2dsphere" })
db.buildings_microsoft.createIndex({ "municipality_code": 1 })
```

---

### Colección: `buildings_google`

```json
{
  "_id": ObjectId,
  "geometry": {                   // GeoJSON MultiPolygon, coordenadas WGS84 [lon, lat]
    "type": "MultiPolygon",       // Fuente original: WKT POLYGON/MULTIPOLYGON → convertido a GeoJSON
    "coordinates": [[[[lon, lat], "..."]]]
  },
  "area_m2": 64.1,               // Campo area_in_meters de la fuente (metros cuadrados)
  "confidence": 0.87,            // Específico de Google: confianza de detección [0.65, 1.0]
  "municipality_code": "string",
  "source": "google",
  "ingested_at": "ISODate"
}
```

**Índices:**
```javascript
db.buildings_google.createIndex({ "geometry": "2dsphere" })
db.buildings_google.createIndex({ "municipality_code": 1 })
db.buildings_google.createIndex({ "confidence": 1 })
```

---

### Colección: `analysis_results`

```json
{
  "_id": ObjectId,
  "municipality_code": "string",
  "municipality_name": "string",
  "dataset": "microsoft | google",
  "building_count": 1523,
  "total_area_m2": 98432.5,
  "avg_area_m2": 64.6,
  "computed_at": "ISODate"
}
```

**Índices:**
```javascript
db.analysis_results.createIndex(
  { "municipality_code": 1, "dataset": 1 },
  { unique: true }
)
```

---

## 4. Diagramas

### Diagrama 1 — Esquema de Documentos y Relaciones

```mermaid
erDiagram
    MUNICIPALITIES {
        ObjectId _id
        string dane_code
        string name
        string department
        bool is_pdet
        GeoJSON_MultiPolygon geometry
        float area_km2
        string source
        ISODate ingested_at
    }

    BUILDINGS_MICROSOFT {
        ObjectId _id
        GeoJSON_MultiPolygon geometry
        float area_m2
        string municipality_code
        string source
        ISODate ingested_at
    }

    BUILDINGS_GOOGLE {
        ObjectId _id
        GeoJSON_MultiPolygon geometry
        float area_m2
        float confidence
        string municipality_code
        string source
        ISODate ingested_at
    }

    ANALYSIS_RESULTS {
        ObjectId _id
        string municipality_code
        string municipality_name
        string dataset
        int building_count
        float total_area_m2
        float avg_area_m2
        ISODate computed_at
    }

    MUNICIPALITIES ||--o{ BUILDINGS_MICROSOFT : "dane_code → municipality_code"
    MUNICIPALITIES ||--o{ BUILDINGS_GOOGLE : "dane_code → municipality_code"
    MUNICIPALITIES ||--o{ ANALYSIS_RESULTS : "dane_code → municipality_code"
```

---

### Diagrama 2 — Pipeline End-to-End

```mermaid
flowchart TD
    A([Shapefile DANE/MGN]) --> B[GeoPandas: lectura y filtrado PDET]
    B --> C[Conversión a GeoJSON MultiPolygon WGS84]
    C --> D[(municipalities)]

    E([Microsoft Building Footprints\nGeoJSON — WGS84]) --> F[Parseo → MultiPolygon\narea_m2 desde fuente]
    F --> G[(buildings_microsoft)]

    H([Google Open Buildings\nCSV WKT POLYGON/MULTIPOLYGON]) --> I[WKT → GeoJSON MultiPolygon\narea_m2 = area_in_meters]
    I --> J[(buildings_google)]

    D --> K{Join Espacial\n$geoIntersects}
    G --> K
    J --> K

    K --> L[Aggregation Pipeline\nconteo + suma de área en m²]
    L --> M[(analysis_results)]
    M --> N([Informe Final / Mapas])

    style D fill:#4DB6AC,color:#fff
    style G fill:#4DB6AC,color:#fff
    style J fill:#4DB6AC,color:#fff
    style M fill:#4DB6AC,color:#fff
```

---

### Diagrama 3 — Estrategia de Índices

```mermaid
flowchart LR
    subgraph municipalities
        A1[2dsphere: geometry]
        A2["— sin índices adicionales —\n~170 docs, escaneo trivial"]
    end

    subgraph buildings_microsoft
        B1[2dsphere: geometry]
        B2[municipality_code]
    end

    subgraph buildings_google
        C1[2dsphere: geometry]
        C2[municipality_code]
        C3[confidence]
    end

    subgraph analysis_results
        D1["unique: {municipality_code, dataset}"]
    end

    Q1([Consulta geoIntersects]) --> A1
    Q1 --> B1
    Q1 --> C1
    Q3([Agregar por municipio]) --> B2
    Q3 --> C2
```

---

### Diagrama 4 — Lógica del Join Espacial (preview Semana 4)

```mermaid
sequenceDiagram
    participant Script
    participant MongoDB

    Script->>MongoDB: Obtener todos los municipios PDET (~170 docs)
    MongoDB-->>Script: Lista de {dane_code, geometry: MultiPolygon}

    loop Por cada municipio
        Script->>MongoDB: buildings_microsoft.find({geometry: {$geoIntersects: muni.geometry}})
        MongoDB-->>Script: edificios coincidentes[]
        Script->>MongoDB: buildings_google.find({geometry: {$geoIntersects: muni.geometry}})
        MongoDB-->>Script: edificios coincidentes[]
        Script->>MongoDB: analysis_results.insertOne({conteo, area_total_m2, dataset})
    end
```

---

## 5. Justificación de MongoDB

MongoDB es la opción NoSQL más apropiada para este proyecto por tres razones concretas:

Primero, soporta GeoJSON de forma nativa y los índices `2dsphere` permiten ejecutar operaciones espaciales directamente en la base de datos, sin necesidad de software GIS externo en la fase de análisis. MongoDB opera sobre WGS84 (EPSG:4326), que es el CRS nativo de ambas fuentes de datos, por lo que no se requiere reproyección para los joins espaciales.

Segundo, su aggregation pipeline permite calcular conteos y sumas de área en una sola consulta, lo que es eficiente para los volúmenes de datos esperados (cientos de miles de edificios por municipio).

Tercero, el esquema flexible de documentos facilita almacenar los campos propios de cada dataset (por ejemplo, `confidence` de Google) sin forzar un esquema rígido común, lo cual simplifica la integración de múltiples fuentes de datos abiertos.

Alternativas como Apache Cassandra o Amazon DynamoDB no tienen soporte espacial nativo y requerirían procesamientos externos adicionales, contradiciendo el objetivo de simplicidad y reproducibilidad del proyecto.

